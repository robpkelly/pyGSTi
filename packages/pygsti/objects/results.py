""" Defines the Results class."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import collections as _collections
import itertools as _itertools
import warnings as _warnings
import copy as _copy

from .. import tools as _tools
from ..tools import compattools as _compat
from .circuitstructure import LsGermsStructure as _LsGermsStructure
from .circuitstructure import LsGermsSerialStructure as _LsGermsSerialStructure
from .estimate import Estimate as _Estimate
from .gaugegroup import TrivialGaugeGroup as _TrivialGaugeGroup
from .gaugegroup import TrivialGaugeGroupElement as _TrivialGaugeGroupElement

#A flag to enable fast-loading of old results files (should
# only be changed by experts)
_SHORTCUT_OLD_RESULTS_LOAD = False


class Results(object):
    """
    Encapsulates a set of related GST estimates.

    A Results object is a container which associates a single `DataSet` and a
    structured set of operation sequences (usually the experiments contained in the
    data set) with a set of estimates.  Each estimate (`Estimate` object) contains
    models as well as parameters used to generate those inputs.  Associated
    `ConfidenceRegion` objects, because they are associated with a set of gate
    sequences, are held in the `Results` object but are associated with estimates.

    Typically, each `Estimate` is related to the input & output of a single
    GST calculation performed by a high-level driver routine like
    :func:`do_long_sequence_gst`.
    """

    def __init__(self):
        """
        Initialize an empty Results object.
        """

        #Dictionaries of inputs & outputs
        self.dataset = None
        self.circuit_lists = _collections.OrderedDict()
        self.circuit_structs = _collections.OrderedDict()
        self.estimates = _collections.OrderedDict()

    def init_dataset(self, dataset):
        """
        Initialize the (single) dataset of this `Results` object.

        Parameters
        ----------
        dataset : DataSet
            The dataset used to construct the estimates found in this
            `Results` object.

        Returns
        -------
        None
        """
        if self.dataset is not None:
            _warnings.warn(("Re-initializing the dataset of a Results object!"
                            "  Usually you don't want to do this."))
        self.dataset = dataset

    def init_circuits(self, structsByIter):
        """
        Initialize the common set operation sequences used to form the
        estimates of this Results object.

        There is one such set per GST iteration (if a non-iterative
        GST method was used, this is treated as a single iteration).

        Parameters
        ----------
        structsByIter : list
            The operation sequences used at each iteration. Ideally, elements are
            `LsGermsStruct` objects, which contain the structure needed to
            create color box plots in reports.  Elements may also be
            unstructured lists of operation sequences (but this may limit
            the amount of data visualization one can perform later).

        Returns
        -------
        None
        """
        if len(self.circuit_structs) > 0:
            _warnings.warn(("Re-initializing the operation sequences of a Results"
                            " object!  Usually you don't want to do this."))

        #Set circuit structures
        self.circuit_structs['iteration'] = []
        for gss in structsByIter:
            if isinstance(gss, (_LsGermsStructure, _LsGermsSerialStructure)):
                self.circuit_structs['iteration'].append(gss)
            elif isinstance(gss, list):
                unindexed_gss = _LsGermsStructure([], [], [], [], None)
                unindexed_gss.add_unindexed(gss)
                self.circuit_structs['iteration'].append(unindexed_gss)
            else:
                raise ValueError("Unknown type of operation sequence specifier: %s"
                                 % str(type(gss)))

        self.circuit_structs['final'] = \
            self.circuit_structs['iteration'][-1]

        #Extract raw circuit lists from structs
        self.circuit_lists['iteration'] = \
            [gss.allstrs for gss in self.circuit_structs['iteration']]
        self.circuit_lists['final'] = self.circuit_lists['iteration'][-1]
        self.circuit_lists['all'] = _tools.remove_duplicates(
            list(_itertools.chain(*self.circuit_lists['iteration'])))

        running_set = set(); delta_lsts = []
        for lst in self.circuit_lists['iteration']:
            delta_lst = [x for x in lst if (x not in running_set)]
            delta_lsts.append(delta_lst); running_set.update(delta_lst)
        self.circuit_lists['iteration delta'] = delta_lsts  # *added* at each iteration

        #Set "Ls and germs" info: gives particular structure
        # to the circuitLists used to obtain estimates
        finalStruct = self.circuit_structs['final']
        if isinstance(finalStruct, _LsGermsStructure):  # FUTURE: do something sensible w/ LsGermsSerialStructure?
            self.circuit_lists['prep fiducials'] = finalStruct.prepStrs
            self.circuit_lists['effect fiducials'] = finalStruct.effectStrs
            self.circuit_lists['germs'] = finalStruct.germs
        else:
            self.circuit_lists['prep fiducials'] = []
            self.circuit_lists['effect fiducials'] = []
            self.circuit_lists['germs'] = []

    def add_estimates(self, results, estimatesToAdd=None):
        """
        Add some or all of the estimates from `results` to this `Results` object.

        Parameters
        ----------
        results : Results
            The object to import estimates from.  Note that this object must contain
            the same data set and gate sequence information as the importing object
            or an error is raised.

        estimatesToAdd : list, optional
            A list of estimate keys to import from `results`.  If None, then all
            the estimates contained in `results` are imported.

        Returns
        -------
        None
        """
        if self.dataset is None:
            raise ValueError(("The data set must be initialized"
                              "*before* adding estimates"))

        if 'iteration' not in self.circuit_structs:
            raise ValueError(("Circuits must be initialized"
                              "*before* adding estimates"))

        assert(results.dataset is self.dataset), "DataSet inconsistency: cannot import estimates!"
        assert(len(self.circuit_structs['iteration']) == len(results.circuit_structs['iteration'])), \
            "Iteration count inconsistency: cannot import estimates!"

        for estimate_key in results.estimates:
            if estimatesToAdd is None or estimate_key in estimatesToAdd:
                if estimate_key in self.estimates:
                    _warnings.warn("Re-initializing the %s estimate" % estimate_key
                                   + " of this Results object!  Usually you don't"
                                   + " want to do this.")
                self.estimates[estimate_key] = results.estimates[estimate_key]

    def rename_estimate(self, old_name, new_name):
        """
        Rename an estimate in this Results object.  Ordering of estimates is
        not changed.

        Parameters
        ----------
        old_name : str
            The labels of the estimate to be renamed

        new_name : str
            The new name for the estimate.

        Returns
        -------
        None
        """
        if old_name not in self.estimates:
            raise KeyError("%s does not name an existing estimate" % old_name)

        if hasattr(self.estimates, "move_to_end"):
            #Python3: use move_to_end method of OrderedDict to restore ordering:
            ordered_keys = list(self.estimates.keys())
            self.estimates[new_name] = self.estimates[old_name]  # at end
            del self.estimates[old_name]
            keys_to_move = ordered_keys[ordered_keys.index(old_name) + 1:]  # everything after old_name
            for key in keys_to_move: self.estimates.move_to_end(key)

        else:
            #Python2.7: Manipulate internals of OrderedDict to change a key while preserving order
            PREV = 0; NEXT = 1  # ~enumerated

            #Unneeded, since root will be manipulated by link_prev or link_next below if needed
            #root = self.estimates._OrderedDict__root # [prev,next,value] element - the
            #  # root of the OrdereDict's circularly-linked list whose next member points
            #  # to the first element of the list.
            #first = root[NEXT] # first [prev,next,val] element of circularly linked list.

            old_element = self.estimates._OrderedDict__map[old_name]
            link_prev, link_next, _ = old_element  # ('_' == old_name)
            new_element = [link_prev, link_next, new_name]

            #Replace element in circularly linked list (w/"root" sentinel element)
            link_prev[NEXT] = new_element
            link_next[PREV] = new_element

            #Replace element in map
            del self.estimates._OrderedDict__map[old_name]
            self.estimates._OrderedDict__map[new_name] = new_element

            #Replace values in underlying dict
            value = dict.__getitem__(self.estimates, old_name)
            dict.__setitem__(self.estimates, new_name, value)

    def add_estimate(self, targetModel, seedModel, modeslByIter,
                     parameters, estimate_key='default'):
        """
        Add a set of `Model` estimates to this `Results` object.

        Parameters
        ----------
        targetModel : Model
            The target model used when optimizing the objective.

        seedModel : Model
            The initial model used to seed the iterative part
            of the objective optimization.  Typically this is
            obtained via LGST.

        modeslByIter : list of Models
            The estimated model at each GST iteration. Typically these are the
            estimated models *before* any gauge optimization is performed.

        parameters : dict
            A dictionary of parameters associated with how this estimate
            was obtained.

        estimate_key : str, optional
            The key or label used to identify this estimate.

        Returns
        -------
        None
        """
        if self.dataset is None:
            raise ValueError(("The data set must be initialized"
                              "*before* adding estimates"))

        if 'iteration' not in self.circuit_structs:
            raise ValueError(("Circuits must be initialized"
                              "*before* adding estimates"))

        la, lb = len(self.circuit_structs['iteration']), len(modeslByIter)
        assert(la == lb), "Number of iterations (%d) must equal %d!" % (lb, la)

        if estimate_key in self.estimates:
            _warnings.warn("Re-initializing the %s estimate" % estimate_key
                           + " of this Results object!  Usually you don't"
                           + " want to do this.")

        self.estimates[estimate_key] = _Estimate(self, targetModel, seedModel,
                                                 modeslByIter, parameters)

        #Set gate sequence related parameters inherited from Results
        self.estimates[estimate_key].parameters['max length list'] = \
            self.circuit_structs['final'].Ls

    def add_model_test(self, targetModel, themodel,
                       estimate_key='test', gauge_opt_keys="auto"):
        """
        Add a new model-test (i.e. non-optimized) estimate to this `Results` object.

        Parameters
        ----------
        targetModel : Model
            The target model used for comparison to the model.

        themodel : Model
            The "model" model whose fit to the data and distance from
            `targetModel` are assessed.

        estimate_key : str, optional
            The key or label used to identify this estimate.

        gauge_opt_keys : list, optional
            A list of gauge-optimization keys to add to the estimate.  All
            of these keys will correspond to trivial gauge optimizations,
            as the model model is assumed to be fixed and to have no
            gauge degrees of freedom.  The special value "auto" creates
            gauge-optimized estimates for all the gauge optimization labels
            currently in this `Results` object.

        Returns
        -------
        None
        """
        nIter = len(self.circuit_structs['iteration'])

        # base parameter values off of existing estimate parameters
        defaults = {'objective': 'logl', 'minProbClip': 1e-4, 'radius': 1e-4,
                    'minProbClipForWeighting': 1e-4, 'opLabelAliases': None,
                    'truncScheme': "whole germ powers"}
        for est in self.estimates.values():
            for ky in defaults:
                if ky in est.parameters: defaults[ky] = est.parameters[ky]

        #Construct a parameters dict, similar to do_model_test(...)
        parameters = _collections.OrderedDict()
        parameters['objective'] = defaults['objective']
        if parameters['objective'] == 'logl':
            parameters['minProbClip'] = defaults['minProbClip']
            parameters['radius'] = defaults['radius']
        elif parameters['objective'] == 'chi2':
            parameters['minProbClipForWeighting'] = defaults['minProbClipForWeighting']
        else:
            raise ValueError("Invalid objective: %s" % parameters['objective'])
        parameters['profiler'] = None
        parameters['opLabelAliases'] = defaults['opLabelAliases']
        parameters['weights'] = None  # Hardcoded

        #Set default gate group to trival group to mimic do_model_test (an to
        # be consistent with this function creating "gauge-optimized" models
        # by just copying the initial one).
        themodel = themodel.copy()
        themodel.default_gauge_group = _TrivialGaugeGroup(themodel.dim)

        self.add_estimate(targetModel, themodel, [themodel] * nIter,
                          parameters, estimate_key=estimate_key)

        #add gauge optimizations (always trivial)
        if gauge_opt_keys == "auto":
            gauge_opt_keys = []
            for est in self.estimates.values():
                for gokey in est.goparameters:
                    if gokey not in gauge_opt_keys:
                        gauge_opt_keys.append(gokey)

        est = self.estimates[estimate_key]
        for gokey in gauge_opt_keys:
            trivialEl = _TrivialGaugeGroupElement(themodel.dim)
            goparams = {'model': themodel,
                        'targetModel': targetModel,
                        '_gaugeGroupEl': trivialEl}
            est.add_gaugeoptimized(goparams, themodel, gokey)

    def view(self, estimate_keys, gaugeopt_keys=None):
        """
        Creates a shallow copy of this Results object containing only the
        given estimate and gauge-optimization keys.

        Parameters
        ----------
        estimate_keys : str or list
            Either a single string-value estimate key or a list of such keys.

        gaugeopt_keys : str or list, optional
            Either a single string-value gauge-optimization key or a list of
            such keys.  If `None`, then all gauge-optimization keys are
            retained.

        Returns
        -------
        Results
        """
        view = Results()
        view.dataset = self.dataset
        view.circuit_lists = self.circuit_lists
        view.circuit_structs = self.circuit_structs

        if _compat.isstr(estimate_keys):
            estimate_keys = [estimate_keys]
        for ky in estimate_keys:
            if ky in self.estimates:
                view.estimates[ky] = self.estimates[ky].view(gaugeopt_keys, view)

        return view

    def copy(self):
        """ Creates a copy of this Results object. """
        #TODO: check whether this deep copies (if we want it to...) - I expect it doesn't currently
        cpy = Results()
        cpy.dataset = self.dataset.copy()
        cpy.circuit_lists = _copy.deepcopy(self.circuit_lists)
        cpy.circuit_structs = _copy.deepcopy(self.circuit_structs)
        for est_key, est in self.estimates.items():
            cpy.estimates[est_key] = est.copy()
        return cpy

    def __setstate__(self, stateDict):

        if '_bEssentialResultsSet' in stateDict:
            raise ValueError(("This Results object is too old to unpickle - "
                              "try using pyGSTi v0.9.6 to upgrade it to a version "
                              "that this version can upgrade to the current version."))

        if 'gatestring_lists' in stateDict:
            _warnings.warn("Unpickling deprecated-format Results.  Please re-save/pickle asap.")
            self.circuit_lists = stateDict['gatestring_lists']
            self.circuit_structs = stateDict['gatestring_structs']
            del stateDict['gatestring_lists']
            del stateDict['gatestring_structs']

        #unpickle normally
        self.__dict__.update(stateDict)
        for est in self.estimates.values():
            est.set_parent(self)

    def __str__(self):
        s = "----------------------------------------------------------\n"
        s += "---------------- pyGSTi Results Object -------------------\n"
        s += "----------------------------------------------------------\n"
        s += "\n"
        s += "How to access my contents:\n\n"
        s += " .dataset    -- the DataSet used to generate these results\n\n"
        s += " .circuit_lists   -- a dict of Circuit lists w/keys:\n"
        s += " ---------------------------------------------------------\n"
        s += "  " + "\n  ".join(list(self.circuit_lists.keys())) + "\n"
        s += "\n"
        s += " .circuit_structs   -- a dict of CircuitStructures w/keys:\n"
        s += " ---------------------------------------------------------\n"
        s += "  " + "\n  ".join(list(self.circuit_structs.keys())) + "\n"
        s += "\n"
        s += " .estimates   -- a dictionary of Estimate objects:\n"
        s += " ---------------------------------------------------------\n"
        s += "  " + "\n  ".join(list(self.estimates.keys())) + "\n"
        s += "\n"
        return s

    #OLD Methods for generating reports which have been removed - show alert
    # message directing users to new factory functions

    def create_full_report_pdf(self, confidenceLevel=None, filename="auto",
                               title="auto", datasetLabel="auto", suffix="",
                               debugAidsAppendix=False, gaugeOptAppendix=False,
                               pixelPlotAppendix=False, whackamoleAppendix=False,
                               pureDataAppendix=False, m=0, M=10, tips=False,
                               verbosity=0, comm=None):
        """ DEPRECATED: use pygsti.report.create_standard_report(...) """
        _warnings.warn(
            ('create_full_report_pdf(...) has been removed from pyGSTi.\n'
             '  Starting in version 0.9.4, pyGSTi\'s PDF reports have been\n'
             '  significantly upgraded.  As a part of this change,\n'
             '  the functions that generate reports are now separate functions.\n'
             '  Please update this call with one to:\n'
             '  pygsti.report.create_standard_report(...)\n'))

    def create_brief_report_pdf(self, confidenceLevel=None,
                                filename="auto", title="auto", datasetLabel="auto",
                                suffix="", m=0, M=10, tips=False, verbosity=0,
                                comm=None):
        """ DEPRECATED: use pygsti.report.create_standard_report(...) """
        _warnings.warn(
            ('create_brief_report_pdf(...) has been removed from pyGSTi.\n'
             '  Starting in version 0.9.4, pyGSTi\'s PDF reports have been\n'
             '  significantly upgraded.  As a part of this change,\n'
             '  the functions that generate reports are now separate functions.\n'
             '  Please update this call with one to:\n'
             '  pygsti.report.create_standard_report(...)\n'))

    def create_presentation_pdf(self, confidenceLevel=None, filename="auto",
                                title="auto", datasetLabel="auto", suffix="",
                                debugAidsAppendix=False,
                                pixelPlotAppendix=False, whackamoleAppendix=False,
                                m=0, M=10, verbosity=0, comm=None):
        """ DEPRECATED: use pygsti.report.create_standard_report(...) """
        _warnings.warn(
            ('create_presentation_pdf(...) has been removed from pyGSTi.\n'
             '  Starting in version 0.9.4, pyGSTi\'s PDF reports have been\n'
             '  significantly upgraded.  As a part of this change,\n'
             '  the functions that generate reports are now separate functions.\n'
             '  Please update this call with one to:\n'
             '  pygsti.report.create_standard_report(...)\n'))

    def create_presentation_ppt(self, confidenceLevel=None, filename="auto",
                                title="auto", datasetLabel="auto", suffix="",
                                debugAidsAppendix=False,
                                pixelPlotAppendix=False, whackamoleAppendix=False,
                                m=0, M=10, verbosity=0, pptTables=False, comm=None):
        """ DEPRECATED: use pygsti.report.create_standard_report(...) """
        _warnings.warn(
            ('create_presentation_ppt(...) has been removed from pyGSTi.\n'
             '  Starting in version 0.9.4, pyGSTi\'s PDF reports have been\n'
             '  significantly upgraded.  As a part of this change,\n'
             '  the functions that generate reports are now separate functions.\n'
             '  Please update this call with one to:\n'
             '  pygsti.report.create_standard_report(...)\n'))

    def create_general_report_pdf(self, confidenceLevel=None, filename="auto",
                                  title="auto", datasetLabel="auto", suffix="",
                                  tips=False, verbosity=0, comm=None,
                                  showAppendix=False):
        """ DEPRECATED: use pygsti.report.create_standard_report(...) """
        _warnings.warn(
            ('create_general_report_pdf(...) has been removed from pyGSTi.\n'
             '  Starting in version 0.9.4, pyGSTi\'s PDF reports have been\n'
             '  significantly upgraded.  As a part of this change,\n'
             '  the functions that generate reports are now separate functions.\n'
             '  Please update this call with one to:\n'
             '  pygsti.report.create_standard_report(...)\n'))
