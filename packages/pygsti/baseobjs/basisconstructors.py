""" Functions for creating the standard sets of matrices in the standard,
    pauli, gell mann, and qutrit bases """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
import itertools as _itertools
import numbers as _numbers
import collections as _collections
import numpy as _np
import scipy.sparse as _sps

from collections import namedtuple as _namedtuple
import functools as _functools

from .parameterized import parameterized as _parameterized
from .opttools import cache_by_hashed_args

#OLD TODO REMOVE
#DefaultBasisInfo = _namedtuple('BuiltinBasisInfo', ['constructor', 'longname', 'real', 'sizesfn', 'labeler'])
#@_parameterized # this decorator takes additional arguments (other than just f)
#def basis_constructor(f, name, longname, sizesfn, real=True):
#    """ This decorator saves f to a dictionary for constructing default bases,
#        as well as enabling caching on the basis creation function: (Important
#        to CP/TP cases of gauge opt) """
#    @cache_by_hashed_args
#    @_functools.wraps(f)
#    def _cached(*args, **kwargs):
#        return f(*args, **kwargs)
#    _basisConstructorDict[name] = DefaultBasisInfo(_cached, longname, real, sizesfn)
#    return _cached

## Pauli basis matrices
sqrt2 = _np.sqrt(2)
id2x2 = _np.array([[1, 0], [0, 1]])
sigmax = _np.array([[0, 1], [1, 0]])
sigmay = _np.array([[0, -1.0j], [1.0j, 0]])
sigmaz = _np.array([[1, 0], [0, -1]])

##Matrix unit basis


def mut(i, j, N):
    mx = _np.zeros((N, N), 'd'); mx[i, j] = 1.0
    return mx


mxUnitVec = (mut(0, 0, 2), mut(0, 1, 2), mut(1, 0, 2), mut(1, 1, 2))
mxUnitVec_2Q = (mut(0, 0, 4), mut(0, 1, 4), mut(0, 2, 4), mut(0, 3, 4),
                mut(1, 0, 4), mut(1, 1, 4), mut(1, 2, 4), mut(1, 3, 4),
                mut(2, 0, 4), mut(2, 1, 4), mut(2, 2, 4), mut(2, 3, 4),
                mut(3, 0, 4), mut(3, 1, 4), mut(3, 2, 4), mut(3, 3, 4))

MAX_BASIS_MATRIX_DIM = 2**6


def _check_dim(dim):
    global MAX_BASIS_MATRIX_DIM
    if not isinstance(dim, _numbers.Integral):
        dim = max(dim)  # assume dim is a list/tuple of dims & just consider max
    if dim > MAX_BASIS_MATRIX_DIM:
        raise ValueError(("You have requested to build a basis with %d x %d matrices."
                          " This is pretty big and so we're throwing this error because"
                          " there's a good chance you didn't mean to to this.  If you "
                          " really want to, increase `pygsti.baseobjs.basisconstructors.MAX_BASIS_MATRIX_DIM`"
                          " (currently == %d) to something greater than %d and rerun this.")
                         % (dim, dim, MAX_BASIS_MATRIX_DIM, dim))


class MatrixBasisConstructor(object):
    def __init__(self, longname, matrixgen_fn, labelgen_fn, real):
        """ TODO: docstring - note function expect *matrix* dimension as arg"""
        self.matrixgen_fn = matrixgen_fn
        self.labelgen_fn = labelgen_fn
        self.longname = longname
        self.real = real

    def matrix_dim(self, dim):
        """ TODO: docstring - dim is *vector-space* dimension """
        d = int(round(_np.sqrt(dim)))
        assert(d**2 == dim), "Matrix bases can only have dimension = perfect square (not %d)!" % dim
        return d

    def labeler(self, dim, sparse):
        """ TODO: docstring - dim is *vector-space* dimension """
        return self.labelgen_fn(self.matrix_dim(dim))

    def constructor(self, dim, sparse):
        """ TODO: docstring - dim is *vector-space* dimension """
        els = self.matrixgen_fn(self.matrix_dim(dim))
        if sparse: els = [_sps.csr_matrix(el) for el in els]
        return els

    """ A "sizes" function for constructing Basis objects
        so that they can know the size & dimension of a
        basis without having the construct the (potentially
        large) set of elements. """

    def sizes(self, dim, sparse):
        """ TODO: docstring - dim is dimension of vector space basis spans,
             i.e. 4 for a basis of 2x2 matrices and 2 for a basis of length=2 vectors"""
        nElements = dim  # the number of matrices in the basis
        basisDim = dim  # the dimension of the vector space this basis is for
        # (== size for a full basis, > size for a partial basis)
        d = self.matrix_dim(dim); elshape = (d, d)
        return nElements, basisDim, elshape


