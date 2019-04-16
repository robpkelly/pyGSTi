""" Utility functions operating on operation matrices """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
import scipy.linalg as _spl
import scipy.sparse as _sps
import scipy.sparse.linalg as _spsl
import warnings as _warnings
import collections as _collections

from . import jamiolkowski as _jam
from . import matrixtools as _mt
from . import lindbladtools as _lt
from . import compattools as _compat
from . import basistools as _bt
from ..baseobjs import Basis as _Basis
from ..baseobjs import ExplicitBasis as _ExplicitBasis
from ..baseobjs import DirectSumBasis as _DirectSumBasis
from ..baseobjs.basis import basis_matrices as _basis_matrices


IMAG_TOL = 1e-7  # tolerance for imaginary part being considered zero


def _flat_mut_blks(i, j, blockDims):
    # like _mut(i,j,dim).flatten() but works with basis *blocks*
    N = sum(blockDims)
    mx = _np.zeros((N, N), 'd'); mx[i, j] = 1.0
    ret = _np.zeros(sum([d**2 for d in blockDims]), 'd')
    i = 0; off = 0
    for d in blockDims:
        ret[i:i + d**2] = mx[off:off + d, off:off + d].flatten()
        i += d**2; off += d
    return ret


def _hack_sqrtm(A):
    sqrt, _ = _spl.sqrtm(A, disp=False)  # Travis found this scipy function
    # to be incorrect in certain cases (we need a workaround)
    if _np.any(_np.isnan(sqrt)):  # this is sometimes a good fallback when sqrtm doesn't work.
        ev, U = _np.linalg.eig(A)
        sqrt = _np.dot(U, _np.dot(_np.diag(_np.sqrt(ev)), _np.linalg.inv(U)))

    return sqrt


def fidelity(A, B):
    """
    Returns the quantum state fidelity between density
      matrices A and B given by :

      F = Tr( sqrt{ sqrt(A) * B * sqrt(A) } )^2

    To compute process fidelity, pass this function the
    Choi matrices of the two processes, or just call
    :function:`entanglement_fidelity` with the operation matrices.

    Parameters
    ----------
    A : numpy array
        First density matrix.

    B : numpy array
        Second density matrix.

    Returns
    -------
    float
        The resulting fidelity.
    """
    evals, U = _np.linalg.eig(A)
    if len([ev for ev in evals if abs(ev) > 1e-8]) == 1:  # special case when A is rank 1
        ivec = _np.argmax(evals)
        vec = U[:, ivec:(ivec + 1)]
        F = _np.dot(_np.conjugate(_np.transpose(vec)), _np.dot(B, vec)).real  # vec^T * B * vec
        return float(F)

    evals, U = _np.linalg.eig(B)
    if len([ev for ev in evals if abs(ev) > 1e-8]) == 1:  # special case when B is rank 1 (recally fidelity is sym in args)
        ivec = _np.argmax(evals)
        vec = U[:, ivec:(ivec + 1)]
        F = _np.dot(_np.conjugate(_np.transpose(vec)), _np.dot(A, vec)).real  # vec^T * A * vec
        return float(F)

    sqrtA = _hack_sqrtm(A)  # _spl.sqrtm(A)
    assert(_np.linalg.norm(_np.dot(sqrtA, sqrtA) - A) < 1e-8)  # test the scipy sqrtm function
    F = (_mt.trace(_hack_sqrtm(_np.dot(sqrtA, _np.dot(B, sqrtA)))).real)**2  # Tr( sqrt{ sqrt(A) * B * sqrt(A) } )^2
    return float(F)


def frobeniusdist(A, B):
    """
    Returns the frobenius distance between gate
      or density matrices A and B given by :

      sqrt( sum( (A_ij-B_ij)^2 ) )

    Parameters
    ----------
    A : numpy array
        First matrix.

    B : numpy array
        Second matrix.

    Returns
    -------
    float
        The resulting frobenius distance.
    """
    return _mt.frobeniusnorm(A - B)


def frobeniusdist2(A, B):
    """
    Returns the square of the frobenius distance between gate
      or density matrices A and B given by :

      sum( (A_ij-B_ij)^2 )

    Parameters
    ----------
    A : numpy array
        First matrix.

    B : numpy array
        Second matrix.

    Returns
    -------
    float
        The resulting frobenius distance.
    """
    return _mt.frobeniusnorm2(A - B)


def residuals(A, B):
    """
    Calculate residuals between the elements of two matrices

    Parameters
    ----------
    A : numpy array
        First matrix.

    B : numpy array
        Second matrix.

    Returns
    -------
    np.array
        residuals
    """
    return (A - B).flatten()


def tracenorm(A):
    """
    Compute the trace norm of matrix A given by:

      Tr( sqrt{ A^dagger * A } )

    Parameters
    ----------
    A : numpy array
        The matrix to compute the trace norm of.
    """
    if _np.linalg.norm(A - _np.conjugate(A.T)) < 1e-8:
        #Hermitian, so just sum eigenvalue magnitudes
        return _np.sum(_np.abs(_np.linalg.eigvals(A)))
    else:
        #Sum of singular values (positive by construction)
        return _np.sum(_np.linalg.svd(A, compute_uv=False))


def tracedist(A, B):
    """
    Compute the trace distance between matrices A and B,
    given by:

      D = 0.5 * Tr( sqrt{ (A-B)^dagger * (A-B) } )

    Parameters
    ----------
    A, B : numpy array
        The matrices to compute the distance between.
    """
    return 0.5 * tracenorm(A - B)


def diamonddist(A, B, mxBasis='pp', return_x=False):
    """
    Returns the approximate diamond norm describing the difference between gate
    matrices A and B given by :

      D = ||A - B ||_diamond = sup_rho || AxI(rho) - BxI(rho) ||_1

    Parameters
    ----------
    A, B : numpy array
        The *gate* matrices to use when computing the diamond norm.

    mxBasis : Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    return_x : bool, optional
        Whether to return a numpy array encoding the state (rho) at
        which the maximal trace distance occurs.

    Returns
    -------
    dm : float
       Diamond norm
    W : numpy array
       Only returned if `return_x = True`.  Encodes the state rho, such that
       `dm = trace( |(J(A)-J(B)).T * W| )`.
    """
    mxBasis = _bt.build_basis_for_matrix(A, mxBasis)

    #currently cvxpy is only needed for this function, so don't import until here

    import sys as _sys
    if _sys.version_info < (3, 0):
        #Attempt "safe" import of cvxpy so that pickle isn't messed up...
        import pickle as _pickle
        p = _pickle.Pickler.dispatch.copy()
        import cvxpy as _cvxpy
        _pickle.Pickler.dispatch = p
    else:  # no need to do this in python3
        import cvxpy as _cvxpy

    #Check if using version < 1.0
    old_cvxpy = bool(tuple(map(int, _cvxpy.__version__.split('.'))) < (1, 0))

    # This SDP implementation is a modified version of Kevin's code

    #Compute the diamond norm

    #Uses the primal SDP from arXiv:1207.5726v2, Sec 3.2

    #Maximize 1/2 ( < J(phi), X > + < J(phi).dag, X.dag > )
    #Subject to  [[ I otimes rho0, X],
    #            [X.dag, I otimes rho1]] >> 0
    #              rho0, rho1 are density matrices
    #              X is linear operator

    #Jamiolkowski representation of the process
    #  J(phi) = sum_ij Phi(Eij) otimes Eij

    #< A, B > = Tr(A.dag B)

    #def vec(matrix_in):
    #    # Stack the columns of a matrix to return a vector
    #    return _np.transpose(matrix_in).flatten()
    #
    #def unvec(vector_in):
    #    # Slice a vector into columns of a matrix
    #    d = int(_np.sqrt(vector_in.size))
    #    return _np.transpose(vector_in.reshape( (d,d) ))

    #Code below assumes *un-normalized* Jamiol-isomorphism, so multiply by
    # density mx dimension (`smallDim`) below
    JAstd = _jam.fast_jamiolkowski_iso_std(A, mxBasis)
    JBstd = _jam.fast_jamiolkowski_iso_std(B, mxBasis)

    #Do this *after* the fast_jamiolkowski_iso calls above because these will convert
    # A & B to a "single-block" basis representation when mxBasis has multiple blocks.
    dim = JAstd.shape[0]
    smallDim = int(_np.sqrt(dim))
    JAstd *= smallDim  # see above comment
    JBstd *= smallDim  # see above comment
    assert(dim == JAstd.shape[1] == JBstd.shape[0] == JBstd.shape[1])

    #CHECK: Kevin's jamiolowski, which implements the un-normalized isomorphism:
    #  smallDim * _jam.jamiolkowski_iso(M, "std", "std")
    #def kevins_jamiolkowski(process, representation = 'superoperator'):
    #    # Return the Choi-Jamiolkowski representation of a quantum process
    #    # Add methods as necessary to accept different representations
    #    process = _np.array(process)
    #    if representation == 'superoperator':
    #        # Superoperator is the linear operator acting on vec(rho)
    #        dimension = int(_np.sqrt(process.shape[0]))
    #        print "dim = ",dimension
    #        jamiolkowski_matrix = _np.zeros([dimension**2, dimension**2], dtype='complex')
    #        for i in range(dimension**2):
    #            Ei_vec= _np.zeros(dimension**2)
    #            Ei_vec[i] = 1
    #            output = unvec(_np.dot(process,Ei_vec))
    #            tmp = _np.kron(output, unvec(Ei_vec))
    #            print "E%d = \n" % i,unvec(Ei_vec)
    #            #print "contrib =",_np.kron(output, unvec(Ei_vec))
    #            jamiolkowski_matrix += tmp
    #        return jamiolkowski_matrix
    #JAstd_kev = jamiolkowski(A)
    #JBstd_kev = jamiolkowski(B)
    #print "diff A = ",_np.linalg.norm(JAstd_kev/2.0-JAstd)
    #print "diff B = ",_np.linalg.norm(JBstd_kev/2.0-JBstd)

    #Kevin's function: def diamondnorm( jamiolkowski_matrix ):
    jamiolkowski_matrix = JBstd - JAstd

    # Here we define a bunch of auxiliary matrices because CVXPY doesn't use complex numbers

    K = jamiolkowski_matrix.real  # J.real
    L = jamiolkowski_matrix.imag  # J.imag

    if old_cvxpy:
        Y = _cvxpy.Variable(dim, dim)  # X.real
        Z = _cvxpy.Variable(dim, dim)  # X.imag

        sig0 = _cvxpy.Variable(smallDim, smallDim)  # rho0.real
        sig1 = _cvxpy.Variable(smallDim, smallDim)  # rho1.real
        tau0 = _cvxpy.Variable(smallDim, smallDim)  # rho1.imag
        tau1 = _cvxpy.Variable(smallDim, smallDim)  # rho1.imag

    else:
        Y = _cvxpy.Variable(shape=(dim, dim))  # X.real
        Z = _cvxpy.Variable(shape=(dim, dim))  # X.imag

        sig0 = _cvxpy.Variable(shape=(smallDim, smallDim))  # rho0.real
        sig1 = _cvxpy.Variable(shape=(smallDim, smallDim))  # rho1.real
        tau0 = _cvxpy.Variable(shape=(smallDim, smallDim))  # rho1.imag
        tau1 = _cvxpy.Variable(shape=(smallDim, smallDim))  # rho1.imag

    ident = _np.identity(smallDim, 'd')

    objective = _cvxpy.Maximize(_cvxpy.trace(K.T * Y + L.T * Z))
    constraints = [_cvxpy.bmat([
        [_cvxpy.kron(ident, sig0), Y, -_cvxpy.kron(ident, tau0), -Z],
        [Y.T, _cvxpy.kron(ident, sig1), Z.T, -_cvxpy.kron(ident, tau1)],
        [_cvxpy.kron(ident, tau0), Z, _cvxpy.kron(ident, sig0), Y],
        [-Z.T, _cvxpy.kron(ident, tau1), Y.T, _cvxpy.kron(ident, sig1)]]) >> 0,
        _cvxpy.bmat([[sig0, -tau0],
                     [tau0, sig0]]) >> 0,
        _cvxpy.bmat([[sig1, -tau1],
                     [tau1, sig1]]) >> 0,
        sig0 == sig0.T,
        sig1 == sig1.T,
        tau0 == -tau0.T,
        tau1 == -tau1.T,
        _cvxpy.trace(sig0) == 1.,
        _cvxpy.trace(sig1) == 1.]

    prob = _cvxpy.Problem(objective, constraints)
    try:
        prob.solve(solver="CVXOPT")
#       prob.solve(solver="ECOS")
#       prob.solve(solver="SCS")#This always fails
    except _cvxpy.error.SolverError as e:
        _warnings.warn("CVXPY failed: %s - diamonddist returning -2!" % str(e))
        return (-2, _np.zeros((dim, dim))) if return_x else -2
    except:
        _warnings.warn("CVXOPT failed (uknown err) - diamonddist returning -2!")
        return (-2, _np.zeros((dim, dim))) if return_x else -2

    #Validate result
    #assert( abs(_np.trace(_np.dot(K.T,Y.value) + _np.dot(L.T,Z.value))-prob.value) < 1e-6 ), \
    #    "Diamondnorm mismatch"

    if return_x:
        X = Y.value + 1j * Z.value  # encodes state at which maximum trace-distance occurs
        return prob.value, X
    else:
        return prob.value


def jtracedist(A, B, mxBasis='pp'):  # Jamiolkowski trace distance:  Tr(|J(A)-J(B)|)
    """
    Compute the Jamiolkowski trace distance between operation matrices A and B,
    given by:

      D = 0.5 * Tr( sqrt{ (J(A)-J(B))^2 } )

    where J(.) is the Jamiolkowski isomorphism map that maps a operation matrix
    to it's corresponding Choi Matrix.

    Parameters
    ----------
    A, B : numpy array
        The matrices to compute the distance between.

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).
    """
    JA = _jam.fast_jamiolkowski_iso_std(A, mxBasis)
    JB = _jam.fast_jamiolkowski_iso_std(B, mxBasis)
    return tracedist(JA, JB)


def entanglement_fidelity(A, B, mxBasis='pp'):
    """
    Returns the "entanglement" process fidelity between gate
    matrices A and B given by :

      F = Tr( sqrt{ sqrt(J(A)) * J(B) * sqrt(J(A)) } )^2

    where J(.) is the Jamiolkowski isomorphism map that maps a operation matrix
    to it's corresponding Choi Matrix.

    Parameters
    ----------
    A, B : numpy array
        The matrices to compute the fidelity between.

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The basis of the matrices.  Allowed values are Matrix-unit (std),
        Gell-Mann (gm), Pauli-product (pp), and Qutrit (qt)
        (or a custom basis object).
    """
    d2 = A.shape[0]
    def isTP(x): return _np.isclose(x[0, 0], 1.0) and all(
        [_np.isclose(x[0, i], 0) for i in range(d2)])

    def isUnitary(x): return _np.allclose(_np.identity(d2, 'd'), _np.dot(x, x.conjugate().T))

    if isTP(A) and isTP(B) and isUnitary(B):  # then assume TP-like gates & use simpler formula
        TrLambda = _np.trace(_np.dot(A, B.conjugate().T))  # same as using _np.linalg.inv(B)
        d2 = A.shape[0]
        return TrLambda / d2

    JA = _jam.jamiolkowski_iso(A, mxBasis, mxBasis)
    JB = _jam.jamiolkowski_iso(B, mxBasis, mxBasis)
    return fidelity(JA, JB)


