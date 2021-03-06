""" Defines classes which represent gates, as well as supporting functions """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import collections as _collections
import itertools as _itertools
import numpy as _np
import scipy as _scipy
import scipy.sparse as _sps
import warnings as _warnings

from .. import objects as _objs
from ..tools import basistools as _bt
from ..tools import matrixtools as _mt
from ..tools import optools as _gt
from ..tools import slicetools as _slct
from ..tools import listtools as _lt
from ..tools import internalgates as _itgs
from ..tools import mpitools as _mpit
from ..tools import compattools as _compat
from ..objects import model as _mdl
from ..objects import operation as _op
from ..objects import opfactory as _opfactory
from ..objects import spamvec as _sv
from ..objects import povm as _povm
from ..objects import qubitgraph as _qgraph
from ..objects import labeldicts as _ld
from ..objects.cloudnoisemodel import CloudNoiseModel as _CloudNoiseModel
from ..objects.labeldicts import StateSpaceLabels as _StateSpaceLabels

from ..baseobjs import VerbosityPrinter as _VerbosityPrinter
from ..baseobjs import Basis as _Basis
from ..baseobjs import BuiltinBasis as _BuiltinBasis
from ..baseobjs import Label as _Lbl
from ..baseobjs import CircuitParser as _CircuitParser

from . import circuitconstruction as _gsc
from .modelconstruction import basis_build_vector as _basis_build_vector

RANK_TOL = 1e-9


def nparams_XYCNOT_cloudnoise_model(nQubits, geometry="line", maxIdleWeight=1, maxhops=0,
                                    extraWeight1Hops=0, extraGateWeight=0, requireConnected=False,
                                    independent1Qgates=True, ZZonly=False, verbosity=0):
    """
    Returns the number of parameters in the :class:`CloudNoiseModel` containing
    X(pi/2), Y(pi/2) and CNOT gates using the specified arguments without
    actually constructing the model (useful for considering parameter-count
    scaling).

    Parameters
    ----------
    Subset of those of :function:`build_cloudnoise_model_from_hops_and_weights`.

    Returns
    -------
    int
    """
    # noise can be either a seed or a random array that is long enough to use

    printer = _VerbosityPrinter.build_printer(verbosity)
    printer.log("Computing parameters for a %d-qubit %s model" % (nQubits, geometry))

    qubitGraph = _objs.QubitGraph.common_graph(nQubits, geometry)
    #printer.log("Created qubit graph:\n"+str(qubitGraph))

    def idle_count_nparams(maxWeight):
        """Parameter count of a `build_nqn_global_idle`-constructed gate"""
        ret = 0
        possible_err_qubit_inds = _np.arange(nQubits)
        for wt in range(1, maxWeight + 1):
            nErrTargetLocations = qubitGraph.connected_combos(possible_err_qubit_inds, wt)
            if ZZonly and wt > 1: basisSizeWoutId = 1**wt  # ( == 1)
            else: basisSizeWoutId = 3**wt  # (X,Y,Z)^wt
            nErrParams = 2 * basisSizeWoutId  # H+S terms
            ret += nErrTargetLocations * nErrParams
        return ret

    def op_count_nparams(target_qubit_inds, weight_maxhops_tuples, debug=False):
        """Parameter count of a `build_nqn_composed_gate`-constructed gate"""
        ret = 0
        #Note: no contrib from idle noise (already parameterized)
        for wt, maxHops in weight_maxhops_tuples:
            possible_err_qubit_inds = _np.array(qubitGraph.radius(target_qubit_inds, maxHops), _np.int64)
            if requireConnected:
                nErrTargetLocations = qubitGraph.connected_combos(possible_err_qubit_inds, wt)
            else:
                nErrTargetLocations = _scipy.special.comb(len(possible_err_qubit_inds), wt)
            if ZZonly and wt > 1: basisSizeWoutId = 1**wt  # ( == 1)
            else: basisSizeWoutId = 3**wt  # (X,Y,Z)^wt
            nErrParams = 2 * basisSizeWoutId  # H+S terms
            if debug:
                print(" -- wt%d, hops%d: inds=%s locs = %d, eparams=%d, total contrib = %d" %
                      (wt, maxHops, str(possible_err_qubit_inds), nErrTargetLocations,
                       nErrParams, nErrTargetLocations * nErrParams))
            ret += nErrTargetLocations * nErrParams
        return ret

    nParams = _collections.OrderedDict()

    printer.log("Creating Idle:")
    nParams[_Lbl('Gi')] = idle_count_nparams(maxIdleWeight)

    #1Q gates: X(pi/2) & Y(pi/2) on each qubit
    weight_maxhops_tuples_1Q = [(1, maxhops + extraWeight1Hops)] + \
                               [(1 + x, maxhops) for x in range(1, extraGateWeight + 1)]

    if independent1Qgates:
        for i in range(nQubits):
            printer.log("Creating 1Q X(pi/2) and Y(pi/2) gates on qubit %d!!" % i)
            nParams[_Lbl("Gx", i)] = op_count_nparams((i,), weight_maxhops_tuples_1Q)
            nParams[_Lbl("Gy", i)] = op_count_nparams((i,), weight_maxhops_tuples_1Q)
    else:
        printer.log("Creating common 1Q X(pi/2) and Y(pi/2) gates")
        rep = int(nQubits / 2)
        nParams[_Lbl("Gxrep")] = op_count_nparams((rep,), weight_maxhops_tuples_1Q)
        nParams[_Lbl("Gyrep")] = op_count_nparams((rep,), weight_maxhops_tuples_1Q)

    #2Q gates: CNOT gates along each graph edge
    weight_maxhops_tuples_2Q = [(1, maxhops + extraWeight1Hops), (2, maxhops)] + \
                               [(2 + x, maxhops) for x in range(1, extraGateWeight + 1)]
    for i, j in qubitGraph.edges():  # note: all edges have i<j so "control" of CNOT is always lower index (arbitrary)
        printer.log("Creating CNOT gate between qubits %d and %d!!" % (i, j))
        nParams[_Lbl("Gcnot", (i, j))] = op_count_nparams((i, j), weight_maxhops_tuples_2Q)

    #SPAM
    nPOVM_1Q = 4  # params for a single 1Q POVM
    nParams[_Lbl('rho0')] = 3 * nQubits  # 3 b/c each component is TP
    nParams[_Lbl('Mdefault')] = nPOVM_1Q * nQubits  # nQubits 1Q-POVMs

    return nParams, sum(nParams.values())


def build_cloudnoise_model_from_hops_and_weights(
        nQubits, gate_names, nonstd_gate_unitaries=None, custom_gates=None,
        availability=None, qubit_labels=None, geometry="line",
        maxIdleWeight=1, maxSpamWeight=1, maxhops=0,
        extraWeight1Hops=0, extraGateWeight=0, sparse=False,
        roughNoise=None, sim_type="auto", parameterization="H+S",
        spamtype="lindblad", addIdleNoiseToAllGates=True,
        errcomp_type="gates", independent_clouds=True,
        return_clouds=False, verbosity=0):  # , debug=False):
    """
    Create a "standard" n-qubit model using a low-weight and geometrically local
    error model with a common "global idle" operation.

    This type of model is referred to as a "cloud noise" model because
    noise specific to a gate may act on a neighborhood or cloud around
    the gate's target qubits.  This type of model is generally useful
    for performing GST on a multi-qubit system, whereas local-noise
    models (:class:`LocalNoiseModel` objects, created by, e.g.,
    :function:`create_standard localnoise_model`) are more useful for
    representing static (non-parameterized) models.

    The returned model is "standard", in that the following standard gate
    names may be specified as elements to `gate_names` without the need to
    supply their corresponding unitaries (as one must when calling
    the constructor directly):

    - 'Gi' : the 1Q idle operation
    - 'Gx','Gy','Gz' : 1Q pi/2 rotations
    - 'Gxpi','Gypi','Gzpi' : 1Q pi rotations
    - 'Gh' : Hadamard
    - 'Gp' : phase
    - 'Gcphase','Gcnot','Gswap' : standard 2Q gates

    Furthermore, if additional "non-standard" gates are needed,
    they are specified by their *unitary* gate action, even if
    the final model propagates density matrices (as opposed
    to state vectors).


    Parameters
    ----------
    nQubits : int
        The total number of qubits.

    gate_names : list
        A list of string-type gate names (e.g. `"Gx"`) either taken from
        the list of builtin "standard" gate names given above or from the
        keys of `nonstd_gate_unitaries`.  These are the typically 1- and 2-qubit
        gates that are repeatedly embedded (based on `availability`) to form
        the resulting model.

    nonstd_gate_unitaries : dict, optional
        A dictionary of numpy arrays which specifies the unitary gate action
        of the gate names given by the dictionary's keys.  As an advanced
        behavior, a unitary-matrix-returning function which takes a single
        argument - a tuple of label arguments - may be given instead of a
        single matrix to create an operation *factory* which allows
        continuously-parameterized gates.  This function must also return
        an empty/dummy unitary when `None` is given as it's argument.

    custom_gates : dict
        A dictionary that associates with gate labels
        :class:`LinearOperator`, :class:`OpFactory`, or `numpy.ndarray`
        objects.  These objects describe the full action of the gate or
        primitive-layer they're labeled by (so if the model represents
        states by density matrices these objects are superoperators, not
        unitaries), and override any standard construction based on builtin
        gate names or `nonstd_gate_unitaries`.  Keys of this dictionary must
        be string-type gate *names* -- they cannot include state space labels
        -- and they must be *static* (have zero parameters) because they
        represent only the ideal behavior of each gate -- the cloudnoise
        operations represent the parameterized noise.  To fine-tune how this
        noise is parameterized, call the :class:`CloudNoiseModel` constructor
        directly.

    availability : dict, optional
        A dictionary whose keys are the same gate names as in
        `gatedict` and whose values are lists of qubit-label-tuples.  Each
        qubit-label-tuple must have length equal to the number of qubits
        the corresponding gate acts upon, and causes that gate to be
        embedded to act on the specified qubits.  For example,
        `{ 'Gx': [(0,),(1,),(2,)], 'Gcnot': [(0,1),(1,2)] }` would cause
        the `1-qubit `'Gx'`-gate to be embedded three times, acting on qubits
        0, 1, and 2, and the 2-qubit `'Gcnot'`-gate to be embedded twice,
        acting on qubits 0 & 1 and 1 & 2.  Instead of a list of tuples,
        values of `availability` may take the special values:

        - `"all-permutations"` and `"all-combinations"` equate to all possible
        permutations and combinations of the appropriate number of qubit labels
        (deterined by the gate's dimension).
        - `"all-edges"` equates to all the vertices, for 1Q gates, and all the
        edges, for 2Q gates of the graphy given by `geometry`.
        - `"arbitrary"` or `"*"` means that the corresponding gate can be placed
        on any target qubits via an :class:`EmbeddingOpFactory` (uses less
        memory but slower than `"all-permutations"`.

        If a gate name (a key of `gatedict`) is not present in `availability`,
        the default is `"all-edges"`.

    qubit_labels : tuple, optional
        The circuit-line labels for each of the qubits, which can be integers
        and/or strings.  Must be of length `nQubits`.  If None, then the
        integers from 0 to `nQubits-1` are used.

    geometry : {"line","ring","grid","torus"} or QubitGraph
        The type of connectivity among the qubits, specifying a
        graph used to define neighbor relationships.  Alternatively,
        a :class:`QubitGraph` object with node labels equal to
        `qubit_labels` may be passed directly.

    maxIdleWeight : int, optional
        The maximum-weight for errors on the global idle gate.

    maxSpamWeight : int, optional
        The maximum-weight for SPAM errors when `spamtype == "linblad"`.

    maxhops : int
        The locality constraint: for a gate, errors (of weight up to the
        maximum weight for the gate) are allowed to occur on the gate's
        target qubits and those reachable by hopping at most `maxhops` times
        from a target qubit along nearest-neighbor links (defined by the
        `geometry`).

    extraWeight1Hops : int, optional
        Additional hops (adds to `maxhops`) for weight-1 errors.  A value > 0
        can be useful for allowing just weight-1 errors (of which there are
        relatively few) to be dispersed farther from a gate's target qubits.
        For example, a crosstalk-detecting model might use this.

    extraGateWeight : int, optional
        Addtional weight, beyond the number of target qubits (taken as a "base
        weight" - i.e. weight 2 for a 2Q gate), allowed for gate errors.  If
        this equals 1, for instance, then 1-qubit gates can have up to weight-2
        errors and 2-qubit gates can have up to weight-3 errors.

    sparse : bool, optional
        Whether the embedded Lindblad-parameterized gates within the constructed
        `nQubits`-qubit gates are sparse or not.  (This is determied by whether
        they are constructed using sparse basis matrices.)  When sparse, these
        Lindblad gates take up less memory, but their action is slightly slower.
        Usually it's fine to leave this as the default (False), except when
        considering particularly high-weight terms (b/c then the Lindblad gates
        are higher dimensional and sparsity has a significant impact).

    roughNoise: tuple or numpy.ndarray, optional
        If not None, noise to place on the gates, the state prep and the povm.
        This can either be a `(seed,strength)` 2-tuple, or a long enough numpy
        array (longer than what is needed is OK).  These values specify random
        `gate.from_vector` initialization for the model, and as such applies an
        often unstructured and unmeaningful type of noise.

    sim_type : {"auto","matrix","map","termorder:<N>"}
        The type of forward simulation (probability computation) to use for the
        returned :class:`Model`.  That is, how should the model compute
        operation sequence/circuit probabilities when requested.  `"matrix"` is better
        for small numbers of qubits, `"map"` is better for larger numbers. The
        `"termorder"` option is designed for even larger numbers.  Usually,
        the default of `"auto"` is what you want.

    parameterization : {"P", "P terms", "P clifford terms"}
        Where *P* can be any Lindblad parameterization base type (e.g. CPTP,
        H+S+A, H+S, S, D, etc.) This is the type of parameterizaton to use in
        the constructed model.  Types without any "terms" suffix perform
        usual density-matrix evolution to compute circuit probabilities.  The
        other "terms" options compute probabilities using a path-integral
        approach designed for larger numbers of qubits (experts only).

    spamtype : { "static", "lindblad", "tensorproduct" }
        Specifies how the SPAM elements of the returned `Model` are formed.
        Static elements are ideal (perfect) operations with no parameters, i.e.
        no possibility for noise.  Lindblad SPAM operations are the "normal"
        way to allow SPAM noise, in which case error terms up to weight
        `maxSpamWeight` are included.  Tensor-product operations require that
        the state prep and POVM effects have a tensor-product structure; the
        "tensorproduct" mode exists for historical reasons and is *deprecated*
        in favor of `"lindblad"`; use it only if you know what you're doing.

    addIdleNoiseToAllGates: bool, optional
        Whether the global idle should be added as a factor following the
        ideal action of each of the non-idle gates.

    errcomp_type : {"gates","errorgens"}
        How errors are composed when creating layer operations in the returned
        model.  `"gates"` means that the errors on multiple gates in a single
        layer are composed as separate and subsequent processes.  Specifically,
        the layer operation has the form `Composed(target,idleErr,cloudErr)`
        where `target` is a composition of all the ideal gate operations in the
        layer, `idleErr` is idle error (`.operation_blks['layers']['globalIdle']`),
        and `cloudErr` is the composition (ordered as layer-label) of cloud-
        noise contributions, i.e. a map that acts as the product of exponentiated
        error-generator matrices.  `"errorgens"` means that layer operations
        have the form `Composed(target, error)` where `target` is as above and
        `error` results from composing the idle and cloud-noise error
        *generators*, i.e. a map that acts as the exponentiated sum of error
        generators (ordering is irrelevant in this case).

    independent_clouds : bool, optional
        Currently this must be set to True.  In a future version, setting to
        true will allow all the clouds of a given gate name to have a similar
        cloud-noise process, mapped to the full qubit graph via a stencil.

    return_clouds : bool, optional
        Whether to return a dictionary of "cloud" objects, used for constructing
        the operation sequences necessary for probing the returned Model's
        parameters.  Used primarily internally within pyGSTi.

    verbosity : int, optional
        An integer >= 0 dictating how must output to send to stdout.

    Returns
    -------
    Model
    """
    mdl = _CloudNoiseModel.build_from_hops_and_weights(
        nQubits, gate_names, nonstd_gate_unitaries, custom_gates,
        availability, qubit_labels, geometry,
        maxIdleWeight, maxSpamWeight, maxhops,
        extraWeight1Hops, extraGateWeight, sparse,
        sim_type, parameterization, spamtype,
        addIdleNoiseToAllGates, errcomp_type,
        independent_clouds, verbosity)

    #Insert noise on everything using roughNoise (really shouldn't be used!)
    if roughNoise is not None:
        vec = mdl.to_vector()
        assert(spamtype == "lindblad"), "Can only apply rough noise when spamtype == lindblad"
        assert(_np.linalg.norm(vec) / len(vec) < 1e-6)  # make sure our base is zero
        if isinstance(roughNoise, tuple):  # use as (seed, strength)
            seed, strength = roughNoise
            rndm = _np.random.RandomState(seed)
            vec += _np.abs(rndm.random_sample(len(vec)) * strength)  # abs b/c some params need to be positive
        else:  # use as a vector
            vec += roughNoise[0:len(vec)]
        mdl.from_vector(vec)

    if return_clouds:
        #FUTURE - just return cloud *keys*? (operation label values are never used
        # downstream, but may still be useful for debugging, so keep for now)
        return mdl, mdl.get_clouds()
    else:
        return mdl


