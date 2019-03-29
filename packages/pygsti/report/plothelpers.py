""" Helper Functions for generating plots """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
import warnings as _warnings

from .. import tools as _tools
from .. import objects as _objs

from ..baseobjs import smart_cached


def total_count_matrix(gsplaq, dataset):
    """
    Computes the total count matrix for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify the counts

    Returns
    -------
    numpy array of shape (M,N)
        total count values (sum of count values for each SPAM label)
        corresponding to operation sequences where circuit is sandwiched
        between the specified set of N prep-fiducial and M effect-fiducial
        operation sequences.
    """
    ret = _np.nan * _np.ones(gsplaq.num_simplified_elements, 'd')
    for i, j, opstr, elIndices, outcomes in gsplaq.iter_simplified():
        ret[elIndices] = dataset[opstr].total
        # OR should it sum only over outcomes, i.e.
        # = sum([dataset[opstr][ol] for ol in outcomes])
    return ret


def count_matrices(gsplaq, dataset):
    """
    Computes spamLabel's count matrix for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify the counts

    spamlabels : list of strings
        The spam labels to extract counts for, e.g. ['plus']

    Returns
    -------
    numpy array of shape ( len(spamlabels), len(effectStrs), len(prepStrs) )
        count values corresponding to spamLabel and operation sequences
        where circuit is sandwiched between the each prep-fiducial and
        effect-fiducial pair.
    """
    ret = _np.nan * _np.ones(gsplaq.num_simplified_elements, 'd')
    for i, j, opstr, elIndices, outcomes in gsplaq.iter_simplified():
        datarow = dataset[opstr]
        ret[elIndices] = [datarow[ol] for ol in outcomes]
    return ret


def frequency_matrices(gsplaq, dataset):
    """
    Computes spamLabel's frequency matrix for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify the frequencies

    spamlabels : list of strings
        The spam labels to extract frequencies for, e.g. ['plus']


    Returns
    -------
    numpy array of shape ( len(spamlabels), len(effectStrs), len(prepStrs) )
        frequency values corresponding to spamLabel and operation sequences
        where circuit is sandwiched between the each prep-fiducial,
        effect-fiducial pair.
    """
    return count_matrices(gsplaq, dataset) \
        / total_count_matrix(gsplaq, dataset)


def probability_matrices(gsplaq, model,
                         probs_precomp_dict=None):
    """
    Computes spamLabel's probability matrix for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    model : Model
        The model used to specify the probabilities

    spamlabels : list of strings
        The spam labels to extract probabilities for, e.g. ['plus']

    probs_precomp_dict : dict, optional
        A dictionary of precomputed probabilities.  Keys are operation sequences
        and values are prob-dictionaries (as returned from Model.probs)
        corresponding to each operation sequence.

    Returns
    -------
    numpy array of shape ( len(spamlabels), len(effectStrs), len(prepStrs) )
        probability values corresponding to spamLabel and operation sequences
        where circuit is sandwiched between the each prep-fiducial,
        effect-fiducial pair.
    """
    ret = _np.nan * _np.ones(gsplaq.num_simplified_elements, 'd')
    if probs_precomp_dict is None:
        if model is not None:
            for i, j, opstr, elIndices, outcomes in gsplaq.iter_simplified():
                probs = model.probs(opstr)
                ret[elIndices] = [probs[ol] for ol in outcomes]
    else:
        for i, j, opstr, elIndices, _ in gsplaq.iter_simplified():
            ret[elIndices] = probs_precomp_dict[opstr]  # precomp is already in element-array form
    return ret


@smart_cached
def chi2_matrix(gsplaq, dataset, model, minProbClipForWeighting=1e-4,
                probs_precomp_dict=None):
    """
    Computes the chi^2 matrix for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify frequencies and counts

    model : Model
        The model used to specify the probabilities and SPAM labels

    minProbClipForWeighting : float, optional
        defines the clipping interval for the statistical weight (see chi2fn).

    probs_precomp_dict : dict, optional
        A dictionary of precomputed probabilities.  Keys are operation sequences
        and values are prob-dictionaries (as returned from Model.probs)
        corresponding to each operation sequence.

    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        chi^2 values corresponding to operation sequences where
        circuit is sandwiched between the each prep-fiducial,
        effect-fiducial pair.
    """
    gsplaq_ds = gsplaq.expand_aliases(dataset, circuit_simplifier=model)
    cnts = total_count_matrix(gsplaq_ds, dataset)
    probs = probability_matrices(gsplaq, model,
                                 probs_precomp_dict)
    freqs = frequency_matrices(gsplaq_ds, dataset)

    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for (i, j, opstr, elIndices, _), (_, _, _, elIndices_ds, _) in zip(
            gsplaq.iter_simplified(), gsplaq_ds.iter_simplified()):
        chiSqs = _tools.chi2fn(cnts[elIndices_ds], probs[elIndices],
                               freqs[elIndices_ds], minProbClipForWeighting)
        ret[i, j] = sum(chiSqs)  # sum all elements for each (i,j) pair
    return ret