def average_gate_fidelity(A, B, mxBasis='pp'):
    """
    Computes the average gate fidelity (AGF) between two gates.
    Average gate fidelity (F_g) is related to entanglement fidelity
    (F_p), via:

      F_g = (d * F_p + 1)/(1 + d),

    where d is the Hilbert space dimension. This formula, and the
    definition of AGF, can be found in Phys. Lett. A 303 249-252 (2002).

    Parameters
    ----------
    A : array or gate
        The gate to compute the AGI to B of. E.g., an imperfect
        implementation of B.

    B : array or gate
        The gate to compute the AGI to A of. E.g., the target gate
        corresponding to A.

    mxBasis : {"std","gm","pp"} or Basis object, optional
        The basis of the matrices.

    Returns
    -------
    AGI : float
        The AGI of A to B.
    """
    d = int(round(_np.sqrt(A.shape[0])))
    PF = entanglement_fidelity(A, B, mxBasis=mxBasis)
    AGF = (d * PF + 1) / (1 + d)
    return float(AGF)


def average_gate_infidelity(A, B, mxBasis="gm"):
    """
    Computes the average gate infidelity (AGI) between two gates.
    Average gate infidelity is related to entanglement infidelity
    (EI) via:

      AGI = (d * (1-EI) + 1)/(1 + d),

    where d is the Hilbert space dimension. This formula, and the
    definition of AGI, can be found in Phys. Lett. A 303 249-252 (2002).

    Parameters
    ----------
    A : array or gate
        The gate to compute the AGI to B of. E.g., an imperfect
        implementation of B.

    B : array or gate
        The gate to compute the AGI to A of. E.g., the target gate
        corresponding to A.

    mxBasis : {"std","gm","pp"} or Basis object, optional
        The basis of the matrices.

    Returns
    ----------
    AGI : float
        The AGI of A to B.
    """
    return 1 - average_gate_fidelity(A, B, mxBasis)


def entanglement_infidelity(A, B, mxBasis='pp'):
    """
    Returns the entanglement infidelity (EI) between gate
    matrices A and B given by :

      EI = 1 - Tr( sqrt{ sqrt(J(A)) * J(B) * sqrt(J(A)) } )^2

    where J(.) is the Jamiolkowski isomorphism map that maps a operation matrix
    to it's corresponding Choi Matrix.

    Parameters
    ----------
    A, B : numpy array
        The matrices to compute the fidelity between.

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The basis of the matrices.  Allowed values are Matrix-unit (std),
        Gell-Mann (gm), Pauli-product (pp), and Qutrit (qt)
        (or a custom basis object).

    Returns
    -------
    EI : float
        The EI of A to B.
    """
    return 1 - float(entanglement_fidelity(A, B, mxBasis))


def unitarity(A, mxBasis="gm"):
    """
    Returns the "unitarity" of a channel, as defined in Wallman et al,
    ``Estimating the Coherence of noise'' NJP 17 113020 (2015). The
    unitarity is given by (Prop 1 in Wallman et al):

    u(A) = Tr( A_u^{\dagger} A_u ) / (d^2  - 1),

    where A_u is the unital submatrix of A, and d is the dimension of
    the Hilbert space. When A is written in any basis for which the
    first element is the  normalized identity (e.g., the pp or gm
    bases), The unital submatrix of A is the matrix obtained when the
    top row and left hand column is removed from A.

    Parameters
    ----------
    A : array or gate
        The gate for which the unitarity is to be computed.

    mxBasis : {"std","gm","pp"} or a Basis object, optional
        The basis of the matrix.

    d : int, optional
        The dimension of the Hilbert space.

    Returns
    ----------
    u : float
        The unitarity of the gate A.

    """
    d = int(round(_np.sqrt(A.shape[0])))
    basisMxs = _basis_matrices(mxBasis, A.shape[0])

    if _np.allclose(basisMxs[0], _np.identity(d, 'd')):
        B = A
    else:
        B = _bt.change_basis(A, mxBasis, "gm")  # everything should be able to be put in the "gm" basis

    unital = B[1:d**2, 1:d**2]
    u = _np.trace(_np.dot(_np.conj(_np.transpose(unital)), unital)) / (d**2 - 1)
    return u


def fidelity_upper_bound(operationMx):
    """
    Get an upper bound on the fidelity of the given
      operation matrix with any unitary operation matrix.

    The closeness of the result to one tells
     how "unitary" the action of operationMx is.

    Parameters
    ----------
    operationMx : numpy array
        The operation matrix to act on.

    Returns
    -------
    float
        The resulting upper bound on fidelity(operationMx, anyUnitaryGateMx)
    """
    choi = _jam.jamiolkowski_iso(operationMx, choiMxBasis="std")
    choi_evals, choi_evecs = _np.linalg.eig(choi)
    maxF_direct = max([_np.sqrt(max(ev.real, 0.0)) for ev in choi_evals]) ** 2

    iMax = _np.argmax([ev.real for ev in choi_evals])  # index of maximum eigenval
    closestVec = choi_evecs[:, iMax:(iMax + 1)]

    ##print "DEBUG: closest evec = ", closestUnitaryVec
    #new_evals = _np.zeros( len(closestUnitaryVec) ); new_evals[iClosestU] = 1.0
    #closestUnitaryJmx = _np.dot(choi_evecs, _np.dot( _np.diag(new_evals), _np.linalg.inv(choi_evecs) ) ) #gives same result
    closestJmx = _np.kron(closestVec, _np.transpose(_np.conjugate(closestVec)))  # closest rank-1 Jmx
    closestJmx /= _mt.trace(closestJmx)  # normalize so trace of Jmx == 1.0

    maxF = fidelity(choi, closestJmx)

    if not _np.isnan(maxF):

        #Uncomment for debugging
        #if abs(maxF - maxF_direct) >= 1e-6:
        #    print "DEBUG: operationMx:\n",operationMx
        #    print "DEBUG: choiMx:\n",choi
        #    print "DEBUG choi_evals = ",choi_evals, " iMax = ",iMax
        #    #print "DEBUG: J = \n", closestUnitaryJmx
        #    print "DEBUG: eigvals(J) = ", _np.linalg.eigvals(closestJmx)
        #    print "DEBUG: trace(J) = ", _mt.trace(closestJmx)
        #    print "DEBUG: maxF = %f,  maxF_direct = %f" % (maxF, maxF_direct)
        #    raise ValueError("ERROR: maxF - maxF_direct = %f" % (maxF -maxF_direct))
        assert(abs(maxF - maxF_direct) < 1e-6)
    else:
        maxF = maxF_direct  # case when maxF is nan, due to scipy sqrtm function being buggy - just use direct F

    closestOpMx = _jam.jamiolkowski_iso_inv(closestJmx, choiMxBasis="std")
    return maxF, closestOpMx

    #closestU_evals, closestU_evecs = _np.linalg.eig(closestUnitaryGateMx)
    #print "DEBUG: U = \n", closestUnitaryGateMx
    #print "DEBUG: closest U evals = ",closestU_evals
    #print "DEBUG:  evecs = \n",closestU_evecs


def get_povm_map(model, povmlbl):
    """
    Constructs a gate-like quantity for the POVM within `model`.

    This is done by embedding the `k`-outcome classical output space of the POVM
    in the Hilbert-Schmidt space of `k` by `k` density matrices by placing the
    classical probability distribution along the diagonal of the density matrix.
    Currently, this is only implemented for the case when `k` equals `d`, the
    dimension of the POVM's Hilbert space.

    Parameters
    ----------
    model : Model
        The model supplying the POVM effect vectors and the basis those
        vectors are in.

    povmlbl : str
        The POVM label

    Returns
    -------
    numpy.ndarray
        The matrix of the "POVM map" in the `model.basis` basis.
    """
    povmVectors = [v.todense()[:, None] for v in model.povms[povmlbl].values()]
    if isinstance(model.basis, _DirectSumBasis):  # HACK - need to get this to work with general bases
        blkDims = [int(_np.sqrt(comp.dim)) for comp in model.basis.component_bases]
    else:
        blkDims = [int(round(_np.sqrt(model.dim)))]  # [d] where density matrix is dxd

    nV = len(povmVectors)
    #assert(d**2 == model.dim), "Model dimension (%d) is not a perfect square!" % model.dim
    #assert( nV**2 == d ), "Can only compute POVM metrics when num of effects == H space dimension"
    #   I don't think above assert is needed - should work in general (Robin?)
    povm_mx = _np.concatenate(povmVectors, axis=1).T  # "povm map" ( B(H) -> S_k ) (shape= nV,model.dim)

    Sk_embedding_in_std = _np.zeros((model.dim, nV))
    for i in range(nV):
        Sk_embedding_in_std[:, i] = _flat_mut_blks(i, i, blkDims)

    std_to_basis = model.basis.reverse_transform_matrix("std")  # _bt.transform_matrix("std", model.basis, blkDims)
    assert(std_to_basis.shape == (model.dim, model.dim))

    return _np.dot(std_to_basis, _np.dot(Sk_embedding_in_std, povm_mx))


def povm_fidelity(model, targetModel, povmlbl):
    """
    Computes the process (entanglement) fidelity between POVM maps.

    Parameters
    ----------
    model, targetModel : Model
        Models containing the two POVMs to compare.

    povmlbl : str
        The POVM label

    Returns
    -------
    float
    """
    povm_mx = get_povm_map(model, povmlbl)
    target_povm_mx = get_povm_map(targetModel, povmlbl)
    return entanglement_fidelity(povm_mx, target_povm_mx, targetModel.basis)


def povm_jtracedist(model, targetModel, povmlbl):
    """
    Computes the Jamiolkowski trace distance between POVM maps using :func:`jtracedist`.

    Parameters
    ----------
    model, targetModel : Model
        Models containing the two POVMs to compare.

    povmlbl : str
        The POVM label

    Returns
    -------
    float
    """
    povm_mx = get_povm_map(model, povmlbl)
    target_povm_mx = get_povm_map(targetModel, povmlbl)
    return jtracedist(povm_mx, target_povm_mx, targetModel.basis)


def povm_diamonddist(model, targetModel, povmlbl):
    """
    Computes the diamond distance between POVM maps using :func:`diamonddist`.

    Parameters
    ----------
    model, targetModel : Model
        Models containing the two POVMs to compare.

    povmlbl : str
        The POVM label

    Returns
    -------
    float
    """
    povm_mx = get_povm_map(model, povmlbl)
    target_povm_mx = get_povm_map(targetModel, povmlbl)
    return diamonddist(povm_mx, target_povm_mx, targetModel.basis)