def build_cloud_crosstalk_model(nQubits, gate_names, error_rates, nonstd_gate_unitaries=None, custom_gates=None,
                                availability=None, qubit_labels=None, geometry="line", parameterization='auto',
                                evotype="auto", sim_type="auto", independent_gates=False, sparse=True,
                                errcomp_type="errorgens", addIdleNoiseToAllGates=True, verbosity=0):
    """
    Create a n-qubit model that may contain crosstalk errors.

    This function constructs a :class:`CloudNoiseModel` that may place noise on
    a gate that affects arbitrary qubits, i.e. qubits in addition to the target
    qubits of the gate.  These errors are specified uing a dictionary of error
    rates.

    Parameters
    ----------
    nQubits : int
        The number of qubits

    error_rates : dict
        A dictionary whose keys are primitive-layer and gate labels (e.g.
        `("Gx",0)` or `"Gx"`) and whose values are "error-dictionaries"
        that determine the type and amount of error placed on each item.
        Error-dictionary keys are `(termType, basisLabel)` tuples, where
        `termType` can be `"H"` (Hamiltonian), `"S"` (Stochastic), or `"A"`
        (Affine), and `basisLabel` is a string of I, X, Y, or Z to describe a
        Pauli basis element appropriate for the gate (i.e. having the same
        number of letters as there are qubits in the gate).  For example, you
        could specify a 0.01-radian Z-rotation error and 0.05 rate of Pauli-
        stochastic X errors on a 1-qubit gate by using the error dictionary:
        `{('H','Z'): 0.01, ('S','X'): 0.05}`.  Furthermore, basis elements
        may be directed at specific qubits using a color followed by a comma-
        separated qubit-label-list.  For example, `('S',"XX:0,1")` would
        mean a weight-2 XX stochastic error on qubits 0 and 1, and this term
        could be placed in the error dictionary for a gate that is only
        supposed to target qubit 0, for instance.  In addition to the primitive
        label names, the special values `"prep"`, `"povm"`, and `"idle"` may be
        used as keys of `error_rates` to specify the error on the state
        preparation, measurement, and global idle, respectively.

    nonstd_gate_unitaries : dict, optional
        A dictionary of numpy arrays which specifies the unitary gate action
        of the gate names given by the dictionary's keys.  As an advanced
        behavior, a unitary-matrix-returning function which takes a single
        argument - a tuple of label arguments - may be given instead of a
        single matrix to create an operation *factory* which allows
        continuously-parameterized gates.  This function must also return
        an empty/dummy unitary when `None` is given as it's argument.

    custom_gates : dict, optional
        A dictionary that associates with gate labels
        :class:`LinearOperator`, :class:`OpFactory`, or `numpy.ndarray`
        objects.  These objects override any other behavior for constructing
        their designated operations (e.g. from `error_rates` or
        `nonstd_gate_unitaries`).  Note: currently these objects must
        be *static*, and keys of this dictionary must by strings - there's
        no way to specify the "cloudnoise" part of a gate via this dict
        yet, only the "target" part.

    availability : dict, optional
        A dictionary whose keys are the same gate names as in
        `gatedict` and whose values are lists of qubit-label-tuples.  Each
        qubit-label-tuple must have length equal to the number of qubits
        the corresponding gate acts upon, and causes that gate to be
        embedded to act on the specified qubits.  For example,
        `{ 'Gx': [(0,),(1,),(2,)], 'Gcnot': [(0,1),(1,2)] }` would cause
        the `1-qubit `'Gx'`-gate to be embedded three times, acting on qubits
        0, 1, and 2, and the 2-qubit `'Gcnot'`-gate to be embedded twice,
        acting on qubits 0 & 1 and 1 & 2.  Instead of a list of tuples,
        values of `availability` may take the special values:

        - `"all-permutations"` and `"all-combinations"` equate to all possible
        permutations and combinations of the appropriate number of qubit labels
        (deterined by the gate's dimension).
        - `"all-edges"` equates to all the vertices, for 1Q gates, and all the
        edges, for 2Q gates of the graphy given by `geometry`.
        - `"arbitrary"` or `"*"` means that the corresponding gate can be placed
        on any target qubits via an :class:`EmbeddingOpFactory` (uses less
        memory but slower than `"all-permutations"`.

        If a gate name (a key of `gatedict`) is not present in `availability`,
        the default is `"all-edges"`.

    qubit_labels : tuple, optional
        The circuit-line labels for each of the qubits, which can be integers
        and/or strings.  Must be of length `nQubits`.  If None, then the
        integers from 0 to `nQubits-1` are used.

    geometry : {"line","ring","grid","torus"} or QubitGraph
        The type of connectivity among the qubits, specifying a
        graph used to define neighbor relationships.  Alternatively,
        a :class:`QubitGraph` object with node labels equal to
        `qubit_labels` may be passed directly.

    parameterization : "auto"
        This argument is for future expansion and currently must be set to `"auto"`.

    evotype : {"auto","densitymx","statevec","stabilizer","svterm","cterm"}
        The evolution type.  If "auto" is specified, "densitymx" is used.

    sim_type : {"auto","matrix","map","termorder:<N>"}
        The type of forward simulation (probability computation) to use for the
        returned :class:`Model`.  That is, how should the model compute
        operation sequence/circuit probabilities when requested.  `"matrix"` is better
        for small numbers of qubits, `"map"` is better for larger numbers. The
        `"termorder"` option is designed for even larger numbers.  Usually,
        the default of `"auto"` is what you want.

    independent_gates : bool, optional
        Whether gates are allowed independent cloud noise or not.  If False,
        then all gates with the same name (e.g. "Gx") will have the *same*
        noise.  If True, then gates with the same name acting on different
        qubits may have different noise.

    sparse : bool, optional
        Whether the embedded Lindblad-parameterized gates within the constructed
        `nQubits`-qubit gates are sparse or not.

    errcomp_type : {"gates","errorgens"}
        How errors are composed when creating layer operations in the returned
        model.  `"gates"` means that the errors on multiple gates in a single
        layer are composed as separate and subsequent processes.  `"errorgens"`
        means that layer operations have the form `Composed(target, error)`
        where `target` is as above and `error` results from composing the idle
        and cloud-noise error *generators*, i.e. a map that acts as the
        exponentiated sum of error generators (ordering is irrelevant in
        this case).

    addIdleNoiseToAllGates: bool, optional
        Whether the global idle should be added as a factor following the
        ideal action of each of the non-idle gates when constructing layer
        operations.

    verbosity : int, optional
        An integer >= 0 dictating how must output to send to stdout.

    Returns
    -------
    CloudNoiseModel
    """
    # E.g. error_rates could == {'Gx': {('H','X'): 0.1, ('S','Y'): 0.2} } # Lindblad, b/c val is dict
    #                        or {'Gx': 0.1 } # Depolarization b/c val is a float
    #                        or {'Gx': (0.1,0.2,0.2) } # Pauli-Stochastic b/c val is a tuple
    # (same as those of a crosstalk-free model) PLUS additional ones which specify which
    # qubits the error operates (not necessarily the target qubits of the gate in question)
    # for example: { 'Gx:Q0': { ('H','X:Q1'): 0.01, ('S','XX:Q0,Q1'): 0.01} }

    #NOTE: to have "independent_gates=False" and specify error rates for "Gx" vs "Gx:Q0", we
    # need to have some ability to stencil a gate's cloud based on different target-qubits in
    # the qubit graph.
    printer = _VerbosityPrinter.build_printer(verbosity)

    if parameterization != "auto":
        raise NotImplementedError(("Future versions of pyGSTi may allow you to specify a non-automatic "
                                   "parameterization - for instance building DepolarizeOp objects "
                                   "instead of LindbladOps for depolarization errors."))

    if evotype == "auto":
        evotype = "densitymx"  # FUTURE: do something more sophisticated?

    if qubit_labels is None:
        qubit_labels = tuple(range(nQubits))

    qubit_dim = 2 if evotype in ('statevec', 'stabilizer') else 4
    if not isinstance(qubit_labels, _ld.StateSpaceLabels):  # allow user to specify a StateSpaceLabels object
        all_sslbls = _ld.StateSpaceLabels(qubit_labels, (qubit_dim,) * len(qubit_labels), evotype=evotype)
    else:
        all_sslbls = qubit_labels
        qubit_labels = [lbl for lbl in all_sslbls.labels[0] if all_sslbls.labeldims[lbl] == qubit_dim]
        #Only extract qubit labels from the first tensor-product block...

    if isinstance(geometry, _qgraph.QubitGraph):
        qubitGraph = geometry
    else:
        qubitGraph = _qgraph.QubitGraph.common_graph(nQubits, geometry, directed=True,
                                                     qubit_labels=qubit_labels, all_directions=True)
        printer.log("Created qubit graph:\n" + str(qubitGraph))

    nQubit_dim = 2**nQubits if evotype in ('statevec', 'stabilizer') else 4**nQubits

    orig_error_rates = error_rates.copy()
    cparser = _CircuitParser()
    cparser.lookup = None  # lookup - functionality removed as it wasn't used
    for k, v in orig_error_rates.items():
        if _compat.isstr(k) and ":" in k:  # then parse this to get a label, allowing, e.g. "Gx:0"
            lbls, _ = cparser.parse(k)
            assert(len(lbls) == 1), "Only single primitive-gate labels allowed as keys! (not %s)" % str(k)
            assert(all([sslbl in qubitGraph.get_node_names() for sslbl in lbls[0].sslbls])), \
                "One or more invalid qubit names in: %s" % k
            del error_rates[k]
            error_rates[lbls[0]] = v
        elif isinstance(k, _Lbl):
            if k.sslbls is not None:
                assert(all([sslbl in qubitGraph.get_node_names() for sslbl in k.sslbls])), \
                    "One or more invalid qubit names in the label: %s" % str(k)

    def _parameterization_from_errgendict(errs):
        paramtypes = []
        if any([nm[0] == 'H' for nm in errs]): paramtypes.append('H')
        if any([nm[0] == 'S' for nm in errs]): paramtypes.append('S')
        if any([nm[0] == 'A' for nm in errs]): paramtypes.append('A')
        if any([nm[0] == 'S' and isinstance(nm, tuple) and len(nm) == 3 for nm in errs]):
            # parameterization must be "CPTP" if there are any ('S',b1,b2) keys
            parameterization = "CPTP"
        else:
            parameterization = '+'.join(paramtypes)
        return parameterization

    def _map_stencil_sslbls(stencil_sslbls, target_lbls):  # deals with graph directions
        ret = [qubitGraph.resolve_relative_nodelabel(s, target_lbls) for s in stencil_sslbls]
        if any([x is None for x in ret]): return None  # signals there is a non-present dirs, e.g. end of chain
        return ret

    def create_error(target_labels, errs=None, stencil=None, return_what="auto"):  # err = an error rates dict
        """
        Create an error generator or error superoperator based on the error dictionary
        `errs`.  This function is used to construct error for SPAM and gate layer operations.

        Parameters
        ----------
        target_labels : tuple
            The target labels of the gate/primitive layer we're constructing an
            error for.  This is needed for knowing the size of the target op and
            for using "@" syntax within stencils.

        errs : dict
            A error-dictionary specifying what types of errors we need to construct.

        stencil : None or OrderedDict
            Instead of specifying `errs`, one can specify `stencil` to tell us how
            and *with what* to construct an error -- `stencil` will contain keys
            that are tuples of "stencil labels" and values which are error generators,
            specifying errors that occur on certain "real" qubits by mapping the
            stencil qubits to real qubits using `target_labels` as an anchor.

        return_what : {"auto", "stencil", "errmap", "errgen"}, optional
            What type of object should be returned.  "auto" causes either an
            "errmap" (a superoperator) or "errgen" (an error generator) to
            be selected based on the outside-scope value of `errcomp_type`.

        Returns
        -------
        LinearOperator or OrderedDict
            The former in the "errmap" and "errgen" cases, the latter in the
            "stencil" case.
        """
        target_nQubits = len(target_labels)

        if return_what == "auto":  # then just base return type on errcomp_type
            return_what == "errgen" if errcomp_type == "errorgens" else "errmap"

        assert(stencil is None or errs is None), "Cannot specify both `errs` and `stencil`!"

        if errs is None:
            if stencil is None:
                if return_what == "stencil":
                    new_stencil = _collections.OrderedDict()  # return an empty stencil
                    return new_stencil
                errgen = _op.ComposedErrorgen([], nQubit_dim, evotype)
            else:
                # stencil is valid: apply it to create errgen
                embedded_errgens = []
                for stencil_sslbls, lind_errgen in stencil.items():
                    # Note: stencil_sslbls should contain directions like "up" or integer indices of target qubits.
                    error_sslbls = _map_stencil_sslbls(stencil_sslbls, target_labels)  # deals with graph directions
                    if error_sslbls is None: continue  # signals not all direction were present => skip this term
                    op_to_embed = lind_errgen.copy() if independent_gates else lind_errgen  # copy for independent gates
                    #REMOVE print("DB: Applying stencil: ",all_sslbls, error_sslbls,op_to_embed.dim)
                    embedded_errgen = _op.EmbeddedErrorgen(all_sslbls, error_sslbls, op_to_embed)
                    embedded_errgens.append(embedded_errgen)
                errgen = _op.ComposedErrorgen(embedded_errgens, nQubit_dim, evotype)
        else:
            #We need to build a stencil (which may contain QubitGraph directions) or an effective stencil
            assert(stencil is None)  # checked by above assert too

            # distinct sets of qubits upon which a single (high-weight) error term acts:
            distinct_errorqubits = _collections.OrderedDict()
            if isinstance(errs, dict):  # either for creating a stencil or an error
                for nm, val in errs.items():
                    #REMOVE print("DB: Processing: ",nm, val)
                    if _compat.isstr(nm): nm = (nm[0], nm[1:])  # e.g. "HXX" => ('H','XX')
                    err_typ, basisEls = nm[0], nm[1:]
                    sslbls = None
                    local_nm = [err_typ]
                    for bel in basisEls:  # e.g. bel could be "X:Q0" or "XX:Q0,Q1"
                        #REMOVE print("Basis el: ",bel)
                        # OR "X:<n>" where n indexes a target qubit or "X:<dir>" where dir indicates
                        # a graph *direction*, e.g. "up"
                        if ':' in bel:
                            bel_name, bel_sslbls = bel.split(':')  # should have form <name>:<comma-separated-sslbls>
                            bel_sslbls = bel_sslbls.split(',')  # e.g. ('Q0','Q1')
                            integerized_sslbls = []
                            for ssl in bel_sslbls:
                                try: integerized_sslbls.append(int(ssl))
                                except: integerized_sslbls.append(ssl)
                            bel_sslbls = tuple(integerized_sslbls)
                        else:
                            bel_name = bel
                            bel_sslbls = target_labels
                        #REMOVE print("DB: Nm + sslbls: ",bel_name,bel_sslbls)

                        if sslbls is None:
                            sslbls = bel_sslbls
                        else:
                            #Note: sslbls should always be the same if there are multiple basisEls,
                            #  i.e for nm == ('S',bel1,bel2)
                            assert(sslbls == bel_sslbls), \
                                "All basis elements of the same error term must operate on the *same* state!"
                        local_nm.append(bel_name)  # drop the state space labels, e.g. "XY:Q0,Q1" => "XY"

                    # keep track of errors by the qubits they act on, as only each such
                    # set will have it's own LindbladErrorgen
                    sslbls = tuple(sorted(sslbls))
                    local_nm = tuple(local_nm)  # so it's hashable
                    if sslbls not in distinct_errorqubits:
                        distinct_errorqubits[sslbls] = _collections.OrderedDict()
                    if local_nm in distinct_errorqubits[sslbls]:
                        distinct_errorqubits[sslbls][local_nm] += val
                    else:
                        distinct_errorqubits[sslbls][local_nm] = val

            elif isinstance(errs, float):  # depolarization, action on only target qubits
                sslbls = tuple(range(target_nQubits)) if return_what == "stencil" else target_labels
                # Note: we use relative target indices in a stencil
                basis = _BuiltinBasis('pp', 4**target_nQubits)  # assume we always use Pauli basis?
                distinct_errorqubits[sslbls] = _collections.OrderedDict()
                perPauliRate = errs / len(basis.labels)
                for bl in basis.labels:
                    distinct_errorqubits[sslbls][('S', bl)] = perPauliRate
            else:
                raise ValueError("Invalid `error_rates` value: %s (type %s)" % (str(errs), type(errs)))

            new_stencil = _collections.OrderedDict()
            for error_sslbls, local_errs_for_these_sslbls in distinct_errorqubits.items():
                local_nQubits = len(error_sslbls)  # weight of this group of errors which act on the same qubits
                local_dim = 4**local_nQubits
                basis = _BuiltinBasis('pp', local_dim)  # assume we're always given basis els in a Pauli basis?

                #Sanity check to catch user errors that would be hard to interpret if they get caught further down
                for nm in local_errs_for_these_sslbls:
                    for bel in nm[1:]:  # bel should be a *local* (bare) basis el name, e.g. "XX" but not "XX:Q0,Q1"
                        if bel not in basis.labels:
                            raise ValueError("In %s: invalid basis element label `%s` where one of {%s} was expected" %
                                             (str(errs), str(bel), ', '.join(basis.labels)))

                parameterization = _parameterization_from_errgendict(local_errs_for_these_sslbls)
                #REMOVE print("DB: Param from ", local_errs_for_these_sslbls, " = ",parameterization)
                _, _, nonham_mode, param_mode = _op.LindbladOp.decomp_paramtype(parameterization)
                lind_errgen = _op.LindbladErrorgen(local_dim, local_errs_for_these_sslbls, basis, param_mode,
                                                   nonham_mode, truncate=False, mxBasis="pp", evotype=evotype)
                #REMOVE print("DB: Adding to stencil: ",error_sslbls,lind_errgen.dim,local_dim)
                new_stencil[error_sslbls] = lind_errgen

            if return_what == "stencil":  # then we just return the stencil, not the error map or generator
                return new_stencil

            #Use stencil to create error map or generator.  Here `new_stencil` is not a "true" stencil
            # in that it should contain only absolute labels (it wasn't created in stencil="create" mode)
            embedded_errgens = []
            for error_sslbls, lind_errgen in new_stencil.items():
                #Then use the stencils for these steps later (if independent errgens is False especially?)
                #REMOVE print("DB: Creating from stencil: ",all_sslbls, error_sslbls)
                embedded_errgen = _op.EmbeddedErrorgen(all_sslbls, error_sslbls, lind_errgen)
                embedded_errgens.append(embedded_errgen)
            errgen = _op.ComposedErrorgen(embedded_errgens, nQubit_dim, evotype)

        #If we get here, we've created errgen, which we either return or package into a map:
        if return_what == "errmap":
            return _op.LindbladOp(None, errgen, sparse_expm=sparse)
        else:
            return errgen

    #Process "auto" sim_type
    _, evotype = _gt.split_lindblad_paramtype(parameterization)  # what about "auto" parameterization?
    assert(evotype in ("densitymx", "svterm", "cterm")), "State-vector evolution types not allowed."
    if sim_type == "auto":
        if evotype in ("svterm", "cterm"): sim_type = "termorder:1"
        else: sim_type = "map" if nQubits > 2 else "matrix"
    assert(sim_type in ("matrix", "map") or sim_type.startswith("termorder"))

    #Global Idle
    if 'idle' in error_rates:
        printer.log("Creating Idle:")
        global_idle_layer = create_error(qubit_labels, error_rates['idle'], return_what="errmap")
    else:
        global_idle_layer = None

    #SPAM
    if 'prep' in error_rates:
        prepPure = _sv.ComputationalSPAMVec([0] * nQubits, evotype)
        prepNoiseMap = create_error(qubit_labels, error_rates['prep'], return_what="errmap")
        prep_layers = [_sv.LindbladSPAMVec(prepPure, prepNoiseMap, "prep")]
    else:
        prep_layers = [_sv.ComputationalSPAMVec([0] * nQubits, evotype)]

    if 'povm' in error_rates:
        povmNoiseMap = create_error(qubit_labels, error_rates['povm'], return_what="errmap")
        povm_layers = [_povm.LindbladPOVM(povmNoiseMap, None, "pp")]
    else:
        povm_layers = [_povm.ComputationalBasisPOVM(nQubits, evotype)]

    stencils = _collections.OrderedDict()

    def build_cloudnoise_fn(lbl):
        # lbl will be for a particular gate and target qubits.  If we have error rates for this specific gate
        # and target qubits (i.e this primitive layer op) then we should build it directly (and independently,
        # regardless of the value of `independent_gates`) using these rates.  Otherwise, if we have a stencil
        # for this gate, then we should use it to construct the output, using a copy when gates are independent
        # and a reference to the *same* stencil operations when `independent_gates==False`.
        if lbl in error_rates:
            return create_error(lbl.sslbls, errs=error_rates[lbl])  # specific instructions for this primitive layer
        elif lbl.name in stencils:
            return create_error(lbl.sslbls, stencil=stencils[lbl.name])  # use existing stencil
        elif lbl.name in error_rates:
            stencils[lbl.name] = create_error(lbl.sslbls, error_rates[lbl.name],
                                              return_what='stencil')  # create stencil
            return create_error(lbl.sslbls, stencil=stencils[lbl.name])  # and then use it
        else:
            return create_error(lbl, None)

    def build_cloudkey_fn(lbl):
        #FUTURE: Get a list of all the qubit labels `lbl`'s cloudnoise error touches and form this into a key
        # For now, we just punt and return a key based on the target labels
        cloud_key = tuple(lbl.sslbls)
        return cloud_key

    # gate_names => gatedict
    if custom_gates is None: custom_gates = {}
    if nonstd_gate_unitaries is None: nonstd_gate_unitaries = {}
    std_unitaries = _itgs.get_standard_gatename_unitaries()

    gatedict = _collections.OrderedDict()
    for name in gate_names:
        if name in custom_gates:
            gatedict[name] = custom_gates[name]
        else:
            U = nonstd_gate_unitaries.get(name, std_unitaries.get(name, None))
            if U is None: raise KeyError("'%s' gate unitary needs to be provided by `nonstd_gate_unitaries` arg" % name)
            if callable(U):  # then assume a function: args -> unitary
                U0 = U(None)  # U fns must return a sample unitary when passed None to get size.
                gatedict[name] = _opfactory.UnitaryOpFactory(U, U0.shape[0], evotype=evotype)
            else:
                gatedict[name] = _bt.change_basis(_gt.unitary_to_process_mx(U), "std", "pp")
                # assume evotype is a densitymx or term type

    #Add anything from custom_gates directly if it wasn't added already
    for lbl, gate in custom_gates.items():
        if lbl not in gate_names: gatedict[lbl] = gate

    return _CloudNoiseModel(nQubits, gatedict, availability, qubit_labels, geometry,
                            global_idle_layer, prep_layers, povm_layers,
                            build_cloudnoise_fn, build_cloudkey_fn,
                            sim_type, evotype, errcomp_type,
                            addIdleNoiseToAllGates, sparse, printer)