class VectorBasisConstructor(object):
    def __init__(self, longname, vectorgen_fn, labelgen_fn, real):
        """ TODO: docstring - note function expect *matrix* dimension as arg"""
        self.vectorgen_fn = vectorgen_fn
        self.labelgen_fn = labelgen_fn
        self.longname = longname
        self.real = real

    def labeler(self, dim, sparse):
        """ TODO: docstring - dim is *vector-space* dimension """
        return self.labelgen_fn(dim)

    def constructor(self, dim, sparse):
        """ TODO: docstring - dim is *vector-space* dimension """
        els = self.vectorgen_fn(dim)
        assert(not sparse), "Sparse vector bases not supported (yet)"
        return els

    def sizes(self, dim, sparse):
        """ TODO: docstring """
        nElements = dim  # the number of matrices in the basis
        basisDim = dim  # the dimension of the vector space this basis
        elshape = (dim,)  # the shape of the (vector) elements
        return nElements, basisDim, elshape


def std_matrices(matrix_dim):
    """
    Get the elements of the matrix unit, or "standard", basis
    spanning the density-matrix space given by matrix_dim.

    #TODO: update docstring since we don't do this embedding anymore - matrix_dim must be an int!
    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    dim. These matrices form an orthonormal basis under
    the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    dim: int
        dimension of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (dim, dim),
        where dim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of dim)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).

    Notes
    -----
    Each element is a matrix containing
    a single "1" entry amidst a background of zeros, and there
    are never "1"s in positions outside the block-diagonal structure.
    """
    _check_dim(matrix_dim)
    basisDim = matrix_dim ** 2

    mxList = []
    for i in range(matrix_dim):
        for j in range(matrix_dim):
            mxList.append(mut(i, j, matrix_dim))
    assert len(mxList) == basisDim
    return mxList


def std_labels(matrix_dim):
    """ TODO: docstring - dim is *matrix* dimension """
    if matrix_dim == 0: return []
    if matrix_dim == 1: return ['']  # special case - use empty label instead of "I"
    return ["(%d,%d)" % (i, j) for i in range(matrix_dim) for j in range(matrix_dim)]


def _GetGellMannNonIdentityDiagMxs(dimension):
    d = dimension
    listOfMxs = []
    if d > 2:
        dm1_listOfMxs = _GetGellMannNonIdentityDiagMxs(d - 1)
        for dm1_mx in dm1_listOfMxs:
            mx = _np.zeros((d, d), 'complex')
            mx[0:d - 1, 0:d - 1] = dm1_mx
            listOfMxs.append(mx)
    if d > 1:
        mx = _np.identity(d, 'complex')
        mx[d - 1, d - 1] = 1 - d
        mx *= _np.sqrt(2.0 / (d * (d - 1)))
        listOfMxs.append(mx)

    return listOfMxs