@smart_cached
def logl_matrix(gsplaq, dataset, model, minProbClip=1e-6,
                probs_precomp_dict=None):
    """
    Computes the log-likelihood matrix of 2*( log(L)_upperbound - log(L) )
    values for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify frequencies and counts

    model : Model
        The model used to specify the probabilities and SPAM labels

    minProbClip : float, optional
        defines the minimum probability "patch-point" of the log-likelihood function.

    probs_precomp_dict : dict, optional
        A dictionary of precomputed probabilities.  Keys are operation sequences
        and values are prob-dictionaries (as returned from Model.probs)
        corresponding to each operation sequence.


    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        logl values corresponding to operation sequences where
        circuit is sandwiched between the each prep-fiducial,
        effect-fiducial pair.
    """
    gsplaq_ds = gsplaq.expand_aliases(dataset, circuit_simplifier=model)

    cnts = total_count_matrix(gsplaq_ds, dataset)
    probs = probability_matrices(gsplaq, model,
                                 probs_precomp_dict)
    freqs = frequency_matrices(gsplaq_ds, dataset)

    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for (i, j, opstr, elIndices, _), (_, _, _, elIndices_ds, _) in zip(
            gsplaq.iter_simplified(), gsplaq_ds.iter_simplified()):
        logLs = _tools.two_delta_loglfn(cnts[elIndices_ds], probs[elIndices],
                                        freqs[elIndices_ds], minProbClip)
        ret[i, j] = sum(logLs)  # sum all elements for each (i,j) pair
    return ret


@smart_cached
def tvd_matrix(gsplaq, dataset, model, probs_precomp_dict=None):
    """
    Computes the total-variational distance matrix of `0.5 * |p-f|`
    values for a base circuit.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dataset : DataSet
        The data used to specify frequencies and counts

    model : Model
        The model used to specify the probabilities and SPAM labels

    probs_precomp_dict : dict, optional
        A dictionary of precomputed probabilities.  Keys are operation sequences
        and values are prob-dictionaries (as returned from Model.probs)
        corresponding to each operation sequence.


    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        logl values corresponding to operation sequences where
        circuit is sandwiched between the each prep-fiducial,
        effect-fiducial pair.
    """
    gsplaq_ds = gsplaq.expand_aliases(dataset, circuit_simplifier=model)

    probs = probability_matrices(gsplaq, model,
                                 probs_precomp_dict)
    freqs = frequency_matrices(gsplaq_ds, dataset)

    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for (i, j, opstr, elIndices, _), (_, _, _, elIndices_ds, _) in zip(
            gsplaq.iter_simplified(), gsplaq_ds.iter_simplified()):
        TVDs = 0.5 * _np.abs(probs[elIndices] - freqs[elIndices_ds])
        ret[i, j] = sum(TVDs)  # sum all elements for each (i,j) pair
    return ret


def small_eigval_err_rate(sigma, directGSTmodels):
    """
    Compute per-gate error rate.

    The per-gate error rate, extrapolated from the smallest eigvalue
    of the Direct GST estimate of the given operation sequence sigma.

    Parameters
    ----------
    sigma : Circuit or tuple of operation labels
        The gate sequence that is used to estimate the error rate

    dataset : DataSet
        The dataset used obtain operation sequence frequencies

    directGSTmodels : dictionary of Models
        A dictionary with keys = operation sequences and
        values = Models.

    Returns
    -------
    float
        the approximate per-gate error rate.
    """
    if sigma is None: return _np.nan  # in plot processing, "None" circuits = no plot output = nan values
    mdl_direct = directGSTmodels[sigma]
    minEigval = min(abs(_np.linalg.eigvals(mdl_direct.operations["GsigmaLbl"])))
    return 1.0 - minEigval**(1.0 / max(len(sigma), 1))  # (approximate) per-gate error rate; max averts divide by zero error