# -----------------------------------------------------------------------------------
#  nqnoise gate sequence construction methods
# -----------------------------------------------------------------------------------

#Note: these methods assume a Model with:
# Gx and Gy gates on each qubit that are pi/2 rotations
# a prep labeled "rho0"
# a povm labeled "Mdefault" - so effects labeled "Mdefault_N" for N=0->2^nQubits-1


def _onqubit(s, iQubit):
    """ Takes `s`, a tuple of gate *names* and creates a Circuit
        where those names act on the `iQubit`-th qubit """
    return _objs.Circuit([_Lbl(nm, iQubit) for nm in s])


def find_amped_polys_for_syntheticidle(qubit_filter, idleStr, model, singleQfiducials=None,
                                       prepLbl=None, effectLbls=None, initJ=None, initJrank=None,
                                       wrtParams=None, algorithm="greedy", require_all_amped=True,
                                       idtPauliDicts=None, comm=None, verbosity=0):
    """
    Find fiducial pairs which amplify the parameters of a synthetic idle gate.

    This routine is primarily used internally within higher-level n-qubit
    sequence selection routines.

    Parameters
    ----------
    qubit_filter : list
        A list specifying which qubits fiducial pairs should be placed upon.
        Typically this is a subset of all the qubits, as the synthetic idle
        is composed of nontrivial gates acting on a localized set of qubits
        and noise/errors are localized around these.

    idleStr : Circuit
        The operation sequence specifying the idle operation to consider.  This may
        just be a single idle gate, or it could be multiple non-idle gates
        which together act as an idle.

    model : Model
        The model used to compute the polynomial expressions of probabilities
        to first-order.  Thus, this model should always have (simulation)
        type "termorder:1".

    singleQfiducials : list, optional
        A list of gate-name tuples (e.g. `('Gx',)`) which specify a set of single-
        qubit fiducials to use when trying to amplify gate parameters.  Note that
        no qubit "state-space" label is required here (i.e. *not* `(('Gx',1),)`);
        the tuples just contain single-qubit gate *names*.  If None, then
        `[(), ('Gx',), ('Gy',)]` is used by default.

    prepLbl : Label, optional
        The state preparation label to use.  If None, then the first (and
        usually the only) state prep label of `model` is used, so it's
        usually fine to leave this as None.

    effectLbls : list, optional
        The list of POVM effect labels to use, as a list of `Label` objects.
        These are *simplified* POVM effect labels, so something like "Mdefault_0",
        and if None the default is all the effect labels of the first POVM of
        `model`, which is usually what you want.

    initJ : numpy.ndarray, optional
        An initial Jacobian giving the derivatives of some other polynomials
        with respect to the same `wrtParams` that this function is called with.
        This acts as a starting point, and essentially informs the fiducial-pair
        selection algorithm that some parameters (or linear combos of them) are
        *already* amplified (e.g. by some other germ that's already been
        selected) and for which fiducial pairs are not needed.

    initJrank : int, optional
        The rank of `initJ`.  The function could compute this from `initJ`
        but in practice one usually has the rank of `initJ` lying around and
        so this saves a call to `np.linalg.matrix_rank`.

    wrtParams : slice, optional
        The parameters to consider for amplification.  (This function seeks
        fiducial pairs that amplify these parameters.)  If None, then pairs
        which amplify all of `model`'s parameters are searched for.

    algorithm : {"greedy","sequential"}
        Which algorithm is used internally to find fiducial pairs.  "greedy"
        will give smaller sets of fiducial pairs (better) but takes longer.
        Usually it's worth the wait and you should use the default ("greedy").

    require_all_amped : bool, optional
        If True and AssertionError is raised when fewer than all of the
        requested parameters (in `wrtParams`) are amplifed by the final set of
        fiducial pairs.

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.


    Returns
    -------
    J : numpy.ndarray
        The final jacobian with rows equal to the number of chosen amplified
        polynomials (note there is one row per fiducial pair *including* the
        outcome - so there will be two different rows for two different
        outcomes) and one column for each parameter specified by `wrtParams`.

    Jrank : int
        The rank of the jacobian `J`, equal to the number of amplified
        parameters (at most the number requested).

    fidpair_lists : list
        The selected fiducial pairs, each in "gatename-fidpair-list" format.
        Elements of `fidpair_lists` are themselves lists, all of length=#qubits.
        Each element of these lists is a (prep1Qnames, meas1Qnames) 2-tuple
        specifying the 1-qubit gates (by *name* only) on the corresponding qubit.
        For example, the single fiducial pair prep=Gx:1Gy:2, meas=Gx:0Gy:0 in a
        3-qubit system would have `fidpair_lists` equal to:
        `[ [ [(),('Gx','Gy')], [('Gx',), ()   ], [('Gy',), ()   ] ] ]`
        `    < Q0 prep,meas >, < Q1 prep,meas >, < Q2 prep,meas >`
    """
    #Note: "useful" fiducial pairs are identified by looking at the rank of a
    # Jacobian matrix.  Each row of this Jacobian is the derivative of the
    # "amplified polynomial" - the L=1 polynomial for a fiducial pair (i.e.
    # pr_poly(F1*(germ)*F2) ) minus the L=0 polynomial (i.e. pr_poly(F1*F2) ).
    # When the model only gives probability polynomials to first order in
    # the error rates this gives the L-dependent and hence amplified part
    # of the polynomial expression for the probability of F1*(germ^L)*F2.
    # This derivative of an amplified polynomial, taken with respect to
    # all the parameters we care about (i.e. wrtParams) would ideally be
    # kept as a polynomial and the "rank" of J would be the number of
    # linearly independent polynomials within the rows of J (each poly
    # would be a vector in the space of polynomials).  We currently take
    # a cheap/HACK way out and evaluate the derivative-polynomial at a
    # random dummy value which should yield linearly dependent vectors
    # in R^n whenever the polynomials are linearly indepdendent - then
    # we can use the usual scipy/numpy routines for computing a matrix
    # rank, etc.

    # Assert that model uses termorder:1, as doing L1-L0 to extract the "amplified" part
    # relies on only expanding to *first* order.
    assert(model._sim_type == "termorder" and model._sim_args[0] == '1'), \
        '`model` must use "termorder:1" simulation type!'

    printer = _VerbosityPrinter.build_printer(verbosity, comm)

    if prepLbl is None:
        prepLbl = model._shlp.get_default_prep_lbl()
    if effectLbls is None:
        povmLbl = model._shlp.get_default_povm_lbl()
        effectLbls = [_Lbl("%s_%s" % (povmLbl, l))
                      for l in model._shlp.get_effect_labels_for_povm(povmLbl)]
    if singleQfiducials is None:
        # TODO: assert model has Gx and Gy gates?
        singleQfiducials = [(), ('Gx',), ('Gy',)]  # ('Gx','Gx')

    #dummy = 0.05*_np.ones(model.num_params(),'d') # for evaluating derivs...
    #dummy = 0.05*_np.arange(1,model.num_params()+1) # for evaluating derivs...
    #dummy = 0.05*_np.random.random(model.num_params())
    dummy = 5.0 * _np.random.random(model.num_params()) + 0.5 * _np.ones(model.num_params(), 'd')
    # expect terms to be either coeff*x or coeff*x^2 - (b/c of latter case don't eval at zero)

    #amped_polys = []
    selected_gatename_fidpair_lists = []
    if wrtParams is None: wrtParams = slice(0, model.num_params())
    Np = _slct.length(wrtParams)
    if initJ is None:
        J = _np.empty((0, Np), 'complex'); Jrank = 0
    else:
        J = initJ; Jrank = initJrank

    if algorithm == "greedy":
        Jrows = _np.empty((len(effectLbls), Np), 'complex')

    #Outer iteration
    while Jrank < Np:

        if algorithm == "sequential":
            printer.log("Sequential find_amped_polys_for_syntheticidle started. Target rank=%d" % Np)
            assert(comm is None), "No MPI support for algorithm='sequential' case!"

        elif algorithm == "greedy":
            maxRankInc = 0
            bestJrows = None
            printer.log("Greedy find_amped_polys_for_syntheticidle started. Target rank=%d" % Np)

        else: raise ValueError("Invalid `algorithm` argument: %s" % algorithm)

        # loop over all possible (remaining) fiducial pairs
        nQubits = len(qubit_filter)
        loc_Indices, _, _ = _mpit.distribute_indices(
            list(range(len(singleQfiducials)**nQubits)), comm, False)
        loc_itr = 0; nLocIters = len(loc_Indices)
        #print("DB: Rank %d indices = " % comm.Get_rank(), loc_Indices)

        with printer.progress_logging(2):
            for itr, prep in enumerate(_itertools.product(*([singleQfiducials] * nQubits))):
                # There's probably a cleaner way to do this,
                if loc_itr < len(loc_Indices) and itr == loc_Indices[loc_itr]:
                    loc_itr += 1  # but this limits us to this processor's local indices
                else:
                    continue
                #print("DB: Rank %d: running itr=%d" % (comm.Get_rank(), itr))

                printer.show_progress(loc_itr, nLocIters, prefix='--- Finding amped-polys for idle: ')
                prepFid = _objs.Circuit(())
                for i, el in enumerate(prep):
                    prepFid = prepFid + _onqubit(el, qubit_filter[i])

                for meas in _itertools.product(*([singleQfiducials] * nQubits)):

                    if idtPauliDicts is not None:
                        # For idle tomography compatibility, only consider fiducial pairs with either
                        # all-the-same or all-different prep & measure basis (basis is determined
                        # by the *last* letter in the value, e.g. ignore '-' sign in '-X').
                        prepDict, measDict = idtPauliDicts
                        rev_prepDict = {v[-1]: k for k, v in prepDict.items()}  # could do this once above,
                        rev_measDict = {v[-1]: k for k, v in measDict.items()}  # but this isn't the bottleneck.
                        cmp = [(rev_prepDict[prep[kk]] == rev_measDict[meas[kk]]) for kk in range(nQubits)]
                        # if all are not the same or all are not different, skip
                        if not (all(cmp) or not any(cmp)): continue

                    measFid = _objs.Circuit(())
                    for i, el in enumerate(meas):
                        measFid = measFid + _onqubit(el, qubit_filter[i])

                    gatename_fidpair_list = [(prep[i], meas[i]) for i in range(nQubits)]
                    if gatename_fidpair_list in selected_gatename_fidpair_lists:
                        continue  # we've already chosen this pair in a previous iteration

                    gstr_L0 = prepFid + measFid            # should be a Circuit
                    gstr_L1 = prepFid + idleStr + measFid  # should be a Circuit
                    ps = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L1)
                    qs = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L0)

                    if algorithm == "sequential":
                        added = False
                        for elbl, p, q in zip(effectLbls, ps, qs):
                            amped = p + -1 * q  # the amplified poly
                            Jrow = _np.array([[amped.deriv(iParam).evaluate(dummy)
                                               for iParam in _slct.as_array(wrtParams)]])
                            if _np.linalg.norm(Jrow) < 1e-8: continue  # row of zeros can fool matrix_rank

                            Jtest = _np.concatenate((J, Jrow), axis=0)
                            testRank = _np.linalg.matrix_rank(Jtest, tol=RANK_TOL)
                            if testRank > Jrank:
                                printer.log("fidpair: %s,%s (%s) increases rank => %d" %
                                            (str(prep), str(meas), str(elbl), testRank), 4)
                                J = Jtest
                                Jrank = testRank
                                if not added:
                                    selected_gatename_fidpair_lists.append(gatename_fidpair_list)
                                    added = True  # only add fidpair once per elabel loop!
                                if Jrank == Np: break  # this is the largest rank J can take!

                    elif algorithm == "greedy":
                        #test adding all effect labels - get the overall increase in rank due to this fidpair
                        for k, (elbl, p, q) in enumerate(zip(effectLbls, ps, qs)):
                            amped = p + -1 * q  # the amplified poly
                            Jrows[k, :] = _np.array([[amped.deriv(iParam).evaluate(dummy)
                                                      for iParam in _slct.as_array(wrtParams)]])
                        Jtest = _np.concatenate((J, Jrows), axis=0)
                        testRank = _np.linalg.matrix_rank(Jtest, tol=RANK_TOL)
                        rankInc = testRank - Jrank
                        if rankInc > maxRankInc:
                            maxRankInc = rankInc
                            bestJrows = Jrows.copy()
                            bestFidpair = gatename_fidpair_list
                            if testRank == Np: break  # this is the largest rank we can get!

        if algorithm == "greedy":
            # get the best of the bestJrows, bestFidpair, and maxRankInc
            if comm is not None:
                maxRankIncs_per_rank = comm.allgather(maxRankInc)
                iWinningRank = maxRankIncs_per_rank.index(max(maxRankIncs_per_rank))
                maxRankInc = maxRankIncs_per_rank[iWinningRank]
                if comm.Get_rank() == iWinningRank:
                    comm.bcast(bestJrows, root=iWinningRank)
                    comm.bcast(bestFidpair, root=iWinningRank)
                else:
                    bestJrows = comm.bcast(None, root=iWinningRank)
                    bestFidpair = comm.bcast(None, root=iWinningRank)

            if require_all_amped:
                assert(maxRankInc > 0), "No fiducial pair increased the Jacobian rank!"
            Jrank += maxRankInc
            J = _np.concatenate((J, bestJrows), axis=0)
            selected_gatename_fidpair_lists.append(bestFidpair)
            printer.log("%d fidpairs => rank %d (Np=%d)" %
                        (len(selected_gatename_fidpair_lists), Jrank, Np))

    #DEBUG
    #print("DB: J = ")
    #_gt.print_mx(J)
    #print("DB: svals of J for synthetic idle: ", _np.linalg.svd(J, compute_uv=False))

    return J, Jrank, selected_gatename_fidpair_lists


def test_amped_polys_for_syntheticidle(fidpairs, idleStr, model, prepLbl=None, effectLbls=None,
                                       wrtParams=None, verbosity=0):
    """
    Compute the number of model parameters amplified by a given (synthetic)
    idle sequence.

    Parameters
    ----------
    fidpairs : list
        A list of `(prep,meas)` 2-tuples, where `prep` and `meas` are
        :class:`Circuit` objects, specifying the fiducial pairs to test.

    idleStr : Circuit
        The operation sequence specifying the idle operation to consider.  This may
        just be a single idle gate, or it could be multiple non-idle gates
        which together act as an idle.

    model : Model
        The model used to compute the polynomial expressions of probabilities
        to first-order.  Thus, this model should always have (simulation)
        type "termorder:1".

    prepLbl : Label, optional
        The state preparation label to use.  If None, then the first (and
        usually the only) state prep label of `model` is used, so it's
        usually fine to leave this as None.

    effectLbls : list, optional
        The list of POVM effect labels to use, as a list of `Label` objects.
        These are *simplified* POVM effect labels, so something like "Mdefault_0",
        and if None the default is all the effect labels of the first POVM of
        `model`, which is usually what you want.

    wrtParams : slice, optional
        The parameters to consider for amplification.  If None, then pairs
        which amplify all of `model`'s parameters are searched for.

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.

    Returns
    -------
    nAmplified : int
        The number of parameters amplified.

    nTotal : int
        The total number of parameters considered for amplification.
    """
    #Assert that model uses termorder:1, as doing L1-L0 to extract the "amplified" part
    # relies on only expanding to *first* order.
    assert(model._sim_type == "termorder" and model._sim_args[0] == '1'), \
        '`model` must use "termorder:1" simulation type!'

    # printer = _VerbosityPrinter.build_printer(verbosity)

    if prepLbl is None:
        prepLbl = model._shlp.get_default_prep_lbl()
    if effectLbls is None:
        povmLbl = model._shlp.get_default_povm_lbl()
        effectLbls = [_Lbl("%s_%s" % (povmLbl, l)) for l in model._shlp.get_effect_labels_for_povm(povmLbl)]
    dummy = 5.0 * _np.random.random(model.num_params()) + 0.5 * _np.ones(model.num_params(), 'd')

    if wrtParams is None: wrtParams = slice(0, model.num_params())
    Np = _slct.length(wrtParams)
    nEffectLbls = len(effectLbls)
    nRows = len(fidpairs) * nEffectLbls  # number of jacobian rows
    J = _np.empty((nRows, Np), 'complex')

    for i, (prepFid, measFid) in enumerate(fidpairs):
        gstr_L0 = prepFid + measFid            # should be a Circuit
        gstr_L1 = prepFid + idleStr + measFid  # should be a Circuit
        ps = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L1)
        qs = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L0)

        for k, (elbl, p, q) in enumerate(zip(effectLbls, ps, qs)):
            amped = p + -1 * q  # the amplified poly
            Jrow = _np.array([[amped.deriv(iParam).evaluate(dummy) for iParam in _slct.as_array(wrtParams)]])
            J[i * nEffectLbls + k, :] = Jrow

    rank = _np.linalg.matrix_rank(J, tol=RANK_TOL)
    #print("Rank = %d, num params = %d" % (rank, Np))
    return rank, Np