def gm_matrices_unnormalized(matrix_dim):
    """
    Get the elements of the generalized Gell-Mann
    basis spanning the density-matrix space given by matrix_dim.

    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    dim. These matrices form an orthogonal but not
    orthonormal basis under the trace inner product.

    Parameters
    ----------
    matrix_dim : int
        Dimension of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (matrix_dim, matrix_dim),
        where matrix_dim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of matrix_dim)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).
    """
    _check_dim(matrix_dim)
    if matrix_dim == 0: return []
    if isinstance(matrix_dim, _numbers.Integral):
        d = matrix_dim
        #Identity Mx
        listOfMxs = [_np.identity(d, 'complex')]

        #Non-diagonal matrices -- only take those whose non-zero elements are not "frozen" in cssb case
        for k in range(d):
            for j in range(k + 1, d):
                mx = _np.zeros((d, d), 'complex')
                mx[k, j] = mx[j, k] = 1.0
                listOfMxs.append(mx)

        for k in range(d):
            for j in range(k + 1, d):
                mx = _np.zeros((d, d), 'complex')
                mx[k, j] = -1.0j; mx[j, k] = 1.0j
                listOfMxs.append(mx)

        #Non-Id Diagonal matrices
        listOfMxs.extend(_GetGellMannNonIdentityDiagMxs(d))

        assert(len(listOfMxs) == d**2)
        return listOfMxs
    else:
        raise ValueError("Invalid matrix_dim = %s" % str(matrix_dim))


def gm_matrices(matrix_dim):
    """
    Get the normalized elements of the generalized Gell-Mann
    basis spanning the density-matrix space given by matrix_dim.

    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    matrix_dim. These matrices form an orthonormal basis
    under the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    matrix_dim : int
        Dimension of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (matrix_dim, matrix_dim),
        where matrix_dim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of matrix_dim)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).
    """
    mxs = [mx.copy() for mx in gm_matrices_unnormalized(matrix_dim)]
    for mx in mxs:
        mx.flags.writeable = True  # Safe because of above copy
    mxs[0] *= 1 / _np.sqrt(mxs[0].shape[0])  # identity mx
    for mx in mxs[1:]:
        mx *= 1 / sqrt2
    return mxs


def gm_labels(matrix_dim):
    if matrix_dim == 0: return []
    if matrix_dim == 1: return ['']  # special case - use empty label instead of "I"
    if matrix_dim == 2:  # Special case of Pauli's
        return ["I", "X", "Y", "Z"]

    d = matrix_dim
    lblList = []

    #labels for gm_matrices of dim "blockDim":
    lblList.append("I")  # identity on i-th block

    #X-like matrices, containing 1's on two off-diagonal elements (k,j) & (j,k)
    lblList.extend(["X_{%d,%d}" % (k, j)
                    for k in range(d) for j in range(k + 1, d)])

    #Y-like matrices, containing -1j & 1j on two off-diagonal elements (k,j) & (j,k)
    lblList.extend(["Y_{%d,%d}" % (k, j)
                    for k in range(d) for j in range(k + 1, d)])

    #Z-like matrices, diagonal mxs with 1's on diagonal until (k,k) element == 1-d,
    # then diagonal elements beyond (k,k) are zero.  This matrix is then scaled
    # by sqrt( 2.0 / (d*(d-1)) ) to ensure proper normalization.
    lblList.extend(["Z_{%d}" % (k) for k in range(1, d)])
    return lblList