def _eformat(f, prec):
    """
    Formatting routine for writing compact representations of
    numbers in plot boxes
    """
    if _np.isnan(f): return ""  # show NAN as blanks
    if prec == 'compact' or prec == 'compacthp':
        if f < 0:
            ef = _eformat(-f, prec)
            return "-" + ef if (ef != "0") else "0"

        if prec == 'compacthp':
            if f <= 0.5e-9:  # can't fit in 3 digits; 1e-9 = "1m9" is the smallest 3-digit (not counting minus signs)
                return "0"
            if f < 0.005:  # then need scientific notation since 3-digit float would be 0.00...
                s = "%.0e" % f
                try:
                    mantissa, exp = s.split('e')
                    exp = int(exp)
                    assert(exp < 0)
                    if exp < -9: return "0"  # should have been caugth above, but just in case
                    return "%sm%d" % (mantissa, -exp)
                except:
                    return "?"
            if f < 1:
                z = "%.2f" % f  # print first two decimal places
                if z.startswith("0."): return z[1:]  # fails for '1.00'; then thunk down to next f<10 case
            if f < 10:
                return "%.1f" % f  # print whole number and tenths

        if f < 100:
            return "%.0f" % f  # print nearest whole number if only 1 or 2 digits

        #if f >= 100, minimal scientific notation, such as "4e7", not "4e+07"
        s = "%.0e" % f
        try:
            mantissa, exp = s.split('e')
            exp = int(exp)
            if exp >= 100: return "B"  # if number is too big to print
            if exp >= 10: return "*%d" % exp
            return "%se%d" % (mantissa, exp)
        except:
            return str(s)[0:3]

    elif type(prec) == int:
        if prec >= 0:
            return "%.*f" % (prec, f)
        else:
            return "%.*g" % (-prec, f)
    else:
        return "%g" % f  # fallback to general format


def _num_non_nan(array):
    ixs = _np.where(_np.isnan(_np.array(array).flatten()) == False)[0]
    return int(len(ixs))


def _all_same(items):
    return all(x == items[0] for x in items)


def _compute_num_boxes_dof(subMxs, sumUp, element_dof):
    """
    A helper function to compute the number of boxes, and corresponding
    number of degrees of freedom, for the GST chi2/logl boxplots.

    """
    if sumUp:
        s = _np.shape(subMxs)
        # Reshape the subMxs into a "flattened" form (as opposed to a
        # two-dimensional one)
        reshape_subMxs = _np.array(_np.reshape(subMxs, (s[0] * s[1], s[2], s[3])))

        #Get all the boxes where the entries are not all NaN
        non_all_NaN = reshape_subMxs[_np.where(_np.array([_np.isnan(k).all() for k in reshape_subMxs]) == False)]
        s = _np.shape(non_all_NaN)
        dof_each_box = [_num_non_nan(k) * element_dof for k in non_all_NaN]

        # Don't assert this anymore -- just use average below
        if not _all_same(dof_each_box):
            _warnings.warn('Number of degrees of freedom different for different boxes!')

        # The number of boxes is equal to the number of rows in non_all_NaN
        n_boxes = s[0]

        if n_boxes > 0:
            # Each box is a chi2_(sum) random variable
            dof_per_box = _np.average(dof_each_box)
        else:
            dof_per_box = None  # unknown, since there are no boxes
    else:
        # Each box is a chi2_m random variable currently dictated by the number of
        # dataset degrees of freedom.
        dof_per_box = element_dof

        # Gets all the non-NaN boxes, flattens the resulting
        # array, and does the sum.
        n_boxes = _np.sum(~_np.isnan(subMxs).flatten())

    return n_boxes, dof_per_box