def find_amped_polys_for_clifford_syntheticidle(qubit_filter, core_filter, trueIdlePairs, idleStr, maxWt,
                                                model, singleQfiducials=None,
                                                prepLbl=None, effectLbls=None, initJ=None, initJrank=None,
                                                wrtParams=None, verbosity=0):
    """
    Similar to :function:`find_amped_polys_for_syntheticidle` but
    specialized to "qubit cloud" processing case used in higher-level
    functions and assumes that `idleStr` is composed of Clifford gates only
    which act on a "core" of qubits (given by `core_filter`).

    In particular, we assume that we already know the fiducial pairs needed
    to amplify all the errors of a "true" (non-synthetic) idle on various
    number of qubits (i.e. max-weights of idle error).  Furthermore, we
    assume that the errors found by these true-idle fiducial pairs are
    of the same kind as those afflicting the synthetic idle, so that
    by restricting our search to just certain true-idle pairs we're able
    to amplify all the parameters of the synthetic idle.

    Because of these assumptions and pre-computed information, this
    function often takes considerably less time to run than
    :function:`find_amped_polys_for_syntheticidle`.


    Parameters
    ----------
    qubit_filter : list
        A list specifying which qubits fiducial pairs should be placed upon.
        Typically this is a subset of all the qubits, as the synthetic idle
        is composed of nontrivial gates acting on a localized set of qubits
        and noise/errors are localized around these.  Within the "cloud"
        picture, `qubit_filter` specifies *all* the qubits in the cloud, not
        just the "core".

    core_filter : list
        A list specifying the "core" qubits - those which the non-idle
        gates within `idleStr` ideally act upon.  This is often a proper subset
        of `qubit_filter` since errors are allowed on qubits which neighbor
        the core qubits in addition to the core qubits themselves.

    trueIdlePairs : dict
        A dictionary whose keys are integer max-weight values and whose values
        are lists of fiducial pairs, each in "gatename-fidpair-list" format,
        whcih give the fiducial pairs needed to amplify all the parameters of
        a non-synthetic idle gate on max-weight qubits.

    idleStr : Circuit
        The operation sequence specifying the idle operation to consider.  This may
        just be a single idle gate, or it could be multiple non-idle gates
        which together act as an idle.

    maxWt : int
        The maximum weight such that the pairs given by `trueIdlePairs[maxWt]`
        will amplify all the possible errors on `idleStr`.  This must account
        for the fact that the nontrivial comprising `idleStr` may increase the
        weight of errors.  For instance if `idleStr` contains CNOT gates
        on qubits 0 and 1 (the "core") and the noise model allows insertion of
        up to weight-2 errors at any location, then a single weight-2 error
        (recall termorder:1 means there can be only 1 error per circuit) on
        qubits 1 and 2 followed by a CNOT on 0 and 1 could yield an weight-3
        error on qubits 0,1, and 2.

    model : Model
        The model used to compute the polynomial expressions of probabilities
        to first-order.  Thus, this model should always have (simulation)
        type "termorder:1".

    singleQfiducials : list, optional
        A list of gate-name tuples (e.g. `('Gx',)`) which specify a set of single-
        qubit fiducials to use when trying to amplify gate parameters.  Note that
        no qubit "state-space" label is required here (i.e. *not* `(('Gx',1),)`);
        the tuples just contain single-qubit gate *names*.  If None, then
        `[(), ('Gx',), ('Gy',)]` is used by default.

    prepLbl : Label, optional
        The state preparation label to use.  If None, then the first (and
        usually the only) state prep label of `model` is used, so it's
        usually fine to leave this as None.

    effectLbls : list, optional
        The list of POVM effect labels to use, as a list of `Label` objects.
        These are *simplified* POVM effect labels, so something like "Mdefault_0",
        and if None the default is all the effect labels of the first POVM of
        `model`, which is usually what you want.

    initJ : numpy.ndarray, optional
        An initial Jacobian giving the derivatives of some other polynomials
        with respect to the same `wrtParams` that this function is called with.
        This acts as a starting point, and essentially informs the fiducial-pair
        selection algorithm that some parameters (or linear combos of them) are
        *already* amplified (e.g. by some other germ that's already been
        selected) and for which fiducial pairs are not needed.

    initJrank : int, optional
        The rank of `initJ`.  The function could compute this from `initJ`
        but in practice one usually has the rank of `initJ` lying around and
        so this saves a call to `np.linalg.matrix_rank`.

    wrtParams : slice, optional
        The parameters to consider for amplification.  (This function seeks
        fiducial pairs that amplify these parameters.)  If None, then pairs
        which amplify all of `model`'s parameters are searched for.

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.


    Returns
    -------
    J : numpy.ndarray
        The final jacobian with rows equal to the number of chosen amplified
        polynomials (note there is one row per fiducial pair *including* the
        outcome - so there will be two different rows for two different
        outcomes) and one column for each parameter specified by `wrtParams`.

    Jrank : int
        The rank of the jacobian `J`, equal to the number of amplified
        parameters (at most the number requested).

    fidpair_lists : list
        The selected fiducial pairs, each in "gatename-fidpair-list" format.
        See :function:`find_amped_polys_for_syntheticidle` for details.
    """

    #Assert that model uses termorder:1, as doing L1-L0 to extract the "amplified" part
    # relies on only expanding to *first* order.
    assert(model._sim_type == "termorder" and model._sim_args[0] == '1'), \
        '`model` must use "termorder:1" simulation type!'

    printer = _VerbosityPrinter.build_printer(verbosity)

    if prepLbl is None:
        prepLbl = model._shlp.get_default_prep_lbl()
    if effectLbls is None:
        povmLbl = model._shlp.get_default_povm_lbl()
        effectLbls = [_Lbl("%s_%s" % (povmLbl, l)) for l in model._shlp.get_effect_labels_for_povm(povmLbl)]
    if singleQfiducials is None:
        # TODO: assert model has Gx and Gy gates?
        singleQfiducials = [(), ('Gx',), ('Gy',)]  # ('Gx','Gx')

    #dummy = 0.05*_np.ones(model.num_params(),'d') # for evaluating derivs...
    #dummy = 0.05*_np.arange(1,model.num_params()+1) # for evaluating derivs...
    #dummy = 0.05*_np.random.random(model.num_params())
    dummy = 5.0 * _np.random.random(model.num_params()) + 0.5 * _np.ones(model.num_params(), 'd')
    # expect terms to be either coeff*x or coeff*x^2 - (b/c of latter case don't eval at zero)

    #amped_polys = []
    selected_gatename_fidpair_lists = []
    if wrtParams is None: wrtParams = slice(0, model.num_params())
    Np = _slct.length(wrtParams)
    if initJ is None:
        J = _np.empty((0, Np), 'complex'); Jrank = 0
    else:
        J = initJ; Jrank = initJrank

    # We presume that we know the fiducial pairs
    #  needed to amplify all "true-idle" errors *of the same
    #  type that are on this synthetic idle* (i.e. H+S
    #  or full LND) up to some weight.  If we also assume
    #  the core-action is Clifford (i.e. maps Paulis->Paulis)
    #  then these same fiducial pairs that find the amplifiable
    #  params of a true idle with up to weight-maxWt terms will
    #  also find all the  amplifiable parameters of the synthetic
    #  idle, with the caveat that the maxWt must account for the
    #  weight-increasing potential of the non-trivial Clifford
    #  action.

    nQubits = len(qubit_filter)
    # nCore = len(core_filter)

    #Tile idle_fidpairs for maxWt onto nQubits
    # (similar to tile_idle_fidpairs(...) but don't need to convert to circuits?)
    tmpl = get_kcoverage_template(nQubits, maxWt)
    idle_gatename_fidpair_lists = trueIdlePairs[maxWt]
    #print("IDLE GFP LISTS = ",idle_gatename_fidpair_lists)

    gatename_fidpair_lists = []
    for gatename_fidpair_list in idle_gatename_fidpair_lists:
        # replace 0..(k-1) in each template string with the corresponding
        # gatename_fidpair (acts on the single qubit identified by the
        # its index within the template string), then convert to a Circuit/Circuit
        gfp = []
        for tmpl_row in tmpl:
            #mod_tmpl_row = tmpl_row[:]
            #for ql in core_filter: mod_tmpl_row[qubit_filter.index(ql)] = 0 # zero out to remove duplicates on non-core
            instance_row = [gatename_fidpair_list[i] for i in tmpl_row]

            gfp.append(tuple(instance_row))

        gatename_fidpair_lists.extend(gfp)
        # tuple so it can be hashed in remove_duplicates
    _lt.remove_duplicates_in_place(gatename_fidpair_lists)
    ##print("GFP LISTS (nQ=%d) = " % nQubits,gatename_fidpair_lists)
    #printer.log("Testing %d fidpairs for %d-wt idle -> %d after %dQ tiling -> %d w/free %d core (vs %d)"
    #            % (len(idle_gatename_fidpair_lists), maxWt, len(gatename_fidpair_lists),
    #               nQubits, len(gatename_fidpair_lists)*(3**(2*nCore)), nCore, 3**(2*nQubits)))
    #print("DB: over %d qubits -> template w/%d els" % (nQubits, len(tmpl)))
    printer.log("Testing %d fidpairs for %d-wt idle -> %d fidpairs after tiling onto %d qubits"
                % (len(idle_gatename_fidpair_lists), maxWt, len(gatename_fidpair_lists), nQubits))

    for gfp_list in gatename_fidpair_lists:
        # # replace 0..(k-1) in each template string with the corresponding
        # # gatename_fidpair (acts on the single qubit identified by the
        # # its index within the template string), then convert to a Circuit
        # tmpl_instance = [ [gatename_fidpair_list[i] for i in tmpl_row]  for tmpl_row in tmpl ]
        # for gfp_list in tmpl_instance: # circuit-fiducialpair list: one (gn-prepstr,gn-measstr) per qubit

        prep = tuple((gfp_list[i][0] for i in range(nQubits)))  # just the prep-part (OLD prep_noncore)
        meas = tuple((gfp_list[i][1] for i in range(nQubits)))  # just the meas-part (OLD meas_noncore)

        #OLD: back when we tried iterating over *all* core fiducial pairs
        # (now we think/know this is unnecessary - the "true idle" fidpairs suffice)
        #for prep_core in _itertools.product(*([singleQfiducials]*nCore) ):
        #
        #    #construct prep, a gatename-string, from prep_noncore and prep_core
        #    prep = list(prep_noncore)
        #    for i,core_ql in enumerate(core_filter):
        #        prep[ qubit_filter.index(core_ql) ] = prep_core[i]
        #    prep = tuple(prep)

        prepFid = _objs.Circuit(())
        for i, el in enumerate(prep):
            prepFid = prepFid + _onqubit(el, qubit_filter[i])

        #OLD: back when we tried iterating over *all* core fiducial pairs
        # (now we think/know this is unnecessary - the "true idle" fidpairs suffice)
        #    for meas_core in [0]: # DEBUG _itertools.product(*([singleQfiducials]*nCore) ):
        #
        #        #construct meas, a gatename-string, from meas_noncore and meas_core
        #        meas = list(meas_noncore)
        #        #for i,core_ql in enumerate(core_filter):
        #        #    meas[ qubit_filter.index(core_ql) ] = meas_core[i]
        #        meas = tuple(meas)

        measFid = _objs.Circuit(())
        for i, el in enumerate(meas):
            measFid = measFid + _onqubit(el, qubit_filter[i])

        #print("PREPMEAS = ",prepFid,measFid)

        gstr_L0 = prepFid + measFid            # should be a Circuit
        gstr_L1 = prepFid + idleStr + measFid  # should be a Circuit
        ps = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L1)
        qs = model._fwdsim().prs_as_polys(prepLbl, effectLbls, gstr_L0)
        added = False
        for elbl, p, q in zip(effectLbls, ps, qs):
            amped = p + -1 * q  # the amplified poly
            Jrow = _np.array([[amped.deriv(iParam).evaluate(dummy) for iParam in _slct.as_array(wrtParams)]])
            if _np.linalg.norm(Jrow) < 1e-8: continue  # row of zeros can fool matrix_rank

            Jtest = _np.concatenate((J, Jrow), axis=0)
            testRank = _np.linalg.matrix_rank(Jtest, tol=RANK_TOL)
            #print("find_amped_polys_for_syntheticidle: ",prep,meas,elbl," => rank ",testRank, " (Np=",Np,")")
            if testRank > Jrank:
                J = Jtest
                Jrank = testRank
                if not added:
                    gatename_fidpair_list = [(prep[i], meas[i]) for i in range(nQubits)]
                    selected_gatename_fidpair_lists.append(gatename_fidpair_list)
                    added = True  # only add fidpair once per elabel loop!
                if Jrank == Np: break  # this is the largest rank J can take!

    #DEBUG
    #print("DB: J = (wrt = ",wrtParams,")")
    #_mt.print_mx(J,width=4,prec=1)
    #print("DB: svals of J for synthetic idle: ", _np.linalg.svd(J, compute_uv=False))

    return J, Jrank, selected_gatename_fidpair_lists


def get_fidpairs_needed_to_access_amped_polys(qubit_filter, core_filter, germPowerStr, amped_polyJ,
                                              idle_gatename_fidpair_lists, model,
                                              singleQfiducials=None, prepLbl=None, effectLbls=None,
                                              wrtParams=None, verbosity=0):
    """
    Computes the fiducial pairs needed to amplify the known-amplifiable
    polynomials corresponding to fiducialpair+germ probabilities.

    This function works within the "cloud" picture of a core of qubits where
    there is nontrivial *ideal* action and a larger set of qubits upon which
    errors may exist.

    This function is used to find, after we know which directions in parameter
    -space are amplifiable by a germ (via analyzing its synthetic idle
    counterpart), which fiducial pairs are needed to amplify these directions
    when a non-synthetic-idle power of the germ is used.

    Parameters
    ----------
    qubit_filter : list
        A list specifying which qubits fiducial pairs should be placed upon.
        Typically this is a subset of all the qubits, and a "cloud" around
        the qubits being ideally acted upon.

    core_filter : list
        A list specifying the "core" qubits - those which the gates in
        `germPowerStr` ideally act upon.  This is often a proper subset
        of `qubit_filter` since errors are allowed on qubits which neighbor
        the core qubits in addition to the core qubits themselves.

    germPowerStr : Circuit
        The (non-synthetic-idle) germ power string under consideration.

    amped_polyJ : numpy.ndarray
        A jacobian matrix whose rowspace gives the space of amplifiable
        parameters.  The shape of this matrix is `(Namplified, Np)`, where
        `Namplified` is the number of independent amplified parameters and
        `Np` is the total number of parameters under consideration (the
        length of `wrtParams`).  This function seeks to find fiducial pairs
        which amplify this same space of parameters.

    idle_gatename_fidpair_lists : list
        A list of the fiducial pairs which amplify the entire space given
        by `amped_polyJ` for the germ when it is repeated enough to be a
        synthetic idle.  The strategy for finding fiducial pairs in the
        present case it to just monkey with the *core-qubit* parts of the
        *measurement* idle fiducials (non-core qubits are ideally the idle,
        and one can either modify the prep or the measure to "catch" what
        the non-idle `germPowerStr` does to the amplified portion of the
        state space).

    model : Model
        The model used to compute the polynomial expressions of probabilities
        to first-order.  Thus, this model should always have (simulation)
        type "termorder:1".

    singleQfiducials : list, optional
        A list of gate-name tuples (e.g. `('Gx',)`) which specify a set of single-
        qubit fiducials to use when trying to amplify gate parameters.  Note that
        no qubit "state-space" label is required here (i.e. *not* `(('Gx',1),)`);
        the tuples just contain single-qubit gate *names*.  If None, then
        `[(), ('Gx',), ('Gy',)]` is used by default.

    prepLbl : Label, optional
        The state preparation label to use.  If None, then the first (and
        usually the only) state prep label of `model` is used, so it's
        usually fine to leave this as None.

    effectLbls : list, optional
        The list of POVM effect labels to use, as a list of `Label` objects.
        These are *simplified* POVM effect labels, so something like "Mdefault_0",
        and if None the default is all the effect labels of the first POVM of
        `model`, which is usually what you want.

    wrtParams : slice, optional
        The parameters being considered for amplification.  (This should be
        the same as that used to produce `idle_gatename_fidpair_lists`).

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.

    Returns
    -------
    fidpair_lists : list
        The selected fiducial pairs, each in "gatename-fidpair-list" format.
        See :function:`find_amped_polys_for_syntheticidle` for details.
    """
    printer = _VerbosityPrinter.build_printer(verbosity)

    if prepLbl is None:
        prepLbl = model._shlp.get_default_prep_lbl()
    if effectLbls is None:
        povmLbl = model._shlp.get_default_povm_lbl()
        effectLbls = model._shlp.get_effect_labels_for_povm(povmLbl)
    if singleQfiducials is None:
        # TODO: assert model has Gx and Gy gates?
        singleQfiducials = [(), ('Gx',), ('Gy',)]  # ('Gx','Gx')

    #dummy = 0.05*_np.ones(model.num_params(),'d') # for evaluating derivs...
    #dummy = 0.05*_np.arange(1,model.num_params()+1) # for evaluating derivs...
    dummy = 5.0 * _np.random.random(model.num_params()) + 0.5 * _np.ones(model.num_params(), 'd')
    # expect terms to be either coeff*x or coeff*x^2 - (b/c of latter case don't eval at zero)

    #OLD: selected_fidpairs = []
    gatename_fidpair_lists = []
    if wrtParams is None: wrtParams = slice(0, model.num_params())
    Np = _slct.length(wrtParams)
    Namped = amped_polyJ.shape[0]; assert(amped_polyJ.shape[1] == Np)
    J = _np.empty((0, Namped), 'complex'); Jrank = 0

    #loop over all possible fiducial pairs
    nQubits = len(qubit_filter)
    nCore = len(core_filter)

    # we already know the idle fidpair preps are almost sufficient
    # - we just *may* need to modify the measure (or prep, but we choose
    #   the measure) fiducial on *core* qubits (with nontrivial base action)

    #OLD
    #idle_preps = [ tuple( (gfp_list[i][0] for i in range(nQubits)) )
    #          for gfp_list in idle_gatename_fidpair_lists ] # just the prep-part
    #_lt.remove_duplicates_in_place(idle_preps)

    printer.log("Testing %d fidpairs for idle -> %d seqs w/free %d core (vs %d)"
                % (len(idle_gatename_fidpair_lists),
                   len(idle_gatename_fidpair_lists) * (3**(nCore)), nCore,
                   3**(2 * nQubits)))

    already_tried = set()
    cores = [None] + list(_itertools.product(*([singleQfiducials] * nCore)))
    # try *no* core insertion at first - leave as idle - before going through them...

    for prep_core in cores:  # weird loop order b/c we don't expect to need this one
        if prep_core is not None:  # I don't think this *should* happen
            _warnings.warn(("Idle's prep fiducials only amplify %d of %d"
                            " directions!  Falling back to vary prep on core")
                           % (Jrank, Namped))

        for gfp_list in idle_gatename_fidpair_lists:
            #print("GFP list = ",gfp_list)
            prep_noncore = tuple((gfp_list[i][0] for i in range(nQubits)))  # just the prep-part
            meas_noncore = tuple((gfp_list[i][1] for i in range(nQubits)))  # just the meas-part

            if prep_core is None:
                prep = prep_noncore  # special case where we try to leave it unchanged.
            else:
                # construct prep, a gatename-string, from prep_noncore and prep_core
                prep = list(prep_noncore)
                for i, core_ql in enumerate(core_filter):
                    prep[qubit_filter.index(core_ql)] = prep_core[i]
                prep = tuple(prep)

            prepFid = _objs.Circuit(())
            for i, el in enumerate(prep):
                prepFid = prepFid + _onqubit(el, qubit_filter[i])

            #for meas in _itertools.product(*([singleQfiducials]*nQubits) ):
            #for meas_core in _itertools.product(*([singleQfiducials]*nCore) ):
            for meas_core in cores:

                if meas_core is None:
                    meas = meas_noncore
                else:
                    #construct meas, a gatename-string, from meas_noncore and meas_core
                    meas = list(meas_noncore)
                    for i, core_ql in enumerate(core_filter):
                        meas[qubit_filter.index(core_ql)] = meas_core[i]
                    meas = tuple(meas)

                measFid = _objs.Circuit(())
                for i, el in enumerate(meas):
                    measFid = measFid + _onqubit(el, qubit_filter[i])
                #print("CONSIDER: ",prep,"-",meas)

                opstr = prepFid + germPowerStr + measFid  # should be a Circuit
                if opstr in already_tried: continue
                else: already_tried.add(opstr)

                ps = model._fwdsim().prs_as_polys(prepLbl, effectLbls, opstr)
                #OLD: Jtest = J
                added = False
                for elbl, p in zip(effectLbls, ps):
                    #print(" POLY = ",p)
                    #For each fiducial pair (included pre/effect), determine how the
                    # (polynomial) probability relates to the *amplified* directions
                    # (also polynomials - now encoded by a "Jac" row/vec)
                    prow = _np.array([p.deriv(iParam).evaluate(dummy)
                                      for iParam in _slct.as_array(wrtParams)])  # complex
                    Jrow = _np.array([[_np.vdot(prow, amped_row) for amped_row in amped_polyJ]])  # complex
                    if _np.linalg.norm(Jrow) < 1e-8: continue  # row of zeros can fool matrix_rank

                    Jtest = _np.concatenate((J, Jrow), axis=0)
                    testRank = _np.linalg.matrix_rank(Jtest, tol=RANK_TOL)
                    if testRank > Jrank:
                        #print("ACCESS")
                        #print("ACCESS: ",prep,meas,testRank, _np.linalg.svd(Jtest, compute_uv=False))
                        J = Jtest
                        Jrank = testRank
                        if not added:
                            gatename_fidpair_lists.append([(prep[i], meas[i]) for i in range(nQubits)])
                            added = True
                        #OLD selected_fidpairs.append( (prepFid, measFid) )
                        if Jrank == Namped:
                            # then we've selected enough pairs to access all of the amplified directions
                            return gatename_fidpair_lists  # (i.e. the rows of `amped_polyJ`)

    #DEBUG
    #print("DEBUG: J = ")
    #_mt.print_mx(J)
    #print("SVals = ",_np.linalg.svd(J, compute_uv=False))
    #print("Nullspace = ")
    #_gt.print_mx(pygsti.tools.nullspace(J))

    raise ValueError(("Could not find sufficient fiducial pairs to access "
                      "all the amplified directions - only %d of %d were accessible")
                     % (Jrank, Namped))
    #_warnings.warn(("Could not find sufficient fiducial pairs to access "
    #                  "all the amplified directions - only %d of %d were accessible")
    #                 % (Jrank,Namped))
    #return gatename_fidpair_lists # (i.e. the rows of `amped_polyJ`)