#decompose operation matrix into axis of rotation, etc
def decompose_gate_matrix(operationMx):
    """
    Compute how the action of a operation matrix can be
    is decomposed into fixed points, axes of rotation,
    angles of rotation, and decays.  Also determines
    whether a gate appears to be valid and/or unitary.

    Parameters
    ----------
    operationMx : numpy array
        The operation matrix to act on.

    Returns
    -------
    dict
       A dictionary describing the decomposed action. Keys are:

         'isValid' : bool
             whether decomposition succeeded
         'isUnitary' : bool
             whether operationMx describes unitary action
         'fixed point' : numpy array
             the fixed point of the action
         'axis of rotation' : numpy array or nan
             the axis of rotation
         'decay of diagonal rotation terms' : float
             decay of diagonal terms
         'rotating axis 1' : numpy array or nan
             1st axis orthogonal to axis of rotation
         'rotating axis 2' : numpy array or nan
             2nd axis orthogonal to axis of rotation
         'decay of off diagonal rotation terms' : float
             decay of off-diagonal terms
         'pi rotations' : float
             angle of rotation in units of pi radians
    """

    op_evals, op_evecs = _np.linalg.eig(_np.asarray(operationMx))
    # fp_eigenvec = None
    # aor_eval = None; aor_eigenvec = None
    # ra_eval  = None; ra1_eigenvec = None; ra2_eigenvec = None

    TOL = 1e-4  # 1e-7

    unit_eval_indices = [i for (i, ev) in enumerate(op_evals) if abs(ev - 1.0) < TOL]
    #unit_eval_indices = [ i for (i,ev) in enumerate(op_evals) if ev > (1.0-TOL) ]

    conjpair_eval_indices = []
    for (i, ev) in enumerate(op_evals):
        if i in unit_eval_indices: continue  # don't include the unit eigenvalues in the conjugate pair count
        # don't include existing conjugate pairs
        if any([(i in conjpair) for conjpair in conjpair_eval_indices]): continue
        for (j, ev2) in enumerate(op_evals[i + 1:]):
            if abs(ev - _np.conjugate(ev2)) < TOL:
                conjpair_eval_indices.append((i, j + (i + 1)))
                break  # don't pair i-th eigenvalue with any other (pairs should be disjoint)

    real_eval_indices = []  # indices of real eigenvalues that are not units or a part of any conjugate pair
    complex_eval_indices = []  # indices of complex eigenvalues that are not units or a part of any conjugate pair
    for (i, ev) in enumerate(op_evals):
        if i in unit_eval_indices: continue  # don't include the unit eigenvalues
        if any([(i in conjpair) for conjpair in conjpair_eval_indices]): continue  # don't include the conjugate pairs
        if abs(ev.imag) < TOL: real_eval_indices.append(i)
        else: complex_eval_indices.append(i)

    #if len(real_eval_indices + unit_eval_indices) > 0:
    #    max_real_eval = max([ op_evals[i] for i in real_eval_indices + unit_eval_indices])
    #    min_real_eval = min([ op_evals[i] for i in real_eval_indices + unit_eval_indices])
    #else:
    #    max_real_eval = _np.nan
    #    min_real_eval = _np.nan
    #
    #fixed_points = [ op_evecs[:,i] for i in unit_eval_indices ]
    #real_eval_axes = [ op_evecs[:,i] for i in real_eval_indices ]
    #conjpair_eval_axes = [ (op_evecs[:,i],op_evecs[:,j]) for (i,j) in conjpair_eval_indices ]
    #
    #ret = { }

    nQubits = _np.log2(operationMx.shape[0]) / 2
    if nQubits == 1:
        #print "DEBUG: 1 qubit decomp --------------------------"
        #print "   --> evals = ", op_evals
        #print "   --> unit eval indices = ", unit_eval_indices
        #print "   --> conj eval indices = ", conjpair_eval_indices
        #print "   --> unpaired real eval indices = ", real_eval_indices

        #Special case: if have two conjugate pairs, check if one (or both) are real
        #  and break the one with the largest (real) value into two unpaired real evals.
        if len(conjpair_eval_indices) == 2:
            iToBreak = None
            if abs(_np.imag(op_evals[conjpair_eval_indices[0][0]])) < TOL and \
               abs(_np.imag(op_evals[conjpair_eval_indices[1][0]])) < TOL:
                iToBreak = _np.argmax([_np.real(conjpair_eval_indices[0][0]), _np.real(conjpair_eval_indices[1][0])])
            elif abs(_np.imag(op_evals[conjpair_eval_indices[0][0]])) < TOL: iToBreak = 0
            elif abs(_np.imag(op_evals[conjpair_eval_indices[1][0]])) < TOL: iToBreak = 1

            if iToBreak is not None:
                real_eval_indices.append(conjpair_eval_indices[iToBreak][0])
                real_eval_indices.append(conjpair_eval_indices[iToBreak][1])
                del conjpair_eval_indices[iToBreak]

        #Find eigenvector corresponding to fixed point (or closest we can get).   This
        # should be a unit eigenvalue with identity eigenvector.
        if len(unit_eval_indices) > 0:
            #Find linear least squares solution within possibly degenerate unit-eigenvalue eigenspace
            # of eigenvector closest to identity density mx (the desired fixed point), then orthogonalize
            # the remaining eigenvectors w.r.t this one.
            A = _np.take(op_evecs, unit_eval_indices, axis=1)
            b = _np.array([[1], [0], [0], [0]], 'd')  # identity density mx
            x = _np.dot(_np.linalg.pinv(_np.dot(A.T, A)), _np.dot(A.T, b))
            fixedPtVec = _np.dot(A, x)  # fixedPtVec / _np.linalg.norm(fixedPtVec)
            fixedPtVec = fixedPtVec[:, 0]

            iLargestContrib = _np.argmax(_np.abs(x))  # index of gate eigenvector which contributed the most
            for ii, i in enumerate(unit_eval_indices):
                if ii == iLargestContrib:
                    op_evecs[:, i] = fixedPtVec
                    iFixedPt = i
                else:
                    op_evecs[:, i] = op_evecs[:, i] - _np.vdot(fixedPtVec, op_evecs[:, i]) * fixedPtVec
                    for jj, j in enumerate(unit_eval_indices[:ii]):
                        if jj == iLargestContrib: continue
                        op_evecs[:, i] = op_evecs[:, i] - _np.vdot(op_evecs[:, j], op_evecs[:, i]) * op_evecs[:, j]
                    op_evecs[:, i] /= _np.linalg.norm(op_evecs[:, i])

        elif len(real_eval_indices) > 0:
            # just take eigenvector corresponding to the largest real eigenvalue?
            #iFixedPt = real_eval_indices[ _np.argmax( [ op_evals[i] for i in real_eval_indices ] ) ]

            # ...OR take eigenvector corresponding to a real unpaired eigenvalue closest to identity:
            idmx = _np.array([[1], [0], [0], [0]], 'd')  # identity density mx
            iFixedPt = real_eval_indices[_np.argmin([_np.linalg.norm(op_evecs[i] - idmx) for i in real_eval_indices])]

        else:
            #No unit or real eigenvalues => two complex conjugate pairs or unpaired complex evals --> bail out
            return {'isValid': False, 'isUnitary': False, 'msg': "All evals are complex."}

        #Find eigenvector corresponding to axis of rotation: find the *largest* unpaired real/unit eval
        indsToConsider = (unit_eval_indices + real_eval_indices)[:]
        del indsToConsider[indsToConsider.index(iFixedPt)]  # don't consider fixed pt evec

        if len(indsToConsider) > 0:
            iRotAxis = indsToConsider[_np.argmax([op_evals[i] for i in indsToConsider])]
        else:
            #No unit or real eigenvalues => an unpaired complex eval --> bail out
            return {'isValid': False, 'isUnitary': False, 'msg': "Unpaired complex eval."}

        #There are only 2 eigenvalues left -- hopefully a conjugate pair giving rotation
        inds = list(range(4))
        del inds[inds.index(iFixedPt)]
        del inds[inds.index(iRotAxis)]
        if abs(op_evals[inds[0]] - _np.conjugate(op_evals[inds[1]])) < TOL:
            iConjPair1, iConjPair2 = inds
        else:
            return {'isValid': False, 'isUnitary': False, 'msg': "No conjugate pair for rotn."}

        return {'isValid': True,
                'isUnitary': bool(len(unit_eval_indices) >= 2),
                'fixed point': op_evecs[:, iFixedPt],
                'axis of rotation': op_evecs[:, iRotAxis],
                'rotating axis 1': op_evecs[:, iConjPair1],
                'rotating axis 2': op_evecs[:, iConjPair2],
                'decay of diagonal rotation terms': 1.0 - abs(op_evals[iRotAxis]),
                'decay of off diagonal rotation terms': 1.0 - abs(op_evals[iConjPair1]),
                'pi rotations': _np.angle(op_evals[iConjPair1]) / _np.pi,
                'msg': "Success"}

    else:
        return {'isValid': False,
                'isUnitary': False,
                'msg': "Unsupported number of qubits: %d" % nQubits}


def state_to_dmvec(psi):
    """
    Compute the vectorized density matrix which acts as the state `psi`.

    This is just the outer product map |psi> => |psi><psi| with the
    output flattened, i.e. `dot(psi, conjugate(psi).T)`.

    Parameters
    ----------
    psi : numpy array
        The state vector.

    Returns
    -------
    numpy array
       The vectorized density matrix.
    """
    psi = psi.reshape((psi.size, 1))  # convert to (N,1) shape if necessary
    dm = _np.dot(psi, _np.conjugate(psi.T))
    return dm.flatten()


def dmvec_to_state(dmvec, tol=1e-6):
    """
    Compute the pure state describing the action of density matrix vector `dmvec`.

    If `dmvec` represents a mixed state, ValueError is raised.

    Parameters
    ----------
    dmvec : numpy array
        The vectorized density matrix, assumed to be in the standard (matrix
        unit) basis.

    tol : float, optional
        tolerance for determining whether an eigenvalue is zero.

    Returns
    -------
    numpy array
       The pure state, as a column vector of shape = (N,1)
    """
    d2 = dmvec.size; d = int(round(_np.sqrt(d2)))
    dm = dmvec.reshape((d, d))
    evals, evecs = _np.linalg.eig(dm)

    k = None
    for i, ev in enumerate(evals):
        if abs(ev) > tol:
            if k is None: k = i
            else: raise ValueError("Cannot convert mixed dmvec to pure state!")
    if k is None: raise ValueError("Cannot convert zero dmvec to puse state!")
    psi = evecs[:, k] * _np.sqrt(evals[k])
    psi.shape = (d, 1)
    return psi


def unitary_to_process_mx(U):
    """
    Compute the super-operator which acts on (row)-vectorized
    density matrices from a unitary operator (matrix) U which
    acts on state vectors.  This super-operator is given by
    the tensor product of U and conjugate(U), i.e. kron(U,U.conj).

    Parameters
    ----------
    U : numpy array
        The unitary matrix which acts on state vectors.

    Returns
    -------
    numpy array
       The super-operator process matrix.
    """
    # U -> kron(U,Uc) since U rho U_dag -> kron(U,Uc)
    #  since AXB --row-vectorize--> kron(A,B.T)*vec(X)
    return _np.kron(U, _np.conjugate(U))


def process_mx_to_unitary(superop):
    """
    Compute the unitary corresponding to the (unitary-action!)
    super-operator `superop` which acts on (row)-vectorized
    density matrices.  The super-operator must be of the form
    `kron(U,U.conj)` or an error will be thrown.

    Parameters
    ----------
    superop : numpy array
        The superoperator matrix which acts on vectorized
        density matrices (in the 'std' matrix-unit basis).

    Returns
    -------
    numpy array
       The unitary matrix which acts on state vectors.
    """
    d2 = superop.shape[0]; d = int(round(_np.sqrt(d2)))
    U = _np.empty((d, d), 'complex')

    for i in range(d):
        densitymx_i = _np.zeros((d, d), 'd'); densitymx_i[i, i] = 1.0  # |i><i|
        UiiU = _np.dot(superop, densitymx_i.flat).reshape((d, d))  # U|i><i|U^dag

        if i > 0:
            j = 0
            densitymx_ij = _np.zeros((d, d), 'd'); densitymx_ij[i, j] = 1.0  # |i><i|
            UijU = _np.dot(superop, densitymx_ij.flat).reshape((d, d))  # U|i><j|U^dag
            Uj = U[:, j]
            Ui = _np.dot(UijU, Uj)
        else:
            ##method1: use random state projection
            #rand_state = _np.random.rand(d)
            #projected_rand_state = _np.dot(UiiU, rand_state)
            #assert(_np.linalg.norm(projected_rand_state) > 1e-8)
            #projected_rand_state /= _np.linalg.norm(projected_rand_state)
            #Ui = projected_rand_state

            #method2: get eigenvector corresponding to largest eigenvalue (more robust)
            evals, evecs = _np.linalg.eig(UiiU)
            imaxeval = _np.argmax(_np.abs(evals))
            #TODO: assert other eigenvalues are much smaller?
            Ui = evecs[:, imaxeval]
            Ui /= _np.linalg.norm(Ui)
        U[:, i] = Ui

    return U


def spam_error_generator(spamvec, target_spamvec, mxBasis, typ="logGTi"):
    """
    Construct an error generator from a SPAM vector and it's target.

    Computes the value of the error generator given by
    `errgen = log( diag(spamvec / target_spamvec) )`, where division is
    element-wise.  This results in a (non-unique) error generator matrix
    `E` such that `spamvec = exp(E) * target_spamvec`.

    Note: This is currently of very limited use, as the above algorithm fails
    whenever `target_spamvec` has zero elements where `spamvec` doesn't.

    Parameters
    ----------
    spamvec : ndarray
      The SPAM vector.

    target_spamvec : ndarray
      The target SPAM vector.

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    typ : {"logGTi"}
      The type of error generator to compute.  Allowed values are:

      - "logGTi" : errgen = log( diag(spamvec / target_spamvec) )

    Returns
    -------
    errgen : ndarray
      The error generator.
    """
    # Compute error generator for rho:   rho = exp(E)rho0 => rho = A*rho0 => A = diag(rho/rho0)
    assert(typ == "logGTi"), "Only logGTi type is supported so far"

    d2 = len(spamvec)
    errgen = _np.zeros((d2, d2), 'd')  # type assumes this is density-mx evolution
    diags = []
    for a, b in zip(spamvec, target_spamvec):
        if _np.isclose(b, 0.0):
            if _np.isclose(a, b): d = 1
            else: raise ValueError("Cannot take spam_error_generator")
        else:
            d = a / b
        diags.append(d)
    errgen[_np.diag_indices(d2)] = diags
    return _spl.logm(errgen)


def error_generator(gate, target_op, mxBasis, typ="logG-logT"):
    """
    Construct the error generator from a gate and its target.

    Computes the value of the error generator given by
    errgen = log( inv(target_op) * gate ), so that
    gate = target_op * exp(errgen).

    Parameters
    ----------
    gate : ndarray
      The operation matrix

    target_op : ndarray
      The target operation matrix

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    typ : {"logG-logT", "logTiG", "logGTi"}
      The type of error generator to compute.  Allowed values are:

      - "logG-logT" : errgen = log(gate) - log(target_op)
      - "logTiG" : errgen = log( dot(inv(target_op), gate) )
      - "logGTi" : errgen = log( dot(gate,inv(target_op)) )

    Returns
    -------
    errgen : ndarray
      The error generator.
    """
    TOL = 1e-8

    if typ == "logG-logT":
        try:
            logT = _mt.unitary_superoperator_matrix_log(target_op, mxBasis)
        except AssertionError:  # if not unitary, fall back to just taking the real log
            logT = _mt.real_matrix_log(target_op, "raise", TOL)  # make a fuss if this can't be done
        logG = _mt.approximate_matrix_log(gate, logT)

        # Both logG and logT *should* be real, so we just take the difference.
        if _np.linalg.norm(_np.imag(logG)) < TOL and \
           _np.linalg.norm(_np.imag(logT)) < TOL:
            return _np.real(logG - logT)

        #Otherwise, there could be branch cut issues or worse, so just
        # raise an error for now (maybe return a dummy if needed elsewhere?)
        raise ValueError("Could not construct a real logarithms for the" +
                         "'logG-logT' generator.  Perhaps you should use " +
                         "the 'logTiG' or 'logGTi' generator instead?")

    elif typ == "logTiG":
        target_op_inv = _spl.inv(target_op)
        try:
            errgen = _mt.near_identity_matrix_log(_np.dot(target_op_inv, gate), TOL)
        except AssertionError:  # not near the identity, fall back to the real log
            _warnings.warn(("Near-identity matrix log failed; falling back "
                            "to approximate log for logTiG error generator"))
            errgen = _mt.real_matrix_log(_np.dot(target_op_inv, gate), "warn", TOL)

        if _np.linalg.norm(errgen.imag) > TOL:
            _warnings.warn("Falling back to approximate log for logTiG error generator")
            errgen = _mt.approximate_matrix_log(_np.dot(target_op_inv, gate),
                                                _np.zeros(gate.shape, 'd'), TOL=TOL)

    elif typ == "logGTi":
        target_op_inv = _spl.inv(target_op)
        try:
            errgen = _mt.near_identity_matrix_log(_np.dot(gate, target_op_inv), TOL)
        except AssertionError as e:  # not near the identity, fall back to the real log
            _warnings.warn(("Near-identity matrix log failed; falling back "
                            "to approximate log for logGTi error generator:\n%s") % str(e))
            errgen = _mt.real_matrix_log(_np.dot(gate, target_op_inv), "warn", TOL)

        if _np.linalg.norm(errgen.imag) > TOL:
            _warnings.warn("Falling back to approximate log for logGTi error generator")
            errgen = _mt.approximate_matrix_log(_np.dot(gate, target_op_inv),
                                                _np.zeros(gate.shape, 'd'), TOL=TOL)

    else:
        raise ValueError("Invalid error-generator type: %s" % typ)

    if _np.linalg.norm(_np.imag(errgen)) > TOL:
        raise ValueError("Could not construct a real generator!")
        #maybe this is actually ok, but a complex error generator will
        # need to be plotted differently, etc -- TODO
    return _np.real(errgen)


def operation_from_error_generator(error_gen, target_op, typ="logG-logT"):
    """
    Construct a gate from an error generator and a target gate.

    Inverts the computation fone in :func:`error_generator` and
    returns the value of the gate given by
    gate = target_op * exp(error_gen).

    Parameters
    ----------
    error_gen : ndarray
      The error generator matrix

    target_op : ndarray
      The target operation matrix

    typ : {"logG-logT", "logTiG"}
      The type of error generator to compute.  Allowed values are:

      - "logG-logT" : errgen = log(gate) - log(target_op)
      - "logTiG" : errgen = log( dot(inv(target_op), gate) )


    Returns
    -------
    ndarray
      The operation matrix.
    """
    if typ == "logG-logT":
        return _spl.expm(error_gen + _spl.logm(target_op))
    elif typ == "logTiG":
        return _np.dot(target_op, _spl.expm(error_gen))
    elif typ == "logGTi":
        return _np.dot(_spl.expm(error_gen), target_op)
    else:
        raise ValueError("Invalid error-generator type: %s" % typ)


