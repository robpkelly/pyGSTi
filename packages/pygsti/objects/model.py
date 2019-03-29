""" Defines the Model class and supporting functionality."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
import scipy as _scipy
import itertools as _itertools
import collections as _collections
import warnings as _warnings
import time as _time
import uuid as _uuid
import bisect as _bisect
import copy as _copy

from ..tools import matrixtools as _mt
from ..tools import optools as _gt
from ..tools import slicetools as _slct
from ..tools import likelihoodfns as _lf
from ..tools import jamiolkowski as _jt
from ..tools import compattools as _compat
from ..tools import basistools as _bt
from ..tools import listtools as _lt
from ..tools import symplectic as _symp

from . import modelmember as _gm
from . import circuit as _cir
from . import operation as _op
from . import spamvec as _sv
from . import povm as _povm
from . import instrument as _instrument
from . import labeldicts as _ld
from . import gaugegroup as _gg
from . import matrixforwardsim as _matrixfwdsim
from . import mapforwardsim as _mapfwdsim
from . import termforwardsim as _termfwdsim
from . import explicitcalc as _explicitcalc

from ..baseobjs import VerbosityPrinter as _VerbosityPrinter
from ..baseobjs import Basis as _Basis
from ..baseobjs import BuiltinBasis as _BuiltinBasis
from ..baseobjs import Label as _Label


class Model(object):
    """
    A predictive model for a Quantum Information Processor (QIP).

    The main function of a `Model` object is to compute the outcome
    probabilities of :class:`Circuit` objects based on the action of the
    model's ideal operations plus (potentially) noise which makes the
    outcome probabilities deviate from the perfect ones.
    """

    def __init__(self, state_space_labels):
        """
        Creates a new Model.  Rarely used except from derived classes
        `__init__` functions.

        Parameters
        ----------
        state_space_labels : StateSpaceLabels or list or tuple
            The decomposition (with labels) of (pure) state-space this model
            acts upon.  Regardless of whether the model contains operators or
            superoperators, this argument describes the Hilbert space dimension
            and imposed structure.  If a list or tuple is given, it must be
            of a from that can be passed to `StateSpaceLabels.__init__`.
        """
        if isinstance(state_space_labels, _ld.StateSpaceLabels):
            self._state_space_labels = state_space_labels
        else:
            self._state_space_labels = _ld.StateSpaceLabels(state_space_labels)

        self._hyperparams = {}
        self._paramvec = _np.zeros(0, 'd')
        self._paramlbls = None  # a placeholder for FUTURE functionality
        self.uuid = _uuid.uuid4()  # a Model's uuid is like a persistent id(), useful for hashing

    @property
    def state_space_labels(self):
        """ State space labels """
        return self._state_space_labels

    @property
    def hyperparams(self):
        """ Dictionary of hyperparameters associated with this model """
        return self._hyperparams  # Note: no need to set this param - just set/update values

    def num_params(self):
        """
        Return the number of free parameters when vectorizing
        this model.

        Returns
        -------
        int
            the number of model parameters.
        """
        return len(self._paramvec)

    def to_vector(self):
        """
        Returns the model vectorized according to the optional parameters.

        Returns
        -------
        numpy array
            The vectorized model parameters.
        """
        return self._paramvec

    def from_vector(self, v, reset_basis=False):
        """
        The inverse of to_vector.  Loads values of gates and rho and E vecs from
        from the vector `v`.  Note that `v` does not specify the number of
        gates, etc., and their labels: this information must be contained in
        this `Model` prior to calling `from_vector`.  In practice, this just
        means you should call the `from_vector` method using the same `Model`
        that was used to generate the vector `v` in the first place.
        """
        assert(len(v) == self.num_params())
        self._paramvec = v.copy()

    def probs(self, circuit, clipTo=None):
        """
        Construct a dictionary containing the probabilities of every spam label
        given a operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        clipTo : 2-tuple, optional
           (min,max) to clip probabilities to if not None.

        Returns
        -------
        probs : dictionary
            A dictionary such that
            probs[SL] = pr(SL,circuit,clipTo)
            for each spam label (string) SL.
        """
        raise NotImplementedError("Derived classes should implement this!")

    def dprobs(self, circuit, returnPr=False, clipTo=None):
        """
        Construct a dictionary containing the probability derivatives of every
        spam label for a given operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        Returns
        -------
        dprobs : dictionary
            A dictionary such that
            dprobs[SL] = dpr(SL,circuit,gates,G0,SPAM,SP0,returnPr,clipTo)
            for each spam label (string) SL.
        """
        #Finite difference default?
        raise NotImplementedError("Derived classes should implement this!")

    def hprobs(self, circuit, returnPr=False, returnDeriv=False, clipTo=None):
        """
        Construct a dictionary containing the probability derivatives of every
        spam label for a given operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        returnDeriv : bool, optional
          when set to True, additionally return the derivatives of the
          probabilities.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        Returns
        -------
        hprobs : dictionary
            A dictionary such that
            hprobs[SL] = hpr(SL,circuit,gates,G0,SPAM,SP0,returnPr,returnDeriv,clipTo)
            for each spam label (string) SL.
        """
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_evaltree_from_resources(self, circuit_list, comm=None, memLimit=None,
                                     distributeMethod="default", subcalls=[],
                                     dataset=None, verbosity=0):
        raise NotImplementedError("Derived classes should implement this!")
        #return circuit_list # MORE?

    def bulk_evaltree(self, circuit_list, minSubtrees=None, maxTreeSize=None,
                      numSubtreeComms=1, dataset=None, verbosity=0):
        raise NotImplementedError("Derived classes should implement this!")
        #return circuit_list # MORE?

    #def uses_evaltrees(self):
    #    """
    #    Whether or not this model uses evaluation trees to compute many
    #    (bulk) probabilities and their derivatives.
    #
    #    Returns
    #    -------
    #    bool
    #    """
    #    return False

    def bulk_probs(self, circuit_list, clipTo=None, check=False,
                   comm=None, memLimit=None, dataset=None, smartc=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_dprobs(self, circuit_list, returnPr=False, clipTo=None,
                    check=False, comm=None, wrtBlockSize=None, dataset=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_hprobs(self, circuit_list, returnPr=False, returnDeriv=False,
                    clipTo=None, check=False, comm=None,
                    wrtBlockSize1=None, wrtBlockSize2=None, dataset=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_fill_probs(self, mxToFill, evalTree, clipTo=None, check=False, comm=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_fill_dprobs(self, mxToFill, evalTree, prMxToFill=None, clipTo=None,
                         check=False, comm=None, wrtBlockSize=None,
                         profiler=None, gatherMemLimit=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_fill_hprobs(self, mxToFill, evalTree=None,
                         prMxToFill=None, derivMxToFill=None,
                         clipTo=None, check=False, comm=None,
                         wrtBlockSize1=None, wrtBlockSize2=None,
                         gatherMemLimit=None):
        raise NotImplementedError("Derived classes should implement this!")

    def bulk_hprobs_by_block(self, evalTree, wrtSlicesList,
                             bReturnDProbs12=False, comm=None):
        raise NotImplementedError("Derived classes should implement this!")

    def _init_copy(self, copyInto):
        """
        Copies any "tricky" member of this model into `copyInto`, before
        deep copying everything else within a .copy() operation.
        """
        copyInto.uuid = _uuid.uuid4()  # new uuid for a copy (don't duplicate!)

    def copy(self):
        """
        Copy this model.

        Returns
        -------
        Model
            a (deep) copy of this model.
        """
        #Avoid having to reconstruct everything via __init__;
        # essentially deepcopy this object, but give the
        # class opportunity to initialize tricky members instead
        # of letting deepcopy do it.
        newModel = type(self).__new__(self.__class__)  # empty object

        #first call _init_copy to initialize any tricky members
        # (like those that contain references to self or other members)
        self._init_copy(newModel)

        for attr, val in self.__dict__.items():
            if not hasattr(newModel, attr):
                assert(attr != "uuid"), "Should not be copying UUID!"
                setattr(newModel, attr, _copy.deepcopy(val))

        return newModel

    def __str__(self):
        pass

    def __hash__(self):
        if self.uuid is not None:
            return hash(self.uuid)
        else:
            raise TypeError('Use digest hash')


class OpModel(Model):
    """
    A Model containing operators (i.e. "members") which are independently
    (sort of) parameterized and can be thought to have dense representations
    (even if they're not actually stored that way).  This gives rise to the
    model having `basis` and `evotype` members.

    Secondly, attached to an `OpModel` is the idea of "circuit simplification"
    whereby the operators (preps, operations, povms, instruments) within
    a circuit get simplified to things corresponding to a single outcome
    probability, i.e. pseudo-circuits containing just preps, operations,
    and POMV effects.

    Thirdly, an `OpModel` is assumed to use a *layer-by-layer* evolution, and,
    because of circuit simplification process, the calculaton of circuit
    outcome probabilities has been pushed to a :class:`ForwardSimulator`
    object which just deals with the forward simulation of simplified circuits.
    Furthermore, instead of relying on a static set of operations a forward
    simulator queries a :class:`LayerLizard` for layer operations, making it
    possible to build up layer operations in an on-demand fashion from pieces
    within the model.
    """

    #Whether to perform extra parameter-vector integrity checks
    _pcheck = False

    def __init__(self, state_space_labels, basis, evotype, simplifier_helper, sim_type="auto"):
        """
        Creates a new OpModel.  Rarely used except from derived classes
        `__init__` functions.

        Parameters
        ----------
        state_space_labels : StateSpaceLabels or list or tuple
            The decomposition (with labels) of (pure) state-space this model
            acts upon.  Regardless of whether the model contains operators or
            superoperators, this argument describes the Hilbert space dimension
            and imposed structure.  If a list or tuple is given, it must be
            of a from that can be passed to `StateSpaceLabels.__init__`.

        basis : Basis
            The basis used for the state space by dense operator representations.

        evotype : {"densitymx", "statevec", "stabilizer", "svterm", "cterm"}
            The evolution type of this model, describing how states are
            represented, allowing compatibility checks with (super)operator
            objects.

        simplifier_helper : SimplifierHelper
            Provides a minimal interface for compiling circuits for forward
            simulation.

        sim_type : {"auto", "matrix", "map", "termorder:X"}
            The type of forward simulator this model should use.  `"auto"`
            tries to determine the best type automatically.
        """
        self._evotype = evotype
        self.set_state_space(state_space_labels, basis)
        #sets self._state_space_labels, self._basis, self._dim

        self.set_simtype(sim_type)
        #sets self._calcClass, self._sim_type, self._sim_args

        self._shlp = simplifier_helper
        self._need_to_rebuild = True  # whether we call _rebuild_paramvec() in to_vector() or num_params()
        self.dirty = False  # indicates when objects and _paramvec may be out of sync

        super(OpModel, self).__init__(self.state_space_labels)

    ##########################################
    ## Get/Set methods
    ##########################################

    @property
    def simtype(self):
        """ Forward simulation type """
        return self._sim_type

    @property
    def evotype(self):
        """ Evolution type """
        return self._evotype

    @property
    def basis(self):
        """ The basis used to represent dense (super)operators of this model """
        return self._basis

    @basis.setter
    def basis(self, basis):
        if isinstance(basis, _Basis):
            assert(basis.dim == self.state_space_labels.dim), \
                "Cannot set basis w/dim=%d when sslbls dim=%d!" % (basis.dim, self.state_space_labels.dim)
            self._basis = basis
        else:  # create a basis with the proper structure & dimension
            self._basis = _Basis.cast(basis, self.state_space_labels)

    def set_simtype(self, sim_type, calc_cache=None, max_cache_size=None):
        """
        Reset the forward simulation type of this model.

        Parameters
        ----------
        sim_type : {"auto", "matrix", "map", "termorder:X"}
            The type of forward simulator this model should use.  `"auto"`
            tries to determine the best type automatically.

        calc_cache : dict or None
            A cache of pre-computed values used in Taylor-term-based forward
            simulation.

        Returns
        -------
        None
        """
        #Calculator selection based on simulation type

        if sim_type == "auto":
            default_param = self.operations.default_param  # assume the same for other dicts
            if _gt.is_valid_lindblad_paramtype(default_param) and \
               _gt.split_lindblad_paramtype(default_param)[1] in ("svterm", "cterm"):
                sim_type = "termorder:1"
            else:
                d = self._dim if (self._dim is not None) else 0
                sim_type = "matrix" if d <= 16 else "map"

        simtype_and_args = sim_type.split(":")
        sim_type = simtype_and_args[0]
        if sim_type == "matrix": c = _matrixfwdsim.MatrixForwardSimulator
        elif sim_type == "map": c = _mapfwdsim.MapForwardSimulator
        elif sim_type == "termorder": c = _termfwdsim.TermForwardSimulator
        else: raise ValueError("Invalid `sim_type` (%s)" % sim_type)

        self._calcClass = c
        self._sim_type = sim_type
        self._sim_args = list(simtype_and_args[1:])

        if sim_type == "termorder":
            cache = calc_cache if (calc_cache is not None) else {}  # make a temp cache if none is given
            self._sim_args.append(cache)  # add calculation cache as another argument
        elif sim_type == "map":
            self._sim_args.append(max_cache_size)  # add cache size as another argument

    #TODO REMOVE
    #def reset_basis(self):
    #    """
    #    "Forgets" the current basis, so that
    #    self.basis becomes a dummy Basis w/name "unknown".
    #    """
    #    self._basis = _BuiltinBasis('unknown', 0)

    def set_state_space(self, lbls, basis="pp"):
        """
        Sets labels for the components of the Hilbert space upon which
        the gates of this Model act.

        Parameters
        ----------
        lbls : list or tuple or StateSpaceLabels object
            A list of state-space labels (can be strings or integers), e.g.
            `['Q0','Q1']` or a :class:`StateSpaceLabels` object.

        basis : Basis or str
            A :class:`Basis` object or a basis name (like `"pp"`), specifying
            the basis used to interpret the operators in this Model.  If a
            `Basis` object, then its dimensions must match those of `lbls`.

        Returns
        -------
        None
        """
        if isinstance(lbls, _ld.StateSpaceLabels):
            self._state_space_labels = lbls
        else:
            self._state_space_labels = _ld.StateSpaceLabels(lbls, evotype=self._evotype)
        self.basis = basis  # invokes basis setter to set self._basis

        #Operator dimension of this Model
        self._dim = self.state_space_labels.dim
        #e.g. 4 for 1Q (densitymx) or 2 for 1Q (statevec)

    @property
    def dim(self):
        """
        The dimension of the model, which equals d when the gate
        matrices have shape d x d and spam vectors have shape d x 1.

        Returns
        -------
        int
            model dimension
        """
        return self._dim

    def get_dimension(self):
        """
        Get the dimension of the model, which equals d when the gate
        matrices have shape d x d and spam vectors have shape d x 1.
        Equivalent to model.dim.

        Returns
        -------
        int
            model dimension
        """
        return self._dim

    ####################################################
    ## Parameter vector maintenance
    ####################################################

    def num_params(self):
        """
        Return the number of free parameters when vectorizing
        this model.

        Returns
        -------
        int
            the number of model parameters.
        """
        self._clean_paramvec()
        return len(self._paramvec)

    def _iter_parameterized_objs(self):
        raise NotImplementedError("Derived Model classes should implement _iter_parameterized_objs")
        #return # default is to have no parameterized objects

    def _check_paramvec(self, debug=False):
        if debug: print("---- Model._check_paramvec ----")

        TOL = 1e-8
        for lbl, obj in self._iter_parameterized_objs():
            if debug: print(lbl, ":", obj.num_params(), obj.gpindices)
            w = obj.to_vector()
            msg = "None" if (obj.parent is None) else id(obj.parent)
            assert(obj.parent is self), "%s's parent is not set correctly (%s)!" % (lbl, msg)
            if obj.gpindices is not None and len(w) > 0:
                if _np.linalg.norm(self._paramvec[obj.gpindices] - w) > TOL:
                    if debug: print(lbl, ".to_vector() = ", w, " but Model's paramvec = ", self._paramvec[obj.gpindices])
                    raise ValueError("%s is out of sync with paramvec!!!" % lbl)
            if self.dirty == False and obj.dirty:
                raise ValueError("%s is dirty but Model.dirty=False!!" % lbl)

    def _clean_paramvec(self):
        """ Updates _paramvec corresponding to any "dirty" elements, which may
            have been modified without out knowing, leaving _paramvec out of
            sync with the element's internal data.  It *may* be necessary
            to resolve conflicts where multiple dirty elements want different
            values for a single parameter.  This method is used as a safety net
            that tries to insure _paramvec & Model elements are consistent
            before their use."""

        #print("Cleaning Paramvec (dirty=%s, rebuild=%s)" % (self.dirty, self._need_to_rebuild))
        if self._need_to_rebuild:
            self._rebuild_paramvec()
            self._need_to_rebuild = False

        if self.dirty:  # if any member object is dirty (ModelMember.dirty setter should set this value)
            TOL = 1e-8

            #Note: lbl args used *just* for potential debugging - could strip out once
            # we're confident this code always works.
            def clean_single_obj(obj, lbl):  # sync an object's to_vector result w/_paramvec
                if obj.dirty:
                    w = obj.to_vector()
                    chk_norm = _np.linalg.norm(self._paramvec[obj.gpindices] - w)
                    #print(lbl, " is dirty! vec = ", w, "  chk_norm = ",chk_norm)
                    if (not _np.isfinite(chk_norm)) or chk_norm > TOL:
                        self._paramvec[obj.gpindices] = w
                    obj.dirty = False

            def clean_obj(obj, lbl):  # recursive so works with objects that have sub-members
                for i, subm in enumerate(obj.submembers()):
                    clean_obj(subm, _Label(lbl.name + ":%d" % i, lbl.sslbls))
                clean_single_obj(obj, lbl)

            def reset_dirty(obj):  # recursive so works with objects that have sub-members
                for i, subm in enumerate(obj.submembers()): reset_dirty(subm)
                obj.dirty = False

            for lbl, obj in self._iter_parameterized_objs():
                clean_obj(obj, lbl)

            #re-update everything to ensure consistency ~ self.from_vector(self._paramvec)
            #print("DEBUG: non-trivially CLEANED paramvec due to dirty elements")
            for _, obj in self._iter_parameterized_objs():
                obj.from_vector(self._paramvec[obj.gpindices])
                reset_dirty(obj)  # like "obj.dirty = False" but recursive
                #object is known to be consistent with _paramvec

        if OpModel._pcheck: self._check_paramvec()

    def _mark_for_rebuild(self, modified_obj=None):
        #re-initialze any members that also depend on the updated parameters
        self._need_to_rebuild = True
        for _, o in self._iter_parameterized_objs():
            if o._obj_refcount(modified_obj) > 0:
                o.clear_gpindices()  # ~ o.gpindices = None but works w/submembers
                # (so params for this obj will be rebuilt)
        self.dirty = True
        #since it's likely we'll set at least one of our object's .dirty flags
        # to True (and said object may have parent=None and so won't
        # auto-propagate up to set this model's dirty flag (self.dirty)

    def _print_gpindices(self):
        print("PRINTING MODEL GPINDICES!!!")
        for lbl, obj in self._iter_parameterized_objs():
            print("LABEL ", lbl)
            obj._print_gpindices()

    def _rebuild_paramvec(self):
        """ Resizes self._paramvec and updates gpindices & parent members as needed,
            and will initialize new elements of _paramvec, but does NOT change
            existing elements of _paramvec (use _update_paramvec for this)"""
        v = self._paramvec
        Np = len(self._paramvec)  # NOT self.num_params() since the latter calls us!
        off = 0
        shift = 0

        #ellist = ", ".join(map(str,list(self.preps.keys()) +list(self.povms.keys()) +list(self.operations.keys())))
        #print("DEBUG: rebuilding... %s" % ellist)

        #Step 1: remove any unused indices from paramvec and shift accordingly
        used_gpindices = set()
        for _, obj in self._iter_parameterized_objs():
            if obj.gpindices is not None:
                assert(obj.parent is self), "Member's parent is not set correctly (%s)!" % str(obj.parent)
                used_gpindices.update(obj.gpindices_as_array())
            else:
                assert(obj.parent is self or obj.parent is None)
                #Note: ok for objects to have parent == None if their gpindices is also None

        indices_to_remove = sorted(set(range(Np)) - used_gpindices)

        if len(indices_to_remove) > 0:
            #print("DEBUG: Removing %d params:"  % len(indices_to_remove), indices_to_remove)
            v = _np.delete(v, indices_to_remove)
            def get_shift(j): return _bisect.bisect_left(indices_to_remove, j)
            memo = set()  # keep track of which object's gpindices have been set
            for _, obj in self._iter_parameterized_objs():
                if obj.gpindices is not None:
                    if id(obj) in memo: continue  # already processed
                    if isinstance(obj.gpindices, slice):
                        new_inds = _slct.shift(obj.gpindices,
                                               -get_shift(obj.gpindices.start))
                    else:
                        new_inds = []
                        for i in obj.gpindices:
                            new_inds.append(i - get_shift(i))
                        new_inds = _np.array(new_inds, _np.int64)
                    obj.set_gpindices(new_inds, self, memo)

        # Step 2: add parameters that don't exist yet
        memo = set()  # keep track of which object's gpindices have been set
        for lbl, obj in self._iter_parameterized_objs():

            if shift > 0 and obj.gpindices is not None:
                if isinstance(obj.gpindices, slice):
                    obj.set_gpindices(_slct.shift(obj.gpindices, shift), self, memo)
                else:
                    obj.set_gpindices(obj.gpindices + shift, self, memo)  # works for integer arrays

            if obj.gpindices is None or obj.parent is not self:
                #Assume all parameters of obj are new independent parameters
                num_new_params = obj.allocate_gpindices(off, self)
                objvec = obj.to_vector()  # may include more than "new" indices
                if num_new_params > 0:
                    new_local_inds = _gm._decompose_gpindices(obj.gpindices, slice(off, off + num_new_params))
                    assert(len(objvec[new_local_inds]) == num_new_params)
                    v = _np.insert(v, off, objvec[new_local_inds])
                #print("objvec len = ",len(objvec), "num_new_params=",num_new_params," gpinds=",obj.gpindices) #," loc=",new_local_inds)

                #obj.set_gpindices( slice(off, off+obj.num_params()), self )
                #shift += obj.num_params()
                #off += obj.num_params()

                shift += num_new_params
                off += num_new_params
                #print("DEBUG: %s: alloc'd & inserted %d new params.  indices = " % (str(lbl),obj.num_params()), obj.gpindices, " off=",off)
            else:
                inds = obj.gpindices_as_array()
                M = max(inds) if len(inds) > 0 else -1
                L = len(v)
                #print("DEBUG: %s: existing indices = " % (str(lbl)), obj.gpindices, " M=",M," L=",L)
                if M >= L:
                    #Some indices specified by obj are absent, and must be created.
                    w = obj.to_vector()
                    v = _np.concatenate((v, _np.empty(M + 1 - L, 'd')), axis=0)  # [v.resize(M+1) doesn't work]
                    shift += M + 1 - L
                    for ii, i in enumerate(inds):
                        if i >= L: v[i] = w[ii]
                    #print("DEBUG:    --> added %d new params" % (M+1-L))
                if M >= 0:  # M == -1 signifies this object has no parameters, so we'll just leave `off` alone
                    off = M + 1

        self._paramvec = v
        #print("DEBUG: Done rebuild: %d params" % len(v))

    def _init_virtual_obj(self, obj):
        """
        Initializes a "virtual object" - an object (e.g. LinearOperator) that *could* be a
        member of the Model but won't be, as it's just built for temporary
        use (e.g. the parallel action of several "base" gates).  As such
        we need to fully initialize its parent and gpindices members so it
        knows it belongs to this Model BUT it's not allowed to add any new
        parameters (they'd just be temporary).  It's also assumed that virtual
        objects don't need to be to/from-vectored as there are already enough
        real (non-virtual) gates/spamvecs/etc. to accomplish this.
        """
        if obj.gpindices is not None:
            assert(obj.parent is self), "Virtual obj has incorrect parent already set!"
            return  # if parent is already set we assume obj has already been init

        #Assume all parameters of obj are new independent parameters
        num_new_params = obj.allocate_gpindices(self.num_params(), self)
        assert(num_new_params == 0), "Virtual object is requesting %d new params!" % num_new_params

    def _obj_refcount(self, obj):
        """ Number of references to `obj` contained within this Model """
        cnt = 0
        for _, o in self._iter_parameterized_objs():
            cnt += o._obj_refcount(obj)
        return cnt

    def to_vector(self):
        """
        Returns the model vectorized according to the optional parameters.

        Returns
        -------
        numpy array
            The vectorized model parameters.
        """
        self._clean_paramvec()  # will rebuild if needed
        return self._paramvec

    def from_vector(self, v):
        """
        The inverse of to_vector.  Loads values of gates and rho and E vecs from
        from the vector `v`.  Note that `v` does not specify the number of
        gates, etc., and their labels: this information must be contained in
        this `Model` prior to calling `from_vector`.  In practice, this just
        means you should call the `from_vector` method using the same `Model`
        that was used to generate the vector `v` in the first place.
        """
        assert(len(v) == self.num_params())

        self._paramvec = v.copy()
        for _, obj in self._iter_parameterized_objs():
            obj.from_vector(v[obj.gpindices])
            obj.dirty = False  # object is known to be consistent with _paramvec

        #if reset_basis:
        #    self.reset_basis()
            # assume the vector we're loading isn't producing gates & vectors in
            # a known basis.
        if OpModel._pcheck: self._check_paramvec()

    ######################################
    ## Compilation
    ######################################

    def _layer_lizard(self):
        """ Return a layer lizard for this model """
        raise NotImplementedError("Derived Model classes should implement this!")

    def _fwdsim(self):
        """ Create & return a forward-simulator ("calculator") for this model """
        self._clean_paramvec()
        layer_lizard = self._layer_lizard()

        kwargs = {}
        if self._sim_type == "termorder":
            kwargs['max_order'] = int(self._sim_args[0])
            kwargs['cache'] = self._sim_args[-1]  # always the list argument
        if self._sim_type == "map":
            kwargs['max_cache_size'] = self._sim_args[0] if len(self._sim_args) > 0 else None  # backward compat

        assert(self._calcClass is not None), "Model does not have a calculator setup yet!"
        return self._calcClass(self._dim, layer_lizard, self._paramvec, **kwargs)  # fwdsim class

    def split_circuit(self, circuit, erroron=('prep', 'povm')):
        """
        Splits a operation sequence into prepLabel + opsOnlyString + povmLabel
        components.  If `circuit` does not contain a prep label or a
        povm label a default label is returned if one exists.

        Parameters
        ----------
        circuit : Circuit
            A operation sequence, possibly beginning with a state preparation
            label and ending with a povm label.

        erroron : tuple of {'prep','povm'}
            A ValueError is raised if a preparation or povm label cannot be
            resolved when 'prep' or 'povm' is included in 'erroron'.  Otherwise
            `None` is returned in place of unresolvable labels.  An exception
            is when this model has no preps or povms, in which case `None`
            is always returned and errors are never raised, since in this
            case one usually doesn't expect to use the Model to compute
            probabilities (e.g. in germ selection).

        Returns
        -------
        prepLabel : str or None
        opsOnlyString : Circuit
        povmLabel : str or None
        """
        if len(circuit) > 0 and self._shlp.is_prep_lbl(circuit[0]):
            prep_lbl = circuit[0]
            circuit = circuit[1:]
        elif self._shlp.get_default_prep_lbl() is not None:
            prep_lbl = self._shlp.get_default_prep_lbl()
        else:
            if 'prep' in erroron and self._shlp.has_preps():
                raise ValueError("Cannot resolve state prep in %s" % circuit)
            else: prep_lbl = None

        if len(circuit) > 0 and self._shlp.is_povm_lbl(circuit[-1]):
            povm_lbl = circuit[-1]
            circuit = circuit[:-1]
        elif self._shlp.get_default_povm_lbl() is not None:
            povm_lbl = self._shlp.get_default_povm_lbl()
        else:
            if 'povm' in erroron and self._shlp.has_povms():
                raise ValueError("Cannot resolve POVM in %s" % circuit)
            else: povm_lbl = None

        return prep_lbl, circuit, povm_lbl

    def simplify_circuits(self, circuits, dataset=None):
        """
        Simplifies a list of :class:`Circuit`s.

        Circuits must be "simplified" before probabilities can be computed for
        them. Each string corresponds to some number of "outcomes", indexed by an
        "outcome label" that is a tuple of POVM-effect or instrument-element
        labels like "0".  Compiling creates maps between operation sequences and their
        outcomes and the structures used in probability computation (see return
        values below).

        Parameters
        ----------
        circuits : list of Circuits
            The list to simplify.

        dataset : DataSet, optional
            If not None, restrict what is simplified to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.

        Returns
        -------
        raw_spamTuples_dict : collections.OrderedDict
            A dictionary whose keys are raw operation sequences (containing just
            "simplified" gates, i.e. not instruments), and whose values are
            lists of (preplbl, effectlbl) tuples.  The effectlbl names a
            "simplified" effect vector; preplbl is just a prep label. Each tuple
            corresponds to a single "final element" of the computation, e.g. a
            probability.  The ordering is important - and is why this needs to be
            an ordered dictionary - when the lists of tuples are concatenated (by
            key) the resulting tuple orderings corresponds to the final-element
            axis of an output array that is being filled (computed).

        elIndices : collections.OrderedDict
            A dictionary whose keys are integer indices into `circuits` and
            whose values are slices and/or integer-arrays into the space/axis of
            final elements.  Thus, to get the final elements corresponding to
            `circuits[i]`, use `filledArray[ elIndices[i] ]`.

        outcomes : collections.OrderedDict
            A dictionary whose keys are integer indices into `circuits` and
            whose values are lists of outcome labels (an outcome label is a tuple
            of POVM-effect and/or instrument-element labels).  Thus, to obtain
            what outcomes the i-th operation sequences's final elements
            (`filledArray[ elIndices[i] ]`)  correspond to, use `outcomes[i]`.

        nTotElements : int
            The total number of "final elements" - this is how big of an array
            is need to hold all of the probabilities `circuits` generates.
        """
        # model.simplify -> odict[raw_gstr] = spamTuples, elementIndices, nElements
        # dataset.simplify -> outcomeLabels[i] = list_of_ds_outcomes, elementIndices, nElements
        # simplify all gsplaq strs -> elementIndices[(i,j)],

        circuits = [(opstr if isinstance(opstr, _cir.Circuit) else _cir.Circuit(opstr))
                    for opstr in circuits]  # cast to Circuits

        #Indexed by raw operation sequence
        raw_spamTuples_dict = _collections.OrderedDict()  # final
        raw_opOutcomes_dict = _collections.OrderedDict()
        raw_offsets = _collections.OrderedDict()

        #Indexed by parent index (an integer)
        elIndicesByParent = _collections.OrderedDict()  # final
        outcomesByParent = _collections.OrderedDict()  # final
        elIndsToOutcomesByParent = _collections.OrderedDict()

        # Helper dict: (rhoLbl,POVM_ELbl) -> (Elbl,) mapping
        def spamTupleToOutcome(spamTuple):
            if spamTuple is None:
                return ("NONE",)  # Dummy label for placeholding (see resolveSPAM below)
            else:
                prep_lbl, povm_and_effect_lbl = spamTuple
                last_underscore = povm_and_effect_lbl.rindex('_')
                effect_lbl = povm_and_effect_lbl[last_underscore + 1:]
                return (effect_lbl,)  # effect label *is* the outcome

        def resolveSPAM(circuit):
            """ Determines spam tuples that correspond to circuit
                and strips any spam-related pieces off """
            prep_lbl, circuit, povm_lbl = \
                self.split_circuit(circuit)
            if prep_lbl is None or povm_lbl is None:
                spamtups = [None]  # put a single "dummy" spam-tuple placeholder
                # so that there's a single "element" for each simplified string,
                # which means that the usual "lookup" or "elIndices" will map
                # original circuit-list indices to simplified-string, i.e.,
                # evalTree index, which is useful when computing products
                # (often the case when a Model has no preps or povms,
                #  e.g. in germ selection)
            else:
                if dataset is not None:
                    #Then we don't need to consider *all* possible spam tuples -
                    # just the ones that are observed, i.e. that correspond to
                    # a final element in the "full" (tuple) outcome labels that
                    # were observed.
                    observed_povm_outcomes = sorted(set(
                        [full_out_tup[-1] for full_out_tup in dataset[circuit].outcomes]))
                    spamtups = [(prep_lbl, povm_lbl + "_" + oout)
                                for oout in observed_povm_outcomes]
                    # elbl = oout[-1] -- the last element corresponds
                    # to the POVM (earlier ones = instruments)
                else:
                    spamtups = [(prep_lbl, povm_lbl + "_" + elbl)
                                for elbl in self._shlp.get_effect_labels_for_povm(povm_lbl)]
            return circuit, spamtups

        def process(s, spamtuples, observed_outcomes, elIndsToOutcomes,
                    op_outcomes=(), start=0):
            """
            Implements recursive processing of a string. Separately
            implements two different behaviors:
              "add" : add entries to raw_spamTuples_dict and raw_opOutcomes_dict
              "index" : adds entries to elIndicesByParent and outcomesByParent
                        assuming that raw_spamTuples_dict and raw_opOutcomes_dict
                        are already build (and won't be modified anymore).
            """
            sub = s if start == 0 else s[start:]
            for i, op_label in enumerate(sub, start=start):

                # OLD: now allow "gate-level" labels which can contain
                # multiple (parallel) instrument labels
                #if op_label in self.instruments:
                #    #we've found an instrument - recurse!
                #    for inst_el_lbl in self.instruments[op_label]:
                #        simplified_el_lbl = op_label + "_" + inst_el_lbl
                #        process(s[0:i] + _cir.Circuit((simplified_el_lbl,)) + s[i+1:],
                #                spamtuples, elIndsToOutcomes, op_outcomes + (inst_el_lbl,), i+1)
                #    break

                if any([self._shlp.is_instrument_lbl(sub_gl) for sub_gl in op_label.components]):
                    # we've found an instrument - recurse!
                    sublabel_tups_to_iter = []  # one per label component (may be only 1)
                    for sub_gl in op_label.components:
                        if self._shlp.is_instrument_lbl(sub_gl):
                            sublabel_tups_to_iter.append([(sub_gl, inst_el_lbl)
                                                          for inst_el_lbl in self._shlp.get_member_labels_for_instrument(sub_gl)])
                        else:
                            sublabel_tups_to_iter.append([(sub_gl, None)])  # just a single element

                    for sublabel_tups in _itertools.product(*sublabel_tups_to_iter):
                        sublabels = []  # the sub-labels of the overall operation label to add
                        outcomes = []  # the outcome tuple associated with this overall label
                        for sub_gl, inst_el_lbl in sublabel_tups:
                            if inst_el_lbl is not None:
                                sublabels.append(sub_gl + "_" + inst_el_lbl)
                                outcomes.append(inst_el_lbl)
                            else:
                                sublabels.append(sub_gl)

                        simplified_el_lbl = _Label(sublabels)
                        simplified_el_outcomes = tuple(outcomes)
                        process(s[0:i] + _cir.Circuit((simplified_el_lbl,)) + s[i + 1:],
                                spamtuples, observed_outcomes, elIndsToOutcomes,
                                op_outcomes + simplified_el_outcomes, i + 1)
                    break

            else:  # no instruments -- add "raw" operation sequence s
                if s in raw_spamTuples_dict:
                    assert(op_outcomes == raw_opOutcomes_dict[s])  # DEBUG
                    #if action == "add":
                    od = raw_spamTuples_dict[s]  # ordered dict
                    for spamtup in spamtuples:
                        outcome_tup = op_outcomes + spamTupleToOutcome(spamtup)
                        if (observed_outcomes is not None) and \
                           (outcome_tup not in observed_outcomes): continue
                        # don't add spamtuples we don't observe

                        spamtup_indx = od.get(spamtup, None)
                        if spamtup is None:
                            # although we've seen this raw string, we haven't
                            # seen spamtup yet - add it at end
                            spamtup_indx = len(od)
                            od[spamtup] = spamtup_indx

                        #Link the current iParent to this index (even if it was already going to be computed)
                        elIndsToOutcomes[(s, spamtup_indx)] = outcome_tup
                else:
                    # Note: store elements of raw_spamTuples_dict as dicts for
                    # now, for faster lookup during "index" mode
                    outcome_tuples = [op_outcomes + spamTupleToOutcome(x) for x in spamtuples]

                    if observed_outcomes is not None:
                        # only add els of `spamtuples` corresponding to observed data (w/indexes starting at 0)
                        spamtup_dict = _collections.OrderedDict()
                        ist = 0
                        for spamtup, outcome_tup in zip(spamtuples, outcome_tuples):
                            if outcome_tup in observed_outcomes:
                                spamtup_dict[spamtup] = ist
                                elIndsToOutcomes[(s, ist)] = outcome_tup
                                ist += 1
                    else:
                        # add all els of `spamtuples` (w/indexes starting at 0)
                        spamtup_dict = _collections.OrderedDict([
                            (spamtup, i) for i, spamtup in enumerate(spamtuples)])

                        for ist, out_tup in enumerate(outcome_tuples):  # ist = spamtuple index
                            elIndsToOutcomes[(s, ist)] = out_tup  # element index is given by (parent_circuit, spamtuple_index) tuple
                            # Note: works even if `i` already exists - doesn't reorder keys then

                    raw_spamTuples_dict[s] = spamtup_dict
                    raw_opOutcomes_dict[s] = op_outcomes  # DEBUG

        #Begin actual processing work:

        # Step1: recursively populate raw_spamTuples_dict,
        #        raw_opOutcomes_dict, and elIndsToOutcomesByParent
        resolved_circuits = list(map(resolveSPAM, circuits))
        for iParent, (opstr, spamtuples) in enumerate(resolved_circuits):
            elIndsToOutcomesByParent[iParent] = _collections.OrderedDict()
            oouts = None if (dataset is None) else set(dataset[opstr].outcomes)
            process(opstr, spamtuples, oouts, elIndsToOutcomesByParent[iParent])

        # Step2: fill raw_offsets dictionary
        off = 0
        for raw_str, spamtuples in raw_spamTuples_dict.items():
            raw_offsets[raw_str] = off
            off += len(spamtuples)
        nTotElements = off

        # Step3: split elIndsToOutcomesByParent into
        #        elIndicesByParent and outcomesByParent
        for iParent, elIndsToOutcomes in elIndsToOutcomesByParent.items():
            elIndicesByParent[iParent] = []
            outcomesByParent[iParent] = []
            for (raw_str, rel_spamtup_indx), outcomes in elIndsToOutcomes.items():
                elIndicesByParent[iParent].append(raw_offsets[raw_str] + rel_spamtup_indx)
                outcomesByParent[iParent].append(outcomes)
            elIndicesByParent[iParent] = _slct.list_to_slice(elIndicesByParent[iParent], array_ok=True)

        #Step3b: convert elements of raw_spamTuples_dict from OrderedDicts
        # to lists not that we don't need to use them for lookups anymore.
        for s in list(raw_spamTuples_dict.keys()):
            raw_spamTuples_dict[s] = list(raw_spamTuples_dict[s].keys())

        #Step4: change lists/slices -> index arrays for user convenience
        elIndicesByParent = _collections.OrderedDict(
            [(k, (v if isinstance(v, slice) else _np.array(v, _np.int64)))
             for k, v in elIndicesByParent.items()])

        ##DEBUG: SANITY CHECK
        #if len(circuits) > 1:
        #    for k,opstr in enumerate(circuits):
        #        _,outcomes_k = self.simplify_circuit(opstr)
        #        nIndices = _slct.length(elIndicesByParent[k]) if isinstance(elIndicesByParent[k], slice) \
        #                      else len(elIndicesByParent[k])
        #        assert(len(outcomes_k) == nIndices)
        #        assert(outcomes_k == outcomesByParent[k])

        #print("Model.simplify debug:")
        #print("input = ",'\n'.join(["%d: %s" % (i,repr(c)) for i,c in enumerate(circuits)]))
        #print("raw_dict = ", raw_spamTuples_dict)
        #print("elIndices = ", elIndicesByParent)
        #print("outcomes = ", outcomesByParent)
        #print("total els = ",nTotElements)

        return (raw_spamTuples_dict, elIndicesByParent,
                outcomesByParent, nTotElements)

    def simplify_circuit(self, circuit):
        """
        Simplifies a single :class:`Circuit`.

        Parameters
        ----------
        circuit : Circuit
            The operation sequence to simplify

        Returns
        -------
        raw_spamTuples_dict : collections.OrderedDict
            A dictionary whose keys are raw operation sequences (containing just
            "simplified" gates, i.e. not instruments), and whose values are
            lists of (preplbl, effectlbl) tuples.  The effectlbl names a
            "simplified" effect vector; preplbl is just a prep label. Each tuple
            corresponds to a single "final element" of the computation for this
            operation sequence.  The ordering is important - and is why this needs to be
            an ordered dictionary - when the lists of tuples are concatenated (by
            key) the resulting tuple orderings corresponds to the final-element
            axis of an output array that is being filled (computed).

        outcomes : list
            A list of outcome labels (an outcome label is a tuple
            of POVM-effect and/or instrument-element labels), corresponding to
            the final elements.
        """
        raw_dict, _, outcomes, nEls = self.simplify_circuits([circuit])
        assert(len(outcomes[0]) == nEls)
        return raw_dict, outcomes[0]

    def probs(self, circuit, clipTo=None):
        """
        Construct a dictionary containing the probabilities of every spam label
        given a operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        clipTo : 2-tuple, optional
           (min,max) to clip probabilities to if not None.

        Returns
        -------
        probs : dictionary
            A dictionary such that
            probs[SL] = pr(SL,circuit,clipTo)
            for each spam label (string) SL.
        """
        return self._fwdsim().probs(self.simplify_circuit(circuit), clipTo)

    def dprobs(self, circuit, returnPr=False, clipTo=None):
        """
        Construct a dictionary containing the probability derivatives of every
        spam label for a given operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        Returns
        -------
        dprobs : dictionary
            A dictionary such that
            dprobs[SL] = dpr(SL,circuit,gates,G0,SPAM,SP0,returnPr,clipTo)
            for each spam label (string) SL.
        """
        return self._fwdsim().dprobs(self.simplify_circuit(circuit),
                                     returnPr, clipTo)

    def hprobs(self, circuit, returnPr=False, returnDeriv=False, clipTo=None):
        """
        Construct a dictionary containing the probability derivatives of every
        spam label for a given operation sequence.

        Parameters
        ----------
        circuit : Circuit or tuple of operation labels
          The sequence of operation labels specifying the operation sequence.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        returnDeriv : bool, optional
          when set to True, additionally return the derivatives of the
          probabilities.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        Returns
        -------
        hprobs : dictionary
            A dictionary such that
            hprobs[SL] = hpr(SL,circuit,gates,G0,SPAM,SP0,returnPr,returnDeriv,clipTo)
            for each spam label (string) SL.
        """
        return self._fwdsim().hprobs(self.simplify_circuit(circuit),
                                     returnPr, returnDeriv, clipTo)

    def bulk_evaltree_from_resources(self, circuit_list, comm=None, memLimit=None,
                                     distributeMethod="default", subcalls=[],
                                     dataset=None, verbosity=0):
        """
        Create an evaluation tree based on available memory and CPUs.

        This tree can be used by other Bulk_* functions, and is it's own
        function so that for many calls to Bulk_* made with the same
        circuit_list, only a single call to bulk_evaltree is needed.

        Parameters
        ----------
        circuit_list : list of (tuples or Circuits)
            Each element specifies a operation sequence to include in the evaluation tree.

        comm : mpi4py.MPI.Comm
            When not None, an MPI communicator for distributing computations
            across multiple processors.

        memLimit : int, optional
            A rough memory limit in bytes which is used to determine subtree
            number and size.

        distributeMethod : {"circuits", "deriv"}
            How to distribute calculation amongst processors (only has effect
            when comm is not None).  "circuits" will divide the list of
            circuits and thereby result in more subtrees; "deriv" will divide
            the columns of any jacobian matrices, thereby resulting in fewer
            (larger) subtrees.

        subcalls : list, optional
            A list of the names of the Model functions that will be called
            using the returned evaluation tree, which are necessary for
            estimating memory usage (for comparison to memLimit).  If
            memLimit is None, then there's no need to specify `subcalls`.

        dataset : DataSet, optional
            If not None, restrict what is computed to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.

        verbosity : int, optional
            How much detail to send to stdout.

        Returns
        -------
        evt : EvalTree
            The evaluation tree object, split as necesary.
        paramBlockSize1 : int or None
            The maximum size of 1st-deriv-dimension parameter blocks
            (i.e. the maximum number of parameters to compute at once
             in calls to dprobs, etc., usually specified as wrtBlockSize
             or wrtBlockSize1).
        paramBlockSize2 : int or None
            The maximum size of 2nd-deriv-dimension parameter blocks
            (i.e. the maximum number of parameters to compute at once
             in calls to hprobs, etc., usually specified as wrtBlockSize2).
        """

        # Let np = # param groups, so 1 <= np <= num_params, size of each param group = num_params/np
        # Let ng = # operation sequence groups == # subtrees, so 1 <= ng <= max_split_num; size of each group = size of corresponding subtree
        # With nprocs processors, split into Ng comms of ~nprocs/Ng procs each.  These comms are each assigned
        #  some number of operation sequence groups, where their ~nprocs/Ng processors are used to partition the np param
        #  groups. Note that 1 <= Ng <= min(ng,nprocs).
        # Notes:
        #  - making np or ng > nprocs can be useful for saving memory.  Raising np saves *Jacobian* and *Hessian*
        #     function memory without evaltree overhead, and I think will typically be preferred over raising
        #     ng which will also save Product function memory but will incur evaltree overhead.
        #  - any given CPU will be running a *single* (ng-index,np-index) pair at any given time, and so many
        #     memory estimates only depend on ng and np, not on Ng.  (The exception is when a routine *gathers*
        #     the end results from a divided computation.)
        #  - "circuits" distributeMethod: never distribute num_params (np == 1, Ng == nprocs always).
        #     Choose ng such that ng >= nprocs, memEstimate(ng,np=1) < memLimit, and ng % nprocs == 0 (ng % Ng == 0).
        #  - "deriv" distributeMethod: if possible, set ng=1, nprocs <= np <= num_params, Ng = 1 (np % nprocs == 0?)
        #     If memory constraints don't allow this, set np = num_params, Ng ~= nprocs/num_params (but Ng >= 1),
        #     and ng set by memEstimate and ng % Ng == 0 (so comms are kept busy)
        #
        # find ng, np, Ng such that:
        # - memEstimate(ng,np,Ng) < memLimit
        # - full cpu usage:
        #       - np*ng >= nprocs (all procs used)
        #       - ng % Ng == 0 (all subtree comms kept busy)
        #     -nice, but not essential:
        #       - num_params % np == 0 (each param group has same size)
        #       - np % (nprocs/Ng) == 0 would be nice (all procs have same num of param groups to process)

        printer = _VerbosityPrinter.build_printer(verbosity, comm)

        nprocs = 1 if comm is None else comm.Get_size()
        num_params = self.num_params()
        evt_cache = {}  # cache of eval trees based on # min subtrees, to avoid re-computation
        C = 1.0 / (1024.0**3)
        calc = self._fwdsim()

        bNp2Matters = ("bulk_fill_hprobs" in subcalls) or ("bulk_hprobs_by_block" in subcalls)

        if memLimit is not None:
            if memLimit <= 0:
                raise MemoryError("Attempted evaltree generation "
                                  + "w/memlimit = %g <= 0!" % memLimit)
            printer.log("Evaltree generation (%s) w/mem limit = %.2fGB"
                        % (distributeMethod, memLimit * C))

        def memEstimate(ng, np1, np2, Ng, fastCacheSz=False, verb=0, cacheSize=None):
            """ Returns a memory estimate based on arguments """
            tm = _time.time()

            nFinalStrs = int(round(len(circuit_list) / ng))  # may not need to be an int...

            if cacheSize is None:
                #Get cache size
                if not fastCacheSz:
                    #Slower (but more accurate way)
                    if ng not in evt_cache:
                        evt_cache[ng] = self.bulk_evaltree(
                            circuit_list, minSubtrees=ng, numSubtreeComms=Ng,
                            dataset=dataset, verbosity=printer)
                        # FUTURE: make a _bulk_evaltree_presimplified version that takes simplified
                        # operation sequences as input so don't have to re-simplify every time we hit this line.
                    cacheSize = max([s.cache_size() for s in evt_cache[ng][0].get_sub_trees()])
                    nFinalStrs = max([s.num_final_strings() for s in evt_cache[ng][0].get_sub_trees()])
                else:
                    #heuristic (but fast)
                    cacheSize = calc.estimate_cache_size(nFinalStrs)

            mem = calc.estimate_mem_usage(subcalls, cacheSize, ng, Ng, np1, np2, nFinalStrs)

            if verb == 1:
                if (not fastCacheSz):
                    fast_estimate = calc.estimate_mem_usage(
                        subcalls, cacheSize, ng, Ng, np1, np2, nFinalStrs)
                    fc_est_str = " (%.2fGB fc)" % (fast_estimate * C)
                else: fc_est_str = ""

                printer.log(" mem(%d subtrees, %d,%d param-grps, %d proc-grps)"
                            % (ng, np1, np2, Ng) + " in %.0fs = %.2fGB%s"
                            % (_time.time() - tm, mem * C, fc_est_str))
            elif verb == 2:
                wrtLen1 = (num_params + np1 - 1) // np1  # ceiling(num_params / np1)
                wrtLen2 = (num_params + np2 - 1) // np2  # ceiling(num_params / np2)
                nSubtreesPerProc = (ng + Ng - 1) // Ng  # ceiling(ng / Ng)
                printer.log(" Memory estimate = %.2fGB" % (mem * C)
                            + " (cache=%d, wrtLen1=%d, wrtLen2=%d, subsPerProc=%d)." %
                            (cacheSize, wrtLen1, wrtLen2, nSubtreesPerProc))
                #printer.log("  subcalls = %s" % str(subcalls))
                #printer.log("  cacheSize = %d" % cacheSize)
                #printer.log("  wrtLen = %d" % wrtLen)
                #printer.log("  nSubtreesPerProc = %d" % nSubtreesPerProc)

            return mem

        if distributeMethod == "default":
            distributeMethod = calc.default_distribute_method()

        if distributeMethod == "circuits":
            Nstrs = len(circuit_list)
            np1 = 1
            np2 = 1
            Ng = min(nprocs, Nstrs)
            ng = Ng
            if memLimit is not None:
                #Increase ng in amounts of Ng (so ng % Ng == 0).  Start
                # with fast cacheSize computation then switch to slow
                while memEstimate(ng, np1, np2, Ng, False) > memLimit:
                    ng += Ng
                    if ng >= Nstrs:
                        # even "maximal" splitting (num trees == num strings)
                        # won't help - see if we can squeeze the this maximally-split tree
                        # to have zero cachesize
                        if Nstrs not in evt_cache:
                            memEstimate(Nstrs, np1, np2, Ng, verb=1)
                        if hasattr(evt_cache[Nstrs], "squeeze") and \
                           memEstimate(Nstrs, np1, np2, Ng, cacheSize=0) <= memLimit:
                            evt_cache[Nstrs].squeeze(0)  # To get here, need to use higher-dim models
                        else:
                            raise MemoryError("Cannot split or squeeze tree to achieve memory limit")

                mem_estimate = memEstimate(ng, np1, np2, Ng, verb=1)
                while mem_estimate > memLimit:
                    ng += Ng
                    next = memEstimate(ng, np1, np2, Ng, verb=1)
                    if(next >= mem_estimate): raise MemoryError("Not enough memory: splitting unproductive")
                    mem_estimate = next

                   #Note: could do these while loops smarter, e.g. binary search-like?
                   #  or assume memEstimate scales linearly in ng? E.g:
                   #     if memLimit < memEstimate:
                   #         reductionFactor = float(memEstimate) / float(memLimit)
                   #         maxTreeSize = int(nstrs / reductionFactor)
            else:
                memEstimate(ng, np1, np2, Ng)  # to compute & cache final EvalTree

        elif distributeMethod == "deriv":

            def set_Ng(desired_Ng):
                """ Set Ng, the number of subTree processor groups, such
                    that Ng divides nprocs evenly or vice versa. """
                if desired_Ng >= nprocs:
                    return nprocs * int(_np.ceil(1. * desired_Ng / nprocs))
                else:
                    fctrs = sorted(_mt.prime_factors(nprocs))
                    i = 1
                    if int(_np.ceil(desired_Ng)) in fctrs:
                        return int(_np.ceil(desired_Ng))  # we got lucky
                    while _np.product(fctrs[0:i]) < desired_Ng: i += 1
                    return _np.product(fctrs[0:i])

            ng = Ng = 1
            if bNp2Matters:
                if nprocs > num_params**2:
                    np1 = np2 = max(num_params, 1)
                    ng = Ng = set_Ng(nprocs / max(num_params**2, 1))  # Note __future__ division
                elif nprocs > num_params:
                    np1 = max(num_params, 1)
                    np2 = int(_np.ceil(nprocs / max(num_params, 1)))
                else:
                    np1 = nprocs
                    np2 = 1
            else:
                np2 = 1
                if nprocs > num_params:
                    np1 = max(num_params, 1)
                    ng = Ng = set_Ng(nprocs / max(num_params, 1))
                else:
                    np1 = nprocs

            if memLimit is not None:

                ok = False
                if (not ok) and np1 < num_params:
                    #First try to decrease mem consumption by increasing np1
                    memEstimate(ng, np1, np2, Ng, verb=1)  # initial estimate (to screen)
                    for n in range(np1, num_params + 1, nprocs):
                        if memEstimate(ng, n, np2, Ng) < memLimit:
                            np1 = n
                            ok = True
                            break
                    else: np1 = num_params

                if (not ok) and bNp2Matters and np2 < num_params:
                    #Next try to decrease mem consumption by increasing np2
                    for n in range(np2, num_params + 1):
                        if memEstimate(ng, np1, n, Ng) < memLimit:
                            np2 = n
                            ok = True
                            break
                    else: np2 = num_params

                if not ok:
                    #Finally, increase ng in amounts of Ng (so ng % Ng == 0).  Start
                    # with fast cacheSize computation then switch to slow
                    while memEstimate(ng, np1, np2, Ng, True) > memLimit: ng += Ng
                    mem_estimate = memEstimate(ng, np1, np2, Ng, verb=1)
                    while mem_estimate > memLimit:
                        ng += Ng
                        next = memEstimate(ng, np1, np2, Ng, verb=1)
                        if next >= mem_estimate:
                            raise MemoryError("Not enough memory: splitting unproductive")
                        mem_estimate = next
            else:
                memEstimate(ng, np1, np2, Ng)  # to compute & cache final EvalTree

        elif distributeMethod == "balanced":
            # try to minimize "unbalanced" procs
            #np = gcf(num_params, nprocs)
            #ng = Ng = max(nprocs / np, 1)
            #if memLimit is not None:
            #    while memEstimate(ng,np1,np2,Ng) > memLimit: ng += Ng #so ng % Ng == 0
            raise NotImplementedError("balanced distribution still todo")

        # Retrieve final EvalTree (already computed from estimates above)
        assert (ng in evt_cache), "Tree Caching Error"
        evt, lookup, outcome_lookup = evt_cache[ng]
        evt.distribution['numSubtreeComms'] = Ng

        paramBlkSize1 = num_params / np1
        paramBlkSize2 = num_params / np2  # the *average* param block size
        # (in general *not* an integer), which ensures that the intended # of
        # param blocks is communicatd to gsCalc.py routines (taking ceiling or
        # floor can lead to inefficient MPI distribution)

        printer.log("Created evaluation tree with %d subtrees.  " % ng
                    + "Will divide %d procs into %d (subtree-processing)" % (nprocs, Ng))
        if bNp2Matters:
            printer.log(" groups of ~%d procs each, to distribute over " % (nprocs / Ng)
                        + "(%d,%d) params (taken as %d,%d param groups of ~%d,%d params)."
                        % (num_params, num_params, np1, np2, paramBlkSize1, paramBlkSize2))
        else:
            printer.log(" groups of ~%d procs each, to distribute over " % (nprocs / Ng)
                        + "%d params (taken as %d param groups of ~%d params)."
                        % (num_params, np1, paramBlkSize1))

        if memLimit is not None:
            memEstimate(ng, np1, np2, Ng, False, verb=2)  # print mem estimate details

        if (comm is None or comm.Get_rank() == 0) and evt.is_split():
            if printer.verbosity >= 2: evt.print_analysis()

        if np1 == 1:  # (paramBlkSize == num_params)
            paramBlkSize1 = None  # == all parameters, and may speed logic in dprobs, etc.
        else:
            if comm is not None:
                blkSizeTest = comm.bcast(paramBlkSize1, root=0)
                assert(abs(blkSizeTest - paramBlkSize1) < 1e-3)
                #all procs should have *same* paramBlkSize1

        if np2 == 1:  # (paramBlkSize == num_params)
            paramBlkSize2 = None  # == all parameters, and may speed logic in hprobs, etc.
        else:
            if comm is not None:
                blkSizeTest = comm.bcast(paramBlkSize2, root=0)
                assert(abs(blkSizeTest - paramBlkSize2) < 1e-3)
                #all procs should have *same* paramBlkSize2

        return evt, paramBlkSize1, paramBlkSize2, lookup, outcome_lookup

    def bulk_evaltree(self, circuit_list, minSubtrees=None, maxTreeSize=None,
                      numSubtreeComms=1, dataset=None, verbosity=0):
        """
        Create an evaluation tree for all the operation sequences in circuit_list.

        This tree can be used by other Bulk_* functions, and is it's own
        function so that for many calls to Bulk_* made with the same
        circuit_list, only a single call to bulk_evaltree is needed.

        Parameters
        ----------
        circuit_list : list of (tuples or Circuits)
            Each element specifies a operation sequence to include in the evaluation tree.

        minSubtrees : int (optional)
            The minimum number of subtrees the resulting EvalTree must have.

        maxTreeSize : int (optional)
            The maximum size allowed for the single un-split tree or any of
            its subtrees.

        numSubtreeComms : int, optional
            The number of processor groups (communicators)
            to divide the subtrees of the EvalTree among
            when calling its `distribute` method.

        dataset : DataSet, optional
            If not None, restrict what is computed to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.

        verbosity : int, optional
            How much detail to send to stdout.

        Returns
        -------
        evt : EvalTree
            An evaluation tree object.

        elIndices : collections.OrderedDict
            A dictionary whose keys are integer indices into `circuit_list` and
            whose values are slices and/or integer-arrays into the space/axis of
            final elements returned by the 'bulk fill' routines.  Thus, to get the
            final elements corresponding to `circuits[i]`, use
            `filledArray[ elIndices[i] ]`.

        outcomes : collections.OrderedDict
            A dictionary whose keys are integer indices into `circuit_list` and
            whose values are lists of outcome labels (an outcome label is a tuple
            of POVM-effect and/or instrument-element labels).  Thus, to obtain
            what outcomes the i-th operation sequences's final elements
            (`filledArray[ elIndices[i] ]`)  correspond to, use `outcomes[i]`.
        """
        tm = _time.time()
        printer = _VerbosityPrinter.build_printer(verbosity)

        def toCircuit(x): return x if isinstance(x, _cir.Circuit) else _cir.Circuit(x)
        circuit_list = list(map(toCircuit, circuit_list))  # make sure simplify_circuits is given Circuits
        simplified_circuits, elIndices, outcomes, nEls = \
            self.simplify_circuits(circuit_list, dataset)

        evalTree = self._fwdsim().construct_evaltree(simplified_circuits, numSubtreeComms)

        printer.log("bulk_evaltree: created initial tree (%d strs) in %.0fs" %
                    (len(circuit_list), _time.time() - tm))
        tm = _time.time()

        if maxTreeSize is not None:
            elIndices = evalTree.split(elIndices, maxTreeSize, None, printer - 1)  # won't split if unnecessary

        if minSubtrees is not None:
            if not evalTree.is_split() or len(evalTree.get_sub_trees()) < minSubtrees:
                evalTree.original_index_lookup = None  # reset this so we can re-split TODO: cleaner
                elIndices = evalTree.split(elIndices, None, minSubtrees, printer - 1)
                if maxTreeSize is not None and \
                        any([len(sub) > maxTreeSize for sub in evalTree.get_sub_trees()]):
                    _warnings.warn("Could not create a tree with minSubtrees=%d" % minSubtrees
                                   + " and maxTreeSize=%d" % maxTreeSize)
                    evalTree.original_index_lookup = None  # reset this so we can re-split TODO: cleaner
                    elIndices = evalTree.split(elIndices, maxTreeSize, None)  # fall back to split for max size

        if maxTreeSize is not None or minSubtrees is not None:
            printer.log("bulk_evaltree: split tree (%d subtrees) in %.0fs"
                        % (len(evalTree.get_sub_trees()), _time.time() - tm))

        assert(evalTree.num_final_elements() == nEls)
        return evalTree, elIndices, outcomes

    def bulk_probs(self, circuit_list, clipTo=None, check=False,
                   comm=None, memLimit=None, dataset=None, smartc=None):
        """
        Construct a dictionary containing the probabilities
        for an entire list of operation sequences.

        Parameters
        ----------
        circuit_list : list of (tuples or Circuits)
          Each element specifies a operation sequence to compute quantities for.

        clipTo : 2-tuple, optional
           (min,max) to clip return value if not None.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is performed over
           subtrees of evalTree (if it is split).

        memLimit : int, optional
            A rough memory limit in bytes which is used to determine processor
            allocation.

        dataset : DataSet, optional
            If not None, restrict what is computed to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.

        smartc : SmartCache, optional
            A cache object to cache & use previously cached values inside this
            function.


        Returns
        -------
        probs : dictionary
            A dictionary such that `probs[opstr]` is an ordered dictionary of
            `(outcome, p)` tuples, where `outcome` is a tuple of labels
            and `p` is the corresponding probability.
        """
        circuit_list = [opstr if isinstance(opstr, _cir.Circuit) else _cir.Circuit(opstr)
                        for opstr in circuit_list]  # cast to Circuits
        evalTree, _, _, elIndices, outcomes = self.bulk_evaltree_from_resources(
            circuit_list, comm, memLimit, subcalls=['bulk_fill_probs'],
            dataset=dataset, verbosity=0)  # FUTURE (maybe make verbosity into an arg?)

        return self._fwdsim().bulk_probs(circuit_list, evalTree, elIndices,
                                         outcomes, clipTo, check, comm, smartc)

    def bulk_dprobs(self, circuit_list, returnPr=False, clipTo=None,
                    check=False, comm=None, wrtBlockSize=None, dataset=None):
        """
        Construct a dictionary containing the probability-derivatives
        for an entire list of operation sequences.

        Parameters
        ----------
        circuit_list : list of (tuples or Circuits)
          Each element specifies a operation sequence to compute quantities for.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is first performed over
           subtrees of evalTree (if it is split), and then over blocks (subsets)
           of the parameters being differentiated with respect to (see
           wrtBlockSize).

        wrtBlockSize : int or float, optional
          The maximum average number of derivative columns to compute *products*
          for simultaneously.  None means compute all columns at once.
          The minimum of wrtBlockSize and the size that makes maximal
          use of available processors is used as the final block size. Use
          this argument to reduce amount of intermediate memory required.

        dataset : DataSet, optional
            If not None, restrict what is computed to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.


        Returns
        -------
        dprobs : dictionary
            A dictionary such that `probs[opstr]` is an ordered dictionary of
            `(outcome, dp, p)` tuples, where `outcome` is a tuple of labels,
            `p` is the corresponding probability, and `dp` is an array containing
            the derivative of `p` with respect to each parameter.  If `returnPr`
            if False, then `p` is not included in the tuples (so they're just
            `(outcome, dp)`).
        """
        circuit_list = [opstr if isinstance(opstr, _cir.Circuit) else _cir.Circuit(opstr)
                        for opstr in circuit_list]  # cast to Circuits
        evalTree, elIndices, outcomes = self.bulk_evaltree(circuit_list, dataset=dataset)
        return self._fwdsim().bulk_dprobs(circuit_list, evalTree, elIndices,
                                          outcomes, returnPr, clipTo,
                                          check, comm, None, wrtBlockSize)

    def bulk_hprobs(self, circuit_list, returnPr=False, returnDeriv=False,
                    clipTo=None, check=False, comm=None,
                    wrtBlockSize1=None, wrtBlockSize2=None, dataset=None):
        """
        Construct a dictionary containing the probability-Hessians
        for an entire list of operation sequences.

        Parameters
        ----------
        circuit_list : list of (tuples or Circuits)
          Each element specifies a operation sequence to compute quantities for.

        returnPr : bool, optional
          when set to True, additionally return the probabilities.

        returnDeriv : bool, optional
          when set to True, additionally return the probability derivatives.

        clipTo : 2-tuple, optional
           (min,max) to clip returned probability to if not None.
           Only relevant when returnPr == True.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.

        wrtBlockSize2, wrtBlockSize2 : int or float, optional
          The maximum number of 1st (row) and 2nd (col) derivatives to compute
          *products* for simultaneously.  None means compute all requested
          rows or columns at once.  The  minimum of wrtBlockSize and the size
          that makes maximal use of available processors is used as the final
          block size.  These arguments must be None if the corresponding
          wrtFilter is not None.  Set this to non-None to reduce amount of
          intermediate memory required.

        dataset : DataSet, optional
            If not None, restrict what is computed to only those
            probabilities corresponding to non-zero counts (observed
            outcomes) in this data set.


        Returns
        -------
        hprobs : dictionary
            A dictionary such that `probs[opstr]` is an ordered dictionary of
            `(outcome, hp, dp, p)` tuples, where `outcome` is a tuple of labels,
            `p` is the corresponding probability, `dp` is a 1D array containing
            the derivative of `p` with respect to each parameter, and `hp` is a
            2D array containing the Hessian of `p` with respect to each parameter.
            If `returnPr` if False, then `p` is not included in the tuples.
            If `returnDeriv` if False, then `dp` is not included in the tuples.
        """
        circuit_list = [opstr if isinstance(opstr, _cir.Circuit) else _cir.Circuit(opstr)
                        for opstr in circuit_list]  # cast to Circuits
        evalTree, elIndices, outcomes = self.bulk_evaltree(circuit_list, dataset=dataset)
        return self._fwdsim().bulk_hprobs(circuit_list, evalTree, elIndices,
                                          outcomes, returnPr, returnDeriv,
                                          clipTo, check, comm, None, None,
                                          wrtBlockSize1, wrtBlockSize2)

    def bulk_fill_probs(self, mxToFill, evalTree, clipTo=None, check=False, comm=None):
        """
        Compute the outcome probabilities for an entire tree of operation sequences.

        This routine fills a 1D array, `mxToFill` with the probabilities
        corresponding to the *simplified* operation sequences found in an evaluation
        tree, `evalTree`.  An initial list of (general) :class:`Circuit`
        objects is *simplified* into a lists of gate-only sequences along with
        a mapping of final elements (i.e. probabilities) to gate-only sequence
        and prep/effect pairs.  The evaluation tree organizes how to efficiently
        compute the gate-only sequences.  This routine fills in `mxToFill`, which
        must have length equal to the number of final elements (this can be
        obtained by `evalTree.num_final_elements()`.  To interpret which elements
        correspond to which strings and outcomes, you'll need the mappings
        generated when the original list of `Circuits` was simplified.

        Parameters
        ----------
        mxToFill : numpy ndarray
          an already-allocated 1D numpy array of length equal to the
          total number of computed elements (i.e. evalTree.num_final_elements())

        evalTree : EvalTree
           given by a prior call to bulk_evaltree.  Specifies the *simplified* gate
           strings to compute the bulk operation on.

        clipTo : 2-tuple, optional
           (min,max) to clip return value if not None.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is performed over
           subtrees of evalTree (if it is split).


        Returns
        -------
        None
        """
        return self._fwdsim().bulk_fill_probs(mxToFill,
                                              evalTree, clipTo, check, comm)

    def bulk_fill_dprobs(self, mxToFill, evalTree, prMxToFill=None, clipTo=None,
                         check=False, comm=None, wrtBlockSize=None,
                         profiler=None, gatherMemLimit=None):
        """
        Compute the outcome probability-derivatives for an entire tree of gate
        strings.

        Similar to `bulk_fill_probs(...)`, but fills a 2D array with
        probability-derivatives for each "final element" of `evalTree`.

        Parameters
        ----------
        mxToFill : numpy ndarray
          an already-allocated ExM numpy array where E is the total number of
          computed elements (i.e. evalTree.num_final_elements()) and M is the
          number of model parameters.

        evalTree : EvalTree
           given by a prior call to bulk_evaltree.  Specifies the *simplified* gate
           strings to compute the bulk operation on.

        prMxToFill : numpy array, optional
          when not None, an already-allocated length-E numpy array that is filled
          with probabilities, just like in bulk_fill_probs(...).

        clipTo : 2-tuple, optional
           (min,max) to clip return value if not None.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is first performed over
           subtrees of evalTree (if it is split), and then over blocks (subsets)
           of the parameters being differentiated with respect to (see
           wrtBlockSize).

        wrtBlockSize : int or float, optional
          The maximum average number of derivative columns to compute *products*
          for simultaneously.  None means compute all columns at once.
          The minimum of wrtBlockSize and the size that makes maximal
          use of available processors is used as the final block size. Use
          this argument to reduce amount of intermediate memory required.

        profiler : Profiler, optional
          A profiler object used for to track timing and memory usage.

        gatherMemLimit : int, optional
          A memory limit in bytes to impose upon the "gather" operations
          performed as a part of MPI processor syncronization.

        Returns
        -------
        None
        """
        return self._fwdsim().bulk_fill_dprobs(mxToFill,
                                               evalTree, prMxToFill, clipTo,
                                               check, comm, None, wrtBlockSize,
                                               profiler, gatherMemLimit)

    def bulk_fill_hprobs(self, mxToFill, evalTree=None,
                         prMxToFill=None, derivMxToFill=None,
                         clipTo=None, check=False, comm=None,
                         wrtBlockSize1=None, wrtBlockSize2=None,
                         gatherMemLimit=None):
        """
        Compute the outcome probability-Hessians for an entire tree of gate
        strings.

        Similar to `bulk_fill_probs(...)`, but fills a 3D array with
        probability-Hessians for each "final element" of `evalTree`.

        Parameters
        ----------
        mxToFill : numpy ndarray
          an already-allocated ExMxM numpy array where E is the total number of
          computed elements (i.e. evalTree.num_final_elements()) and M1 & M2 are
          the number of selected gate-set parameters (by wrtFilter1 and wrtFilter2).

        evalTree : EvalTree
           given by a prior call to bulk_evaltree.  Specifies the *simplified* gate
           strings to compute the bulk operation on.

        prMxToFill : numpy array, optional
          when not None, an already-allocated length-E numpy array that is filled
          with probabilities, just like in bulk_fill_probs(...).

        derivMxToFill1, derivMxToFill2 : numpy array, optional
          when not None, an already-allocated ExM numpy array that is filled
          with probability derivatives, similar to bulk_fill_dprobs(...), but
          where M is the number of model parameters selected for the 1st and 2nd
          differentiation, respectively (i.e. by wrtFilter1 and wrtFilter2).

        clipTo : 2-tuple, optional
           (min,max) to clip return value if not None.

        check : boolean, optional
          If True, perform extra checks within code to verify correctness,
          generating warnings when checks fail.  Used for testing, and runs
          much slower when True.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is first performed over
           subtrees of evalTree (if it is split), and then over blocks (subsets)
           of the parameters being differentiated with respect to (see
           wrtBlockSize).

        wrtBlockSize2, wrtBlockSize2 : int or float, optional
          The maximum number of 1st (row) and 2nd (col) derivatives to compute
          *products* for simultaneously.  None means compute all requested
          rows or columns at once.  The  minimum of wrtBlockSize and the size
          that makes maximal use of available processors is used as the final
          block size.  These arguments must be None if the corresponding
          wrtFilter is not None.  Set this to non-None to reduce amount of
          intermediate memory required.

        profiler : Profiler, optional
          A profiler object used for to track timing and memory usage.

        gatherMemLimit : int, optional
          A memory limit in bytes to impose upon the "gather" operations
          performed as a part of MPI processor syncronization.

        Returns
        -------
        None
        """
        return self._fwdsim().bulk_fill_hprobs(mxToFill,
                                               evalTree, prMxToFill, derivMxToFill, None,
                                               clipTo, check, comm, None, None,
                                               wrtBlockSize1, wrtBlockSize2, gatherMemLimit)

    def bulk_hprobs_by_block(self, evalTree, wrtSlicesList,
                             bReturnDProbs12=False, comm=None):
        """
        Constructs a generator that computes the 2nd derivatives of the
        probabilities generated by a each gate sequence given by evalTree
        column-by-column.

        This routine can be useful when memory constraints make constructing
        the entire Hessian at once impractical, and one is able to compute
        reduce results from a single column of the Hessian at a time.  For
        example, the Hessian of a function of many gate sequence probabilities
        can often be computed column-by-column from the using the columns of
        the operation sequences.


        Parameters
        ----------
        spam_label_rows : dictionary
          a dictionary with keys == spam labels and values which
          are integer row indices into mxToFill, specifying the
          correspondence between rows of mxToFill and spam labels.

        evalTree : EvalTree
           given by a prior call to bulk_evaltree.  Specifies the operation sequences
           to compute the bulk operation on.  This tree *cannot* be split.

        wrtSlicesList : list
            A list of `(rowSlice,colSlice)` 2-tuples, each of which specify
            a "block" of the Hessian to compute.  Iterating over the output
            of this function iterates over these computed blocks, in the order
            given by `wrtSlicesList`.  `rowSlice` and `colSlice` must by Python
            `slice` objects.

        bReturnDProbs12 : boolean, optional
           If true, the generator computes a 2-tuple: (hessian_col, d12_col),
           where d12_col is a column of the matrix d12 defined by:
           d12[iSpamLabel,iOpStr,p1,p2] = dP/d(p1)*dP/d(p2) where P is is
           the probability generated by the sequence and spam label indexed
           by iOpStr and iSpamLabel.  d12 has the same dimensions as the
           Hessian, and turns out to be useful when computing the Hessian
           of functions of the probabilities.

        comm : mpi4py.MPI.Comm, optional
           When not None, an MPI communicator for distributing the computation
           across multiple processors.  Distribution is performed as in
           bulk_product, bulk_dproduct, and bulk_hproduct.


        Returns
        -------
        block_generator
          A generator which, when iterated, yields the 3-tuple
          `(rowSlice, colSlice, hprobs)` or `(rowSlice, colSlice, dprobs12)`
          (the latter if `bReturnDProbs12 == True`).  `rowSlice` and `colSlice`
          are slices directly from `wrtSlicesList`. `hprobs` and `dprobs12` are
          arrays of shape K x S x B x B', where:

          - K is the length of spam_label_rows,
          - S is the number of operation sequences (i.e. evalTree.num_final_strings()),
          - B is the number of parameter rows (the length of rowSlice)
          - B' is the number of parameter columns (the length of colSlice)

          If `mx` and `dp` the outputs of :func:`bulk_fill_hprobs`
          (i.e. args `mxToFill` and `derivMxToFill`), then:

          - `hprobs == mx[:,:,rowSlice,colSlice]`
          - `dprobs12 == dp[:,:,rowSlice,None] * dp[:,:,None,colSlice]`
        """
        return self._fwdsim().bulk_hprobs_by_block(
            evalTree, wrtSlicesList,
            bReturnDProbs12, comm)

    def _init_copy(self, copyInto):
        """
        Copies any "tricky" member of this model into `copyInto`, before
        deep copying everything else within a .copy() operation.
        """
        self._clean_paramvec()  # make sure _paramvec is valid before copying (necessary?)
        copyInto._shlp = None  # must be set by a derived-class _init_copy() method
        copyInto._need_to_rebuild = True  # copy will have all gpindices = None, etc.
        super(OpModel, self)._init_copy(copyInto)

    def copy(self):
        """
        Copy this model.

        Returns
        -------
        Model
            a (deep) copy of this model.
        """
        self._clean_paramvec()  # ensure _paramvec is rebuilt if needed
        if OpModel._pcheck: self._check_paramvec()
        ret = Model.copy(self)
        if OpModel._pcheck: ret._check_paramvec()
        return ret