def tile_idle_fidpairs(qubit_labels, idle_gatename_fidpair_lists, maxIdleWeight):
    """
    "Tile" a set of fiducial pairs sufficient for amplifying all the true-idle
    errors on `maxIdleWeight` qubits (so with weight up to `maxIdleWeight`
    onto `nQubits` qubits.

    This function essentaily converts fiducial pairs that amplify all
    up-to-weight-k errors on k qubits to fiducial pairs that amplify all
    up-to-weight-k errors on `nQubits` qubits (where `k = maxIdleWeight`).

    Parameters
    ----------
    qubit_labels : int
        The labels of the final qubits.  These are the line labels of the
        returned circuits.

    idle_gatename_fidpair_lists : list
        A list of the fiducial pairs which amplify the errors on
        `maxIdleWeight` qubits (so with weight up to `maxIdleWeight`).
        Each element of this list is a fiducial pair in
        "gatename-fidpair-list" format.  These are the fiducial pairs
        to "tile".

    maxIdleWeight : int
        The number of qubits and maximum amplified error weight for
        the fiducial pairs given by `idle_gatename_fidpair_lists`.

    Returns
    -------
    fidpairs : list
        A list of `(prep,meas)` 2-tuples, where `prep` and `meas` are
        :class:`Circuit` objects, giving the tiled fiducial pairs.
    """

    # "Tile w/overlap" the fidpairs for a k-qubit subset (where k == maxIdleWeight)

    # we want to create a k-coverage set of length-nQubits strings/lists containing
    # the elements 012..(k-1)(giving the "fiducial" - possible a gate sequence - for
    # each qubit) such that for any k qubits the set includes string where these qubits
    # take on all the fiducial pairs given in the idle fiducial pairs

    # Each element of idle_gatename_fidpair_lists is a "gatename_fidpair_list".
    # Each "gatename_fidpair_list" is a list of k (prep-gate-name-str, meas-gate-name-str)
    # tuples, one per *qubit*, giving the gate names to perform on *that* qubit.

    #OLD - we don't need this conversion since we can take the gatename_fidpair_lists as an arg.
    # XX idle_fidpairs elements are (prepStr, measStr) on qubits 0->(k-1); to convert each
    # XX element to a list of k (prep-gate-name-str, meas-gate-name-str) tuples one per *qubit*.

    nQubits = len(qubit_labels)
    tmpl = get_kcoverage_template(nQubits, maxIdleWeight)
    final_fidpairs = []

    def merge_into_1Q(gStr, gate_names, qubit_label):
        """ Add gate_names, all acting on qubit_label, to gStr """
        while len(gStr) < len(gate_names): gStr.append([])  # make sure gStr is long enough
        for iLayer, name in enumerate(gate_names):
            # only 1 op per qubit per layer!
            assert(qubit_label not in set(_itertools.chain(*[l.sslbls for l in gStr[iLayer]])))
            gStr[iLayer].append(_Lbl(name, qubit_label))  # gStr[i] is a list of i-th layer labels
            if iLayer > 0: assert(qubit_label in set(_itertools.chain(
                *[l.sslbls for l in gStr[iLayer - 1]])))  # just to be safe

    for gatename_fidpair_list in idle_gatename_fidpair_lists:
        # replace 0..(k-1) in each template string with the corresponding
        # gatename_fidpair (acts on the single qubit identified by the
        # its index within the template string), then convert to a Circuit
        tmpl_instance = [[gatename_fidpair_list[i] for i in tmpl_row] for tmpl_row in tmpl]
        for tmpl_instance_row in tmpl_instance:
            # tmpl_instance_row row is nQubits long; elements give the
            # gate *names* to perform on that qubit.
            prep_gates = []
            meas_gates = []
            for iQubit, gatename_fidpair in enumerate(tmpl_instance_row):
                prep_gatenames, meas_gatenames = gatename_fidpair
                #prep_gates.extend( [_Lbl(gatename,iQubit) for gatename in prep_gatenames ]) #OLD: SERIAL strs
                #meas_gates.extend( [_Lbl(gatename,iQubit) for gatename in meas_gatenames ]) #OLD: SERIAL strs
                merge_into_1Q(prep_gates, prep_gatenames, iQubit)
                merge_into_1Q(meas_gates, meas_gatenames, iQubit)

            final_fidpairs.append((_objs.Circuit(prep_gates, line_labels=qubit_labels),
                                   _objs.Circuit(meas_gates, line_labels=qubit_labels)))

    _lt.remove_duplicates_in_place(final_fidpairs)
    return final_fidpairs


def tile_cloud_fidpairs(template_gatename_fidpair_lists, template_germPower, L, template_germ, clouds, qubit_labels):
    """
    Take a "cloud template", giving the fiducial pairs for a germ power acting
    on qubits labeled 0 to `cloudsize-1`, and map those fiducial pairs into
    fiducial pairs for all the qubits by placing in parallel the pairs for
    as many non-overlapping clouds as possible.  This function performs a
    function analogous to :function:`tile_idle_fidpairs` except here we tile
    fiducial pairs for non-idle operations.

    Parameters
    ----------
    template_gatename_fidpair_lists : list
        A list of the fiducial pairs for the given template - that is, the
        pairs with which amplify all the desired errors for `template_germPower`
        (acting on qubits labeled by the integers 0 to the cloud size minus one).

    template_germPower : Circuit
        The germ power string under consideration.  This gives the action on
        the "core" qubits of the clouds, and is needed to construct the
        final fiducial + germPower + fiducial sequences returned by this
        function.

    L : int
        The maximum length used to construct template_germPower.  This is only
        needed to tag elements of the returned `sequences` list.

    template_germ : Circuit
        The germ string under consideration.  This is only needed to tag
        elements of the returned `sequences` list and place elements in
        the returned `germs` list.

    clouds : list
        A list of `(cloud_dict, template_to_cloud_map)` tuples specifying the
        set of equivalent clouds corresponding to the template.

    qubit_labels : list
        A list of the final qubit labels, which are the line labels of
        the returned circuits.

    Returns
    -------
    sequences : list
        A list of (Circuit, L, germ, prepFid, measFid) tuples specifying the
        final "tiled" fiducial pairs sandwiching `germPowerStr` for as many
        clouds in parallel as possible.  Actual qubit labels (not the always-
        integer labels used in templates) are used in these strings.  There are
        no duplicates in this list.

    germs : list
        A list of Circuit objects giving all the germs (with appropriate
        qubit labels).
    """
    unused_clouds = list(clouds)
    sequences = []
    germs = []

    while(len(unused_clouds) > 0):

        #figure out what clouds can be processed in parallel
        first_unused = unused_clouds[0]  # a cloud_dict, template_to_cloud_map tuple
        parallel_clouds = [first_unused]
        parallel_qubits = set(first_unused[0]['qubits'])  # qubits used by parallel_clouds
        del unused_clouds[0]

        to_delete = []
        for i, cloud in enumerate(unused_clouds):
            if len(parallel_qubits.intersection(cloud[0]['qubits'])) == 0:
                parallel_qubits.update(cloud[0]['qubits'])
                parallel_clouds.append(cloud)
                to_delete.append(i)
        for i in reversed(to_delete):
            del unused_clouds[i]

        #Create gate sequence "info-tuples" by processing in parallel the
        # list of parallel_clouds

        def merge_into_1Q(gStr, gate_names, qubit_label):
            """ Add gate_names, all acting on qubit_label, to gStr """
            while len(gStr) < len(gate_names): gStr.append([])  # make sure prepStr is long enough
            for iLayer, name in enumerate(gate_names):
                # only 1 op per qubit per layer!
                assert(qubit_label not in set(_itertools.chain(*[l.sslbls for l in gStr[iLayer]])))
                gStr[iLayer].append(_Lbl(name, qubit_label))  # gStr[i] is a list of i-th layer labels
                if iLayer > 0: assert(qubit_label in set(_itertools.chain(
                    *[l.sslbls for l in gStr[iLayer - 1]])))  # only 1 op per qubit per layer!

        def merge_into(gStr, gStr_qubits, op_labels):
            """ Add op_labels to gStr using gStr_qubits to keep track of available qubits """
            for lbl in op_labels:
                iLayer = 0
                while True:  # find a layer that can accomodate lbl
                    if len(gStr_qubits) < iLayer + 1:
                        gStr.append([]); gStr_qubits.append(set())
                    if len(gStr_qubits[iLayer].intersection(lbl.sslbls)) == 0:
                        break
                    iLayer += 1
                gStr[iLayer].append(lbl)
                gStr_qubits[iLayer].update(lbl.sslbls)

        for template_gatename_fidpair_list in template_gatename_fidpair_lists:
            prepStr = []
            measStr = []
            germStr = []; germStr_qubits = []
            germPowerStr = []; germPowerStr_qubits = []
            for cloud in parallel_clouds:
                cloud_dict, template_to_cloud_map = cloud
                cloud_to_template_map = {c: t for t, c in template_to_cloud_map.items()}

                germ = template_germ.map_state_space_labels(template_to_cloud_map)
                germPower = template_germPower.map_state_space_labels(template_to_cloud_map)

                for cloud_ql in cloud_dict['qubits']:
                    prep, meas = template_gatename_fidpair_list[cloud_to_template_map[cloud_ql]]  # gate-name lists
                    #prepStr.extend( [_Lbl(name,cloud_ql) for name in prep] ) #OLD: SERIAL strs
                    #measStr.extend( [_Lbl(name,cloud_ql) for name in meas] ) #OLD: SERIAL strs
                    merge_into_1Q(prepStr, prep, cloud_ql)
                    merge_into_1Q(measStr, meas, cloud_ql)

                #germStr.extend( list(germ) ) #OLD: SERIAL strs
                #germPowerStr.extend( list(germPower) ) #OLD: SERIAL strs
                merge_into(germStr, germStr_qubits, germ)
                merge_into(germPowerStr, germPowerStr_qubits, germPower)

            germs.append(_objs.Circuit(germStr, line_labels=qubit_labels))
            sequences.append((_objs.Circuit(prepStr + germPowerStr + measStr, line_labels=qubit_labels), L, germs[-1],
                              _objs.Circuit(prepStr, line_labels=qubit_labels),
                              _objs.Circuit(measStr, line_labels=qubit_labels)))
            # circuit, L, germ, prepFidIndex, measFidIndex??

    # return a list of operation sequences (duplicates removed)
    return _lt.remove_duplicates(sequences), _lt.remove_duplicates(germs)


def reps_for_synthetic_idle(model, germStr, nqubits, core_qubits):
    """
    Return the number of times `germStr` must be repeated to form a synthetic
    idle gate.

    Parameters
    ----------
    model : Model
        A model containing matrix representations of all the gates
        in `germStr`.

    germStr : Circuit
        The germ operation sequence to repeat.

    nqubits : int
        The total number of qubits that `model` acts on.  This
        is used primarily for sanity checks.

    core_qubits : list
        A list of the qubit labels upon which `germStr` ideally acts
        nontrivially.  This could be inferred from `germStr` but serves
        as a sanity check and more concrete specification of what
        state space the gate action takes place within.

    Returns
    -------
    int
    """
    # First, get a dense representation of germStr on core_qubits
    # Note: only works with one level of embedding...
    def extract_gate(g):
        """ Get the gate action as a dense gate on core_qubits """
        if isinstance(g, _objs.EmbeddedOp):
            assert(len(g.state_space_labels.labels) == 1)  # 1 tensor product block
            assert(len(g.state_space_labels.labels[0]) == nqubits)  # expected qubit count
            qubit_labels = g.state_space_labels.labels[0]

            # for now - assume we know the form of qubit_labels
            assert(list(qubit_labels) == [('Q%d' % i) for i in range(nqubits)]
                   or list(qubit_labels) == [i for i in range(nqubits)])
            new_qubit_labels = []
            for core_ql in core_qubits:
                if core_ql in qubit_labels: new_qubit_labels.append(core_ql)  # same convention!
                elif ("Q%d" % core_ql) in qubit_labels: new_qubit_labels.append("Q%d" % core_ql)  # HACK!
            ssl = _StateSpaceLabels(new_qubit_labels)
            assert(all([(tgt in new_qubit_labels) for tgt in g.targetLabels]))  # all target qubits should be kept!
            if len(new_qubit_labels) == len(g.targetLabels):
                # embedded gate acts on entire core-qubit space:
                return g.embedded_op
            else:
                return _objs.EmbeddedDenseOp(ssl, g.targetLabels, g.embedded_op)

        elif isinstance(g, _objs.ComposedOp):
            return _objs.ComposedDenseOp([extract_gate(f) for f in g.factorops])
        else:
            raise ValueError("Cannot extract core contrib from %s" % str(type(g)))

    core_dim = 4**len(core_qubits)
    product = _np.identity(core_dim, 'd')
    core_gates = {}
    for gl in germStr:
        if gl not in core_gates:
            core_gates[gl] = extract_gate(model.operation_blks['layers'][gl])
        product = _np.dot(core_gates[gl], product)

    # Then just do matrix products until we hit the identity (or a large order)
    reps = 1; target = _np.identity(core_dim, 'd')
    repeated = product
    while(_np.linalg.norm(repeated - target) > 1e-6 and reps < 20):  # HARDCODED MAX_REPS
        repeated = _np.dot(repeated, product); reps += 1

    return reps


def get_candidates_for_core(model, core_qubits, candidate_counts, seedStart):
    """
    Returns a list of candidate germs which act on a given set of "core" qubits.

    This function figures out what gates within `model` are available to act
    (only) on `core_qubits` and then randomly selects a set of them based on
    `candidate_counts`.  In each candidate germ, at least one gate will act
    on *all* of the core qubits (if the core is 2 qubits then this function
    won't return a germ consisting of just 1-qubit gates).

    This list serves as the inital candidate list when a new cloud template is
    created within create_cloudnoise_sequences.

    Parameters
    ----------
    model : Model
        The model specifying the gates allowed to be in the germs.

    core_qubits : list
        A list of the qubit labels.  All returned candidate germs (ideally) act
        nontrivially only on these qubits.

    candidate_counts : dict
        A dictionary specifying how many germs of each length to include in the
        returned set.  Thus both keys and values are integers (key specifies
        germ length, value specifies number).  The special value `"all upto"`
        means that all possible candidate germs up to the corresponding key's
        value should be included.  A typical value for this argument might be
        `{4: 'all upto', 5: 10, 6: 10 }`.

    seedStart : int
        A *initial* random number generator seed value to use.  Incrementally
        greater seeds are used for the different keys of `candidate_counts`.

    Returns
    -------
    list : candidate_germs
        A list of Circuit objects.
    """
    # or should this be ...for_cloudbank - so then we can check that gates for all "equivalent" clouds exist?

    # collect gates that only act on core_qubits.
    oplabel_list = []; full_core_list = []
    for gl in model.get_primitive_op_labels():
        if gl.sslbls is None: continue  # gates that act on everything (usually just the identity Gi gate)
        if set(gl.sslbls).issubset(core_qubits):
            oplabel_list.append(gl)
        if set(gl.sslbls) == set(core_qubits):
            full_core_list.append(gl)

    # form all low-length strings out of these gates.
    candidate_germs = []
    for i, (germLength, count) in enumerate(candidate_counts.items()):
        if count == "all upto":
            candidate_germs.extend(_gsc.list_all_circuits_without_powers_and_cycles(
                oplabel_list, maxLength=germLength))
        else:
            candidate_germs.extend(_gsc.list_random_circuits_onelen(
                oplabel_list, germLength, count, seed=seedStart + i))

    #filter: make sure there's at least one gate in each germ that acts on the *entire* core
    candidate_germs = [g for g in candidate_germs if any([(gl in g) for gl in full_core_list])]  # filter?

    return candidate_germs


def create_XYCNOT_cloudnoise_sequences(nQubits, maxLengths, geometry, cnot_edges, maxIdleWeight=1, maxhops=0,
                                       extraWeight1Hops=0, extraGateWeight=0, paramroot="H+S",
                                       sparse=False, verbosity=0, cache=None, idleOnly=False,
                                       idtPauliDicts=None, algorithm="greedy", comm=None):

    from pygsti.construction import std1Q_XY  # the base model for 1Q gates
    from pygsti.construction import std2Q_XYICNOT  # the base model for 2Q (CNOT) gate

    tgt1Q = std1Q_XY.target_model("static")
    tgt2Q = std2Q_XYICNOT.target_model("static")
    Gx = tgt1Q.operations['Gx']
    Gy = tgt1Q.operations['Gy']
    Gcnot = tgt2Q.operations['Gcnot']
    gatedict = _collections.OrderedDict([('Gx', Gx), ('Gy', Gy), ('Gcnot', Gcnot)])
    availability = {}
    if cnot_edges is not None: availability['Gcnot'] = cnot_edges

    if paramroot in ("H+S", "S", "H+D", "D",
                     "H+s", "s", "H+d", "d"):  # no affine - can get away w/1 fewer fiducials
        singleQfiducials = [(), ('Gx',), ('Gy',)]
    else:
        singleQfiducials = [(), ('Gx',), ('Gy',), ('Gx', 'Gx')]

    return create_cloudnoise_sequences(nQubits, maxLengths, singleQfiducials,
                                       gatedict, availability, geometry, maxIdleWeight, maxhops,
                                       extraWeight1Hops, extraGateWeight, paramroot,
                                       sparse, verbosity, cache, idleOnly,
                                       idtPauliDicts, algorithm, comm=comm)


def create_standard_cloudnoise_sequences(nQubits, maxLengths, singleQfiducials,
                                         gate_names, nonstd_gate_unitaries=None,
                                         availability=None, geometry="line",
                                         maxIdleWeight=1, maxhops=0, extraWeight1Hops=0, extraGateWeight=0,
                                         paramroot="H+S", sparse=False, verbosity=0, cache=None, idleOnly=False,
                                         idtPauliDicts=None, algorithm="greedy", idleOpStr=((),), comm=None):
    """
    Create a set of `fiducial1+germ^power+fiducial2` sequences which amplify
    all of the parameters of a `CloudNoiseModel` created by passing the
    arguments of this function to
    :function:`build_cloudnoise_model_from_hops_and_weights`.

    Note that this function essentialy performs fiducial selection, germ
    selection, and fiducial-pair reduction simultaneously.  It is used to
    generate a short (ideally minimal) list of sequences needed for multi-
    qubit GST.

    This function allows the cloud noise model to be created by specifing
    standard gate names or additional gates as *unitary* operators.  Some
    example gate names are:

        - 'Gx','Gy','Gz' : 1Q pi/2 rotations
        - 'Gxpi','Gypi','Gzpi' : 1Q pi rotations
        - 'Gh' : Hadamard
        - 'Gp' : phase
        - 'Gcphase','Gcnot','Gswap' : standard 2Q gates


    Parameters
    ----------
    nQubits : int
        The number of qubits

    maxLengths : list
        A list of integers specifying the different maximum lengths for germ
        powers.  Typically these values start a 1 and increase by powers of
        2, e.g. `[1,2,4,8,16]`.

    singleQfiducials : list
        A list of gate-name-tuples, e.g. `[(), ('Gx',), ('Gy',), ('Gx','Gx')]`,
        which form a set of 1-qubit fiducials for the given model (compatible
        with both the gates it posseses and their parameterizations - for
        instance, only `[(), ('Gx',), ('Gy',)]` is needed for just Hamiltonian
        and Stochastic errors.

    gate_names, nonstd_gate_unitaries, availability, geometry,
    maxIdleWeight, maxhops, extraWeight1Hops, extraGateWeight, sparse : various
        Cloud-noise model parameters specifying the model to create sequences
        for. See function:`build_cloudnoise_model_from_hops_and_weights`
        for details.

    paramroot : {"CPTP", "H+S+A", "H+S", "S", "H+D+A", "D+A", "D"}
        The "root" (no trailing " terms", etc.) parameterization used for the
        cloud noise model (which specifies what needs to be amplified).

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.

    cache : dict, optional
        A cache dictionary which holds template information so that repeated
        calls to `create_standard_cloudnoise_sequences` can draw on the same
        pool of templates.

    idleOnly : bool, optional
        If True, only sequences for the idle germ are returned.  This is useful
        for idle tomography in particular.

    idtPauliDicts : tuple, optional
        A (prepDict,measDict) tuple of dicts that maps a 1-qubit Pauli basis
        string (e.g. 'X' or '-Y') to a sequence of gate *names*.  If given,
        the idle-germ fiducial pairs chosen by this function are restricted
        to those where either 1) each qubit is prepared and measured in the
        same basis or 2) each qubits is prepared and measured in different
        bases (note: '-X' and 'X" are considered the *same* basis).  This
        restriction makes the resulting sequences more like the "standard"
        ones of idle tomography, and thereby easier to interpret.

    algorithm : {"greedy","sequential"}
        The algorithm is used internall by
        :function:`find_amped_polys_for_syntheticidle`.  You should leave this
        as the default unless you know what you're doing.

    idleOpStr : Circuit or tuple, optional
        The circuit or label that is used to indicate a completely
        idle layer (all qubits idle).

    Returns
    -------
    LsGermsSerialStructure
        An object holding a structured (using germ and fiducial sub-sequences)
        list of sequences.
    """

    if nonstd_gate_unitaries is None: nonstd_gate_unitaries = {}
    std_unitaries = _itgs.get_standard_gatename_unitaries()

    gatedict = _collections.OrderedDict()
    for name in gate_names:
        U = nonstd_gate_unitaries.get(name, std_unitaries.get(name, None))
        if U is None: raise KeyError("'%s' gate unitary needs to be provided by `nonstd_gate_unitaries` arg" % name)
        if callable(U):  # then assume a function: args -> unitary
            raise NotImplementedError("Factories are not allowed to passed to create_standard_cloudnoise_sequences yet")
        gatedict[name] = _bt.change_basis(_gt.unitary_to_process_mx(U), "std", "pp")
        # assume evotype is a densitymx or term type

    return create_cloudnoise_sequences(nQubits, maxLengths, singleQfiducials,
                                       gatedict, availability, geometry, maxIdleWeight, maxhops,
                                       extraWeight1Hops, extraGateWeight, paramroot,
                                       sparse, verbosity, cache, idleOnly,
                                       idtPauliDicts, algorithm, idleOpStr, comm)