def std_scale_factor(dim, projection_type):
    """
    Returns the multiplicative scaling that should be applied to the output of
    :func"`std_error_generators`, before using them as projectors, in order to
    compute the "standard" reported projection onto that type of error (i.e.
    the coefficient of the standard generator terms built un-normalized-Paulis).

    Parameters
    ----------
    dim : int
      The dimension of the error generators; also the  associated gate
      dimension.  This must be a perfect square, as `sqrt(dim)`
      is the dimension of density matrices. For a single qubit, dim == 4.

    projection_type : {"hamiltonian", "stochastic", "affine"}
      The type/class of error generators to get the scaling for.

    Returns
    -------
    float
    """
    d2 = dim
    d = int(_np.sqrt(d2))

    if projection_type == "hamiltonian":
        scaleFctr = 1.0 / (d * _np.sqrt(2))
        # so projection is coefficient of Hamiltonian term (w/un-normalized Paulis)
    elif projection_type == "stochastic":
        scaleFctr = 1.0 / d
        # so projection is coefficient of P*rho*P stochastic term in generator (w/un-normalized Paulis)
    elif projection_type == "affine":
        scaleFctr = 1.0  # so projection is coefficient of P affine term in generator (w/un-normalized Paulis)
    else:
        raise ValueError("Invalid projection_type argument: %s"
                         % projection_type)
    return scaleFctr


def std_error_generators(dim, projection_type, projection_basis):
    """
    Compute the gate error generators for a standard set of errors which
    correspond to "Hamiltonian"- or "Stochastic"-type errors in terms of the
    elements of the specified basis.

    Parameters
    ----------
    dim : int
      The dimension of the error generators to be returned.  This is also the
      associated gate dimension, and must be a perfect square, as `sqrt(dim)`
      is the dimension of density matrices. For a single qubit, dim == 4.

    projection_type : {"hamiltonian", "stochastic", "affine"}
      The type of error generators to construct.  If "hamiltonian", then the
      Hamiltonian generators which take a density matrix rho -> -i*[ H, rho ]
      for Pauli-product matrix H.  If "stochastic", then the Stochastic error
      generators which take rho -> P*rho*P for Pauli-product matrix P.  If
      "affine", then the affine generators which take rho -> P.

    projection_basis : {'std', 'gm', 'pp', 'qt'}
      Which basis is used to construct the error generators.  Allowed
      values are Matrix-unit (std), Gell-Mann (gm),
      Pauli-product (pp) and Qutrit (qt).

    Returns
    -------
    generators : numpy.ndarray
      An array of shape (#basis-elements,dim,dim).  `generators[i]` is the
      generator corresponding to the ith basis matrix in the
      *std* (matrix unit) basis.  (Note that in most cases #basis-elements
      == dim, so the size of `generators` is (dim,dim,dim) ).  Each
      generator is normalized so that as a vector it has unit Frobenius norm.
    """
    d2 = dim
    d = int(_np.sqrt(d2))

    #Get a list of the basis matrices
    mxs = _basis_matrices(projection_basis, d2)

    assert(len(mxs) <= d2)  # OK if there are fewer basis matrices (e.g. for bases w/multiple blocks)
    assert(_np.isclose(d * d, d2))  # d2 must be a perfect square

    lindbladMxs = _np.empty((len(mxs), d2, d2), 'complex')
    for i, basisMx in enumerate(mxs):
        if projection_type == "hamiltonian":
            lindbladMxs[i] = _lt.hamiltonian_to_lindbladian(basisMx)  # in std basis
        elif projection_type == "stochastic":
            lindbladMxs[i] = _lt.stochastic_lindbladian(basisMx)  # in std basis
        elif projection_type == "affine":
            lindbladMxs[i] = _lt.affine_lindbladian(basisMx)  # in std basis
        else:
            raise ValueError("Invalid projection_type argument: %s"
                             % projection_type)
        norm = _np.linalg.norm(lindbladMxs[i].flat)
        if not _np.isclose(norm, 0):
            lindbladMxs[i] /= norm  # normalize projector
            assert(_np.isclose(_np.linalg.norm(lindbladMxs[i].flat), 1.0))

    return lindbladMxs


def std_errgen_projections(errgen, projection_type, projection_basis,
                           mxBasis="gm", return_generators=False,
                           return_scale_fctr=False):
    """
    Compute the projections of a gate error generator onto generators
    for a standard set of errors constructed from the elements of a
    specified basis.

    Parameters
    ----------
    errgen: : ndarray
      The error generator matrix to project.

    projection_type : {"hamiltonian", "stochastic", "affine"}
      The type of error generators to project the gate error generator onto.
      If "hamiltonian", then use the Hamiltonian generators which take a density
      matrix rho -> -i*[ H, rho ] for Pauli-product matrix H.  If "stochastic",
      then use the Stochastic error generators which take rho -> P*rho*P for
      Pauli-product matrix P (recall P is self adjoint).  If "affine", then
      use the affine error generators which take rho -> P (superop is |P>><<1|).

    projection_basis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    return_generators : bool, optional
      If True, return the error generators projected against along with the
      projection values themseves.

    return_scale_fctr : bool, optional
      If True, also return the scaling factor that was used to multply the
      projections onto *normalized* error generators to get the returned
      values.

    Returns
    -------
    projections : numpy.ndarray
      An array of length equal to the number of elements in the
      basis used to construct the projectors.  Typically this is
      is also the dimension of the gate (e.g. 4 for a single qubit).

    generators : numpy.ndarray
      Only returned when `return_generators == True`.  An array of shape
      (#basis-els,op_dim,op_dim) such that  `generators[i]` is the
      generator corresponding to the i-th basis element.  Note
      that these matricies are in the *std* (matrix unit) basis.

    scale : float
      Only returned when `return_scale_fctr == True`.  A mulitplicative
      scaling constant that *has already been applied* to `projections`.
    """

    if isinstance(mxBasis, _Basis):
        errgen_std = _bt.change_basis(errgen, mxBasis, mxBasis.equivalent('std'))

        #expand operation matrix so it acts on entire space of dmDim x dmDim density matrices
        errgen_std = _bt.resize_std_mx(errgen_std, 'expand', mxBasis.equivalent('std'),
                                       mxBasis.simple_equivalent('std'))
    else:
        errgen_std = _bt.change_basis(errgen, mxBasis, "std")

    d2 = errgen_std.shape[0]
    d = int(_np.sqrt(d2))
    # nQubits = _np.log2(d)

    #Get a list of the d2 generators (in corresspondence with the
    #  Pauli-product matrices given by _basis.pp_matrices(d) ).
    lindbladMxs = std_error_generators(d2, projection_type, projection_basis)  # in std basis

    assert(len(lindbladMxs) <= d2)  # can be fewer projection matrices (== lenght of projection_basis)
    assert(_np.isclose(d * d, d2))  # d2 must be a perfect square

    projections = _np.empty(len(lindbladMxs), 'd')
    for i, lindbladMx in enumerate(lindbladMxs):
        proj = _np.real_if_close(_np.vdot(errgen_std.flatten(), lindbladMx.flatten()), tol=1000)

        #DEBUG - for checking why perfect gates gave weird projections --> log ambiguity
        #print("DB: rawproj(%d) = " % i,proj)
        #errgen_pp = errgen.copy()#_bt.change_basis(errgen_std,"std","pp")
        #lindbladMx_pp = _bt.change_basis(lindbladMx,"std","pp")
        #if proj > 1.0:
        #    for k in range(errgen_std.shape[0]):
        #        for j in range(errgen_std.shape[1]):
        #            if abs(errgen_pp[k,j].conjugate() * lindbladMx_pp[k,j]) > 1e-2:
        #                print(" [%d,%d]: + " % (k,j),errgen_pp[k,j].conjugate(),"*",lindbladMx_pp[k,j],"=",(errgen_pp[k,j].conjugate() * lindbladMx_pp[i,j]))

        #assert(_np.isreal(proj)), "non-real projection: %s" % str(proj) #just a warning now
        if not _np.isreal(proj):
            _warnings.warn("Taking abs() of non-real projection: %s" % str(proj))
            proj = abs(proj)
        projections[i] = proj

    scaleFctr = std_scale_factor(d2, projection_type)
    projections *= scaleFctr
    lindbladMxs /= scaleFctr  # so projections * generators give original

    ret = [projections]
    if return_generators: ret.append(lindbladMxs)
    if return_scale_fctr: ret.append(scaleFctr)
    return ret[0] if len(ret) == 1 else tuple(ret)


def _assert_shape(ar, shape, sparse=False):
    """ Asserts ar.shape == shape ; works with sparse matrices too """
    if not sparse or len(shape) == 2:
        assert(ar.shape == shape), \
            "Shape mismatch: %s != %s!" % (str(ar.shape), str(shape))
    else:
        if len(shape) == 3:  # first "dim" is a list
            assert(len(ar) == shape[0]), \
                "Leading dim mismatch: %d != %d!" % (len(ar), shape[0])
            assert(shape[0] == 0 or ar[0].shape == (shape[1], shape[2])), \
                "Shape mismatch: %s != %s!" % (str(ar[0].shape), str(shape[1:]))
        elif len(shape) == 4:  # first 2 dims are lists
            assert(len(ar) == shape[0]), \
                "Leading dim mismatch: %d != %d!" % (len(ar), shape[0])
            assert(shape[0] == 0 or len(ar[0]) == shape[1]), \
                "Second dim mismatch: %d != %d!" % (len(ar[0]), shape[1])
            assert(shape[0] == 0 or shape[1] == 0 or ar[0][0].shape == (shape[2], shape[3])), \
                "Shape mismatch: %s != %s!" % (str(ar[0][0].shape), str(shape[2:]))
        else:
            raise NotImplementedError("Number of dimensions must be <= 4!")


def lindblad_error_generators(dmbasis_ham, dmbasis_other, normalize,
                              other_mode="all"):
    """
    Compute the superoperator-generators corresponding to Lindblad terms.

    This routine computes the Hamiltonian and Non-Hamiltonian ("other")
    superoperator generators which correspond to the terms of the Lindblad
    expression:

    L(rho) = sum_i( h_i [A_i,rho] ) +
             sum_ij( o_ij * (B_i rho B_j^dag -
                             0.5( rho B_j^dag B_i + B_j^dag B_i rho) ) )

    where {A_i} and {B_i} are bases (possibly the same) for Hilbert Schmidt
    (density matrix) space with the identity element removed so that each
    A_i and B_i are traceless.  If we write L(rho) in terms of superoperators
    H_i and O_ij,

    L(rho) = sum_i( h_i H_i(rho) ) + sum_ij( o_ij O_ij(rho) )

    then this function computes the matrices for H_i and O_ij using the given
    density matrix basis.  Thus, if `dmbasis` is expressed in the standard
    basis (as it should be), the returned matrices are also in this basis.

    If these elements are used as projectors it may be usedful to normalize
    them (by setting `normalize=True`).  Note, however, that these projectors
    are not all orthogonal - in particular the O_ij's are not orthogonal to
    one another.

    Parameters
    ----------
    dmbasis_ham : list
        A list of basis matrices {B_i} *including* the identity as the first
        element, for the returned Hamiltonian-type error generators.  This
        argument is easily obtained by call to  :func:`pp_matrices` or a
        similar function.  The matrices are expected to be in the standard
        basis, and should be traceless except for the identity.  Matrices
        should be NumPy arrays or SciPy CSR sparse matrices.

    dmbasis_other : list
        A list of basis matrices {B_i} *including* the identity as the first
        element, for the returned Stochastic-type error generators.  This
        argument is easily obtained by call to  :func:`pp_matrices` or a
        similar function.  The matrices are expected to be in the standard
        basis, and should be traceless except for the identity.  Matrices
        should be NumPy arrays or SciPy CSR sparse matrices.

    normalize : bool
        Whether or not generators should be normalized so that
        numpy.linalg.norm(generator.flat) == 1.0  Note that the generators
        will still, in general, be non-orthogonal.

    other_mode : {"diagonal", "diag_affine", "all"}
        Which non-Hamiltonian Lindblad error generators to construct.
        Allowed values are: `"diagonal"` (only the diagonal Stochastic
        generators are returned; that is, the generators corresponding to the
        `i==j` terms in the Lindblad expression.), `"diag_affine"` (diagonal +
        affine generators), and `"all"` (all generators).


    Returns
    -------
    ham_generators : numpy.ndarray or list of SciPy CSR matrices
        If dense matrices where given, an array of shape (d-1,d,d), where d is
        the size of the basis, i.e. d == len(dmbasis).  `ham_generators[i]`
        gives the matrix for H_i.  If sparse matrices were given, a list
        of shape (d,d) CSR matrices.

    other_generators : numpy.ndarray or list of lists of SciPy CSR matrices
        If dense matrices where given, An array of shape (d-1,d-1,d,d),
        (2,d-1,d,d), or (d-1,d,d), where d is the size of the basis, for
        `other_mode` equal to `"all"`, `"diag_affine"`, or `"diagonal"`,
        respectively.  For instance, in the `"all"` case,
        `other_generators[i,j]` gives the matrix for O_ij.  If sparse matrices
        were given, the all but the final 2 dimensions are lists (e.g. the
        `"all"` case returns a list of lists of shape (d,d) CSR matrices).
    """
    if dmbasis_ham is not None:
        ham_mxs = dmbasis_ham  # list of basis matrices (assumed to be in std basis)
        ham_nMxs = len(ham_mxs)  # usually == d2, but not necessary (e.g. w/maxWeight)
    else:
        ham_nMxs = 0

    if dmbasis_other is not None:
        other_mxs = dmbasis_other  # list of basis matrices (assumed to be in std basis)
        other_nMxs = len(other_mxs)  # usually == d2, but not necessary (e.g. w/maxWeight)
    else:
        other_nMxs = 0

    if ham_nMxs > 0:
        d = ham_mxs[0].shape[0]
        sparse = _sps.issparse(ham_mxs[0])
    elif other_nMxs > 0:
        d = other_mxs[0].shape[0]
        sparse = _sps.issparse(other_mxs[0])
    else:
        d = 0  # will end up returning no generators
        sparse = False
    d2 = d**2
    normfn = _spsl.norm if sparse else _np.linalg.norm
    identityfn = (lambda d: _sps.identity(d, 'd', 'csr')) if sparse else _np.identity

    if ham_nMxs > 0 and other_nMxs > 0:
        assert(other_mxs[0].shape[0] == ham_mxs[0].shape[0]), \
            "Bases must have the same dimension!"

    if ham_nMxs > 0:
        assert(_np.isclose(normfn(ham_mxs[0] - identityfn(d) / _np.sqrt(d)), 0)),\
            "The first matrix in 'dmbasis_ham' must be the identity"

        hamLindbladTerms = [None] * (ham_nMxs - 1) if sparse else \
            _np.empty((ham_nMxs - 1, d2, d2), 'complex')

        for i, B in enumerate(ham_mxs[1:]):  # don't include identity
            hamLindbladTerms[i] = _lt.hamiltonian_to_lindbladian(B, sparse)  # in std basis
            if normalize:
                norm = normfn(hamLindbladTerms[i])  # same as norm(term.flat)
                if not _np.isclose(norm, 0):
                    hamLindbladTerms[i] /= norm  # normalize projector
                    assert(_np.isclose(normfn(hamLindbladTerms[i]), 1.0))
    else:
        hamLindbladTerms = None

    if other_nMxs > 0:
        assert(_np.isclose(normfn(other_mxs[0] - identityfn(d) / _np.sqrt(d)), 0)),\
            "The first matrix in 'dmbasis_other' must be the identity"

        if other_mode == "diagonal":
            otherLindbladTerms = [None] * (other_nMxs - 1) if sparse else \
                _np.empty((other_nMxs - 1, d2, d2), 'complex')
            for i, Lm in enumerate(other_mxs[1:]):  # don't include identity
                otherLindbladTerms[i] = _lt.nonham_lindbladian(Lm, Lm, sparse)
                if normalize:
                    norm = normfn(otherLindbladTerms[i])  # same as norm(term.flat)
                    if not _np.isclose(norm, 0):
                        otherLindbladTerms[i] /= norm  # normalize projector
                        assert(_np.isclose(normfn(otherLindbladTerms[i]), 1.0))

        elif other_mode == "diag_affine":
            otherLindbladTerms = [[None] * (other_nMxs - 1)] * 2 if sparse else \
                _np.empty((2, other_nMxs - 1, d2, d2), 'complex')
            for i, Lm in enumerate(other_mxs[1:]):  # don't include identity
                otherLindbladTerms[0][i] = _lt.nonham_lindbladian(Lm, Lm, sparse)
                otherLindbladTerms[1][i] = _lt.affine_lindbladian(Lm, sparse)
                if normalize:
                    for k in (0, 1):
                        norm = normfn(otherLindbladTerms[k][i])  # same as norm(term.flat)
                        if not _np.isclose(norm, 0):
                            otherLindbladTerms[k][i] /= norm  # normalize projector
                            assert(_np.isclose(normfn(otherLindbladTerms[k][i]), 1.0))

        else:  # other_mode == "all"
            otherLindbladTerms = \
                [[None] * (other_nMxs - 1) for i in range(other_nMxs - 1)] if sparse else \
                _np.empty((other_nMxs - 1, other_nMxs - 1, d2, d2), 'complex')

            for i, Lm in enumerate(other_mxs[1:]):  # don't include identity
                for j, Ln in enumerate(other_mxs[1:]):  # don't include identity
                    #print("DEBUG NONHAM LIND (%d,%d)" % (i,j)) #DEBUG!!!
                    otherLindbladTerms[i][j] = _lt.nonham_lindbladian(Lm, Ln, sparse)
                    if normalize:
                        norm = normfn(otherLindbladTerms[i][j])  # same as norm(term.flat)
                        if not _np.isclose(norm, 0):
                            otherLindbladTerms[i][j] /= norm  # normalize projector
                            assert(_np.isclose(normfn(otherLindbladTerms[i][j]), 1.0))
                    #I don't think this is true in general, but appears to be true for "pp" basis (why?)
                    #if j < i: # check that other[i,j] == other[j,i].C, i.e. other is Hermitian
                    #    assert(_np.isclose(_np.linalg.norm(
                    #                otherLindbladTerms[i][j]-
                    #                otherLindbladTerms[j][i].conjugate()),0))
    else:
        otherLindbladTerms = None

    #Check for orthogonality - otherLindblad terms are *not* orthogonal!
    #N = otherLindbladTerms.shape[0]
    #for i in range(N):
    #    for j in range(N):
    #        v1 = otherLindbladTerms[i,j].flatten()
    #        for k in range(N):
    #            for l in range(N):
    #                if k == i and l == j: continue
    #                v2 = otherLindbladTerms[k,l].flatten()
    #                if not _np.isclose(0, _np.vdot(v1,v2)):
    #                    print("%d,%d <-> %d,%d dot = %g [%g]" % (i,j,k,l,_np.vdot(v1,v2),_np.dot(v1,v2)))
    #                    #print("v1 = ",v1)
    #                    #print("v2 = ",v2)
    #                #    assert(False)
    #                #assert(_np.isclose(0, _np.vdot(v1,v2)))

    #Check hamiltonian error gens are orthogonal to others
    #N = otherLindbladTerms.shape[0]
    #for i,hlt in enumerate(hamLindbladTerms):
    #    v1 = hlt.flatten()
    #    for j in range(N):
    #        for k in range(N):
    #            v2 = otherLindbladTerms[j,k].flatten()
    #            assert(_np.isclose(0, _np.vdot(v1,v2)))

    return hamLindbladTerms, otherLindbladTerms