def _computeProbabilities(gss, model, dataset, probClipInterval=(-1e6, 1e6),
                          check=False, opLabelAliases=None,
                          comm=None, smartc=None, wildcard=None):
    """
    Returns a dictionary of probabilities for each gate sequence in
    CircuitStructure `gss`.
    """
    def smart(fn, *args, **kwargs):
        if smartc:
            return smartc.cached_compute(fn, args, kwargs)[1]
        else:
            if '_filledarrays' in kwargs: del kwargs['_filledarrays']
            return fn(*args, **kwargs)

    circuitList = gss.allstrs

    #compute probabilities
    #OLD: evt,lookup,_ = smart(model.bulk_evaltree, circuitList, dataset=dataset)
    evt, _, _, lookup, outcomes_lookup = smart(model.bulk_evaltree_from_resources,
                                               circuitList, comm, dataset=dataset)

    bulk_probs = _np.zeros(evt.num_final_elements(), 'd')  # _np.empty(evt.num_final_elements(), 'd') - .zeros b/c of caching
    smart(model.bulk_fill_probs, bulk_probs, evt, probClipInterval, check, comm, _filledarrays=(0,))
    # bulk_probs indexed by [element_index]

    if wildcard:
        freqs = _np.empty(evt.num_final_elements(), 'd')
        ds_circuit_list = _tools.find_replace_tuple_list(
            circuitList, opLabelAliases)
        for (i, opStr) in enumerate(ds_circuit_list):
            cnts = dataset[opStr].counts
            total = sum(cnts.values())
            freqs[lookup[i]] = [cnts.get(x, 0) / total for x in outcomes_lookup[i]]

        probs_in = bulk_probs.copy()
        wildcard.update_probs(probs_in, bulk_probs, freqs, circuitList, lookup)

    probs_dict = \
        {circuitList[i]: bulk_probs.take(_tools.as_array(lookup[i]))
         for i in range(len(circuitList))}
    return probs_dict


#@smart_cached
def _computeSubMxs(gss, model, subMxCreationFn, dataset=None, subMxCreationFn_extra_arg=None):
    if model is not None: gss.simplify_plaquettes(model, dataset)
    subMxs = [[subMxCreationFn(gss.get_plaquette(x, y), x, y, subMxCreationFn_extra_arg)
               for x in gss.used_xvals()] for y in gss.used_yvals()]
    #Note: subMxs[y-index][x-index] is proper usage
    return subMxs


@smart_cached
def direct_chi2_matrix(gsplaq, gss, dataset, directModel,
                       minProbClipForWeighting=1e-4):
    """
    Computes the Direct-X chi^2 matrix for a base circuit sigma.

    Similar to chi2_matrix, except the probabilities used to compute
    chi^2 values come from using the "composite gate" of directModels[sigma],
    a Model assumed to contain some estimate of sigma stored under the
    operation label "GsigmaLbl".

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        (for accessing the dataset) they correspond to.

    gss : CircuitStructure
        The operation sequence structure object containing `gsplaq`.  The structure is
        neede to create a special plaquette for computing probabilities from the
        direct model containing a "GsigmaLbl" gate.

    dataset : DataSet
        The data used to specify frequencies and counts

    directModel : Model
        Model which contains an estimate of sigma stored
        under the operation label "GsigmaLbl".

    minProbClipForWeighting : float, optional
        defines the clipping interval for the statistical weight (see chi2fn).


    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        Direct-X chi^2 values corresponding to operation sequences where
        circuit is sandwiched between the each (effectStr,prepStr) pair.
    """
    if len(gsplaq.get_all_strs()) > 0:  # skip cases with no strings
        plaq_ds = gsplaq.expand_aliases(dataset, circuit_simplifier=directModel)
        plaq_pr = gss.create_plaquette(_objs.Circuit(("GsigmaLbl",)))
        plaq_pr.simplify_circuits(directModel)

        cnts = total_count_matrix(plaq_ds, dataset)
        probs = probability_matrices(plaq_pr, directModel)  # no probs_precomp_dict
        freqs = frequency_matrices(plaq_ds, dataset)

        ret = _np.empty((plaq_ds.rows, plaq_ds.cols), 'd')
        for (i, j, opstr, elIndices, _), (_, _, _, elIndices_ds, _) in zip(
                plaq_pr.iter_simplified(), plaq_ds.iter_simplified()):
            chiSqs = _tools.chi2fn(cnts[elIndices_ds], probs[elIndices],
                                   freqs[elIndices_ds], minProbClipForWeighting)
            ret[i, j] = sum(chiSqs)  # sum all elements for each (i,j) pair

        return ret
    else:
        return _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')