def create_cloudnoise_sequences(nQubits, maxLengths, singleQfiducials,
                                gatedict, availability, geometry, maxIdleWeight=1, maxhops=0,
                                extraWeight1Hops=0, extraGateWeight=0, paramroot="H+S",
                                sparse=False, verbosity=0, cache=None, idleOnly=False,
                                idtPauliDicts=None, algorithm="greedy", idleOpStr=((),), comm=None):
    """
    Create a set of `fiducial1+germ^power+fiducial2` sequences which amplify
    all of the parameters of a `CloudNoiseModel` created by passing the
    arguments of this function to
    function:`build_cloudnoise_model_from_hops_and_weights`.

    Note that this function essentialy performs fiducial selection, germ
    selection, and fiducial-pair reduction simultaneously.  It is used to
    generate a short (ideally minimal) list of sequences needed for multi-
    qubit GST.


    Parameters
    ----------
    nQubits : int
        The number of qubits

    maxLengths : list
        A list of integers specifying the different maximum lengths for germ
        powers.  Typically these values start a 1 and increase by powers of
        2, e.g. `[1,2,4,8,16]`.

    singleQfiducials : list
        A list of gate-name-tuples, e.g. `[(), ('Gx',), ('Gy',), ('Gx','Gx')]`,
        which form a set of 1-qubit fiducials for the given model (compatible
        with both the gates it posseses and their parameterizations - for
        instance, only `[(), ('Gx',), ('Gy',)]` is needed for just Hamiltonian
        and Stochastic errors.

    gatedict, availability, geometry,
    maxIdleWeight, maxhops, extraWeight1Hops, extraGateWeight, sparse : various
        Cloud-noise model parameters specifying the model to create sequences
        for. See class:`CloudNoiseModel` constructor for details.

    paramroot : {"CPTP", "H+S+A", "H+S", "S", "H+D+A", "D+A", "D"}
        The parameterization used to define which parameters need to be
        amplified.  Note this is only the "root", e.g. you shouldn't pass
        "H+S terms" here, since the latter is implied by "H+S" when necessary.

    verbosity : int, optional
        The level of detail printed to stdout.  0 means silent.

    cache : dict, optional
        A cache dictionary which holds template information so that repeated
        calls to `create_cloudnoise_sequences` can draw on the same pool of
        templates.

    idleOnly : bool, optional
        If True, only sequences for the idle germ are returned.  This is useful
        for idle tomography in particular.

    idtPauliDicts : tuple, optional
        A (prepDict,measDict) tuple of dicts that maps a 1-qubit Pauli basis
        string (e.g. 'X' or '-Y') to a sequence of gate *names*.  If given,
        the idle-germ fiducial pairs chosen by this function are restricted
        to those where either 1) each qubit is prepared and measured in the
        same basis or 2) each qubits is prepared and measured in different
        bases (note: '-X' and 'X" are considered the *same* basis).  This
        restriction makes the resulting sequences more like the "standard"
        ones of idle tomography, and thereby easier to interpret.

    algorithm : {"greedy","sequential"}
        The algorithm is used internall by
        :function:`find_amped_polys_for_syntheticidle`.  You should leave this
        as the default unless you know what you're doing.

    idleOpStr : Circuit or tuple, optional
        The circuit or label that is used to indicate a completely
        idle layer (all qubits idle).

    Returns
    -------
    LsGermsSerialStructure
        An object holding a structured (using germ and fiducial sub-sequences)
        list of sequences.
    """

    #The algorithm here takes the following basic structure:
    # - compute idle fiducial pairs with a max-weight appropriate for
    #   the true idle gate.
    # - Add the idle germ + fiducial pairs, which amplify all the "idle
    #   parameters" (the parameters of the Gi gate)
    # - precompute other idle fiducial pairs needed for 1 & 2Q synthetic
    #   idles (with maxWeight = gate-error-weight + spreading potential)
    # - To amplify the remaining parameters iterate through the "clouds"
    #   constructed by a CloudNoiseModel (these essentially give
    #   the areas of the qubit graph where non-Gi gates should act and where
    #   they aren't supposted to act but can have errors).  For each cloud
    #   we either create a new "cloud template" for it and find a set of
    #   germs and fiducial pairs (for all requested L values) such that all
    #   the parameters of gates acting on the *entire* core of the cloud
    #   are amplified (not counting any Gi parameters which are already
    #   amplified) OR we identify that the cloud is equivalent to one
    #   we already computed sequences for and just associate the cloud
    #   with the existing cloud's template; we "add it to a cloudbank".
    #   I this latter case, we compute the template sequences for any
    #   needed additional L values not already present in the template.
    # - Once there exist templates for all the clouds which support all
    #   the needed L values, we simply iterate through the cloudbanks
    #   and "tile" the template sequences, converting them to real
    #   sequences with as many clouds in parallel as possible.

    if cache is None: cache = {}
    if 'Idle gatename fidpair lists' not in cache:
        cache['Idle gatename fidpair lists'] = {}
    if 'Cloud templates' not in cache:
        cache['Cloud templates'] = _collections.defaultdict(list)

    ptermstype = paramroot + " terms"
    #the parameterization type used for constructing Models
    # that will be used to construct 1st order prob polynomials.

    printer = _VerbosityPrinter.build_printer(verbosity, comm)
    printer.log("Creating full model")

    if isinstance(geometry, _objs.QubitGraph):
        qubitGraph = geometry
    else:
        qubitGraph = _objs.QubitGraph.common_graph(nQubits, geometry, directed=False)
        printer.log("Created qubit graph:\n" + str(qubitGraph))
    all_qubit_labels = qubitGraph.get_node_names()

    model = _CloudNoiseModel.build_from_hops_and_weights(
        nQubits, tuple(gatedict.keys()), None, gatedict,
        availability, None, qubitGraph,
        maxIdleWeight, 0, maxhops, extraWeight1Hops,
        extraGateWeight, sparse, verbosity=printer - 5,
        sim_type="termorder:1", parameterization=ptermstype)
    clouds = model.get_clouds()
    #Note: maxSpamWeight=0 above b/c we don't care about amplifying SPAM errors (?)
    #print("DB: GATES = ",model.operation_blks['layers'].keys())
    #print("DB: CLOUDS = ",clouds)

    # clouds is a list of (core_qubits,cloud_qubits) tuples, giving the
    # different "supports" of performing the various gates in the model
    # whose parameters we want to amplify.  The 'core' of a cloud is the
    # set of qubits that have a non-trivial ideal action applied to them.
    # The 'qubits' of a cloud are all the qubits that have any action -
    # ideal or error - except that which is the same as the Gi gate.

    ideal_model = _CloudNoiseModel.build_from_hops_and_weights(
        nQubits, tuple(gatedict.keys()), None, gatedict,
        availability, None, qubitGraph,
        0, 0, 0, 0, 0, False, verbosity=printer - 5,
        sim_type="map", parameterization=paramroot)
    # for testing for synthetic idles - so no " terms"

    Np = model.num_params()
    idleOpStr = _objs.Circuit(idleOpStr, num_lines=nQubits)
    prepLbl = _Lbl("rho0")
    effectLbls = [_Lbl("Mdefault_%s" % l) for l in model._shlp.get_effect_labels_for_povm('Mdefault')]

    # create a model with maxIdleWeight qubits that includes all
    # the errors of the actual n-qubit model...
    #Note: geometry doens't matter here, since we just look at the idle gate (so just use 'line'; no CNOTs)
    # - actually better to pass qubitGraph here so we get the correct qubit labels (node labels of graphO
    printer.log("Creating \"idle error\" model on %d qubits" % maxIdleWeight)
    idle_model = _CloudNoiseModel.build_from_hops_and_weights(
        maxIdleWeight, tuple(gatedict.keys()), None, gatedict, {}, None, qubitGraph,
        maxIdleWeight, 0, maxhops, extraWeight1Hops,
        extraGateWeight, sparse, verbosity=printer - 5,
        sim_type="termorder:1", parameterization=ptermstype)
    idle_model._clean_paramvec()  # allocates/updates .gpindices of all blocks
    # these are the params we want to amplify at first...
    idle_params = idle_model.operation_blks['layers']['globalIdle'].gpindices

    if maxIdleWeight in cache['Idle gatename fidpair lists']:
        printer.log("Getting cached sequences needed for max-weight=%d errors on the idle gate" % maxIdleWeight)
        idle_maxwt_gatename_fidpair_lists = cache['Idle gatename fidpair lists'][maxIdleWeight]
    else:
        #First get "idle germ" sequences since the idle is special
        printer.log("Getting sequences needed for max-weight=%d errors on the idle gate" % maxIdleWeight)
        ampedJ, ampedJ_rank, idle_maxwt_gatename_fidpair_lists = \
            find_amped_polys_for_syntheticidle(list(range(maxIdleWeight)),
                                               idleOpStr, idle_model, singleQfiducials,
                                               prepLbl, None, wrtParams=idle_params,
                                               algorithm=algorithm, idtPauliDicts=idtPauliDicts,
                                               comm=comm, verbosity=printer - 1)
        #ampedJ, ampedJ_rank, idle_maxwt_gatename_fidpair_lists = None,0,[] # DEBUG GRAPH ISO
        cache['Idle gatename fidpair lists'][maxIdleWeight] = idle_maxwt_gatename_fidpair_lists

    #Since this is the idle, these maxIdleWeight-qubit fidpairs can be "tiled"
    # to the n-qubits
    printer.log("%d \"idle template pairs\".  Tiling these to all %d qubits" %
                (len(idle_maxwt_gatename_fidpair_lists), nQubits), 2)
    idle_fidpairs = tile_idle_fidpairs(all_qubit_labels, idle_maxwt_gatename_fidpair_lists, maxIdleWeight)
    printer.log("%d idle pairs found" % len(idle_fidpairs), 2)

    # Create idle sequences by sandwiching Gi^L between all idle fiducial pairs
    sequences = []
    selected_germs = [idleOpStr]
    for L in maxLengths:
        for fidpair in idle_fidpairs:
            prepFid, measFid = fidpair
            sequences.append((prepFid + idleOpStr * L + measFid, L, idleOpStr,
                              prepFid, measFid))  # was XX
            # circuit, L, germ, prepFidIndex, measFidIndex??
    printer.log("%d idle sequences (for all max-lengths: %s)" % (len(sequences), str(maxLengths)))

    if idleOnly:  # Exit now when we just wanted idle-tomography sequences
        #OLD: return sequences, selected_germs

        #Post processing: convert sequence tuples to a operation sequence structure
        Gi_fidpairs = _collections.defaultdict(list)  # lists of fidpairs for each L value
        for _, L, _, prepFid, measFid in sequences:
            Gi_fidpairs[L].append((prepFid, measFid))

        maxPlaqEls = max([len(fidpairs) for fidpairs in Gi_fidpairs.values()])
        nMinorRows = nMinorCols = int(_np.floor(_np.sqrt(maxPlaqEls)))
        if nMinorRows * nMinorCols < maxPlaqEls: nMinorCols += 1
        if nMinorRows * nMinorCols < maxPlaqEls: nMinorRows += 1
        assert(nMinorRows * nMinorCols >= maxPlaqEls), "Logic Error!"

        germList = [idleOpStr]
        Ls = sorted(maxLengths)
        gss = _objs.LsGermsSerialStructure(Ls, germList, nMinorRows, nMinorCols,
                                           aliases=None, sequenceRules=None)
        serial_germ = idleOpStr.serialize()  # must serialize to get correct count
        for L, fidpairs in Gi_fidpairs.items():
            germ_power = _gsc.repeat_with_max_length(serial_germ, L)
            # returns 'missing_list'; useful if using dsfilter arg
            gss.add_plaquette(germ_power, L, idleOpStr, fidpairs)

        return gss

    #Compute "true-idle" fidpairs for checking synthetic idle errors for 1 & 2Q gates (HARDCODED OK?)
    # NOTE: this works when ideal gates are cliffords and Gi has same type of errors as gates...
    weights = set([len(gl.sslbls) for gl in model.get_primitive_op_labels() if (gl.sslbls is not None)])
    for gateWt in sorted(list(weights)):
        maxSyntheticIdleWt = (gateWt + extraGateWeight) + (gateWt - 1)  # gate-error-wt + spreading potential
        maxSyntheticIdleWt = min(maxSyntheticIdleWt, nQubits)

        if maxSyntheticIdleWt not in cache['Idle gatename fidpair lists']:
            printer.log("Getting sequences needed for max-weight=%d errors" % maxSyntheticIdleWt)
            printer.log(" on the idle gate (for %d-Q synthetic idles)" % gateWt)
            sidle_model = _CloudNoiseModel.build_from_hops_and_weights(
                maxSyntheticIdleWt, tuple(gatedict.keys()), None, gatedict, {}, None, 'line',
                maxIdleWeight, 0, maxhops, extraWeight1Hops,
                extraGateWeight, sparse, verbosity=printer - 5,
                sim_type="termorder:1", parameterization=ptermstype)
            sidle_model._clean_paramvec()  # allocates/updates .gpindices of all blocks
            # these are the params we want to amplify...
            idle_params = sidle_model.operation_blks['layers']['globalIdle'].gpindices

            _, _, idle_gatename_fidpair_lists = find_amped_polys_for_syntheticidle(
                list(range(maxSyntheticIdleWt)), idleOpStr, sidle_model,
                singleQfiducials, prepLbl, None, wrtParams=idle_params,
                algorithm=algorithm, comm=comm, verbosity=printer - 1)
            #idle_gatename_fidpair_lists = [] # DEBUG GRAPH ISO
            cache['Idle gatename fidpair lists'][maxSyntheticIdleWt] = idle_gatename_fidpair_lists

    #Look for and add additional germs to amplify the *rest* of the model's parameters
    Gi_nparams = model.operation_blks['layers']['globalIdle'].num_params()  # assumes nqnoise (Implicit) model
    SPAM_nparams = sum([obj.num_params() for obj in _itertools.chain(model.prep_blks['layers'].values(),
                                                                     model.povm_blks['layers'].values())])
    Np_to_amplify = model.num_params() - Gi_nparams - SPAM_nparams
    printer.log("Idle gate has %d (amplified) params; Spam has %d (unamplifiable) params; %d gate params left" %
                (Gi_nparams, SPAM_nparams, Np_to_amplify))

    printer.log("Beginning search for non-idle germs & fiducial pairs")

    # Cloudbanks are lists of "equivalent" clouds, such that the same template
    # can be applied to all of them given a qubit mapping.  Elements of
    # `cloudbanks` are dicts with keys "template" and "clouds":
    #   - "template" is a (template_glabels, template_graph, germ_dict) tuple, where
    #      germ_dict is where all the actual germ&fidpair selection results are kept.
    #   - "clouds" is a list of (cloud_dict, template->cloud map) tuples specifying
    #      how to map the template's sequences onto the cloud (of *actual* qubits)
    cloudbanks = _collections.OrderedDict()
    for icloud, (core_qubits, cloud_qubits) in enumerate(clouds):
        cloud_dict = {'core': core_qubits, 'qubits': cloud_qubits}  # just for clarity, label the pieces

        # Collect "pure gate" params of gates that *exactly* on (just and only) the core_qubits;
        # these are the parameters we want this cloud to amplify.  If all the gates which act on
        # the core act on the entire core (when there are no gates that only act on only a part
        # of the core), then these params will be the *only* ones the choosen germs will amplify.
        # But, if there are partial-core gates, the germs might amplify some of their parameters
        # (e.g. Gx:0 params might get amplified when processing a cloud whose core is [0,1]).
        # This is fine, but we don't demand that such params be amplified, since they *must* be
        # amplified for another cloud with core exaclty equal to the gate's target qubits (e.g. [0])
        wrtParams = set()
        # OK b/c model.num_params() called above
        Gi_params = set(_slct.as_array(model.operation_blks['layers']['globalIdle'].gpindices))
        pure_op_labels = []
        for gl in model.get_primitive_op_labels():  # take this as the set of "base"/"serial" operations
            if gl.sslbls is None: continue  # gates that act on everything (usually just the identity Gi gate)
            if set(gl.sslbls) == set(core_qubits):
                pure_op_labels.append(gl)
                wrtParams.update(_slct.as_array(model.operation_blks['cloudnoise'][gl].gpindices))
        pure_op_params = wrtParams - Gi_params  # (Gi params don't count)
        wrtParams = _slct.list_to_slice(sorted(list(pure_op_params)), array_ok=True)
        Ngp = _slct.length(wrtParams)  # number of "pure gate" params that we want to amplify

        J = _np.empty((0, Ngp), 'complex'); Jrank = 0

        printer.log("Cloud %d of %d: qubits = %s, core = %s, nparams = %d" %
                    (icloud + 1, len(clouds), str(cloud_qubits), str(core_qubits), Ngp), 2)

        # cache struture:
        #  'Idle gatename fidpair lists' - dict w/keys = ints == max-idle-weights
        #      - values = gatename-fidpair lists (on max-idle-weight qubits)
        #  'Cloud templates' - dict w/ complex cloud-class-identifying keys (tuples)
        #      - values = list of "cloud templates": (oplabels, qubit_graph, germ_dict) tuples, where
        #        oplabels is a list/set of the operation labels for this cloud template
        #        qubit_graph is a graph giving the connectivity of the cloud template's qubits
        #        germ_dict is a dict w/keys = germs
        #           - values = (germ_order, access_cache) tuples for each germ, where
        #              germ_order is an integer
        #              access_cache is a dict w/keys = "effective germ reps" = actual_reps % germ_order
        #                 - values = gatename-fidpair lists (on cloud qubits)

        def get_cloud_key(cloud, maxhops, extraWeight1Hops, extraGateWeight):
            """ Get the cache key we use for a cloud """
            return (len(cloud['qubits']), len(cloud['core']), maxhops, extraWeight1Hops, extraGateWeight)

        def map_cloud_template(cloud, oplabels, graph, template):
            """ Attempt to map `cloud` onto the cloud template `template`"""
            template_glabels, template_graph, _ = template
            #Note: number of total & core qubits should be the same,
            # since cloud is in the same "class" as template
            nCore = len(cloud['core'])
            nQubits = len(cloud['qubits'])
            template_core_graph = template_graph.subgraph(list(range(nCore)))
            template_cloud_graph = template_graph.subgraph(list(range(nQubits)))
            core_graph = graph.subgraph(cloud['core'])
            cloud_graph = graph.subgraph(cloud['qubits'])

            #Make sure each has the same number of operation labels
            if len(template_glabels) != len(oplabels):
                return None

            # Try to match core qubit labels (via oplabels & graph)
            for possible_perm in _itertools.permutations(cloud['core']):
                # possible_perm is a permutation of cloud's core labels, e.g. ('Q1','Q0','Q2')
                # such that the ordering gives the mapping from template index/labels 0 to nCore-1
                possible_template_to_cloud_map = {i: ql for i, ql in enumerate(possible_perm)}

                gr = core_graph.copy()
                for template_edge in template_core_graph.edges():
                    edge = (possible_template_to_cloud_map[template_edge[0]],
                            possible_template_to_cloud_map[template_edge[1]])
                    if gr.has_edge(edge):  # works w/directed & undirected graphs
                        gr.remove_edge(edge[0], edge[1])
                    else:
                        break  # missing edge -> possible_perm no good
                else:  # no missing templage edges!
                    if len(gr.edges()) == 0:  # and all edges were present - a match so far!

                        #Now test operation labels
                        for template_gl in template_glabels:
                            gl = template_gl.map_state_space_labels(possible_template_to_cloud_map)
                            if gl not in oplabels:
                                break
                        else:
                            #All oplabels match (oplabels can't have extra b/c we know length are the same)
                            core_map = possible_template_to_cloud_map

                            # Try to match non-core qubit labels (via graph)
                            non_core_qubits = [ql for ql in cloud['qubits'] if (ql not in cloud['core'])]
                            for possible_perm in _itertools.permutations(non_core_qubits):
                                # possible_perm is a permutation of cloud's non-core labels, e.g. ('Q4','Q3')
                                # such that the ordering gives the mapping from template index/labels nCore to nQubits-1
                                possible_template_to_cloud_map = core_map.copy()
                                possible_template_to_cloud_map.update(
                                    {i: ql for i, ql in enumerate(possible_perm, start=nCore)})
                                # now possible_template_to_cloud_map maps *all* of the qubits

                                gr = cloud_graph.copy()
                                for template_edge in template_cloud_graph.edges():
                                    edge = (possible_template_to_cloud_map[template_edge[0]],
                                            possible_template_to_cloud_map[template_edge[1]])
                                    if gr.has_edge(edge):  # works w/directed & undirected graphs
                                        gr.remove_edge(edge[0], edge[1])
                                    else:
                                        break  # missing edge -> possible_perm no good
                                else:  # no missing templage edges!
                                    if len(gr.edges()) == 0:  # and all edges were present - a match!!!
                                        return possible_template_to_cloud_map

            return None

        def create_cloud_template(cloud, pure_op_labels, graph):
            """ Creates a new cloud template, currently a (template_glabels, template_graph, germ_dict) tuple """
            nQubits = len(cloud['qubits'])
            cloud_to_template_map = {ql: i for i, ql in enumerate(
                cloud['core'])}  # core qubits always first in template
            # then non-core
            cloud_to_template_map.update(
                {ql: i for i, ql in
                 enumerate(filter(lambda x: x not in cloud['core'], cloud['qubits']), start=len(cloud['core']))}
            )
            template_glabels = [gl.map_state_space_labels(cloud_to_template_map)
                                for gl in pure_op_labels]
            template_edges = []
            cloud_graph = graph.subgraph(cloud['qubits'])
            for edge in cloud_graph.edges():
                template_edges.append((cloud_to_template_map[edge[0]],
                                       cloud_to_template_map[edge[1]]))

            template_graph = _objs.QubitGraph(list(range(nQubits)),
                                              initial_edges=template_edges,
                                              directed=graph.directed)
            cloud_template = (template_glabels, template_graph, {})
            template_to_cloud_map = {t: c for c, t in cloud_to_template_map.items()}
            return cloud_template, template_to_cloud_map

        cloud_class_key = get_cloud_key(cloud_dict, maxhops, extraWeight1Hops, extraGateWeight)
        cloud_class_templates = cache['Cloud templates'][cloud_class_key]
        for cloud_template in cloud_class_templates:
            template_to_cloud_map = map_cloud_template(cloud_dict, pure_op_labels, qubitGraph, cloud_template)
            if template_to_cloud_map is not None:  # a cloud template is found!
                template_glabels, template_graph, _ = cloud_template
                printer.log("Found cached template for this cloud: %d qubits, gates: %s, map: %s" %
                            (len(cloud_qubits), template_glabels, template_to_cloud_map), 2)
                break
        else:
            cloud_template, template_to_cloud_map = create_cloud_template(cloud_dict, pure_op_labels, qubitGraph)
            cloud_class_templates.append(cloud_template)
            printer.log("Created a new template for this cloud: %d qubits, gates: %s, map: %s" %
                        (len(cloud_qubits), cloud_template[0], template_to_cloud_map), 2)

        #File this cloud under the found/created "cloud template", as these identify classes of
        # "equivalent" clouds that can be tiled together below
        if id(cloud_template) not in cloudbanks:
            printer.log("Created a new cloudbank (%d) for this cloud" % id(cloud_template), 2)
            cloudbanks[id(cloud_template)] = {'template': cloud_template,
                                              'clouds': []}  # a list of (cloud_dict, template->cloud map) tuples
        else:
            printer.log("Adding this cloud to existing cloudbank (%d)" % id(cloud_template), 2)
        cloudbanks[id(cloud_template)]['clouds'].append((cloud_dict, template_to_cloud_map))

        # *** For the rest of this loop over clouds, we just make sure the identified
        #     template supports everything we need (it has germs, and fidpairs for all needed L values)

        cloud_to_template_map = {c: t for t, c in template_to_cloud_map.items()}
        germ_dict = cloud_template[2]  # see above structure
        if len(germ_dict) > 0:  # germ_dict should always be non-None
            allLsExist = all([all([
                ((_gsc.repeat_count_with_max_length(germ, L) % germ_order) in access_cache)
                for L in maxLengths])
                for germ, (germ_order, access_cache) in germ_dict.items()])
        else: allLsExist = False

        if len(germ_dict) == 0 or not allLsExist:

            if len(germ_dict) == 0:  # we need to do the germ selection using a set of candidate germs
                candidate_counts = {4: 'all upto', 5: 10, 6: 10}  # should be an arg? HARDCODED!
                candidate_germs = get_candidates_for_core(model, core_qubits, candidate_counts, seedStart=1234)
                # candidate_germs should only use gates with support on *core* qubits?
                germ_type = "Candidate"
            else:
                # allLsExist == False, but we have the germs already (since cloud_template is not None),
                # and maybe some L-value support
                #TODO: use qubit_map to translate germ_dict keys to candidate germs
                candidate_germs = [germ.map_state_space_labels(template_to_cloud_map)
                                   for germ in germ_dict]  # just iterate over the known-good germs
                germ_type = "Pre-computed"

            consecutive_unhelpful_germs = 0
            for candidate_germ in candidate_germs:
                template_germ = candidate_germ.map_state_space_labels(cloud_to_template_map)

                #Check if we need any new L-value support for this germ
                if template_germ in germ_dict:
                    germ_order, access_cache = germ_dict[template_germ]
                    if all([((_gsc.repeat_count_with_max_length(template_germ, L) % germ_order)
                             in access_cache) for L in maxLengths]):
                        continue  # move on to the next germ

                #Let's see if we want to add this germ
                sireps = reps_for_synthetic_idle(ideal_model, candidate_germ, nQubits, core_qubits)
                syntheticIdle = candidate_germ * sireps
                maxWt = min((len(core_qubits) + extraGateWeight) + (len(core_qubits) - 1),
                            len(cloud_qubits))  # gate-error-wt + spreading potential
                printer.log("%s germ: %s (synthetic idle %s)" %
                            (germ_type, candidate_germ.str, syntheticIdle.str), 3)

                old_Jrank = Jrank
                printer.log("Finding amped-polys for clifford synIdle w/max-weight = %d" % maxWt, 3)
                J, Jrank, sidle_gatename_fidpair_lists = find_amped_polys_for_clifford_syntheticidle(
                    cloud_qubits, core_qubits, cache['Idle gatename fidpair lists'], syntheticIdle, maxWt, model,
                    singleQfiducials, prepLbl, effectLbls, J, Jrank, wrtParams, printer - 2)
                #J, Jrank, sidle_gatename_fidpair_lists = None, 0, None # DEBUG GRAPH ISO

                #J, Jrank, sidle_gatename_fidpair_lists = find_amped_polys_for_syntheticidle(
                #    cloud_qubits, syntheticIdle, model, singleQfiducials, prepLbl, effectLbls, J, Jrank, wrtParams)

                nNewAmpedDirs = Jrank - old_Jrank  # OLD: not nec. equal to this: len(sidle_gatename_fidpair_lists)
                if nNewAmpedDirs > 0:
                    # then there are some "directions" that this germ amplifies that previous ones didn't...
                    # assume each cloud amplifies an independent set of params
                    printer.log("Germ amplifies %d additional parameters (so %d of %d amplified for this base cloud)" %
                                (nNewAmpedDirs, Jrank, Ngp), 3)

                    if template_germ not in germ_dict:
                        germ_dict[template_germ] = (sireps, {})  # germ_order, access_cache
                    access_fidpairs_cache = germ_dict[template_germ][1]  # see above structure
                    access_fidpairs_cache[0] = sidle_gatename_fidpair_lists  # idle: effective_reps == 0

                    amped_polyJ = J[-nNewAmpedDirs:, :]  # just the rows of the Jacobian corresponding to
                    # the directions we want the current germ to amplify
                    #print("DB: amped_polyJ = ",amped_polyJ)
                    #print("DB: amped_polyJ svals = ",_np.linalg.svd(amped_polyJ, compute_uv=False))

                    #Figure out which fiducial pairs access the amplified directions at each value of L
                    for L in maxLengths:
                        reps = _gsc.repeat_count_with_max_length(candidate_germ, L)
                        if reps == 0: continue  # don't process when we don't use the germ at all...
                        effective_reps = reps % sireps
                        germPower = candidate_germ * effective_reps  # germ^effective_reps

                        if effective_reps not in access_fidpairs_cache:
                            printer.log("Finding the fiducial pairs needed to amplify %s^%d (L=%d, effreps=%d)" %
                                        (candidate_germ.str, reps, L, effective_reps), 4)
                            gatename_fidpair_lists = get_fidpairs_needed_to_access_amped_polys(
                                cloud_qubits, core_qubits, germPower, amped_polyJ, sidle_gatename_fidpair_lists,
                                model, singleQfiducials, prepLbl, effectLbls, wrtParams, printer - 3)
                            #gatename_fidpair_lists = None # DEBUG GRAPH ISO
                            printer.log("Found %d fiducial pairs" % len(gatename_fidpair_lists), 4)

                            #Convert cloud -> template gatename fidpair lists
                            template_gatename_fidpair_lists = []
                            for gatename_fidpair_list in gatename_fidpair_lists:
                                template_gatename_fidpair_lists.append([
                                    gatename_fidpair_list[cloud_qubits.index(template_to_cloud_map[tl])]
                                    for tl in range(len(cloud_qubits))])  # tl ~= "Q0" is *label* of a template qubit
                            #E.G if template qubit labels are [0,1,2] , cloud_qubits = [Q3,Q4,Q2] and map is 0->Q4,
                            # 1->Q2, 2->Q3 then we need to know what *index* Q4,Q2,Q3 are with the template, i.e the
                            # index of template_to_cloud[0], template_to_cloud[1], ... in cloud_qubits

                            access_fidpairs_cache[effective_reps] = gatename_fidpair_lists
                        else:
                            printer.log("Already found fiducial pairs needed to amplify %s^%d (L=%d, effreps=%d)" %
                                        (candidate_germ.str, reps, L, effective_reps), 4)

                    # really this will never happen b/c we'll never amplify SPAM and gauge directions...
                    if Jrank == Np:
                        break       # instead exit after we haven't seen a germ that amplifies anything new in a while
                    consecutive_unhelpful_germs = 0
                else:
                    consecutive_unhelpful_germs += 1
                    printer.log(("No additional amplified params: %d consecutive unhelpful germs."
                                 % consecutive_unhelpful_germs), 3)
                    if consecutive_unhelpful_germs == 5:  # ??
                        break  # next cloudbank
        else:
            printer.log("Fiducials for all L-values are cached!", 3)

    for icb, cloudbank in enumerate(cloudbanks.values()):
        template_glabels, template_graph, germ_dict = cloudbank['template']

        printer.log("Tiling cloudbank %d of %d: %d clouds, template labels = %s, qubits = %s" %
                    (icb + 1, len(cloudbanks), len(cloudbank['clouds']),
                     str(template_glabels), str(template_graph.nqubits)), 2)

        # At this point, we have a cloud template w/germ_dict that
        #  supports all the L-values we need.  Now tile to this
        #  cloudbank.
        for template_germ, (germ_order, access_cache) in germ_dict.items():

            printer.log("Tiling for template germ = %s" % template_germ.str, 3)
            add_germs = True
            for L in maxLengths:
                reps = _gsc.repeat_count_with_max_length(template_germ, L)
                if reps == 0: continue  # don't process when we don't use the germ at all...
                effective_reps = reps % germ_order
                template_gatename_fidpair_lists = access_cache[effective_reps]

                template_germPower = template_germ * reps  # germ^reps
                addl_seqs, addl_germs = tile_cloud_fidpairs(template_gatename_fidpair_lists,
                                                            template_germPower, L, template_germ,
                                                            cloudbank['clouds'], all_qubit_labels)

                sequences.extend(addl_seqs)
                if add_germs:  # addl_germs is independent of L - so just add once
                    selected_germs.extend(addl_germs)
                    add_germs = False

                printer.log("After tiling L=%d to cloudbank, have %d sequences, %d germs" %
                            (L, len(sequences), len(selected_germs)), 4)

    printer.log("Done: %d sequences, %d germs" % (len(sequences), len(selected_germs)))
    #OLD: return sequences, selected_germs
    #sequences : list
    #    A list of (Circuit, L, germ, prepFid, measFid) tuples specifying the
    #    final sequences categorized by max-length (L) and germ.
    #
    #germs : list
    #    A list of Circuit objects specifying all the germs found in
    #    `sequences`.

    #Post processing: convert sequence tuples to a operation sequence structure
    Ls = set()
    germs = _collections.OrderedDict()

    for opstr, L, germ, prepFid, measFid in sequences:
        Ls.add(L)
        if germ not in germs: germs[germ] = {}
        if L not in germs[germ]: germs[germ][L] = []
        germs[germ][L].append((prepFid, measFid))

    maxPlaqEls = max([len(fidpairs) for gdict in germs.values() for fidpairs in gdict.values()])
    nMinorRows = nMinorCols = int(_np.floor(_np.sqrt(maxPlaqEls)))
    if nMinorRows * nMinorCols < maxPlaqEls: nMinorCols += 1
    if nMinorRows * nMinorCols < maxPlaqEls: nMinorRows += 1
    assert(nMinorRows * nMinorCols >= maxPlaqEls), "Logic Error!"

    germList = list(germs.keys())  # ordered dict so retains nice ordering
    Ls = sorted(list(Ls))
    gss = _objs.LsGermsSerialStructure(Ls, germList, nMinorRows, nMinorCols,
                                       aliases=None, sequenceRules=None)

    for germ, gdict in germs.items():
        serial_germ = germ.serialize()  # must serialize to get correct count
        for L, fidpairs in gdict.items():
            germ_power = _gsc.repeat_with_max_length(serial_germ, L)
            gss.add_plaquette(germ_power, L, germ, fidpairs)  # returns 'missing_list'; useful if using dsfilter arg

    return gss