def lindblad_errgen_projections(errgen, ham_basis,
                                other_basis, mxBasis="gm",
                                normalize=True, return_generators=False,
                                other_mode="all", sparse=False):
    """
    Compute the projections of a gate error generator onto generators
    for the Lindblad-term errors when expressed in the given
    "projection basis".

    Parameters
    ----------
    errgen: : ndarray
      The error generator matrix to project.

    ham_basis: {'std', 'gm', 'pp', 'qt'}, list of matrices, or Basis object
        The basis used to construct the Hamiltonian-type lindblad error
        Allowed values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt), list of numpy arrays, or a custom basis object.

    other_basis : {'std', 'gm', 'pp', 'qt'}, list of matrices, or Basis object
        The basis used to construct the Stochastic-type lindblad error
        Allowed values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt), list of numpy arrays, or a custom basis object.

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source basis. Allowed values are Matrix-unit (std),
        Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).

    normalize : bool, optional
      Whether or not the generators being projected onto are normalized, so
      that numpy.linalg.norm(generator.flat) == 1.0.  Note that the generators
      will still, in general, be non-orthogonal.

    return_generators : bool, optional
      If True, return the error generators projected against along with the
      projection values themseves.

    other_mode : {"diagonal", "diag_affine", "all"}
      Which non-Hamiltonian Lindblad error projections to obtain.
      Allowed values are: `"diagonal"` (only the diagonal Stochastic),
      `"diag_affine"` (diagonal + affine generators), and `"all"`
      (all generators).

    sparse : bool, optional
      Whether to create sparse or dense basis matrices when strings
      are given as `ham_basis` and `other_basis`

    Returns
    -------
    ham_projections : numpy.ndarray
      An array of length d-1, where d is the dimension of the gate,
      giving the projections onto the Hamiltonian-type Lindblad terms.

    other_projections : numpy.ndarray
      An array of shape (d-1,d-1), (2,d-1), or (d-1,), where d is the dimension
      of the gate, for `other_mode` equal to `"all"`, `"diag_affine"`, or
      `"diagonal"`, respectively.  Values give the projections onto the
      non-Hamiltonian-type Lindblad terms.

    ham_generators : numpy.ndarray
      The Hamiltonian-type Lindblad term generators, as would be returned
      from `lindblad_error_generators(pp_matrices(sqrt(d)), normalize)`.
      Shape is (d-1,d,d), and `ham_generators[i]` is in the standard basis.

    other_generators : numpy.ndarray
      The Stochastic-type Lindblad term generators, as would be returned
      from `lindblad_error_generators(pp_matrices(sqrt(d)), normalize)`.
      Shape is (d-1,d-1,d,d), (2,d-1,d,d), or (d-1,d,d) for `other_mode`
      equal to `"all"`, `"diag_affine"`, or `"diagonal"`, respectively,
      and `other_generators[i]` is in the std basis.

    """
    errgen_std = _bt.change_basis(errgen, mxBasis, "std")
    if _sps.issparse(errgen_std):
        errgen_std_flat = errgen_std.tolil().reshape(
            (errgen_std.shape[0] * errgen_std.shape[1], 1)).tocsr()  # b/c lil's are only type that can reshape...
    else:
        errgen_std_flat = errgen_std.flatten()
    errgen_std = None  # ununsed below, and sparse reshape doesn't copy, so mark as None

    d2 = errgen.shape[0]
    d = int(_np.sqrt(d2))
    #nQubits = _np.log2(d)

    #Get a list of the generators in corresspondence with the
    #  specified basis elements.
    if isinstance(ham_basis, _Basis):
        hamBasisMxs = ham_basis.elements
    elif _compat.isstr(ham_basis):
        hamBasisMxs = _basis_matrices(ham_basis, d2, sparse=sparse)
    else:
        hamBasisMxs = ham_basis

    if isinstance(other_basis, _Basis):
        otherBasisMxs = other_basis.elements
    elif _compat.isstr(other_basis):
        otherBasisMxs = _basis_matrices(other_basis, d2, sparse=sparse)
    else:
        otherBasisMxs = other_basis

    hamGens, otherGens = lindblad_error_generators(
        hamBasisMxs, otherBasisMxs, normalize, other_mode)  # in std basis

    if hamBasisMxs is not None:
        bsH = len(hamBasisMxs)  # basis size (not necessarily d2)
    else: bsH = 0

    if otherBasisMxs is not None:
        bsO = len(otherBasisMxs)  # basis size (not necessarily d2)
    else: bsO = 0

    if bsH > 0: sparse = _sps.issparse(hamBasisMxs[0])
    elif bsO > 0: sparse = _sps.issparse(otherBasisMxs[0])
    else: sparse = False  # default?

    assert(_np.isclose(d * d, d2))  # d2 must be a perfect square
    if bsH > 0:
        _assert_shape(hamGens, (bsH - 1, d2, d2), sparse)
    if bsO > 0:
        if other_mode == "diagonal":
            _assert_shape(otherGens, (bsO - 1, d2, d2), sparse)
        elif other_mode == "diag_affine":
            _assert_shape(otherGens, (2, bsO - 1, d2, d2), sparse)
        else:  # other_mode == "all"
            _assert_shape(otherGens, (bsO - 1, bsO - 1, d2, d2), sparse)

    #Perform linear least squares solve to find "projections" onto each otherGens element - defined so that
    #  sum_i projection_i * otherGen_i = (errgen_std-ham_errgen) as well as possible.

    #ham_error_gen = _np.einsum('i,ijk', hamProjs, hamGens)
    #other_errgen = errgen_std - ham_error_gen #what's left once hamiltonian errors are projected out

    #Do linear least squares soln to expressing errgen_std as a linear combo
    # of the lindblad generators
    if bsH > 0:
        if not sparse:
            H = hamGens.reshape((bsH - 1, d2**2)).T  # ham generators == columns
            Hdag = H.T.conjugate()

            #Do linear least squares: this is what takes the bulk of the time
            hamProjs = _np.linalg.solve(_np.dot(Hdag, H), _np.dot(Hdag, errgen_std_flat))
            hamProjs.shape = (hamGens.shape[0],)
        else:
            rows = [hamGen.tolil().reshape((1, d2**2)) for hamGen in hamGens]
            H = _sps.vstack(rows, 'csr').transpose()
            Hdag = H.copy().transpose().conjugate()

            #Do linear least squares: this is what takes the bulk of the time
            if _mt.safenorm(errgen_std_flat) < 1e-8:  # protect against singular RHS
                hamProjs = _np.zeros(bsH - 1, 'd')
            else:
                hamProjs = _spsl.spsolve(Hdag.dot(H), Hdag.dot(errgen_std_flat))
                if _sps.issparse(hamProjs): hamProjs = hamProjs.toarray().flatten()
            hamProjs.shape = (bsH - 1,)
    else:
        hamProjs = None

    if bsO > 0:
        if not sparse:
            if other_mode == "diagonal":
                O = otherGens.reshape((bsO - 1, d2**2)).T  # other generators == columns
            elif other_mode == "diag_affine":
                O = otherGens.reshape((2 * (bsO - 1), d2**2)).T  # other generators == columns
            else:
                O = otherGens.reshape(((bsO - 1)**2, d2**2)).T  # other generators == columns
            Odag = O.T.conjugate()

            #Do linear least squares: this is what takes the bulk of the time
            otherProjs = _np.linalg.solve(_np.dot(Odag, O), _np.dot(Odag, errgen_std_flat))

            if other_mode == "diagonal":
                otherProjs.shape = (otherGens.shape[0],)
            elif other_mode == "diag_affine":
                otherProjs.shape = (2, otherGens.shape[1])
            else:
                otherProjs.shape = (otherGens.shape[0], otherGens.shape[1])

        else:
            if other_mode == "diagonal":
                rows = [oGen.tolil().reshape((1, d2**2)) for oGen in otherGens]
                O = _sps.vstack(rows, 'csr').transpose()  # other generators == columns
            else:  # "diag_affine" or "all"
                rows = [oGen.tolil().reshape((1, d2**2)) for oGenRow in otherGens for oGen in oGenRow]
                O = _sps.vstack(rows, 'csr').transpose()  # other generators == columns
            Odag = O.copy().transpose().conjugate()  # TODO: maybe conjugate copies data?

            #Do linear least squares: this is what takes the bulk of the time
            if _mt.safenorm(errgen_std_flat) < 1e-8:  # protect against singular RHS
                if other_mode == "diagonal": otherProjs = _np.zeros(bsO - 1, 'd')
                elif other_mode == "diag_affine": otherProjs = _np.zeros((2, bsO - 1), 'd')
                else: otherProjs = _np.zeros((bsO - 1, bsO - 1), 'd')
            else:
                otherProjs = _spsl.spsolve(Odag.dot(O), Odag.dot(errgen_std_flat))
                if _sps.issparse(otherProjs): otherProjs = otherProjs.toarray().flatten()

            if other_mode == "diagonal":
                otherProjs.shape = (bsO - 1,)
            elif other_mode == "diag_affine":
                otherProjs.shape = (2, bsO - 1)
            else:  # other_mode == "all"
                otherProjs.shape = (bsO - 1, bsO - 1)
    else:
        otherProjs = None

    #check err gens are linearly independent -- but can take a very long time, so comment out!
    #assert(_np.linalg.matrix_rank(H,1e-7) == H.shape[1])
    #assert(_np.linalg.matrix_rank(O,1e-7) == O.shape[1])
    #if False: # further check against older (slower) version
    #    M = _np.concatenate( (hamGens.reshape((bs-1,d2**2)).T, otherGens.reshape(((bs-1)**2,d2**2)).T), axis=1)
    #    assert(_np.linalg.matrix_rank(M,1e-7) == M.shape[1]) #check err gens are linearly independent
    #    Mdag = M.T.conjugate()
    #    print("DB D: %.1f" % (time.time()-t)); t = time.time()
    #    projs = _np.linalg.solve(_np.dot(Mdag,M), _np.dot(Mdag,errgen_std_flat))
    #    hamProjs_chk = projs[0:(bs-1)]
    #    otherProjs_chk = projs[(bs-1):]
    #    assert(_np.linalg.norm(hamProjs-hamProjs_chk) < 1e-6)
    #    assert(_np.linalg.norm(otherProjs-otherProjs_chk) < 1e-6)

    if return_generators:
        return hamProjs, otherProjs, hamGens, otherGens
    else:
        return hamProjs, otherProjs