def pp_matrices(matrix_dim, maxWeight=None):
    """
    Get the elements of the Pauil-product basis
    spanning the space of matrix_dim x matrix_dim density matrices
    (matrix-dimension matrix_dim, space dimension matrix_dim^2).

    The returned matrices are given in the standard basis of the
    density matrix space, and are thus kronecker products of
    the standard representation of the Pauli matrices, (i.e. where
    sigma_y == [[ 0, -i ], [i, 0]] ) normalized so that the
    resulting basis is orthonormal under the trace inner product,
    i.e. Tr( dot(Mi,Mj) ) == delta_ij.  In the returned list,
    the right-most factor of the kronecker product varies the
    fastsest, so, for example, when matrix_dim == 4 the returned list
    is [ II,IX,IY,IZ,XI,XX,XY,XY,YI,YX,YY,YZ,ZI,ZX,ZY,ZZ ].

    Parameters
    ----------
    matrix_dim : int
        Matrix-dimension of the density-matrix space.  Must be
        a power of 2.

    maxWeight : int, optional
        Restrict the elements returned to those having weight <= `maxWeight`. An
        element's "weight" is defined as the number of non-identity single-qubit
        factors of which it is comprised.  For example, if `matrix_dim == 4` and
        `maxWeight == 1` then the returned list is [II, IX, IY, IZ, XI, YI, ZI].


    Returns
    -------
    list
        A list of N numpy arrays each of shape (matrix_dim, matrix_dim), where N == matrix_dim^2,
        the dimension of the density-matrix space. (Exception: when maxWeight
        is not None, the returned list may have fewer than N elements.)

    Notes
    -----
    Matrices are ordered with first qubit being most significant,
    e.g., for 2 qubits: II, IX, IY, IZ, XI, XX, XY, XZ, YI, ... ZZ
    """
    _check_dim(matrix_dim)
    sigmaVec = (id2x2 / sqrt2, sigmax / sqrt2, sigmay / sqrt2, sigmaz / sqrt2)
    if matrix_dim == 0: return []

    def _is_integer(x):
        return bool(abs(x - round(x)) < 1e-6)

    nQubits = _np.log2(matrix_dim)
    if not _is_integer(nQubits):
        raise ValueError(
            "Dimension for Pauli tensor product matrices must be an integer *power of 2* (not %d)" % matrix_dim)
    nQubits = int(round(nQubits))

    if nQubits == 0:  # special case: return single 1x1 identity mx
        return [_np.identity(1, 'complex')]

    matrices = []
    basisIndList = [[0, 1, 2, 3]] * nQubits
    for sigmaInds in _itertools.product(*basisIndList):
        if maxWeight is not None:
            if sigmaInds.count(0) < nQubits - maxWeight: continue

        M = _np.identity(1, 'complex')
        for i in sigmaInds:
            M = _np.kron(M, sigmaVec[i])
        matrices.append(M)

    return matrices


def pp_labels(matrix_dim):
    def _is_integer(x):
        return bool(abs(x - round(x)) < 1e-6)
    if matrix_dim == 0: return []
    if matrix_dim == 1: return ['']  # special case - use empty label instead of "I"

    nQubits = _np.log2(matrix_dim)
    if not _is_integer(nQubits):
        raise ValueError("Dimension for Pauli tensor product matrices must be an integer *power of 2*")
    nQubits = int(round(nQubits))

    lblList = []
    basisLblList = [['I', 'X', 'Y', 'Z']] * nQubits
    for sigmaLbls in _itertools.product(*basisLblList):
        lblList.append(''.join(sigmaLbls))
    return lblList


def qt_matrices(matrix_dim, selected_pp_indices=[0, 5, 10, 11, 1, 2, 3, 6, 7]):
    """
    Get the elements of a special basis spanning the density-matrix space of
    a qutrit.

    The returned matrices are given in the standard basis of the
    density matrix space. These matrices form an orthonormal basis
    under the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    matrix_dim : int
        Matrix-dimension of the density-matrix space.  Must equal 3
        (present just to maintain consistency which other routines)

    Returns
    -------
    list
        A list of 9 numpy arrays each of shape (3, 3).
    """
    if matrix_dim == 1:  # special case of just identity mx
        return [_np.identity(1, 'd')]

    assert(matrix_dim == 3)
    A = _np.array([[1, 0, 0, 0],
                   [0, 1. / _np.sqrt(2), 1. / _np.sqrt(2), 0],
                   [0, 0, 0, 1]], 'd')  # projector onto symmetric space

    def _toQutritSpace(inputMat):
        return _np.dot(A, _np.dot(inputMat, A.transpose()))

    qt_mxs = []
    pp_mxs = pp_matrices(4)
    #selected_pp_indices = [0,5,10,11,1,2,3,6,7] #which pp mxs to project
    # labels = ['II', 'XX', 'YY', 'YZ', 'IX', 'IY', 'IZ', 'XY', 'XZ']
    qt_mxs = [_toQutritSpace(pp_mxs[i]) for i in selected_pp_indices]

    # Normalize so Tr(BiBj) = delta_ij (done by hand, since only 3x3 mxs)
    qt_mxs[0] *= 1 / _np.sqrt(0.75)

    #TAKE 2 (more symmetric = better?)
    q1 = qt_mxs[1] - qt_mxs[0] * _np.sqrt(0.75) / 3
    q2 = qt_mxs[2] - qt_mxs[0] * _np.sqrt(0.75) / 3
    qt_mxs[1] = (q1 + q2) / _np.sqrt(2. / 3.)
    qt_mxs[2] = (q1 - q2) / _np.sqrt(2)

    #TAKE 1 (XX-II and YY-XX-II terms... not symmetric):
    #qt_mxs[1] = (qt_mxs[1] - qt_mxs[0]*_np.sqrt(0.75)/3) / _np.sqrt(2.0/3.0)
    #qt_mxs[2] = (qt_mxs[2] - qt_mxs[0]*_np.sqrt(0.75)/3 + qt_mxs[1]*_np.sqrt(2.0/3.0)/2) / _np.sqrt(0.5)

    for i in range(3, 9): qt_mxs[i] *= 1 / _np.sqrt(0.5)

    return qt_mxs