def _get_kcoverage_template_k2(n):
    """ Special case where k == 2 -> use hypercube construction """
    # k = 2 implies binary strings of 0's and 1's
    def bitstr(nQubits, bit):
        """ Returns a length-nQubits list of the values of the bit-th bit in the integers 0->nQubits"""
        return [((i >> bit) & 1) for i in range(nQubits)]

    def invert(bstr):
        return [(0 if x else 1) for x in bstr]

    half = [bitstr(n, k) for k in range(int(_np.ceil(_np.math.log(n, 2))))]
    other_half = [invert(bstr) for bstr in half]
    return half + other_half


def get_kcoverage_template(n, k, verbosity=0):
    """
    Get a template for how to create a "k-coverage" set of length-`n` sequences.

    Consider a set of length-`n` words from a `k`-letter alphabet.  These words
    (sequences of letters) have the "k-coverage" property if, for any choice of
    `k` different letter positions (indexed from 0 to `n-1`), every permutation
    of the `k` distinct letters (symbols) appears in those positions for at
    least one element (word) in the set.  Such a set of sequences is returned
    by this function, namely a list length-`n` lists containing the integers
    0 to `k-1`.

    This notion has application to idle-gate fiducial pair tiling, when we have
    found a set of fiducial pairs for `k` qubits and want to find a set of
    sequences on `n > k` qubits such that any subset of `k` qubits experiences
    the entire set of (`k`-qubit) fiducial pairs.  Simply take the k-coverage
    template and replace the letters (0 to `k-1`) with the per-qubit 1Q pieces
    of each k-qubit fiducial pair.

    Parameters
    ----------
    n, k : int
        The sequence (word) length and letter count as described above.

    verbosity : int, optional
        Amount of detail to print to stdout.

    Returns
    -------
    list
        A list of length-`n` lists containing the integers 0 to `k-1`.
        The length of the outer lists depends on the particular values
        of `n` and `k` and is not guaranteed to be minimal.
    """
    #n = total number of qubits
    #indices run 0->(k-1)
    assert(n >= k), "Total number of qubits must be >= k"

    if k == 2:
        return _get_kcoverage_template_k2(n)

    #first k cols -> k! permutations of the k indices:
    cols = [list() for i in range(k)]
    for row in _itertools.permutations(range(k), k):
        for i in range(k):
            cols[i].append(row[i])
    nRows = len(cols[0])
    if verbosity > 0: print("get_template(n=%d,k=%d):" % (n, k))

    # Now add cols k to n-1:
    for a in range(k, n):  # a is index of column we're adding
        if verbosity > 1: print(" - Adding column %d: currently %d rows" % (a, nRows))

        #We know that columns 0..(a-1) satisfy the property that
        # the values of any k of them contain every permutation
        # of the integers 0..(k-1) (perhaps multiple times).  It is
        # then also true that the values of any (k-1) columns take
        # on each Perm(k,k-1) - i.e. the length-(k-1) permutations of
        # the first k integers.
        #
        # So at this point we consider all combinations of k columns
        # that include the a-th one (so really just combinations of
        # k-1 existing colums), and fill in the a-th column values
        # so that the k-columns take on each permuations of k integers.
        #

        col_a = [None] * nRows  # the new column - start with None sentinels in all current rows

        # added heuristic step for increased efficiency:
        # preference each open element of the a-th column by taking the
        # "majority vote" among what the existing column values "want"
        # the a-th column to be.
        pref_a = []
        for m in range(nRows):
            votes = _collections.defaultdict(lambda: 0)
            for existing_cols in _itertools.combinations(range(a), k - 1):
                vals = set(range(k))  # the values the k-1 existing + a-th columns need to take
                vals = vals - set([cols[i][m] for i in existing_cols])
                if len(vals) > 1: continue  # if our chosen existing cols don't
                # even cover all but one val then don't cast a vote
                assert(len(vals) == 1)
                val = vals.pop()  # pops the *only* element
                votes[val] += 1

            majority = None; majority_cnt = 0
            for ky, val in votes.items():
                if val > majority_cnt:
                    majority, majority_cnt = ky, val
            pref_a.append(majority)

        for existing_cols in _itertools.combinations(range(a - 1, -1, -1), k - 1):  # reverse-range(a) == heuristic
            if verbosity > 2: print("  - check perms are present for cols %s" % str(existing_cols + (a,)))

            #make sure cols existing_cols + [a] take on all the needed permutations
            # Since existing_cols already takes on all permuations minus the last
            # value (which is determined as it's the only one missing from the k-1
            # existing cols) - we just need to *complete* each existing row and possibly
            # duplicate + add rows to ensure all completions exist.
            for desired_row in _itertools.permutations(range(k), k):

                matching_rows = []  # rows that match desired_row on existing_cols
                open_rows = []  # rows with a-th column open (unassigned)

                for m in range(nRows):
                    if all([cols[existing_cols[i]][m] == desired_row[i] for i in range(k - 1)]):
                        # m-th row matches desired_row on existing_cols
                        matching_rows.append(m)
                    if col_a[m] is None:
                        open_rows.append(m)

                if verbosity > 3: print("   - perm %s: %d rows, %d match perm, %d open"
                                        % (str(desired_row), nRows, len(matching_rows), len(open_rows)))
                v = {'value': desired_row[k - 1], 'alternate_rows': matching_rows}
                placed = False

                #Best: find a row that already has the value we're looking for (set via previous iteration)
                for m in matching_rows:
                    if col_a[m] and col_a[m]['value'] == desired_row[k - 1]:
                        # a perfect match! - no need to take an open slot
                        updated_alts = [i for i in col_a[m]['alternate_rows'] if i in matching_rows]
                        if verbosity > 3: print("    -> existing row (index %d) perfectly matches!" % m)
                        col_a[m]['alternate_rows'] = updated_alts; placed = True; break
                if placed: continue

                #Better: find an open row that prefers the value we want to place in it
                for m in matching_rows:
                    # slot is open & prefers the value we want to place in it - take it!
                    if col_a[m] is None and pref_a[m] == desired_row[k - 1]:
                        if verbosity > 3: print("    -> open preffered row (index %d) matches!" % m)
                        col_a[m] = v; placed = True; break
                if placed: continue

                #Good: find any open row (FUTURE: maybe try to shift for preference first?)
                for m in matching_rows:
                    if col_a[m] is None:  # slot is open - take it!
                        if verbosity > 3: print("    -> open row (index %d) matches!" % m)
                        col_a[m] = v; placed = True; break
                if placed: continue

                # no open slots
                # option1: (if there are any open rows)
                #  Look to swap an existing value in a matching row
                #   to an open row allowing us to complete the matching
                #   row using the current desired_row.
                open_rows = set(open_rows)  # b/c use intersection below
                shift_soln_found = False
                if len(open_rows) > 0:
                    for m in matching_rows:
                        # can assume col_a[m] is *not* None given above logic
                        ist = open_rows.intersection(col_a[m]['alternate_rows'])
                        if len(ist) > 0:
                            m2 = ist.pop()  # just get the first element
                            # move value in row m to m2, then put v into the now-open m-th row
                            col_a[m2] = col_a[m]
                            col_a[m] = v
                            if verbosity > 3: print("    -> row %d >> row %d, and row %d matches!" % (m, m2, m))
                            shift_soln_found = True
                            break

                if not shift_soln_found:
                    # no shifting can be performed to place v into an open row,
                    # so we just create a new row equal to desired_row on existing_cols.
                    # How do we choose the non-(existing & last) colums? For now, just
                    # replicate the first element of matching_rows:
                    if verbosity > 3: print("    -> creating NEW row.")
                    for i in range(a):
                        cols[i].append(cols[i][matching_rows[0]])
                    col_a.append(v)
                    nRows += 1

        #Check for any remaining open rows that we never needed to use.
        # (the a-th column can then be anything we want, so as heuristic
        #  choose a least-common value in the row already)
        for m in range(nRows):
            if col_a[m] is None:
                cnts = {v: 0 for v in range(k)}  # count of each possible value
                for i in range(a): cnts[cols[i][m]] += 1
                val = 0; mincnt = cnts[0]
                for v, cnt in cnts.items():  # get value with minimal count
                    if cnt < mincnt:
                        val = v; mincnt = cnt
                col_a[m] = {'value': val, 'alternate_rows': "N/A"}

        # a-th column is complete; "cement" it by replacing
        # value/alternative_rows dicts with just the values
        col_a = [d['value'] for d in col_a]
        cols.append(col_a)

    #convert cols to "strings" (rows)
    assert(len(cols) == n)
    rows = []
    for i in range(len(cols[0])):
        rows.append([cols[j][i] for j in range(n)])

    if verbosity > 0: print(" Done: %d rows total" % len(rows))
    return rows