def projections_to_lindblad_terms(hamProjs, otherProjs, ham_basis, other_basis,
                                  other_mode="all"):
    """
    Converts the projections of an error generator onto basis elements into
    the Lindblad-term and basis dictionaries used to individually specify
    Lindblad terms.

    Parameters
    ----------
    hamProjs : numpy.ndarray
        An array of length d-1, where d is the dimension of the projected error
        generator, giving the projections onto the Hamiltonian-type Lindblad
        terms.

    otherProjs : numpy.ndarray
        An array of shape (d-1,d-1), (2,d-1), or (d-1,), where d is the dimension
        of the projected error generator, for `other_mode` equal to `"all"`,
        `"diag_affine"`, or `"diagonal"`, respectively.  Values give the
        projections onto the non-Hamiltonian-type Lindblad terms.

    ham_basis: {'std', 'gm', 'pp', 'qt'}, list of matrices, or Basis object
        The basis used to construct `hamProjs`.  Allowed values are Matrix-unit
        (std), Gell-Mann (gm), Pauli-product (pp), and Qutrit (qt), list of
        numpy arrays, or a custom basis object.

    other_basis : {'std', 'gm', 'pp', 'qt'}, list of matrices, or Basis object
        The basis used to construct `otherProjs`.  Allowed values are
        Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp), and Qutrit (qt),
        list of numpy arrays, or a custom basis object.

    other_mode : {"diagonal", "diag_affine", "all"}
      Which non-Hamiltonian Lindblad error projections `otherProjs` includes.
      Allowed values are: `"diagonal"` (only the diagonal Stochastic),
      `"diag_affine"` (diagonal + affine generators), and `"all"`
      (all generators).


    Returns
    -------
    Ltermdict : dict
        Keys are `(termType, basisLabel1, <basisLabel2>)`
        tuples, where `termType` is `"H"` (Hamiltonian), `"S"` (Stochastic), or
        `"A"` (Affine).  Hamiltonian and Affine terms always have a single basis
        label (so key is a 2-tuple) whereas Stochastic tuples have 1 basis label
        to indicate a *diagonal* term and otherwise have 2 basis labels to
        specify off-diagonal non-Hamiltonian Lindblad terms.  Basis labels
        are integers starting at 0.  Values are complex coefficients (the
        projections).

    basisdict : dict
        A dictionary mapping the integer basis labels used in the
        keys of `Ltermdict` to basis matrices (elements of `ham_basis` and
        `other_basis`).
    """

    # Make None => length-0 arrays so iteration code works below (when basis is None)
    if hamProjs is None: hamProjs = _np.empty(0, 'd')
    if otherProjs is None:
        otherProjs = _np.empty(0, 'd') if other_mode == "diagonal" \
            else _np.empty((0, 0), 'd')

    # Construct a pair of dictionaries describing all of the
    # Lindblad-terms:
    #   Ltermdict keys= ('H',basisLbl), ('S',basisLbl), or ('S',bLbl1,bLbl2)
    #             vals= coefficients of these terms (projections from errgen)
    #   basisdict keys= basis labels (just has to match Ltermdict keys)
    #             vals= basis matrices - can be either sparse or dense
    Ltermdict = _collections.OrderedDict()
    basisdict = _collections.OrderedDict()
    nextLbl = 0

    def get_basislbl(bmx, nxt_blbl):
        """ Retrieves or creates a basis-element "label" (just an integer) from `basisdict` """
        for l, b in basisdict.items():
            if _mt.safenorm(b - bmx) < 1e-8: return l, nxt_blbl
        basisdict[nxt_blbl] = bmx
        nxt_blbl += 1
        return nxt_blbl - 1, nxt_blbl  # <assigned basis lbl>, <new next-basis-label>

    #Add Hamiltonian error elements
    ham_mxs = ham_basis.elements  # can be sparse
    assert(len(ham_mxs[1:]) == len(hamProjs))
    for coeff, bmx in zip(hamProjs, ham_mxs[1:]):  # skip identity
        Ltermdict[('H', nextLbl)] = coeff
        basisdict[nextLbl] = bmx  # no need to call get_basislbl yet
        nextLbl += 1

    #Add "other" error elements
    other_mxs = other_basis.elements  # can be sparse
    if other_mode == "diagonal":
        assert(len(other_mxs[1:]) == len(otherProjs))
        for coeff, bmx in zip(otherProjs, other_mxs[1:]):  # skip identity
            blbl, nextLbl = get_basislbl(bmx, nextLbl)
            Ltermdict[('S', blbl)] = coeff

    elif other_mode == "diag_affine":
        assert((2, len(other_mxs[1:])) == otherProjs.shape)
        for coeff, bmx in zip(otherProjs[0], other_mxs[1:]):  # skip identity
            blbl, nextLbl = get_basislbl(bmx, nextLbl)
            Ltermdict[('S', blbl)] = coeff
        for coeff, bmx in zip(otherProjs[1], other_mxs[1:]):  # skip identity
            blbl, nextLbl = get_basislbl(bmx, nextLbl)
            Ltermdict[('A', blbl)] = coeff

    else:
        assert((len(other_mxs[1:]), len(other_mxs[1:])) == otherProjs.shape)
        for i, bmx1 in enumerate(other_mxs[1:]):  # skip identity
            blbl1, nextLbl = get_basislbl(bmx1, nextLbl)
            for j, bmx2 in enumerate(other_mxs[1:]):  # skip identity
                blbl2, nextLbl = get_basislbl(bmx2, nextLbl)
                Ltermdict[('S', blbl1, blbl2)] = otherProjs[i, j]

    #DEBUG: print("DB: Ltermdict = ",Ltermdict)
    #DEBUG: print("DB: basisdict = ")
    #DEBUG: for k,v in basisdict.items():
    #DEBUG:     print(k,":")
    #DEBUG:     print(v)
    return Ltermdict, basisdict


def lindblad_terms_to_projections(Ltermdict, basisdict, basisdim, other_mode="all"):
    """
    Convert a set of Lindblad terms into a dense matrix/grid of projections.

    Essentially the inverse of :function:`projections_to_lindblad_terms`.

    Parameters
    ----------
    Ltermdict : dict
        A dictionary specifying which Linblad terms are present in the gate
        parameteriztion.  Keys are `(termType, basisLabel1, <basisLabel2>)`
        tuples, where `termType` is `"H"` (Hamiltonian), `"S"` (Stochastic), or
        `"A"` (Affine).  Hamiltonian and Affine terms always have a single basis
        label (so key is a 2-tuple) whereas Stochastic tuples with 1 basis label
        indicate a *diagonal* term, and are the only types of terms allowed when
        `nonham_mode != "all"`.  Otherwise, Stochastic term tuples can include 2
        basis labels to specify "off-diagonal" non-Hamiltonian Lindblad terms.
        Basis labels can be strings or integers.  Values are complex
        coefficients (error rates).

    basisdict : dict
        A dictionary mapping the basis labels (strings or ints) used in the
        keys of `Ltermdict` to basis matrices (numpy arrays or Scipy sparse
        matrices).

    basisdim : int
        The dimension of the basis elements (4 for single-qubit).  Required
        for the case when `basisdict` is empty.

    other_mode : {"diagonal", "diag_affine", "all"}
      Which non-Hamiltonian terms are allowed in `Ltermdict`.
      Allowed values are: `"diagonal"` (only the diagonal Stochastic),
      `"diag_affine"` (diagonal + affine generators), and `"all"`
      (all generators).

    Returns
    -------
    hamProjs : numpy.ndarray
        An array of length `basisdim-1`, giving the projections onto a
        full set of the Hamiltonian-type Lindblad terms (onto each element of
        `ham_basis`).

    otherProjs : numpy.ndarray
        An array of shape (d-1,d-1), (2,d-1), or (d-1,), where d=`basisdim`
        for `other_mode` equal to `"all"`, `"diag_affine"`, or `"diagonal"`,
        respectively.  Values give the projections onto the non-Hamiltonian
        -type Lindblad terms.

    ham_basis: Basis
        The basis used to construct `hamProjs`.

    other_basis : Basis
        The basis used to construct `otherProjs`.

    hamBasisIndices : OrderedDict
        A dictionary mapping the some or all of the basis labels of `basisdict`
        to the integers 0 to `len(ham_basis)`.  These are indices into
        `hamProjs`, giving the projection associated with each Hamiltonian
        basis element.

    otherBasisIndices : OrderedDict
        A dictionary mapping the some or all of the basis labels of `basisdict`
        to the integers 0 to `len(other_basis)`.  These are row and column
        indices into `otherProjs`, giving the projection associated with each
        pair of "other" basis elements (or single basis element if
        `other_mode!="all"`).
    """

    d2 = basisdim

    #Separately enumerate the (distinct) basis elements used for Hamiltonian
    # and Stochasitic error terms
    hamBasisIndices = _collections.OrderedDict()  # holds index of each basis element
    otherBasisIndices = _collections.OrderedDict()  # in coefficient/projection arrays
    for termLbl, coeff in Ltermdict.items():
        termType = termLbl[0]
        if termType == "H":  # Hamiltonian
            assert(len(termLbl) == 2), "Hamiltonian term labels should have form ('H',<basis element label>)"
            if termLbl[1] not in hamBasisIndices:
                hamBasisIndices[termLbl[1]] = len(hamBasisIndices)

        elif termType == "S":  # Stochastic
            if other_mode in ("diagonal", "diag_affine"):
                assert(len(termLbl) == 2), "Stochastic term labels should have form ('S',<basis element label>)"
                if termLbl[1] not in otherBasisIndices:
                    otherBasisIndices[termLbl[1]] = len(otherBasisIndices)
            else:
                assert(len(termLbl) == 3), "Stochastic term labels should have form ('S',<bel1>, <bel2>)"
                if termLbl[1] not in otherBasisIndices:
                    otherBasisIndices[termLbl[1]] = len(otherBasisIndices)
                if termLbl[2] not in otherBasisIndices:
                    otherBasisIndices[termLbl[2]] = len(otherBasisIndices)

        elif termType == "A":  # Affine
            assert(other_mode == "diag_affine"), "Affine labels are only allowed in an affine mode"
            assert(len(termLbl) == 2), "Affine term labels should have form ('A',<basis element label>)"
            if termLbl[1] not in otherBasisIndices:
                otherBasisIndices[termLbl[1]] = len(otherBasisIndices)

    #Construct bases
    ham_basis_mxs = [basisdict[bl] for bl in hamBasisIndices]  # requires OrderedDict
    other_basis_mxs = [basisdict[bl] for bl in otherBasisIndices]  # requires OrderedDict

    if len(ham_basis_mxs) > 0: sparse = _sps.issparse(ham_basis_mxs[0])
    elif len(other_basis_mxs) > 0: sparse = _sps.issparse(other_basis_mxs[0])
    else: sparse = False

    # Note: these lists of basis matrices shouldn't contain the identity, since
    # the terms above shouldn't contain identity terms - so add identity els
    # to non-empty bases (empty bases stay empty!) to be consistent with the
    # rest of the framework (bases *have* Ids)
    # TODO: could assert this?
    d = int(round(_np.sqrt(d2)))
    assert(d * d == d2), "Dimension must be a perfect square"
    Id = _sps.identity(d, 'complex', 'csr') / _np.sqrt(d) if sparse \
        else _np.identity(d, 'complex') / _np.sqrt(d)
    if len(ham_basis_mxs) > 0: ham_basis_mxs = [Id] + ham_basis_mxs
    if len(other_basis_mxs) > 0: other_basis_mxs = [Id] + other_basis_mxs

    #Special check: update basis name to "pp" if we have a Pauli Basis
    # (for small d when this isn't too expensive)
    if d in (2, 4, 8, 16) and all([_mt.safenorm(b0 - b1) < 1e-8 for b0, b1 in
                                   zip(_basis_matrices("pp", d2, sparse), ham_basis_mxs)]):
        ham_name = "pp"
    else: ham_name = None

    if d in (2, 4, 8, 16) and all([_mt.safenorm(b0 - b1) < 1e-8 for b0, b1 in
                                   zip(_basis_matrices("pp", d2, sparse), other_basis_mxs)]):
        other_name = "pp"
    else: other_name = None

    ham_basis = _ExplicitBasis(ham_basis_mxs, name=ham_name, real=True, sparse=sparse)
    other_basis = _ExplicitBasis(other_basis_mxs, name=other_name, real=True, sparse=sparse)
    bsH, bsO = len(ham_basis), len(other_basis)

    #Create projection (term coefficient) arrays - or return None if
    # the corresponding basis is empty (as per our convention)
    hamProjs = _np.zeros(bsH - 1, 'complex') if bsH > 0 else None
    if bsO > 0:
        if other_mode == "diagonal":  # OK if this runs for 'auto' too since then len(otherBasisIndices) == 0
            otherProjs = _np.zeros(bsO - 1, 'complex')
        elif other_mode == "diag_affine":
            otherProjs = _np.zeros((2, bsO - 1), 'complex')
        else:
            otherProjs = _np.zeros((bsO - 1, bsO - 1), 'complex')
    else: otherProjs = None

    #Fill arrays
    for termLbl, coeff in Ltermdict.items():
        termType = termLbl[0]
        if termType == "H":  # Hamiltonian
            k = hamBasisIndices[termLbl[1]]  # index of coefficient in array
            hamProjs[k] = coeff
        elif termType == "S":  # Stochastic
            if other_mode == "diagonal":
                k = otherBasisIndices[termLbl[1]]  # index of coefficient in array
                otherProjs[k] = coeff
            elif other_mode == "diag_affine":
                k = otherBasisIndices[termLbl[1]]  # index of coefficient in array
                otherProjs[0, k] = coeff
            else:  # other_mode == "all"
                k = otherBasisIndices[termLbl[1]]  # index of row in "other" coefficient matrix
                j = otherBasisIndices[termLbl[2]]  # index of col in "other" coefficient matrix
                otherProjs[k, j] = coeff
        elif termType == "A":  # Affine
            assert(other_mode == "diag_affine")
            k = otherBasisIndices[termLbl[1]]  # index of coefficient in array
            otherProjs[1, k] = coeff

    return hamProjs, otherProjs, ham_basis, other_basis, hamBasisIndices, otherBasisIndices


