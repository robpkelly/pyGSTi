"""Utility functions related to the Choi representation of gates."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
from ..baseobjs.basis import basis_matrices as _basis_matrices
from ..baseobjs.basis import Basis as _Basis
from . import basistools as _bt
from . import matrixtools as _mt


# Gate Mx G:      rho  --> G rho                    where G and rho are in the Pauli basis (by definition/convention)
#            vec(rhoS) --> GStd vec(rhoS)           where GS and rhoS are in the std basis, GS = PtoS * G * StoP
# Choi Mx J:     rho  --> sum_ij Jij Bi rho Bj^dag  where Bi is some basis of mxs for rho-space; independent of basis for rho and Bi
#           vec(rhoS) --> sum_ij Jij (BSi x BSj^*) vec(rhoS)  where rhoS and BSi's are in std basis
#  Now,
#       Jkl = Trace( sum_ij Jij (BSi x BSj^*) , (BSk x BSl^*)^dag ) / Trace( (BSk x BSl^*), (BSk x BSl^*)^dag )
#           = Trace( GStd , (BSk x BSl^*)^dag ) / Trace( (BSk x BSl^*), (BSk x BSl^*)^dag )
#  In below function, take Bi's to be Pauli matrices
#  Note: vec(.) vectorization above is assumed to be done by-*rows* (as numpy.flatten does).

#Note that in just the std basis, the construction of the Jamiolkowski representation of a process phi is
#  J(Phi) = sum_(0<i,j<n) Phi(|i><j|) x |i><j|    where {|i>}_1^n spans the state space
#
#  Derivation: if we write:
#    Phi(|i><j|) = sum_kl C[(kl)(ij)] |k><l|
#  and
#    rho = sum_ij rho_ij |i><j|
#  then
#    Phi(rho) = sum_(ij)(kl) C[(kl)(ij)] rho_ij |k><l|
#             = sum_(ij)(kl) C[(kl)(ij)] |k> rho_ij <l|
#             = sum_(ij)(kl) C[(kl)(ij)] |k> <i| rho |j> <l|
#             = sum_(ij)(kl) C[(ik)(jl)] |i> <j| rho |l> <k|  (just permute index labels)
#  The definition of the Jamiolkoski matrix J is:
#    Phi(rho) = sum_(ij)(kl) J(ij)(kl) |i><j| rho |l><k|
#  so
#    J(ij)(kl) == C[(ik)(jl)]
#
#  Note: |i><j| x |k><l| is an object in "gate/process" space, since
#    it maps a vectorized density matrix, e.g. |a><b| to another density matrix via:
#    (|i><j| x |k><l|) vec(|a><b|) = [mx with 1 in (i*dmDim + k) row and (j*dmDim + l) col][vec with 1 in a*dmDim+b row]
#                                  = vec(|i><k|) if |a><b| == |j><l| else 0
#    so (|i><j| x |k><l|) vec(|j><l|) = vec(|i><k|)
#    and could write as: (|ik><jl|) |jl> = |ik>
#
# Now write J as:
#    J  = sum_ijkl |ij> J(ij)(kl) <kl|
#       = sum_ijkl J(ij)(kl) |ij> <kl|
#       = sum_ijkl J(ij)(kl) (|i><k| x |j><l|)
#       = sum_ijkl C(ik)(jl) (|i><k| x |j><l|)
#       = sum_jl [ sum_ik C(ik)(jl) |i><k| ] x |j><l| (using Note above)
#       = sum_jl Phi(|j><l|) x |j><l|   (using definition Phi(|i><j|) = sum_kl C[(kl)(ij)] |k><l|)
#  which is the original J(Phi) expression.
#
# This can be written equivalently as:
#  J(Phi) = sum_(0<i,j<n) Phi(Eij) otimes Eij
#  where Eij is the matrix unit with a single element in the (i,j)-th position, i.e. Eij == |i><j|

def jamiolkowski_iso(operationMx, opMxBasis='pp', choiMxBasis='pp'):
    """
    Given a operation matrix, return the corresponding Choi matrix that is normalized
    to have trace == 1.

    Parameters
    ----------
    operationMx : numpy array
        the operation matrix to compute Choi matrix of.

    opMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    choiMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    Returns
    -------
    numpy array
        the Choi matrix, normalized to have trace == 1, in the desired basis.
    """
    operationMx = _np.asarray(operationMx)
    opMxBasis = _bt.build_basis_for_matrix(operationMx, opMxBasis)
    opMxInStdBasis = _bt.change_basis(operationMx, opMxBasis, opMxBasis.equivalent('std'))

    #expand operation matrix so it acts on entire space of dmDim x dmDim density matrices
    #  so that we can take dot products with the BVec matrices below
    opMxInStdBasis = _bt.resize_std_mx(opMxInStdBasis, 'expand', opMxBasis.equivalent('std'), opMxBasis.simple_equivalent('std'))

    N = opMxInStdBasis.shape[0]  # dimension of the full-basis (expanded) gate
    dmDim = int(round(_np.sqrt(N)))  # density matrix dimension

    #Note: we need to use the *full* basis of Matrix Unit, Gell-Mann, or Pauli-product matrices when
    # generating the Choi matrix, even when the original operation matrix doesn't include the entire basis.
    # This is because even when the original operation matrix doesn't include a certain basis element (B0 say),
    # conjugating with this basis element and tracing, i.e. trace(B0^dag * Operation * B0), is not necessarily zero.

    #get full list of basis matrices (in std basis) -- i.e. we use dmDim
    if not isinstance(choiMxBasis, _Basis):
        choiMxBasis = _Basis.cast(choiMxBasis, N)  # we'd like a basis of dimension N

    BVec = choiMxBasis.simple_equivalent().elements
    M = len(BVec)  # can be < N if basis has multiple block dims
    assert(M == N), 'Expected {}, got {}'.format(M, N)

    #TODO REMOVE - now we just use simple_equivalent above
    #if M < N: # then try to make a complete basis based on the *name* of the desired basis
    #    BVec = choiMxBasis.simple_equivalent().elements
    #    M = len(BVec)
    #    assert(M == N), 'Expected {}, got {}'.format(M, N)  #make sure the number of basis matrices matches the dim of the gate given

    choiMx = _np.empty((N, N), 'complex')
    for i in range(M):
        for j in range(M):
            BiBj = _np.kron(BVec[i], _np.conjugate(BVec[j]))
            BiBj_dag = _np.transpose(_np.conjugate(BiBj))
            choiMx[i, j] = _mt.trace(_np.dot(opMxInStdBasis, BiBj_dag)) \
                / _mt.trace(_np.dot(BiBj, BiBj_dag))

    # This construction results in a Jmx with trace == dim(H) = sqrt(operationMx.shape[0]) (dimension of density matrix)
    #  but we'd like a Jmx with trace == 1, so normalize:
    choiMx_normalized = choiMx / dmDim
    return choiMx_normalized

# GStd = sum_ij Jij (BSi x BSj^*)


def jamiolkowski_iso_inv(choiMx, choiMxBasis='pp', opMxBasis='pp'):
    """
    Given a choi matrix, return the corresponding operation matrix.  This function
    performs the inverse of jamiolkowski_iso(...).

    Parameters
    ----------
    choiMx : numpy array
        the Choi matrix, normalized to have trace == 1, to compute operation matrix for.

    choiMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    opMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    Returns
    -------
    numpy array
        operation matrix in the desired basis.
    """
    choiMx = _np.asarray(choiMx)  # will have "expanded" dimension even if bases are for reduced...
    N = choiMx.shape[0]  # dimension of full-basis (expanded) operation matrix
    if not isinstance(choiMxBasis, _Basis):  # if we're not given a basis, build
        choiMxBasis = _Basis.cast(choiMxBasis, N)  # one with the full dimension

    dmDim = int(round(_np.sqrt(N)))  # density matrix dimension

    #get full list of basis matrices (in std basis)
    BVec = _basis_matrices(choiMxBasis.simple_equivalent(), N)
    assert(len(BVec) == N)  # make sure the number of basis matrices matches the dim of the choi matrix given

    # Invert normalization
    choiMx_unnorm = choiMx * dmDim

    opMxInStdBasis = _np.zeros((N, N), 'complex')  # in matrix unit basis of entire density matrix
    for i in range(N):
        for j in range(N):
            BiBj = _np.kron(BVec[i], _np.conjugate(BVec[j]))
            opMxInStdBasis += choiMx_unnorm[i, j] * BiBj

    if not isinstance(opMxBasis, _Basis):
        opMxBasis = _Basis.cast(opMxBasis, N)  # make sure opMxBasis is a Basis; we'd like dimension to be N

    #project operation matrix so it acts only on the space given by the desired state space blocks
    opMxInStdBasis = _bt.resize_std_mx(opMxInStdBasis, 'contract',
                                       opMxBasis.simple_equivalent('std'), opMxBasis.equivalent('std'))

    #transform operation matrix into appropriate basis
    return _bt.change_basis(opMxInStdBasis, opMxBasis.equivalent('std'), opMxBasis)


def fast_jamiolkowski_iso_std(operationMx, opMxBasis):
    """
    Given a operation matrix, return the corresponding Choi matrix in the standard
    basis that is normalized to have trace == 1.

    This routine *only* computes the case of the Choi matrix being in the
    standard (matrix unit) basis, but does so more quickly than
    :func:`jamiolkowski_iso` and so is particuarly useful when only the
    eigenvalues of the Choi matrix are needed.

    Parameters
    ----------
    operationMx : numpy array
        the operation matrix to compute Choi matrix of.

    opMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    Returns
    -------
    numpy array
        the Choi matrix, normalized to have trace == 1, in the std basis.
    """

    #first, get operation matrix into std basis
    operationMx = _np.asarray(operationMx)
    opMxBasis = _bt.build_basis_for_matrix(operationMx, opMxBasis)
    opMxInStdBasis = _bt.change_basis(operationMx, opMxBasis, opMxBasis.equivalent('std'))

    #expand operation matrix so it acts on entire space of dmDim x dmDim density matrices
    opMxInStdBasis = _bt.resize_std_mx(opMxInStdBasis, 'expand', opMxBasis.equivalent('std'),
                                       opMxBasis.simple_equivalent('std'))

    #Shuffle indices to go from process matrix to Jamiolkowski matrix (they vectorize differently)
    N2 = opMxInStdBasis.shape[0]
    N = int(_np.sqrt(N2))
    assert(N * N == N2)  # make sure N2 is a perfect square
    Jmx = opMxInStdBasis.reshape((N, N, N, N))
    Jmx = _np.swapaxes(Jmx, 1, 2).flatten()
    Jmx = Jmx.reshape((N2, N2))

    # This construction results in a Jmx with trace == dim(H) = sqrt(gateMxInPauliBasis.shape[0])
    #  but we'd like a Jmx with trace == 1, so normalize:
    Jmx_norm = Jmx / N
    return Jmx_norm


def fast_jamiolkowski_iso_std_inv(choiMx, opMxBasis):
    """
    Given a choi matrix in the standard basis, return the corresponding operation matrix.
    This function performs the inverse of fast_jamiolkowski_iso_std(...).

    Parameters
    ----------
    choiMx : numpy array
        the Choi matrix in the standard (matrix units) basis, normalized to
        have trace == 1, to compute operation matrix for.

    opMxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    Returns
    -------
    numpy array
        operation matrix in the desired basis.
    """

    #Shuffle indices to go from process matrix to Jamiolkowski matrix (they vectorize differently)
    N2 = choiMx.shape[0]
    N = int(_np.sqrt(N2))
    assert(N * N == N2)  # make sure N2 is a perfect square
    opMxInStdBasis = choiMx.reshape((N, N, N, N)) * N
    opMxInStdBasis = _np.swapaxes(opMxInStdBasis, 1, 2).flatten()
    opMxInStdBasis = opMxInStdBasis.reshape((N2, N2))
    opMxBasis = _bt.build_basis_for_matrix(opMxInStdBasis, opMxBasis)

    #project operation matrix so it acts only on the space given by the desired state space blocks
    opMxInStdBasis = _bt.resize_std_mx(opMxInStdBasis, 'contract',
                                       opMxBasis.simple_equivalent('std'), opMxBasis.equivalent('std'))

    #transform operation matrix into appropriate basis
    return _bt.change_basis(opMxInStdBasis, opMxBasis.equivalent('std'), opMxBasis)


def sum_of_negative_choi_evals(model, weights=None):
    """
    Compute the amount of non-CP-ness of a model by summing the negative
    eigenvalues of the Choi matrix for each gate in model.

    Parameters
    ----------
    model : Model
        The model to act on.

    weights : dict
        A dictionary of weights used to multiply the negative
        eigenvalues of different gates.  Keys are operation labels, values
        are floating point numbers.

    Returns
    -------
    float
        the sum of negative eigenvalues of the Choi matrix for each gate.
    """
    if weights is not None:
        default = weights.get('gates', 1.0)
        sums = sums_of_negative_choi_evals(model)
        return sum([s * weights.get(gl, default)
                    for gl, s in zip(model.operations.keys(), sums)])
    else:
        return sum(sums_of_negative_choi_evals(model))


def sums_of_negative_choi_evals(model):
    """
    Compute the amount of non-CP-ness of a model by summing the negative
    eigenvalues of the Choi matrix for each gate in model separately.

    Parameters
    ----------
    model : Model
        The model to act on.

    Returns
    -------
    list of floats
        each element == sum of the negative eigenvalues of the Choi matrix
        for the corresponding gate (as ordered  by model.operations.iteritems()).
    """
    ret = []
    for (_, gate) in model.operations.items():
        J = fast_jamiolkowski_iso_std(gate, model.basis)  # Choi mx basis doesn't matter
        evals = _np.linalg.eigvals(J)  # could use eigvalsh, but wary of this since eigh can be wrong...
        sumOfNeg = 0.0
        for ev in evals:
            if ev.real < 0: sumOfNeg -= ev.real
        ret.append(sumOfNeg)
    return ret


def mags_of_negative_choi_evals(model):
    """
    Compute the magnitudes of the negative eigenvalues of the Choi matricies
    for each gate in model.

    Parameters
    ----------
    model : Model
        The model to act on.

    Returns
    -------
    list of floats
        list of the magnitues of all negative Choi eigenvalues.  The length of
        this list will vary based on how many negative eigenvalues are found,
        as positive eigenvalues contribute nothing to this list.
    """
    ret = []
    for (_, gate) in model.operations.items():
        J = jamiolkowski_iso(gate, model.basis, choiMxBasis=model.basis.simple_equivalent('std'))
        evals = _np.linalg.eigvals(J)  # could use eigvalsh, but wary of this since eigh can be wrong...
        for ev in evals:
            ret.append(-ev.real if ev.real < 0 else 0.0)
    return ret