def check_kcoverage_template(rows, n, k, verbosity=0):
    """
    Verify that `rows` satisfies the `k`-coverage conditions for length-`n`
    sequences.  Raises an AssertionError if the check fails.

    Parameters
    ----------
    rows : list
        A list of k-coverage words.  The same as whas is returned by
        :function:`get_kcoverage_template`.

    n, k : int
        The k-coverate word length and letter count.

    verbosity : int, optional
        Amount of detail to print to stdout.
    """
    if verbosity > 0: print("check_template(n=%d,k=%d)" % (n, k))

    #for each set of k qubits (of the total n qubits)
    for cols_to_check in _itertools.combinations(range(n), k):
        if verbosity > 1: print(" - checking cols %s" % str(cols_to_check))
        for perm in _itertools.permutations(range(k), k):
            for m, row in enumerate(rows):
                if all([row[i] == perm[i] for i in range(k)]):
                    if verbosity > 2: print("  - perm %s: found at row %d" % (str(perm), m))
                    break
            else:
                assert(False), \
                    "Permutation %s on qubits (cols) %s is not present!" % (str(perm), str(cols_to_check))
    if verbosity > 0: print(" check succeeded!")


def filter_nqubit_sequences(sequence_tuples, sectors_to_keep,
                            new_sectors=None, idle='Gi'):
    """
    Creates a new set of qubit sequences-tuples that is the restriction of
    `sequence_tuples` to the sectors identified by `sectors_to_keep`.

    More specifically, this function removes any operation labels which act
    specifically on sectors not in `sectors_to_keep` (e.g. an idle gate acting
    on *all* sectors because it's `.sslbls` is None will *not* be removed --
    see :function:`filter_circuit` for details).  Non-empty sequences for
    which all labels are removed in the *germ* are not included in the output
    (as these correspond to an irrelevant germ).

    A typical case is when the state-space is that of *n* qubits, and the
    state space labels the intergers 0 to *n-1*.  One may want to "rebase" the
    indices to 0 in the returned data set using `new_sectors`
    (E.g. `sectors_to_keep == [4,5,6]` and `new_sectors == [0,1,2]`).

    Parameters
    ----------
    sequence_tuples : list
        A list of (circuit, L, germ, prepfid, measfid) tuples giving the
        sequences to process.

    sectors_to_keep : list or tuple
        The state-space labels (strings or integers) of the "sectors" to keep in
        the returned tuple list.

    new_sectors : list or tuple, optional
        New sectors names to map the elements of `sectors_to_keep` onto in the
        output DataSet's operation sequences.  None means the labels are not renamed.
        This can be useful if, for instance, you want to run a 2-qubit protocol
        that expects the qubits to be labeled "0" and "1" on qubits "4" and "5"
        of a larger set.  Simply set `sectors_to_keep == [4,5]` and
        `new_sectors == [0,1]`.

    idle : string or Label, optional
        The operation label to be used when there are no kept components of a
        "layer" (element) of a circuit.


    Returns
    -------
    filtered_sequence_tuples : list
        A list of tuples with the same structure as `sequence tuples`.
    """
    ret = []
    for opstr, L, germ, prepfid, measfid in sequence_tuples:
        new_germ = _gsc.filter_circuit(germ, sectors_to_keep, new_sectors, idle)
        if len(new_germ) > 0 or len(opstr) == 0:
            new_prep = _gsc.filter_circuit(prepfid, sectors_to_keep, new_sectors, idle)
            new_meas = _gsc.filter_circuit(measfid, sectors_to_keep, new_sectors, idle)
            new_gstr = _gsc.filter_circuit(opstr, sectors_to_keep, new_sectors, idle)
            ret.append((new_gstr, L, new_germ, new_prep, new_meas))

    return ret


#Utility functions
def gatename_fidpair_list_to_fidpairs(gatename_fidpair_list):
    """
    Converts a "gatename fiducial pair list" to a standard list of 2-tuples
    of :class:`Circuit` objects.  This format is used internally for storing
    fiducial circuits containing only *single-qubit* gates.

    A "gatename fiducial pair list" is a list with one element per fiducial
    pair.  Each element is itself a list of `(prep_names, meas_names)` tuples,
    one per *qubit*.  `prep_names` and `meas_names` are tuples of simple strings
    giving the names of the (1-qubit) gates acting on the respective qubit.  The
    qubit labels for the output circuits are taken to be the integers starting
    at 0.

    For example, the input:
    `[ [ (('Gx','Gx'),('Gy',)),(('Gz','Gz'),()) ] ]`
    would result in:
    `[ ( Circuit(Gx:0Gx:0Gz:1Gz:1), Circuit(Gy:0) ) ]`

    Parameters
    ----------
    gatename_fidpair_list : list
        Each element corresponds to one (prep, meas) pair of circuits, and is
        a list of `(prep_names, meas_names)` tuples, on per qubit.

    Returns
    -------
    list
        A list of `(prep_fiducial, meas_fiducial)` pairs, where `prep_fiducial`
        and `meas_fiducial` are :class:`Circuit` objects.
    """
    fidpairs = []
    for gatenames_per_qubit in gatename_fidpair_list:
        prepStr = []
        measStr = []
        nQubits = len(gatenames_per_qubit)
        for iQubit, gatenames in enumerate(gatenames_per_qubit):
            prepnames, measnames = gatenames
            prepStr.extend([_Lbl(name, iQubit) for name in prepnames])
            measStr.extend([_Lbl(name, iQubit) for name in measnames])
        fidpair = (_objs.Circuit(prepStr, num_lines=nQubits),
                   _objs.Circuit(measStr, num_lines=nQubits))
        fidpairs.append(fidpair)
    return fidpairs


def fidpairs_to_gatename_fidpair_list(fidpairs, nQubits):
    """
    The inverse of :function:`gatename_fidpair_list_to_fidpairs`.

    Converts a list of `(prep,meas)` pairs of fiducial circuits (containing
    only single-qubit gates!) to the "gatename fiducial pair list" format,
    consisting of per-qubit lists of gate names (see docstring for
    :function:`gatename_fidpair_list_to_fidpairs` for mor details).

    Parameters
    ----------
    fidpairs : list
        A list of `(prep_fiducial, meas_fiducial)` pairs, where `prep_fiducial`
        and `meas_fiducial` are :class:`Circuit` objects.

    nQubits : int
        The number of qubits.  Qubit labels within `fidpairs` are assumed to
        be the integers from 0 to `nQubits-1`.

    Returns
    -------
    gatename_fidpair_list : list
        Each element corresponds to an elmeent of `fidpairs`, and is a list of
        `(prep_names, meas_names)` tuples, on per qubit.  `prep_names` and
        `meas_names` are tuples of single-qubit gate *names* (strings).
    """
    gatename_fidpair_list = []
    for fidpair in fidpairs:
        gatenames_per_qubit = [(list(), list()) for i in range(nQubits)]  # prepnames, measnames for each qubit
        prepStr, measStr = fidpair

        for lbl in prepStr:
            assert(len(lbl.sslbls) == 1), "Can only convert strings with solely 1Q gates"
            gatename = lbl.name
            iQubit = lbl.sslbls[0]
            gatenames_per_qubit[iQubit][0].append(gatename)

        for lbl in measStr:
            assert(len(lbl.sslbls) == 1), "Can only convert strings with solely 1Q gates"
            gatename = lbl.name
            iQubit = lbl.sslbls[0]
            gatenames_per_qubit[iQubit][1].append(gatename)

        #Convert lists -> tuples
        gatenames_per_qubit = tuple([(tuple(x[0]), tuple(x[1])) for x in gatenames_per_qubit])
        gatename_fidpair_list.append(gatenames_per_qubit)
    return gatename_fidpair_list


def stdmodule_to_smqmodule(std_module):
    """
    Converts a pyGSTi "standard module" to a "standard multi-qubit module".

    PyGSTi provides a number of 1- and 2-qubit models corrsponding to commonly
    used gate sets, along with related meta-information.  Each such
    model+metadata is stored in a "standard module" beneath `pygsti.construction`
    (e.g. `pygsti.construction.std1Q_XYI` is the standard module for modeling a
    single-qubit quantum processor which can perform X(pi/2), Y(pi/2) and idle
    operations).  Because they deal with just 1- and 2-qubit models, multi-qubit
    labelling conventions are not used to improve readability.  For example, a
    "X(pi/2)" gate is labelled "Gx" (in a 1Q context) or "Gix" (in a 2Q context)
    rather than "Gx:0" or "Gx:1" respectively.

    There are times, however, when you many *want* a standard module with this
    multi-qubit labelling convention (e.g. performing 1Q-GST on the 3rd qubit
    of a 5-qubit processor).  We call such a module a standard *multi-qubit*
    module, and these typically begin with `"smq"` rather than `"std"`.

    Standard multi-qubit modules are *created* by this function.  For example,
    If you want the multi-qubit version of `pygsti.construction.std1Q_XYI`
    you must:

    1. import `std1Q_XYI` (`from pygsti.construction import std1Q_XYI`)
    2. call this function (i.e. `stdmodule_to_smqmodule(std1Q_XYI)`)
    3. import `smq1Q_XYI` (`from pygsti.construction import smq1Q_XYI`)

    The `smq1Q_XYI` module will look just like the `std1Q_XYI` module but use
    multi-qubit labelling conventions.

    Parameters
    ----------
    std_module : Module
        The standard module to convert to a standard-multi-qubit module.

    Returns
    -------
    Module
       The new module, although it's better to import this using the appropriate
       "smq"-prefixed name as described above.
    """
    from types import ModuleType as _ModuleType
    import sys as _sys
    import importlib

    std_module_name_parts = std_module.__name__.split('.')
    std_module_name_parts[-1] = std_module_name_parts[-1].replace('std', 'smq')
    new_module_name = '.'.join(std_module_name_parts)

    try:
        return importlib.import_module(new_module_name)
    except ImportError:
        pass  # ok, this is what the rest of the function is for

    out_module = {}
    std_target_model = std_module.target_model()  # could use ._target_model to save a copy
    dim = std_target_model.dim
    if dim == 4:
        sslbls = [0]
        find_replace_labels = {'Gi': (), 'Gx': ('Gx', 0), 'Gy': ('Gy', 0),
                               'Gz': ('Gz', 0), 'Gn': ('Gn', 0)}
        find_replace_strs = [((oldgl,), (newgl,)) for oldgl, newgl
                             in find_replace_labels.items()]
    elif dim == 16:
        sslbls = [0, 1]
        find_replace_labels = {'Gii': (),
                               'Gxi': ('Gx', 0), 'Gyi': ('Gy', 0), 'Gzi': ('Gz', 0),
                               'Gix': ('Gx', 1), 'Giy': ('Gy', 1), 'Giz': ('Gz', 1),
                               'Gxx': ('Gxx', 0, 1), 'Gxy': ('Gxy', 0, 1),
                               'Gyx': ('Gxy', 0, 1), 'Gyy': ('Gyy', 0, 1),
                               'Gcnot': ('Gcnot', 0, 1), 'Gcphase': ('Gcphase', 0, 1)}
        find_replace_strs = [((oldgl,), (newgl,)) for oldgl, newgl
                             in find_replace_labels.items()]
        #find_replace_strs.append( (('Gxx',), (('Gx',0),('Gx',1))) )
        #find_replace_strs.append( (('Gxy',), (('Gx',0),('Gy',1))) )
        #find_replace_strs.append( (('Gyx',), (('Gy',0),('Gx',1))) )
        #find_replace_strs.append( (('Gyy',), (('Gy',0),('Gy',1))) )
    else:
        #TODO: add qutrit?
        raise ValueError("Unsupported model dimension: %d" % dim)

    def upgrade_dataset(ds):
        """
        Update DataSet `ds` in-place to use  multi-qubit style labels.
        """
        ds.process_circuits(lambda s: _gsc.manipulate_circuit(
            s, find_replace_strs, sslbls))

    out_module['find_replace_gatelabels'] = find_replace_labels
    out_module['find_replace_circuits'] = find_replace_strs
    out_module['upgrade_dataset'] = upgrade_dataset

    # gate names
    out_module['gates'] = [find_replace_labels.get(nm, nm) for nm in std_module.gates]

    #Fully-parameterized target model (update labels)
    new_target_model = _objs.ExplicitOpModel(sslbls, std_target_model.basis.copy())
    new_target_model._evotype = std_target_model._evotype
    new_target_model._default_gauge_group = std_target_model._default_gauge_group

    for lbl, obj in std_target_model.preps.items():
        new_lbl = find_replace_labels.get(lbl, lbl)
        new_target_model.preps[new_lbl] = obj.copy()
    for lbl, obj in std_target_model.povms.items():
        new_lbl = find_replace_labels.get(lbl, lbl)
        new_target_model.povms[new_lbl] = obj.copy()
    for lbl, obj in std_target_model.operations.items():
        new_lbl = find_replace_labels.get(lbl, lbl)
        new_target_model.operations[new_lbl] = obj.copy()
    for lbl, obj in std_target_model.instruments.items():
        new_lbl = find_replace_labels.get(lbl, lbl)
        new_target_model.instruments[new_lbl] = obj.copy()
    out_module['_target_model'] = new_target_model

    # _stdtarget and _gscache need to be *locals* as well so target_model(...) works
    _stdtarget = importlib.import_module('.stdtarget', 'pygsti.construction')
    _gscache = {("full", "auto"): new_target_model}
    out_module['_stdtarget'] = _stdtarget
    out_module['_gscache'] = _gscache

    def target_model(parameterization_type="full", sim_type="auto"):
        """
        Returns a copy of the target model in the given parameterization.

        Parameters
        ----------
        parameterization_type : {"TP", "CPTP", "H+S", "S", ... }
            The gate and SPAM vector parameterization type. See
            :function:`Model.set_all_parameterizations` for all allowed values.

        sim_type : {"auto", "matrix", "map", "termorder:X" }
            The simulator type to be used for model calculations (leave as
            "auto" if you're not sure what this is).

        Returns
        -------
        Model
        """
        return _stdtarget._copy_target(_sys.modules[new_module_name], parameterization_type,
                                       sim_type, _gscache)
    out_module['target_model'] = target_model

    # circuit lists
    circuitlist_names = ['germs', 'germs_lite', 'prepStrs', 'effectStrs', 'fiducials']
    for nm in circuitlist_names:
        if hasattr(std_module, nm):
            out_module[nm] = _gsc.manipulate_circuit_list(getattr(std_module, nm), find_replace_strs, sslbls)

    # clifford compilation (keys are lists of operation labels)
    if hasattr(std_module, 'clifford_compilation'):
        new_cc = _collections.OrderedDict()
        for ky, val in std_module.clifford_compilation.items():
            new_val = [find_replace_labels.get(lbl, lbl) for lbl in val]
            new_cc[ky] = new_val

    passthrough_names = ['global_fidPairs', 'pergerm_fidPairsDict', 'global_fidPairs_lite', 'pergerm_fidPairsDict_lite']
    for nm in passthrough_names:
        if hasattr(std_module, nm):
            out_module[nm] = getattr(std_module, nm)

    #Create the new module
    new_module = _ModuleType(str(new_module_name))  # str(.) converts to native string for Python 2 compatibility
    for k, v in out_module.items():
        setattr(new_module, k, v)
    _sys.modules[new_module_name] = new_module
    return new_module