def lindblad_projections_to_paramvals(hamProjs, otherProjs, param_mode="cptp",
                                      other_mode="all", truncate=True):
    """
    Construct the array of Lindblad-gate parameter values from the separate
    arrays of Hamiltonian and non-Hamiltonian Lindblad-term projections.

    When `cptp=True`, this function handles parameterizing the projections
    to that for (real) parameter values correspond to projections for a valid
    CPTP gate (e.g. by parameterizing the Cholesky decomposition of `otherProjs`
    instead of otherProjs itself).  This function is closely related to
    implementation details of the LindbladOp class.

    Parameters
    ----------
    hamProjs : numpy.ndarray
        An array of length d-1, where d is the gate dimension, giving the
        projections onto a full set of the Hamiltonian-type Lindblad terms.

    otherProjs : numpy.ndarray
        An array of shape (d-1,d-1), (2,d-1), or (d-1,), where d is the gate
        dimension, for `other_mode` equal to `"all"`,`"diag_affine"`, or
        `"diagonal"`, respectively.  Values give the projections onto a full
        set of non-Hamiltonian-type Lindblad terms.

    param_mode : {"unconstrained", "cptp", "depol", "reldepol"}
        Describes how values in `hamProjs` and `otherProj` relate to the
        returned parameter values.  Allowed values are:
        `"unconstrained"` (projs are independent unconstrained parameters),
        `"cptp"` (independent parameters but constrained so map is CPTP),
        `"reldepol"` (all non-Ham. diagonal projs take the *same* value),
        `"depol"` (same as `"reldepol"` but projs must be *positive*)

    other_mode : {"diagonal", "diag_affine", "all"}
        Which non-Hamiltonian Lindblad error projections `otherProjs` includes.
        Allowed values are: `"diagonal"` (only the diagonal Stochastic),
        `"diag_affine"` (diagonal + affine generators), and `"all"`.

    truncate : bool, optional
        Whether to truncate the projections onto the Lindblad terms in
        order to meet constraints (e.g. to preserve CPTP) when necessary.
        If False, then an error is thrown when the given projections
        cannot be parameterized as specified.

    Returns
    -------
    numpy.ndarray
        A 1D array of real parameter values consisting of d-1 Hamiltonian
        values followed by either (d-1)^2, 2*(d-1), or just d-1 non-Hamiltonian
        values for `other_mode` equal to `"all"`, `"diag_affine"`, or
        `"diagonal"`, respectively.
    """
    if hamProjs is not None:
        assert(_np.isclose(_np.linalg.norm(hamProjs.imag), 0)), \
            "Hamiltoian projections (coefficients) are not all real!"
        hamParams = hamProjs.real
    else:
        hamParams = _np.empty(0, 'd')

    if otherProjs is not None:
        if other_mode == "diagonal":
            assert(_np.isclose(_np.linalg.norm(_np.imag(otherProjs)), 0)), \
                "Diagonal stochastic projections (coefficients) are not all real!"

            if param_mode == "depol":  # otherParams is a *single-element* 1D vector of the sqrt of each diagonal el
                assert(truncate or all([v >= -1e-12 for v in otherProjs])), \
                    "Lindblad coefficients are not CPTP (truncate == False)!"
                assert(truncate or all([_np.isclose(v, otherProjs[0]) for v in otherProjs])), \
                    "Diagonal lindblad coefficients are not equal (truncate == False)!"
                otherProj = _np.mean(otherProjs.clip(1e-16, 1e100))
                otherParams = _np.array(_np.sqrt(_np.real(otherProj)), 'd')  # shape (1,)

            elif param_mode == "cptp":  # otherParams is a 1D vector of the sqrts of diagonal els
                assert(truncate or all([v >= -1e-12 for v in otherProjs])), \
                    "Lindblad coefficients are not CPTP (truncate == False)!"
                otherProjs = otherProjs.clip(1e-16, 1e100)
                otherParams = _np.sqrt(otherProjs.real)  # shape (bsO-1,)
            else:  # "unconstrained": otherParams is a 1D vector of the real diagonal els of otherProjs
                otherParams = otherProjs.real  # shape (bsO-1,)

        elif other_mode == "diag_affine":
            assert(_np.isclose(_np.linalg.norm(_np.imag(otherProjs)), 0)), \
                "Diagonal stochastic and affine projections (coefficients) are not all real!"

            if param_mode == "depol":  # otherParams is a single depol value + unconstrained affine coeffs
                assert(truncate or all([v >= -1e-12 for v in otherProjs[0]])), \
                    "Lindblad coefficients are not CPTP (truncate == False)!"
                assert(truncate or all([_np.isclose(v, otherProjs[0, 0]) for v in otherProjs[0]])), \
                    "Diagonal lindblad coefficients are not equal (truncate == False)!"
                depolProj = _np.mean(otherProjs[0, :].clip(1e-16, 1e100))
                otherParams = _np.concatenate(([_np.sqrt(_np.real(depolProj))],
                                               otherProjs[1].real))  # shape (1+(bsO-1),)

            elif param_mode == "cptp":  # Note: does not constrained affine coeffs to CPTP
                assert(truncate or all([v >= -1e-12 for v in otherProjs[0]])), \
                    "Lindblad coefficients are not CPTP (truncate == False)!"
                diagParams = _np.sqrt(_np.real(otherProjs[0, :]).clip(1e-16, 1e100))  # shape (bsO-1,)
                otherParams = _np.concatenate((diagParams, otherProjs[1].real))  # diag + affine params

            else:  # param_mode == "unconstrained": otherParams is a 1D vector of the real diagonal els of otherProjs
                otherParams = otherProjs.real  # shape (2,bsO-1)

        else:  # other_mode == "all"
            assert(_np.isclose(_np.linalg.norm(otherProjs - otherProjs.T.conjugate()), 0)
                   ), "Other projection/coefficient mx is not Hermitian!"
            assert(param_mode != "depol"), "`depol` is not supported when `other_mode == 'all'`"

            bsO = otherProjs.shape[0] + 1  # +1 to keep convention that this is the basis (w/Identity) size
            otherParams = _np.empty((bsO - 1, bsO - 1), 'd')

            if param_mode == "cptp":  # otherParams mx stores Cholesky decomp

                #push any slightly negative evals of otherProjs positive so that
                # the Cholesky decomp will work.
                evals, U = _np.linalg.eig(otherProjs)
                Ui = _np.linalg.inv(U)

                assert(truncate or all([ev >= -1e-12 for ev in evals])), \
                    "Lindblad coefficients are not CPTP (truncate == False)!"

                pos_evals = evals.clip(1e-16, 1e100)
                otherProjs = _np.dot(U, _np.dot(_np.diag(pos_evals), Ui))
                try:
                    Lmx = _np.linalg.cholesky(otherProjs)

                # if Lmx not postitive definite, try again with 1e-12 (same lines as above)
                except _np.linalg.LinAlgError:                         # pragma: no cover
                    pos_evals = evals.clip(1e-12, 1e100)                # pragma: no cover
                    otherProjs = _np.dot(U, _np.dot(_np.diag(pos_evals), Ui))  # pragma: no cover
                    Lmx = _np.linalg.cholesky(otherProjs)                  # pragma: no cover

                for i in range(bsO - 1):
                    assert(_np.linalg.norm(_np.imag(Lmx[i, i])) < IMAG_TOL)
                    otherParams[i, i] = Lmx[i, i].real
                    for j in range(i):
                        otherParams[i, j] = Lmx[i, j].real
                        otherParams[j, i] = Lmx[i, j].imag

            else:  # param_mode == "unconstrained": otherParams mx stores otherProjs (hermitian) directly
                for i in range(bsO - 1):
                    assert(_np.linalg.norm(_np.imag(otherProjs[i, i])) < IMAG_TOL)
                    otherParams[i, i] = otherProjs[i, i].real
                    for j in range(i):
                        otherParams[i, j] = otherProjs[i, j].real
                        otherParams[j, i] = otherProjs[i, j].imag
    else:
        otherParams = _np.empty(0, 'd')

    assert(not _np.iscomplexobj(hamParams))   # params should always
    assert(not _np.iscomplexobj(otherParams))  # be *real*
    return _np.concatenate((hamParams, otherParams.flat))


def paramvals_to_lindblad_projections(paramvals, ham_basis_size,
                                      other_basis_size, param_mode="cptp",
                                      other_mode="all", Lmx=None):
    """
    Construct the separate arrays of Hamiltonian and non-Hamiltonian
    Lindblad-term projections from the array of Lindblad-gate parameter values.

    This function essentially performs the inverse of
    :function:`lindblad_projections_to_paramvals`.

    Parameters
    ----------
    paramvals : numpy.ndarray
        A 1D array of real parameter values consisting of d-1 Hamiltonian
        values followed by either (d-1)^2 or just d-1 non-Hamiltonian
        values (the latter when `other_mode in ('diagonal','diag_affine')`).

    ham_basis_size, other_basis_size : int
        The number of elements in the Hamiltonian and non-Hamiltonian
        bases used to construct `paramvals`.  As such, `ham_basis_size`
        gives the offset into `paramvals` where the non-Hamiltonian
        parameters begin.

    param_mode : {"unconstrained", "cptp", "depol", "reldepol"}
        Specifies how the Lindblad-term coefficients are mapped to the set of
        (real) parameter values.  This really just applies to the "other"
        (non-Hamiltonian) coefficients.  "unconstrained" means that ranging
        over the parameter values lets the coefficient-matrix vary over all
        matrices, "cptp" restricts this to postitive matrices. "depol"
        maps all of the coefficients to the *same, positive* parameter (only
        available for "diagonal" and "diag_affine" other-modes), and "reldepol"
        does the same thing but without the positivity constraint.

    other_mode : {"all", "diagonal", "diag_affine"}
        Specifies the structure of the matrix of other (non-Hamiltonian)
        coefficients.  If d is the gate dimension, "all" means a (d-1,d-1)
        matrix is used; "diagonal" means just the (d2-1,) diagonal of this
        matrix is used; "diag_affine" means the coefficients are in a (2,d2-1)
        array with the diagonal-term coefficients being the first row and the
        affine coefficients being the second row.

    Lmx : ndarray, optional
        Scratch space that is used to store the lower-triangular
        Cholesky decomposition matrix that is used to construct
        the "other" projections when there is a CPTP constraint.

    Returns
    -------
    hamProjs : numpy.ndarray
        An array of length d-1, where d is the gate dimension, giving the
        projections onto a full set of the Hamiltonian-type Lindblad terms.

    otherProjs : numpy.ndarray
        An array of shape (d-1,d-1) or (d-1,) or (2,d-1) where d is the gate
        dimension, giving the projections onto a full set of non-Hamiltonian
        -type Lindblad terms (see `other_mode` above).
    """
    bsH = ham_basis_size
    bsO = other_basis_size

    if Lmx is None:
        Lmx = _np.zeros((bsO - 1, bsO - 1), 'complex') if bsO > 0 else None

    # self.paramvals = [hamCoeffs] + [otherParams]
    #  where hamCoeffs are *real* and of length d2-1 (self.dim == d2)
    if bsH > 0:
        hamCoeffs = paramvals[0:bsH - 1]
        nHam = bsH - 1
    else:
        hamCoeffs = None
        nHam = 0

    #built up otherCoeffs based on param_mode and nonham_mode
    if bsO > 0:
        if other_mode == "diagonal":
            otherParams = paramvals[nHam:]
            expected_shape = (1,) if (param_mode in ("depol", "reldepol")) else (bsO - 1,)
            assert(otherParams.shape == expected_shape)

            if param_mode in ("cptp", "depol"):
                otherCoeffs = otherParams**2  # Analagous to L*L_dagger
            else:  # "unconstrained"
                otherCoeffs = otherParams

        elif other_mode == "diag_affine":

            if param_mode in ("depol", "reldepol"):
                otherParams = paramvals[nHam:].reshape((1 + bsO - 1,))
                otherCoeffs = _np.empty((2, bsO - 1), 'd')  # leave as real type b/c doesn't have complex entries
                if param_mode == "depol":
                    otherCoeffs[0, :] = otherParams[0]**2
                else:
                    otherCoeffs[0, :] = otherParams[0]
                otherCoeffs[1, :] = otherParams[1:]

            else:
                otherParams = paramvals[nHam:].reshape((2, bsO - 1))
                if param_mode == "cptp":
                    otherCoeffs = otherParams.copy()
                    otherCoeffs[0, :] = otherParams[0]**2
                else:  # param_mode == "unconstrained"
                    #otherCoeffs = _np.empty((2,bsO-1),'complex')
                    otherCoeffs = otherParams

        else:  # other_mode == "all"
            otherParams = paramvals[nHam:].reshape((bsO - 1, bsO - 1))

            if param_mode == "cptp":
                #  otherParams is an array of length (bs-1)*(bs-1) that
                #  encodes a lower-triangular matrix "Lmx" via:
                #  Lmx[i,i] = otherParams[i,i]
                #  Lmx[i,j] = otherParams[i,j] + 1j*otherParams[j,i] (i > j)
                for i in range(bsO - 1):
                    Lmx[i, i] = otherParams[i, i]
                    for j in range(i):
                        Lmx[i, j] = otherParams[i, j] + 1j * otherParams[j, i]

                #The matrix of (complex) "other"-coefficients is build by
                # assuming Lmx is its Cholesky decomp; means otherCoeffs
                # is pos-def.

                # NOTE that the Cholesky decomp with all positive real diagonal
                # elements is *unique* for a given positive-definite otherCoeffs
                # matrix, but we don't care about this uniqueness criteria and so
                # the diagonal els of Lmx can be negative and that's fine -
                # otherCoeffs will still be posdef.
                otherCoeffs = _np.dot(Lmx, Lmx.T.conjugate())

                #DEBUG - test for pos-def
                #evals = _np.linalg.eigvalsh(otherCoeffs)
                #DEBUG_TOL = 1e-16; #print("EVALS DEBUG = ",evals)
                #assert(all([ev >= -DEBUG_TOL for ev in evals]))

            else:  # param_mode == "unconstrained"
                #otherParams holds otherCoeff real and imaginary parts directly
                otherCoeffs = _np.empty((bsO - 1, bsO - 1), 'complex')
                for i in range(bsO - 1):
                    otherCoeffs[i, i] = otherParams[i, i]
                    for j in range(i):
                        otherCoeffs[i, j] = otherParams[i, j] + 1j * otherParams[j, i]
                        otherCoeffs[j, i] = otherParams[i, j] - 1j * otherParams[j, i]
    else:
        otherCoeffs = None

    return hamCoeffs, otherCoeffs


#TODO: replace two_qubit_gate, one_qubit_gate, unitary_to_pauligate_* with
# calls to this one and unitary_to_processmx
def rotation_gate_mx(r, mxBasis="gm"):
    """
    Construct a rotation operation matrix.

    Build the operation matrix corresponding to the unitary
    `exp(-i * (r[0]/2*PP[0]*sqrt(d) + r[1]/2*PP[1]*sqrt(d) + ...) )`
    where `PP' is the array of Pauli-product matrices
    obtained via `pp_matrices(d)`, where `d = sqrt(len(r)+1)`.
    The division by 2 is for convention, and the sqrt(d) is to
    essentially un-normalise the matrices returned by `pp_matrices`
    to they are equal to products of the *standard* Pauli matrices.

    Parameters
    ----------
    r : tuple
        A tuple of coeffiecients, one per non-identity
        Pauli-product basis element

    mxBasis : {'std', 'gm', 'pp', 'qt'} or Basis object
        The source and destination basis, respectively.  Allowed
        values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp),
        and Qutrit (qt) (or a custom basis object).
.
    Returns
    -------
    numpy array
        a d^2 x d^2 operation matrix in the specified basis.
    """
    d = int(round(_np.sqrt(len(r) + 1)))
    assert(d**2 == len(r) + 1), "Invalid number of rotation angles"

    #get Pauli-product matrices (in std basis)
    pp = _basis_matrices('pp', d**2)
    assert(len(r) == len(pp[1:]))

    #build unitary (in std basis)
    ex = _np.zeros((d, d), 'complex')
    for rot, pp_mx in zip(r, pp[1:]):
        ex += rot / 2.0 * pp_mx * _np.sqrt(d)
    U = _spl.expm(-1j * ex)
    stdGate = unitary_to_process_mx(U)

    ret = _bt.change_basis(stdGate, 'std', mxBasis)

    return ret