def qt_labels(matrix_dim):
    """ TODO: docstring """
    if matrix_dim == 0: return []
    if matrix_dim == 1: return ['']  # special case
    assert(matrix_dim == 3), "Qutrit basis must have matrix_dim == 3!"
    return ['II', 'X+Y', 'X-Y', 'YZ', 'IX', 'IY', 'IZ', 'XY', 'XZ']


def cl_vectors(dim):
    """
    Get the elements (vectors) of the classical basis with
    dimension `dim` - i.e. the `dim` standard unit vectors
    of length `dim`.

    Parameters
    ----------
    dim: int
        dimension of the vector space.

    Returns
    -------
    list
        A list of `dim` numpy arrays each of shape (dim,).
    """
    vecList = []
    for i in range(dim):
        v = _np.zeros(dim, 'd'); v[i] = 1.0
        vecList.append(v)
    return vecList


def cl_labels(dim):
    """ TODO: docstring """
    if dim == 0: return []
    if dim == 1: return ['']  # special case - use empty label instead of "0"
    return ["%d" % i for i in range(dim)]


def sv_vectors(dim):
    """
    Get the elements (vectors) of the complex state-vectro basis with
    dimension `dim` - i.e. the `dim` standard complex unit vectors
    of length `dim`.

    Parameters
    ----------
    dim: int
        dimension of the vector space.

    Returns
    -------
    list
        A list of `dim` numpy arrays each of shape (dim,).
    """
    vecList = []
    for i in range(dim):
        v = _np.zeros(dim, complex); v[i] = 1.0
        vecList.append(v)
    return vecList


def sv_labels(dim):
    """ TODO: docstring """
    if dim == 0: return []
    if dim == 1: return ['']  # special case - use empty label instead of "0"
    return ["|%d>" % i for i in range(dim)]


def unknown_els(dim):
    assert(dim == 0), "Unknown basis must have dimension 0!"
    return []


def unknown_labels(dim):
    return []


_basisConstructorDict = dict()  # global dict holding all builtin basis constructors (used by Basis objects)
_basisConstructorDict['std'] = MatrixBasisConstructor('Matrix-unit basis', std_matrices, std_labels, False)
_basisConstructorDict['gm_unnormalized'] = MatrixBasisConstructor(
    'Unnormalized Gell-Mann basis', gm_matrices_unnormalized, gm_labels, True)
_basisConstructorDict['gm'] = MatrixBasisConstructor('Gell-Mann basis', gm_matrices, gm_labels, True)
_basisConstructorDict['pp'] = MatrixBasisConstructor('Pauli-Product basis', pp_matrices, pp_labels, True)
_basisConstructorDict['qt'] = MatrixBasisConstructor('Qutrit basis', qt_matrices, qt_labels, True)
_basisConstructorDict['cl'] = VectorBasisConstructor('Classical basis', cl_vectors, cl_labels, True)
_basisConstructorDict['sv'] = VectorBasisConstructor('State-vector basis', sv_vectors, sv_labels, False)
_basisConstructorDict['unknown'] = VectorBasisConstructor('Unknown (0-dim) basis', unknown_els, unknown_labels, False)