@smart_cached
def direct_logl_matrix(gsplaq, gss, dataset, directModel,
                       minProbClip=1e-6):
    """
    Computes the Direct-X log-likelihood matrix, containing the values
     of 2*( log(L)_upperbound - log(L) ) for a base circuit sigma.

    Similar to logl_matrix, except the probabilities used to compute
    LogL values come from using the "composite gate" of directModels[sigma],
    a Model assumed to contain some estimate of sigma stored under the
    operation label "GsigmaLbl".

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        (for accessing the dataset) they correspond to.

    gss : CircuitStructure
        The operation sequence structure object containing `gsplaq`.  The structure is
        neede to create a special plaquette for computing probabilities from the
        direct model containing a "GsigmaLbl" gate.

    dataset : DataSet
        The data used to specify frequencies and counts

    directModel : Model
        Model which contains an estimate of sigma stored
        under the operation label "GsigmaLbl".

    minProbClip : float, optional
        defines the minimum probability clipping.

    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        Direct-X logL values corresponding to operation sequences where
        circuit is sandwiched between the each (effectStr,prepStr) pair.
    """
    if len(gsplaq.get_all_strs()) > 0:  # skip cases with no strings
        plaq_ds = gsplaq.expand_aliases(dataset, circuit_simplifier=directModel)
        plaq_pr = gss.create_plaquette(_objs.Circuit(("GsigmaLbl",)))
        plaq_pr.simplify_circuits(directModel)

        cnts = total_count_matrix(plaq_ds, dataset)
        probs = probability_matrices(plaq_pr, directModel)  # no probs_precomp_dict
        freqs = frequency_matrices(plaq_ds, dataset)

        ret = _np.empty((plaq_ds.rows, plaq_ds.cols), 'd')
        for (i, j, opstr, elIndices, _), (_, _, _, elIndices_ds, _) in zip(
                plaq_pr.iter_simplified(), plaq_ds.iter_simplified()):
            logLs = _tools.two_delta_loglfn(cnts[elIndices_ds], probs[elIndices],
                                            freqs[elIndices_ds], minProbClip)
            ret[i, j] = sum(logLs)  # sum all elements for each (i,j) pair
        return ret
    else:
        return _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')


@smart_cached
def dscompare_llr_matrices(gsplaq, dscomparator):
    """
    Computes matrix of 2*log-likelihood-ratios comparing the
    datasets of `dscomparator`.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    dscomparator : DataComparator
        The object specifying the data to be compared.

    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        log-likelihood-ratio values corresponding to the operation sequences
        where a base circuit is sandwiched between the each prep-fiducial and
        effect-fiducial pair.
    """
    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for i, j, opstr in gsplaq:
        ret[i, j] = dscomparator.llrs[opstr]
    return ret


@smart_cached
def drift_oneoverpvalue_matrices(gsplaq, driftresults):
    """
    Computes matrix of 1 / pvalues for testing the
    "no drift" null hypothesis in each sequence, using the
    "max power in spectra" test. These are the pvalues associated
    with the quantities returned by `drift_maxpower_matrices`.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    driftresults : BasicDriftResults
        The drift analysis results.

    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        1 / pvalues for testing the "no drift" null hypothesis, using the "max power in
        spectra" test, on the relevant sequences. This operation sequences correspond to the
        operation sequences where a base circuit is sandwiched between the each prep-fiducial
        and effect-fiducial pair.

    """
    pvalues_and_strings_dict = {}
    #for opstr in driftresults.circuitlist:
    #    pvalues_and_strings_dict[opstr] = driftresults.get_maxpower_pvalue(sequence=opstr)

    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for i, j, opstr in gsplaq:
        try:
            pval = driftresults.get_maxpower_pvalue(sequence=opstr)
            if pval <= 0.:
                #oneoverpvls = 1./driftresults.ps_pvalue.copy()
                #oneoverpvls = oneoverpvls[_np.isfinite(oneoverpvls)]
                #ret[i,j] = 2*_np.round(_np.max(oneoverpvls))
                ret[i, j] = 16
            else:
                ret[i, j] = _np.log10(1. / pval)  # pvalues_and_strings_dict[opstr])
        except:
            pass
    return ret


@smart_cached
def drift_maxpower_matrices(gsplaq, driftresults):
    """
    Computes matrix of max powers in the time-series power spectra. This
    value is a reasonable proxy for how "drifty" the sequence appears
    to be.

    Parameters
    ----------
    gsplaq : CircuitPlaquette
        Obtained via :method:`CircuitStructure.get_plaquette`, this object
        specifies which matrix indices should be computed and which operation sequences
        they correspond to.

    driftresults : BasicDriftResults
        The drift analysis results.

    Returns
    -------
    numpy array of shape ( len(effectStrs), len(prepStrs) )
        Matrix of max powers in the time-series power spectra forthe operation sequences where a
        base circuit is sandwiched between the each prep-fiducial and effect-fiducial pair.

    """
    maxpowers_and_strings_dict = {}
    #for opstr in driftresults.circuitlist:
    #    maxpowers_and_strings_dict[opstr] = driftresults.get_maxpower(sequence=opstr)

    ret = _np.nan * _np.ones((gsplaq.rows, gsplaq.cols), 'd')
    for i, j, opstr in gsplaq:
        try:
            ret[i, j] = driftresults.get_maxpower(sequence=opstr)
            #maxpowers_and_strings_dict[opstr]
        except:
            pass
    return ret