def project_model(model, targetModel,
                  projectiontypes=('H', 'S', 'H+S', 'LND'),
                  genType="logG-logT"):
    """
    Construct one or more new models by projecting the error generator of
    `model` onto some sub-space then reconstructing.

    Parameters
    ----------
    model : Model
        The model whose error generator should be projected.

    targetModel : Model
        The set of target (ideal) gates.

    projectiontypes : tuple of {'H','S','H+S','LND','LNDCP'}
        Which projections to use.  The length of this tuple gives the
        number of `Model` objects returned.  Allowed values are:

        - 'H' = Hamiltonian errors
        - 'S' = Stochastic Pauli-channel errors
        - 'H+S' = both of the above error types
        - 'LND' = errgen projected to a normal (CPTP) Lindbladian
        - 'LNDF' = errgen projected to an unrestricted (full) Lindbladian

    genType : {"logG-logT", "logTiG"}
      The type of error generator to compute.  Allowed values are:

      - "logG-logT" : errgen = log(gate) - log(target_op)
      - "logTiG" : errgen = log( dot(inv(target_op), gate) )

    Returns
    -------
    projected_models : list of Models
       Elements are projected versions of `model` corresponding to
       the elements of `projectiontypes`.

    Nps : list of parameter counts
       Integer parameter counts for each model in `projected_models`.
       Useful for computing the expected log-likelihood or chi2.
    """

    opLabels = list(model.operations.keys())  # operation labels
    basis = model.basis

    #The projection basis needs to be a basis for density matrices
    # (i.e. 2x2 mxs in 1Q case) rather than superoperators (4x4 mxs
    # in 1Q case) - whcih is what model.basis is.  So, we just extract
    # a builtin basis name for the projection basis.
    if basis.name in ('pp', 'gm', 'std', 'qt'):
        proj_basis_name = basis.name
    else:
        proj_basis_name = 'pp'  # model.basis is weird so just use paulis as projection basis

    if basis.name != targetModel.basis.name:
        raise ValueError("Basis mismatch between model (%s) and target (%s)!"
                         % (model.basis.name, targetModel.basis.name))

    # Note: set to "full" parameterization so we can set the gates below
    #  regardless of what parameterization the original model had.
    gsDict = {}; NpDict = {}
    for p in projectiontypes:
        gsDict[p] = model.copy()
        gsDict[p].set_all_parameterizations("full")
        NpDict[p] = 0

    errgens = [error_generator(model.operations[gl],
                               targetModel.operations[gl],
                               targetModel.basis, genType)
               for gl in opLabels]

    for gl, errgen in zip(opLabels, errgens):
        if ('H' in projectiontypes) or ('H+S' in projectiontypes):
            hamProj, hamGens = std_errgen_projections(
                errgen, "hamiltonian", proj_basis_name, basis, True)
            #ham_error_gen = _np.einsum('i,ijk', hamProj, hamGens)
            ham_error_gen = _np.tensordot(hamProj, hamGens, (0, 0))
            ham_error_gen = _bt.change_basis(ham_error_gen, "std", basis)

        if ('S' in projectiontypes) or ('H+S' in projectiontypes):
            stoProj, stoGens = std_errgen_projections(
                errgen, "stochastic", proj_basis_name, basis, True)
            #sto_error_gen = _np.einsum('i,ijk', stoProj, stoGens)
            sto_error_gen = _np.tensordot(stoProj, stoGens, (0, 0))
            sto_error_gen = _bt.change_basis(sto_error_gen, "std", basis)

        if ('LND' in projectiontypes) or ('LNDF' in projectiontypes):
            HProj, OProj, HGens, OGens = \
                lindblad_errgen_projections(
                    errgen, proj_basis_name, proj_basis_name, basis, normalize=False,
                    return_generators=True)
            #Note: return values *can* be None if an empty/None basis is given
            #lnd_error_gen = _np.einsum('i,ijk', HProj, HGens) + \
            #                _np.einsum('ij,ijkl', OProj, OGens)
            lnd_error_gen = _np.tensordot(HProj, HGens, (0, 0)) + \
                _np.tensordot(OProj, OGens, ((0, 1), (0, 1)))
            lnd_error_gen = _bt.change_basis(lnd_error_gen, "std", basis)

        targetOp = targetModel.operations[gl]

        if 'H' in projectiontypes:
            gsDict['H'].operations[gl] = operation_from_error_generator(
                ham_error_gen, targetOp, genType)
            NpDict['H'] += len(hamProj)

        if 'S' in projectiontypes:
            gsDict['S'].operations[gl] = operation_from_error_generator(
                sto_error_gen, targetOp, genType)
            NpDict['S'] += len(stoProj)

        if 'H+S' in projectiontypes:
            gsDict['H+S'].operations[gl] = operation_from_error_generator(
                ham_error_gen + sto_error_gen, targetOp, genType)
            NpDict['H+S'] += len(hamProj) + len(stoProj)

        if 'LNDF' in projectiontypes:
            gsDict['LNDF'].operations[gl] = operation_from_error_generator(
                lnd_error_gen, targetOp, genType)
            NpDict['LNDF'] += HProj.size + OProj.size

        if 'LND' in projectiontypes:
            evals, U = _np.linalg.eig(OProj)
            pos_evals = evals.clip(0, 1e100)  # clip negative eigenvalues to 0
            OProj_cp = _np.dot(U, _np.dot(_np.diag(pos_evals), _np.linalg.inv(U)))
            #OProj_cp is now a pos-def matrix
            #lnd_error_gen_cp = _np.einsum('i,ijk', HProj, HGens) + \
            #                   _np.einsum('ij,ijkl', OProj_cp, OGens)
            lnd_error_gen_cp = _np.tensordot(HProj, HGens, (0, 0)) + \
                _np.tensordot(OProj_cp, OGens, ((0, 1), (0, 1)))
            lnd_error_gen_cp = _bt.change_basis(lnd_error_gen_cp, "std", basis)

            gsDict['LND'].operations[gl] = operation_from_error_generator(
                lnd_error_gen_cp, targetOp, genType)
            NpDict['LND'] += HProj.size + OProj.size

        #Removed attempt to contract H+S to CPTP by removing positive stochastic projections,
        # but this doesn't always return the gate to being CPTP (maybe b/c of normalization)...
        #sto_error_gen_cp = _np.einsum('i,ijk', stoProj.clip(None,0), stoGens)
        #  # (only negative stochastic projections OK)
        #sto_error_gen_cp = _tools.std_to_pp(sto_error_gen_cp)
        #gsHSCP.operations[gl] = _tools.operation_from_error_generator(
        #    ham_error_gen, targetOp, genType) #+sto_error_gen_cp

    #DEBUG!!!
    #print("DEBUG: BEST sum neg evals = ",_tools.sum_of_negative_choi_evals(model))
    #print("DEBUG: LNDCP sum neg evals = ",_tools.sum_of_negative_choi_evals(gsDict['LND']))

    #Check for CPTP where expected
    #assert(_tools.sum_of_negative_choi_evals(gsHSCP) < 1e-6)
    #assert(_tools.sum_of_negative_choi_evals(gsDict['LND']) < 1e-6)

    #Collect and return requrested results:
    ret_gs = [gsDict[p] for p in projectiontypes]
    ret_Nps = [NpDict[p] for p in projectiontypes]
    return ret_gs, ret_Nps


def project_to_target_eigenspace(model, targetModel, EPS=1e-6):
    """
    Project each gate of `model` onto the eigenspace of the corresponding
    gate within `targetModel`.  Return the resulting `Model`.

    Parameters
    ----------
    model, targetModel : Model
        The model being projected and the model specifying the "target"
        eigen-spaces, respectively.

    EPS : float, optional
        Small magnitude specifying how much to "nudge" the target gates
        before eigen-decomposing them, so that their spectra will have the
        same conjugacy structure as the gates of `model`.

    Returns
    -------
    Model
    """
    ret = targetModel.copy()
    ret.set_all_parameterizations("full")  # so we can freely assign gates new values

    for gl, gate in model.operations.items():
        tgt_gate = targetModel.operations[gl].copy()
        evals_gate = _np.linalg.eigvals(gate.todense())

        #Essentially, we want to replace the eigenvalues of `tgt_gate`
        # (and *only* the eigenvalues) with those of `gate`.  A complication
        # is that the eigenvalues of `tgt_gate` are usually highly degenerate,
        # and so matching up eigenvalues can't be done just based on value.
        # Our algorithm consists of two steps:
        # 1) match gate & target eigenvalues based on value, ensuring conjugacy
        #    relationships between eigenvalues are preserved.
        # 2) for each eigenvalue/vector of `gate`, project the eigenvector onto
        #    the eigenspace of `tgt_gate` corresponding to the matched eigenvalue.
        #    (treat conj-pair eigenvalues of `gate` together).

        evals_tgt, Utgt = _np.linalg.eig(tgt_gate.todense())
        evals_gate, Uop = _np.linalg.eig(gate.todense())
        #_, pairs = _mt.minweight_match(evals_tgt, evals_gate, return_pairs=True)
        pairs = _mt.minweight_match_realmxeigs(evals_tgt, evals_gate)

        #Form eigenspaces of Utgt
        eigenspace = {}  # key = index of target eigenval, val = assoc. eigenspace
        for i, ev in enumerate(evals_tgt):
            for j in eigenspace:
                if _np.isclose(ev, evals_tgt[j]):  # then add evector[i] to this eigenspace
                    eigenspace[j].append(Utgt[:, i])
                    eigenspace[i] = eigenspace[j]  # reference!
                    break
            else:
                eigenspace[i] = [Utgt[:, i]]  # new list = new eigenspace

        #Project each eigenvector (col of Uop) onto space of cols
        evectors = {}  # key = index of gate eigenval, val = assoc. (projected) eigenvec
        for ipair, (i, j) in enumerate(pairs):
            tgt_eval = evals_tgt[i]
            if j in evectors: continue  # we already processed this one!

            # non-orthog projection:
            # v = E * coeffs s.t. |E*coeffs-v|^2 is minimal  (E is not square so can't invert)
            # --> E.dag * v = E.dag * E * coeffs
            # --> inv(E.dag * E) * E.dag * v = coeffs
            # E*coeffs = E * inv(E.dag * E) * E.dag * v

            E = _np.array(eigenspace[i]).T; Edag = E.T.conjugate()
            coeffs = _np.dot(_np.dot(_np.linalg.inv(_np.dot(Edag, E)), Edag), Uop[:, j])
            evectors[j] = _np.dot(E, coeffs)

            #check for conjugate pair
            for i2, j2 in pairs[ipair + 1:]:
                if abs(evals_gate[j].imag) > 1e-6 and _np.isclose(evals_gate[j], _np.conjugate(evals_gate[j2])):
                    evectors[j2] = _np.conjugate(evectors[j])
                    E2 = _np.array(eigenspace[i2]).T; E2dag = E2.T.conjugate()
                    x = _np.linalg.solve(_np.dot(Edag, E), _np.dot(Edag, evectors[j2]))
                    #assert(_np.isclose(_np.linalg.norm(x),_np.linalg.norm(coeffs))) ??
                    #check that this vector is in the span of eigenspace[i2]?

        #build new "Utgt" using specially chosen linear combos of degenerate-eigenvecs
        Uproj = _np.array([evectors[i] for i in range(Utgt.shape[1])]).T
        Uproj_inv = _np.linalg.inv(Uproj)
        epgate = _np.dot(Uproj, _np.dot(_np.diag(evals_gate), Uproj_inv))
        epgate = _np.real_if_close(epgate, tol=1000)

        assert(_np.linalg.norm(_np.imag(epgate)) < 1e-7)
        # this should never happen & indicates an uncaught failure in
        # minweight_match_realmxeigs(...)

        ret.operations[gl] = epgate

    return ret


def unitary_to_pauligate(U):
    """
    Get the linear operator on (vectorized) density
    matrices corresponding to a n-qubit unitary
    operator on states.

    Parameters
    ----------
    U : numpy array
        A dxd array giving the action of the unitary
        on a state in the sigma-z basis.
        where d = 2 ** n-qubits

    Returns
    -------
    numpy array
        The operator on density matrices that have been
        vectorized as d**2 vectors in the Pauli basis.
    """
    assert U.shape[0] == U.shape[1], '"Unitary" matrix is not square'
    return _bt.change_basis(unitary_to_process_mx(U), 'std', 'pp')


def is_valid_lindblad_paramtype(typ):
    """
    Whether `typ` is a recognized Lindblad-gate parameterization type.

    A *Lindblad type* is comprised of a parameter specification followed
    optionally by an evolution-type suffix.  The parameter spec can be
    "GLND" (general unconstrained Lindbladian), "CPTP" (cptp-constrained),
    or any/all of the letters "H" (Hamiltonian), "S" (Stochastic, CPTP),
    "s" (Stochastic), "A" (Affine), "D" (Depolarization, CPTP),
    "d" (Depolarization) joined with plus (+) signs.  Note that "H"
    cannot appear alone, and that "A" cannot appear without one of
    {"S","s","D","d"}. The suffix can be non-existent (density-matrix),
    "terms" (state-vector terms) or "clifford terms" (stabilizer-state
    terms).  For example, valid Lindblad types are "H+S", "H+d+A",
    "CPTP clifford terms", or "S+A terms".

    Returns
    -------
    bool
    """
    try:
        baseTyp, _ = split_lindblad_paramtype(typ)
    except ValueError:
        return False  # if can't even split `typ`
    return baseTyp in ("CPTP", "H+S", "S", "H+S+A", "S+A", "H+D", "D", "H+D+A", "D+A",
                       "GLND", "H+s", "s", "H+s+A", "s+A", "H+d", "d", "H+d+A", "d+A")


def split_lindblad_paramtype(typ):
    """
    Splits a Lindblad-gate parameteriation type into
    a base-type (e.g. "H+S") and an evolution-type
    string.

    Parameters
    ----------
    typ : str
        The parameterization type, e.g. "H+S terms".

    Returns
    -------
    base_type : str
        The "base-parameterization" part of `typ`.
    evotype : str
        The evolution type corresponding to `typ`.
    """
    bTyp = typ.split()[0]  # "base" type
    evostr = " ".join(typ.split()[1:])

    if evostr == "": evotype = "densitymx"
    elif evostr == "terms": evotype = "svterm"
    elif evostr == "clifford terms": evotype = "cterm"
    else: raise ValueError("Unrecognized evotype in `typ`=%s" % typ)
    return bTyp, evotype