def ratedNsigma(dataset, model, gss, objective, Np=None, wildcard=None, returnAll=False,
                comm=None, smartc=None):  # TODO: pipe down minprobclip, radius, probclipinterval?
    """
    Computes the number of standard deviations of model violation, comparing
    the data in `dataset` with the `model` model at the "points" (sequences)
    specified by `gss`.

    Parameters
    ----------
    dataset : DataSet
        The data set.

    model : Model
        The model (model).

    gss : CircuitStructure
        A operation sequence structure whose `.allstrs` member contains a list of
        `Circuits` specifiying the sequences used to compare the data and
        model.  Its `.aliases` member optionally specifies operation label aliases
        to be used when querying `dataset`.

    objective : {"logl", "chi2"}
        Which objective function is used to compute the model violation.

    Np : int, optional
        The number of free parameters in the model.  If None, then
        `model.num_nongauge_params()` is used.

    wildcard : TODO: docstring

    returnAll : bool, optional
        Returns additional information such as the raw and expected model
        violation (see below).

    comm : mpi4py.MPI.Comm, optional
        When not None, an MPI communicator for distributing the computation
        across multiple processors.

    smartc : SmartCache, optional
        A cache object to cache & use previously cached values inside this
        function.


    Returns
    -------
    Nsig : float
        The number of sigma of model violaition

    rating : int
        A 1-5 rating (e.g. "number of stars") used to indicate the rough
        abililty of the model to fit the data (better fit = higher rating).

    modelViolation : float
        The raw value of the objective function.  Only returned when
        `returnAll==True`.

    expectedViolation : float
        The expected value of the objective function.  Only returned when
        `returnAll==True`.

    Ns, Np : int
        The number of dataset and model parameters, respectively. Only
        returned when `returnAll==True`.

    """
    gstrs = gss.allstrs
    if objective == "chi2":
        assert(wildcard is None), "Can only use wildcard budget with 'logl' objective!"
        fitQty = _tools.chi2(model, dataset, gstrs,
                             minProbClipForWeighting=1e-4,
                             opLabelAliases=gss.aliases,
                             comm=comm, smartc=smartc)
    elif objective == "logl":
        logL_upperbound = _tools.logl_max(model, dataset, gstrs, opLabelAliases=gss.aliases,
                                          smartc=smartc)
        logl = _tools.logl(model, dataset, gstrs, opLabelAliases=gss.aliases,
                           comm=comm, smartc=smartc, wildcard=wildcard)
        fitQty = 2 * (logL_upperbound - logl)  # twoDeltaLogL
        if(logL_upperbound < logl):
            if _np.isclose(logL_upperbound, logl):
                logl = logl_upperbound
                fitQty = 0.0
            else:
                raise ValueError("LogL upper bound = %g but logl = %g!!" % (logL_upperbound, logl))

    ds_gstrs = _tools.find_replace_tuple_list(gstrs, gss.aliases)

    if Np is None: Np = model.num_nongauge_params()
    Ns = dataset.get_degrees_of_freedom(ds_gstrs)  # number of independent parameters in dataset
    k = max(Ns - Np, 1)  # expected chi^2 or 2*(logL_ub-logl) mean
    Nsig = (fitQty - k) / _np.sqrt(2 * k)
    if Ns <= Np: _warnings.warn("Max-model params (%d) <= model params (%d)!  Using k == 1." % (Ns, Np))
    #pv = 1.0 - _stats.chi2.cdf(chi2,k) # reject GST model if p-value < threshold (~0.05?)

    if Nsig <= 2: rating = 5
    elif Nsig <= 20: rating = 4
    elif Nsig <= 100: rating = 3
    elif Nsig <= 500: rating = 2
    else: rating = 1

    if returnAll:
        return Nsig, rating, fitQty, k, Ns, Np
    else:
        return Nsig, rating
