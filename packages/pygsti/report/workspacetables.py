""" Classes corresponding to tables within a Workspace context."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import warnings as _warnings
import numpy as _np
import scipy.sparse as _sps

from .. import construction as _cnst
from .. import tools as _tools
from .. import objects as _objs
from . import reportables as _reportables
from .reportables import evaluate as _ev
from ..baseobjs import Label as _Lbl

from .table import ReportTable as _ReportTable

from .workspace import WorkspaceTable
from . import workspaceplots as _wp
from . import plothelpers as _ph


class BlankTable(WorkspaceTable):
    """A completely blank placeholder table."""

    def __init__(self, ws):
        """A completely blank placeholder table."""
        super(BlankTable, self).__init__(ws, self._create)

    def _create(self):
        table = _ReportTable(['Blank'], [None])
        table.finish()
        return table


class SpamTable(WorkspaceTable):
    """ A table of one or more model's SPAM elements. """

    def __init__(self, ws, models, titles=None,
                 display_as="boxes", confidenceRegionInfo=None,
                 includeHSVec=True):
        """
        A table of one or more model's SPAM elements.

        Parameters
        ----------
        models : Model or list of Models
            The Model(s) whose SPAM elements should be displayed. If
            multiple Models are given, they should have the same SPAM
            elements..

        titles : list of strs, optional
            Titles correponding to elements of `models`, e.g. `"Target"`.

        display_as : {"numbers", "boxes"}, optional
            How to display the SPAM matrices, as either numerical
            grids (fine for small matrices) or as a plot of colored
            boxes (space-conserving and better for large matrices).

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        includeHSVec : boolean, optional
            Whether or not to include Hilbert-Schmidt
            vector representation columns in the table.
        """
        super(SpamTable, self).__init__(ws, self._create, models,
                                        titles, display_as, confidenceRegionInfo,
                                        includeHSVec)

    def _create(self, models, titles, display_as, confidenceRegionInfo,
                includeHSVec):

        if isinstance(models, _objs.Model):
            models = [models]

        rhoLabels = list(models[0].preps.keys())  # use labels of 1st model
        povmLabels = list(models[0].povms.keys())  # use labels of 1st model

        if titles is None:
            titles = [''] * len(models)

        colHeadings = ['Operator']
        for model, title in zip(models, titles):
            colHeadings.append('%sMatrix' % (title + ' ' if title else ''))
        for model, title in zip(models, titles):
            colHeadings.append('%sEigenvals' % (title + ' ' if title else ''))

        formatters = [None] * len(colHeadings)

        if includeHSVec:
            model = models[-1]  # only show HSVec for last model
            basisNm = _tools.basis_longname(model.basis)
            colHeadings.append('Hilbert-Schmidt vector (%s basis)' % basisNm)
            formatters.append(None)

            if confidenceRegionInfo is not None:
                colHeadings.append('%g%% C.I. half-width' % confidenceRegionInfo.level)
                formatters.append('Conversion')

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        for lbl in rhoLabels:
            rowData = [lbl]
            rowFormatters = ['Rho']

            for model in models:
                rhoMx = _ev(_reportables.Vec_as_stdmx(model, lbl, "prep"))
                # confidenceRegionInfo) #don't put CIs on matrices for now
                if display_as == "numbers":
                    rowData.append(rhoMx)
                    rowFormatters.append('Brackets')
                elif display_as == "boxes":
                    rhoMx_real = rhoMx.hermitian_to_real()
                    v = rhoMx_real.get_value()
                    fig = _wp.GateMatrixPlot(self.ws, v, colorbar=False,
                                             boxLabels=True, prec='compacthp',
                                             mxBasis=None)  # no basis labels
                    rowData.append(fig)
                    rowFormatters.append('Figure')
                else:
                    raise ValueError("Invalid 'display_as' argument: %s" % display_as)

            for model in models:
                cri = confidenceRegionInfo if confidenceRegionInfo and \
                    (confidenceRegionInfo.model.frobeniusdist(model) < 1e-6) else None
                evals = _ev(_reportables.Vec_as_stdmx_eigenvalues(model, lbl, "prep"),
                            cri)
                rowData.append(evals)
                rowFormatters.append('Brackets')

            if includeHSVec:
                rowData.append(models[-1].preps[lbl])
                rowFormatters.append('Normal')

                if confidenceRegionInfo is not None:
                    intervalVec = confidenceRegionInfo.get_profile_likelihood_confidence_intervals(lbl)[:, None]
                    if intervalVec.shape[0] == models[-1].get_dimension() - 1:
                        #TP constrained, so pad with zero top row
                        intervalVec = _np.concatenate((_np.zeros((1, 1), 'd'), intervalVec), axis=0)
                    rowData.append(intervalVec)
                    rowFormatters.append('Normal')

            #Note: no dependence on confidence region (yet) when HS vector is not shown...
            table.addrow(rowData, rowFormatters)

        for povmlbl in povmLabels:
            for lbl in models[0].povms[povmlbl].keys():
                povmAndELbl = str(povmlbl) + ":" + lbl  # format for ModelFunction objs
                rowData = [lbl] if (len(povmLabels) == 1) else [povmAndELbl]  # show POVM name if there's more than one of them
                rowFormatters = ['Effect']

                for model in models:
                    EMx = _ev(_reportables.Vec_as_stdmx(model, povmAndELbl, "effect"))
                    #confidenceRegionInfo) #don't put CIs on matrices for now
                    if display_as == "numbers":
                        rowData.append(EMx)
                        rowFormatters.append('Brackets')
                    elif display_as == "boxes":
                        EMx_real = EMx.hermitian_to_real()
                        v = EMx_real.get_value()
                        fig = _wp.GateMatrixPlot(self.ws, v, colorbar=False,
                                                 boxLabels=True, prec='compacthp',
                                                 mxBasis=None)  # no basis labels
                        rowData.append(fig)
                        rowFormatters.append('Figure')
                    else:
                        raise ValueError("Invalid 'display_as' argument: %s" % display_as)  # pragma: no cover

                for model in models:
                    cri = confidenceRegionInfo if confidenceRegionInfo and \
                        (confidenceRegionInfo.model.frobeniusdist(model) < 1e-6) else None
                    evals = _ev(_reportables.Vec_as_stdmx_eigenvalues(model, povmAndELbl, "effect"),
                                cri)
                    rowData.append(evals)
                    rowFormatters.append('Brackets')

                if includeHSVec:
                    rowData.append(models[-1].povms[povmlbl][lbl])
                    rowFormatters.append('Normal')

                    if confidenceRegionInfo is not None:
                        intervalVec = confidenceRegionInfo.get_profile_likelihood_confidence_intervals(povmlbl)[:, None]  # for all povm params
                        intervalVec = intervalVec[models[-1].povms[povmlbl][lbl].gpindices]  # specific to this effect
                        rowData.append(intervalVec)
                        rowFormatters.append('Normal')

                #Note: no dependence on confidence region (yet) when HS vector is not shown...
                table.addrow(rowData, rowFormatters)

        table.finish()
        return table


class SpamParametersTable(WorkspaceTable):
    """ A table for "SPAM parameters" (dot products of SPAM vectors)"""

    def __init__(self, ws, models, titles=None, confidenceRegionInfo=None):
        """
        Create a table for model's "SPAM parameters", that is, the
        dot products of prep-vectors and effect-vectors.

        Parameters
        ----------
        models : Model or list of Models
            The Model(s) whose SPAM parameters should be displayed. If
            multiple Models are given, they should have the same gates.

        titles : list of strs, optional
            Titles correponding to elements of `models`, e.g. `"Target"`.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(SpamParametersTable, self).__init__(ws, self._create, models, titles, confidenceRegionInfo)

    def _create(self, models, titles, confidenceRegionInfo):

        if isinstance(models, _objs.Model):
            models = [models]
        if titles is None:
            titles = [''] * len(models)

        if len(models[0].povms) == 1:
            povmKey = list(models[0].povms.keys())[0]
            effectLbls = [eLbl for eLbl in models[0].povms[povmKey]]
        else:
            effectLbls = [povmLbl + "." + eLbl
                          for povmLbl, povm in models[0].povms.items()
                          for eLbl in povm.keys()]

        colHeadings = [''] + effectLbls
        formatters = [None] + ['Effect'] * len(effectLbls)

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        for gstitle, model in zip(titles, models):
            cri = confidenceRegionInfo if (confidenceRegionInfo
                                           and confidenceRegionInfo.model.frobeniusdist(model) < 1e-6) else None
            spamDotProdsQty = _ev(_reportables.Spam_dotprods(model), cri)
            DPs, DPEBs = spamDotProdsQty.get_value_and_err_bar()
            assert(DPs.shape[1] == len(effectLbls)), \
                "Models must have the same number of POVMs & effects"

            formatters = ['Rho'] + ['Normal'] * len(effectLbls)  # for rows below

            for ii, prepLabel in enumerate(model.preps.keys()):  # ii enumerates rhoLabels to index DPs
                prefix = gstitle + " " if len(gstitle) else ""
                rowData = [prefix + str(prepLabel)]
                for jj, _ in enumerate(effectLbls):  # jj enumerates eLabels to index DPs
                    if cri is None:
                        rowData.append((DPs[ii, jj], None))
                    else:
                        rowData.append((DPs[ii, jj], DPEBs[ii, jj]))
                table.addrow(rowData, formatters)

        table.finish()
        return table


class GatesTable(WorkspaceTable):
    """ Create a table showing a model's raw gates. """

    def __init__(self, ws, models, titles=None, display_as="boxes",
                 confidenceRegionInfo=None):
        """
        Create a table showing a model's raw gates.

        Parameters
        ----------
        models : Model or list of Models
            The Model(s) whose gates should be displayed.  If multiple
            Models are given, they should have the same operation labels.

        titles : list of strings, optional
            A list of titles corresponding to the models, used to
            prefix the column(s) for that model. E.g. `"Target"`.

        display_as : {"numbers", "boxes"}, optional
            How to display the operation matrices, as either numerical
            grids (fine for small matrices) or as a plot of colored
            boxes (space-conserving and better for large matrices).

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals for the *final*
            element of `models`.

        Returns
        -------
        ReportTable
        """
        super(GatesTable, self).__init__(ws, self._create, models, titles,
                                         display_as, confidenceRegionInfo)

    def _create(self, models, titles, display_as, confidenceRegionInfo):

        if isinstance(models, _objs.Model):
            models = [models]

        opLabels = models[0].get_primitive_op_labels()  # use labels of 1st model
        assert(isinstance(models[0], _objs.ExplicitOpModel)), "%s only works with explicit models" % str(type(self))

        if titles is None:
            titles = [''] * len(models)

        colHeadings = ['Gate']
        for model, title in zip(models, titles):
            basisLongNm = _tools.basis_longname(model.basis)
            pre = (title + ' ' if title else '')
            colHeadings.append('%sSuperoperator (%s basis)' % (pre, basisLongNm))
        formatters = [None] * len(colHeadings)

        if confidenceRegionInfo is not None:
            #Only use confidence region for the *final* model.
            colHeadings.append('%g%% C.I. half-width' % confidenceRegionInfo.level)
            formatters.append('Conversion')

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        for gl in opLabels:
            #Note: currently, we don't use confidence region...
            row_data = [gl]
            row_formatters = [None]

            for model in models:
                basis = model.basis

                if display_as == "numbers":
                    row_data.append(model.operations[gl])
                    row_formatters.append('Brackets')
                elif display_as == "boxes":
                    fig = _wp.GateMatrixPlot(self.ws, model.operations[gl].todense(),
                                             colorbar=False,
                                             mxBasis=basis)

                    row_data.append(fig)
                    row_formatters.append('Figure')
                else:
                    raise ValueError("Invalid 'display_as' argument: %s" % display_as)

            if confidenceRegionInfo is not None:
                intervalVec = confidenceRegionInfo.get_profile_likelihood_confidence_intervals(gl)[:, None]
                if isinstance(models[-1].operations[gl], _objs.FullDenseOp):
                    #then we know how to reshape into a matrix
                    op_dim = models[-1].get_dimension()
                    basis = models[-1].basis
                    intervalMx = intervalVec.reshape(op_dim, op_dim)
                elif isinstance(models[-1].operations[gl], _objs.TPDenseOp):
                    #then we know how to reshape into a matrix
                    op_dim = models[-1].get_dimension()
                    basis = models[-1].basis
                    intervalMx = _np.concatenate((_np.zeros((1, op_dim), 'd'),
                                                  intervalVec.reshape(op_dim - 1, op_dim)), axis=0)
                else:
                    # we don't know how best to reshape interval matrix for gate, so
                    # use derivative
                    op_dim = models[-1].get_dimension()
                    basis = models[-1].basis
                    op_deriv = models[-1].operations[gl].deriv_wrt_params()
                    intervalMx = _np.abs(_np.dot(op_deriv, intervalVec).reshape(op_dim, op_dim))

                if display_as == "numbers":
                    row_data.append(intervalMx)
                    row_formatters.append('Brackets')

                elif display_as == "boxes":
                    maxAbsVal = _np.max(_np.abs(intervalMx))
                    fig = _wp.GateMatrixPlot(self.ws, intervalMx,
                                             m=-maxAbsVal, M=maxAbsVal,
                                             colorbar=False,
                                             mxBasis=basis)
                    row_data.append(fig)
                    row_formatters.append('Figure')
                else:
                    assert(False)  # pragma: no cover

            table.addrow(row_data, row_formatters)

        table.finish()
        return table


class ChoiTable(WorkspaceTable):
    """A table of the Choi representations of a Model's gates"""

    def __init__(self, ws, models, titles=None,
                 confidenceRegionInfo=None,
                 display=("matrix", "eigenvalues", "barplot")):
        """
        Create a table of the Choi matrices and/or their eigenvalues of
        a model's gates.

        Parameters
        ----------
        models : Model or list of Models
            The Model(s) whose Choi info should be displayed.  If multiple
            Models are given, they should have the same operation labels.

        titles : list of strings, optional
            A list of titles corresponding to the models, used to
            prefix the column(s) for that model. E.g. `"Target"`.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display eigenvalue error intervals for the
            *final* Model in `models`.

        display : tuple/list of {"matrices","eigenvalues","barplot","boxplot"}
            Which columns to display: the Choi matrices (as numerical grids),
            the Choi matrix eigenvalues (as a numerical list), the eigenvalues
            on a bar plot, and/or the matrix as a plot of colored boxes.


        Returns
        -------
        ReportTable
        """
        super(ChoiTable, self).__init__(ws, self._create, models, titles,
                                        confidenceRegionInfo, display)

    def _create(self, models, titles, confidenceRegionInfo, display):
        if isinstance(models, _objs.Model):
            models = [models]

        opLabels = models[0].get_primitive_op_labels()  # use labels of 1st model
        assert(isinstance(models[0], _objs.ExplicitOpModel)), "%s only works with explicit models" % str(type(self))

        if titles is None:
            titles = [''] * len(models)

        qtysList = []
        for model in models:
            opLabels = model.get_primitive_op_labels()  # operation labels
            #qtys_to_compute = []
            if 'matrix' in display or 'boxplot' in display:
                choiMxs = [_ev(_reportables.Choi_matrix(model, gl)) for gl in opLabels]
            else:
                choiMxs = None
            if 'eigenvalues' in display or 'barplot' in display:
                evals = [_ev(_reportables.Choi_evals(model, gl), confidenceRegionInfo) for gl in opLabels]
            else:
                evals = None
            qtysList.append((choiMxs, evals))
        colHeadings = ['Gate']
        for disp in display:
            if disp == "matrix":
                for model, title in zip(models, titles):
                    basisLongNm = _tools.basis_longname(model.basis)
                    pre = (title + ' ' if title else '')
                    colHeadings.append('%sChoi matrix (%s basis)' % (pre, basisLongNm))
            elif disp == "eigenvalues":
                for model, title in zip(models, titles):
                    pre = (title + ' ' if title else '')
                    colHeadings.append('%sEigenvalues' % pre)
            elif disp == "barplot":
                for model, title in zip(models, titles):
                    pre = (title + ' ' if title else '')
                    colHeadings.append('%sEigenvalue Magnitudes' % pre)
            elif disp == "boxplot":
                for model, title in zip(models, titles):
                    basisLongNm = _tools.basis_longname(model.basis)
                    pre = (title + ' ' if title else '')
                    colHeadings.append('%sChoi matrix (%s basis)' % (pre, basisLongNm))
            else:
                raise ValueError("Invalid element of `display`: %s" % disp)
        formatters = [None] * len(colHeadings)

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        for i, gl in enumerate(opLabels):
            #Note: currently, we don't use confidence region...
            row_data = [gl]
            row_formatters = [None]

            for disp in display:
                if disp == "matrix":
                    for model, (choiMxs, _) in zip(models, qtysList):
                        row_data.append(choiMxs[i])
                        row_formatters.append('Brackets')

                elif disp == "eigenvalues":
                    for model, (_, evals) in zip(models, qtysList):
                        try:
                            evals[i] = evals[i].reshape(evals[i].size // 4, 4)
                            #assumes len(evals) is multiple of 4!
                        except:  # if it isn't try 3 (qutrits)
                            evals[i] = evals[i].reshape(evals[i].size // 3, 3)
                            #assumes len(evals) is multiple of 3!
                        row_data.append(evals[i])
                        row_formatters.append('Normal')

                elif disp == "barplot":
                    for model, (_, evals) in zip(models, qtysList):
                        evs, evsEB = evals[i].get_value_and_err_bar()
                        fig = _wp.ChoiEigenvalueBarPlot(self.ws, evs, evsEB)
                        row_data.append(fig)
                        row_formatters.append('Figure')

                elif disp == "boxplot":
                    for model, (choiMxs, _) in zip(models, qtysList):
                        choiMx_real = choiMxs[i].hermitian_to_real()
                        choiMx, EB = choiMx_real.get_value_and_err_bar()
                        fig = _wp.GateMatrixPlot(self.ws, choiMx,
                                                 colorbar=False,
                                                 mxBasis=model.basis,
                                                 EBmatrix=EB)
                        row_data.append(fig)
                        row_formatters.append('Figure')

            table.addrow(row_data, row_formatters)
        table.finish()
        return table


class ModelVsTargetTable(WorkspaceTable):
    """ Table comparing a Model (as a whole) to a target """

    def __init__(self, ws, model, targetModel, clifford_compilation, confidenceRegionInfo=None):
        """
        Create a table comparing a model (as a whole) to a target model
        using metrics that can be evaluatd for an entire model.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare

        clifford_compilation : dict
            A dictionary of operation sequences, one for each Clifford operation
            in the Clifford group relevant to the model Hilbert space.  If
            None, then rows requiring a clifford compilation are omitted.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(ModelVsTargetTable, self).__init__(ws, self._create, model,
                                                 targetModel, clifford_compilation,
                                                 confidenceRegionInfo)

    def _create(self, model, targetModel, clifford_compilation, confidenceRegionInfo):

        colHeadings = ('Metric', "Value")
        formatters = (None, None)

        tooltips = colHeadings
        table = _ReportTable(colHeadings, formatters, colHeadingLabels=tooltips, confidenceRegionInfo=confidenceRegionInfo)

        #Leave this off for now, as it's primary use is to compare with RB and the predicted RB number is better for this.
        #pAGsI = _ev(_reportables.Average_gateset_infidelity(model, targetModel), confidenceRegionInfo)
        #table.addrow(("Avg. primitive model infidelity", pAGsI), (None, 'Normal') )

        pRBnum = _ev(_reportables.Predicted_rb_number(model, targetModel), confidenceRegionInfo)
        table.addrow(("Predicted primitive RB number", pRBnum), (None, 'Normal'))

        if clifford_compilation:
            clifford_model = _cnst.build_explicit_alias_model(model, clifford_compilation)
            clifford_targetModel = _cnst.build_explicit_alias_model(targetModel, clifford_compilation)

            ##For clifford versions we don't have a confidence region - so no error bars
            #AGsI = _ev(_reportables.Average_gateset_infidelity(clifford_model, clifford_targetModel))
            #table.addrow(("Avg. clifford model infidelity", AGsI), (None, 'Normal') )

            RBnum = _ev(_reportables.Predicted_rb_number(clifford_model, clifford_targetModel))
            table.addrow(("Predicted Clifford RB number", RBnum), (None, 'Normal'))

        table.finish()
        return table


class GatesVsTargetTable(WorkspaceTable):
    """ Table comparing a Model's gates to those of a target model """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None,
                 display=('inf', 'agi', 'trace', 'diamond', 'nuinf', 'nuagi'),
                 virtual_ops=None, wildcard=None):
        """
        Create a table comparing a model's gates to a target model using
        metrics such as the  infidelity, diamond-norm distance, and trace distance.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        display : tuple, optional
            A tuple of one or more of the allowed options (see below) which
            specify which columns are displayed in the table.

            - "inf" :     entanglement infidelity
            - "agi" :     average gate infidelity
            - "trace" :   1/2 trace distance
            - "diamond" : 1/2 diamond norm distance
            - "nuinf" :   non-unitary entanglement infidelity
            - "nuagi" :   non-unitary entanglement infidelity
            - "evinf" :     eigenvalue entanglement infidelity
            - "evagi" :     eigenvalue average gate infidelity
            - "evnuinf" :   eigenvalue non-unitary entanglement infidelity
            - "evnuagi" :   eigenvalue non-unitary entanglement infidelity
            - "evdiamond" : eigenvalue 1/2 diamond norm distance
            - "evnudiamond" : eigenvalue non-unitary 1/2 diamond norm distance
            - "frob" :    frobenius distance
            - "unmodeled" : unmodeled "wildcard" budget

        virtual_ops : list, optional
            If not None, a list of `Circuit` objects specifying additional "gates"
            (i.e. processes) to compute eigenvalues of.  Length-1 operation sequences are
            automatically discarded so they are not displayed twice.

        wildcard: TODO: docstring

        Returns
        -------
        ReportTable
        """
        super(GatesVsTargetTable, self).__init__(ws, self._create, model,
                                                 targetModel, confidenceRegionInfo,
                                                 display, virtual_ops, wildcard)

    def _create(self, model, targetModel, confidenceRegionInfo,
                display, virtual_ops, wildcard):

        opLabels = model.get_primitive_op_labels()  # operation labels
        assert(isinstance(model, _objs.ExplicitOpModel)), "%s only works with explicit models" % str(type(self))

        colHeadings = ['Gate'] if (virtual_ops is None) else ['Gate or Germ']
        tooltips = ['Gate'] if (virtual_ops is None) else ['Gate or Germ']
        for disp in display:
            try:
                heading, tooltip = _reportables.info_of_opfn_by_name(disp)
            except ValueError:
                raise ValueError("Invalid display column name: %s" % disp)
            colHeadings.append(heading)
            tooltips.append(tooltip)

        formatters = (None,) + ('Conversion',) * (len(colHeadings) - 1)

        table = _ReportTable(colHeadings, formatters, colHeadingLabels=tooltips,
                             confidenceRegionInfo=confidenceRegionInfo)

        formatters = (None,) + ('Normal',) * (len(colHeadings) - 1)

        if virtual_ops is None:
            iterOver = opLabels
        else:
            iterOver = opLabels + tuple((v for v in virtual_ops if len(v) > 1))

        for gl in iterOver:
            #Note: gl may be a operation label (a string) or a Circuit
            row_data = [str(gl)]

            for disp in display:
                if disp == "unmodeled":  # a special case for now
                    row_data.append(_objs.reportableqty.ReportableQty(
                        wildcard.get_op_budget(gl)))
                    continue

                #import time as _time #DEBUG
                #tStart = _time.time() #DEBUG
                qty = _reportables.evaluate_opfn_by_name(
                    disp, model, targetModel, gl, confidenceRegionInfo)
                #tm = _time.time()-tStart #DEBUG
                #if tm > 0.01: print("DB: Evaluated %s in %gs" % (disp, tm)) #DEBUG
                row_data.append(qty)

            table.addrow(row_data, formatters)
        table.finish()
        return table


class SpamVsTargetTable(WorkspaceTable):
    """ Table comparing a Model's SPAM vectors to those of a target """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None):
        """
        Create a table comparing a model's SPAM operations to a target model
        using state infidelity and trace distance.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(SpamVsTargetTable, self).__init__(ws, self._create, model,
                                                targetModel, confidenceRegionInfo)

    def _create(self, model, targetModel, confidenceRegionInfo):

        prepLabels = list(model.preps.keys())
        povmLabels = list(model.povms.keys())

        colHeadings = ('Prep/POVM', "Infidelity", "1/2 Trace|Distance", "1/2 Diamond-Dist")
        formatters = (None, 'Conversion', 'Conversion', 'Conversion')
        tooltips = ('', 'State infidelity or entanglement infidelity of POVM map',
                    'Trace distance between states (preps) or Jamiolkowski states of POVM maps',
                    'Half-diamond-norm distance between POVM maps')
        table = _ReportTable(colHeadings, formatters, colHeadingLabels=tooltips,
                             confidenceRegionInfo=confidenceRegionInfo)

        formatters = ['Rho'] + ['Normal'] * (len(colHeadings) - 1)
        prepInfidelities = [_ev(_reportables.Vec_infidelity(model, targetModel, l,
                                                            'prep'), confidenceRegionInfo)
                            for l in prepLabels]
        prepTraceDists = [_ev(_reportables.Vec_tr_diff(model, targetModel, l,
                                                       'prep'), confidenceRegionInfo)
                          for l in prepLabels]
        prepDiamondDists = [_objs.reportableqty.ReportableQty(_np.nan)] * len(prepLabels)
        for rowData in zip(prepLabels, prepInfidelities, prepTraceDists,
                           prepDiamondDists):
            table.addrow(rowData, formatters)

        formatters = ['Normal'] + ['Normal'] * (len(colHeadings) - 1)
        povmInfidelities = [_ev(_reportables.POVM_entanglement_infidelity(
            model, targetModel, l), confidenceRegionInfo)
            for l in povmLabels]
        povmTraceDists = [_ev(_reportables.POVM_jt_diff(
            model, targetModel, l), confidenceRegionInfo)
            for l in povmLabels]
        povmDiamondDists = [_ev(_reportables.POVM_half_diamond_norm(
            model, targetModel, l), confidenceRegionInfo)
            for l in povmLabels]

        for rowData in zip(povmLabels, povmInfidelities, povmTraceDists,
                           povmDiamondDists):
            table.addrow(rowData, formatters)

        table.finish()
        return table


class ErrgenTable(WorkspaceTable):
    """ Table displaying the error generators of a Model's gates as well
        as their projections onto spaces of standard generators """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None,
                 display=("errgen", "H", "S", "A"), display_as="boxes",
                 genType="logGTi"):
        """
        Create a table listing the error generators obtained by
        comparing a model's gates to a target model.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare

        display : tuple of {"errgen","H","S","A"}
            Specifes which columns to include: the error generator itself
            and the projections of the generator onto Hamiltoian-type error
            (generators), Stochastic-type errors, and Affine-type errors.

        display_as : {"numbers", "boxes"}, optional
            How to display the requested matrices, as either numerical
            grids (fine for small matrices) or as a plot of colored boxes
            (space-conserving and better for large matrices).

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        genType : {"logG-logT", "logTiG", "logGTi"}
            The type of error generator to compute.  Allowed values are:

            - "logG-logT" : errgen = log(gate) - log(target_op)
            - "logTiG" : errgen = log( dot(inv(target_op), gate) )
            - "logTiG" : errgen = log( dot(gate, inv(target_op)) )

        Returns
        -------
        ReportTable
        """
        super(ErrgenTable, self).__init__(ws, self._create, model,
                                          targetModel, confidenceRegionInfo,
                                          display, display_as, genType)

    def _create(self, model, targetModel,
                confidenceRegionInfo, display, display_as, genType):

        opLabels = model.get_primitive_op_labels()  # operation labels
        basis = model.basis
        basisPrefix = ""
        if basis.name == "pp": basisPrefix = "Pauli "
        elif basis.name == "qt": basisPrefix = "Qutrit "
        elif basis.name == "gm": basisPrefix = "GM "
        elif basis.name == "std": basisPrefix = "Mx unit "

        colHeadings = ['Gate']

        for disp in display:
            if disp == "errgen":
                colHeadings.append('Error Generator')
            elif disp == "H":
                colHeadings.append('%sHamiltonian Projections' % basisPrefix)
            elif disp == "S":
                colHeadings.append('%sStochastic Projections' % basisPrefix)
            elif disp == "A":
                colHeadings.append('%sAffine Projections' % basisPrefix)
            else: raise ValueError("Invalid display element: %s" % disp)

        assert(display_as == "boxes" or display_as == "numbers")
        table = _ReportTable(colHeadings, (None,) * len(colHeadings),
                             confidenceRegionInfo=confidenceRegionInfo)

        errgenAndProjs = {}
        errgensM = []
        hamProjsM = []
        stoProjsM = []
        affProjsM = []

        def getMinMax(max_lst, M):
            """return a [min,max] already in list if there's one within an
               order of magnitude"""
            M = max(M, ABS_THRESHOLD)
            for mx in max_lst:
                if (abs(M) >= 1e-6 and 0.9999 < mx / M < 10) or (abs(mx) < 1e-6 and abs(M) < 1e-6):
                    return -mx, mx
            return None

        ABS_THRESHOLD = 1e-6  # don't let color scales run from 0 to 0: at least this much!

        def addMax(max_lst, M):
            """add `M` to a list of maximas if it's different enough from
               existing elements"""
            M = max(M, ABS_THRESHOLD)
            if not getMinMax(max_lst, M):
                max_lst.append(M)

        #Do computation, so shared color scales can be computed
        for gl in opLabels:
            if genType == "logG-logT":
                info = _ev(_reportables.LogGmlogT_and_projections(
                    model, targetModel, gl), confidenceRegionInfo)
            elif genType == "logTiG":
                info = _ev(_reportables.LogTiG_and_projections(
                    model, targetModel, gl), confidenceRegionInfo)
            elif genType == "logGTi":
                info = _ev(_reportables.LogGTi_and_projections(
                    model, targetModel, gl), confidenceRegionInfo)
            else: raise ValueError("Invalid generator type: %s" % genType)
            errgenAndProjs[gl] = info

            errgen = info['error generator'].get_value()
            absMax = _np.max(_np.abs(errgen))
            addMax(errgensM, absMax)

            if "H" in display:
                absMax = _np.max(_np.abs(info['hamiltonian projections'].get_value()))
                addMax(hamProjsM, absMax)

            if "S" in display:
                absMax = _np.max(_np.abs(info['stochastic projections'].get_value()))
                addMax(stoProjsM, absMax)

            if "A" in display:
                absMax = _np.max(_np.abs(info['affine projections'].get_value()))
                addMax(affProjsM, absMax)

        #Do plotting
        for gl in opLabels:
            row_data = [gl]
            row_formatters = [None]
            info = errgenAndProjs[gl]

            for disp in display:
                if disp == "errgen":
                    if display_as == "boxes":
                        errgen, EB = info['error generator'].get_value_and_err_bar()
                        m, M = getMinMax(errgensM, _np.max(_np.abs(errgen)))
                        errgen_fig = _wp.GateMatrixPlot(self.ws, errgen, m, M,
                                                        basis, EBmatrix=EB)
                        row_data.append(errgen_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(info['error generator'])
                        row_formatters.append('Brackets')

                elif disp == "H":
                    if display_as == "boxes":
                        T = "Power %.2g" % info['hamiltonian projection power'].get_value()
                        hamProjs, EB = info['hamiltonian projections'].get_value_and_err_bar()
                        m, M = getMinMax(hamProjsM, _np.max(_np.abs(hamProjs)))
                        hamdecomp_fig = _wp.ProjectionsBoxPlot(
                            self.ws, hamProjs, basis, m, M,
                            boxLabels=True, EBmatrix=EB, title=T)
                        row_data.append(hamdecomp_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(info['hamiltonian projections'])
                        row_formatters.append('Brackets')

                elif disp == "S":
                    if display_as == "boxes":
                        T = "Power %.2g" % info['stochastic projection power'].get_value()
                        stoProjs, EB = info['stochastic projections'].get_value_and_err_bar()
                        m, M = getMinMax(stoProjsM, _np.max(_np.abs(stoProjs)))
                        stodecomp_fig = _wp.ProjectionsBoxPlot(
                            self.ws, stoProjs, basis, m, M,
                            boxLabels=True, EBmatrix=EB, title=T)
                        row_data.append(stodecomp_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(info['stochastic projections'])
                        row_formatters.append('Brackets')

                elif disp == "A":
                    if display_as == "boxes":
                        T = "Power %.2g" % info['affine projection power'].get_value()
                        affProjs, EB = info['affine projections'].get_value_and_err_bar()
                        m, M = getMinMax(affProjsM, _np.max(_np.abs(affProjs)))
                        affdecomp_fig = _wp.ProjectionsBoxPlot(
                            self.ws, affProjs, basis, m, M,
                            boxLabels=True, EBmatrix=EB, title=T)
                        row_data.append(affdecomp_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(info['affine projections'])
                        row_formatters.append('Brackets')

            table.addrow(row_data, row_formatters)

        table.finish()
        return table


class GaugeRobustErrgenTable(WorkspaceTable):
    """ Table displaying the first-order gauge invariant ("gauge robust")
        linear combinations of standard error generator coefficients for
        the gates in a model.
    """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None,
                 genType="logGTi"):
        """
        Create a table listing the first-order gauge invariant ("gauge robust")
        linear combinations of standard error generator coefficients for
        the gates in `model`.  This table identifies, through the use of
        "synthetic idle tomography", which combinations of standard-error-
        generator coefficients are robust (to first-order) to gauge variations.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        genType : {"logG-logT", "logTiG", "logGTi"}
            The type of error generator to compute.  Allowed values are:

            - "logG-logT" : errgen = log(gate) - log(target_op)
            - "logTiG" : errgen = log( dot(inv(target_op), gate) )
            - "logTiG" : errgen = log( dot(gate, inv(target_op)) )

        Returns
        -------
        ReportTable
        """
        super(GaugeRobustErrgenTable, self).__init__(ws, self._create, model,
                                                     targetModel, confidenceRegionInfo,
                                                     genType)

    def _create(self, model, targetModel, confidenceRegionInfo, genType):

        opLabels = model.get_primitive_op_labels()  # operation labels
        assert(isinstance(model, _objs.ExplicitOpModel)), "%s only works with explicit models" % str(type(self))

        colHeadings = ['Error rates', 'Value']

        table = _ReportTable(colHeadings, (None,) * len(colHeadings),
                             confidenceRegionInfo=confidenceRegionInfo)

        assert(genType == "logGTi"), "Only `genType == \"logGTI\"` is supported when `gaugeRobust` is True"
        syntheticIdleStrs = []

        ## Construct synthetic idles
        maxPower = 4
        maxLen = 6
        Id = _np.identity(targetModel.dim, 'd')
        baseStrs = _cnst.list_all_circuits_without_powers_and_cycles(list(model.operations.keys()), maxLen)
        for s in baseStrs:
            for i in range(1, maxPower):
                if len(s**i) > 1 and _np.linalg.norm(targetModel.product(s**i) - Id) < 1e-6:
                    syntheticIdleStrs.append(s**i)
                    break
        #syntheticIdleStrs = _cnst.circuit_list([ ('Gx',)*4, ('Gy',)*4 ] ) #DEBUG!!!
        #syntheticIdleStrs = _cnst.circuit_list([ ('Gx',)*4, ('Gy',)*4, ('Gy','Gx','Gx')*2] ) #DEBUG!!!
        print("Using synthetic idles: \n", '\n'.join([str(opstr) for opstr in syntheticIdleStrs]))

        gaugeRobust_info = _ev(_reportables.Robust_LogGTi_and_projections(
            model, targetModel, syntheticIdleStrs), confidenceRegionInfo)

        for linear_combo_lbl, val in gaugeRobust_info.items():
            row_data = [linear_combo_lbl, val]
            row_formatters = [None, 'Normal']
            table.addrow(row_data, row_formatters)

        table.finish()
        return table


class NQubitErrgenTable(WorkspaceTable):
    """
    Table displaying the error rates (coefficients of error generators) of a
    Model's gates.  The gates are assumed to have a particular structure.

    Specifically, gates must be :class:`LindbladOp` or
    :class:`StaticDenseOp` objects wrapped within :class:`EmbeddedOp` and/or
    :class:`ComposedOp` objects (this is consistent with the operation
    blocks of a :class:`CloudNoiseModel`).  As such, error rates
    are read directly from the gate objects rather than being computed by
    projecting dense gate representations onto a "basis" of fixed error
    generators (e.g. H+S+A generators).
    """

    def __init__(self, ws, model, confidenceRegionInfo=None,
                 display=("H", "S", "A"), display_as="boxes"):
        """
        Create a table listing the error rates of the gates in `model`.

        The gates in `model` are assumed to have a particular structure,
        namely: they must be :class:`LindbladOp` or
        :class:`StaticDenseOp` objects wrapped within :class:`EmbeddedOp`
        and/or :class:`ComposedOp` objects.

        Error rates are organized by order of composition and which qubits
        the corresponding error generators act upon.

        Parameters
        ----------
        model : Model
            The model to analyze.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        display : tuple of {"H","S","A"}
            Specifes which columns to include: Hamiltoian-type,
            Pauli-Stochastic-type, and Affine-type rates, respectively.

        display_as : {"numbers", "boxes"}, optional
            How to display the requested matrices, as either numerical
            grids (fine for small matrices) or as a plot of colored boxes
            (space-conserving and better for large matrices).

        Returns
        -------
        ReportTable
        """
        super(NQubitErrgenTable, self).__init__(ws, self._create, model,
                                                confidenceRegionInfo,
                                                display, display_as)

    def _create(self, model, confidenceRegionInfo, display, display_as):
        opLabels = model.get_primitive_op_labels()  # operation labels

        #basis = model.basis
        #basisPrefix = ""
        #if basis.name == "pp": basisPrefix = "Pauli "
        #elif basis.name == "qt": basisPrefix = "Qutrit "
        #elif basis.name == "gm": basisPrefix = "GM "
        #elif basis.name == "std": basisPrefix = "Mx unit "

        colHeadings = ['Gate', 'Compos', 'SSLbls']

        for disp in display:
            #if disp == "errgen":
            #    colHeadings.append('Error Generator')
            if disp == "H":
                colHeadings.append('Hamiltonian Coeffs')
            elif disp == "S":
                colHeadings.append('Stochastic Coeffs')
            elif disp == "A":
                colHeadings.append('Affine Coeffs')
            else: raise ValueError("Invalid display element: %s" % disp)

        assert(display_as == "boxes" or display_as == "numbers")
        table = _ReportTable(colHeadings, (None,) * len(colHeadings),
                             confidenceRegionInfo=confidenceRegionInfo)

        def getMinMax(max_lst, M):
            """return a [min,max] already in list if there's one within an
               order of magnitude"""
            M = max(M, ABS_THRESHOLD)
            for mx in max_lst:
                if (abs(M) >= 1e-6 and 0.9999 < mx / M < 10) or (abs(mx) < 1e-6 and abs(M) < 1e-6):
                    return -mx, mx
            return None

        ABS_THRESHOLD = 1e-6  # don't let color scales run from 0 to 0: at least this much!

        def addMax(max_lst, M):
            """add `M` to a list of maximas if it's different enough from
               existing elements"""
            M = max(M, ABS_THRESHOLD)
            if not getMinMax(max_lst, M):
                max_lst.append(M)

        pre_rows = []
        displayed_params = set()

        def process_gate(lbl, gate, comppos_prefix, sslbls):
            if isinstance(gate, _objs.ComposedOp):
                for i, fgate in enumerate(gate.factorops):
                    process_gate(lbl, fgate, comppos_prefix + (i,), sslbls)
            elif isinstance(gate, _objs.EmbeddedOp):
                process_gate(lbl, gate.embedded_op, comppos_prefix, gate.targetLabels)
            elif isinstance(gate, _objs.StaticDenseOp):
                pass  # no error coefficients associated w/static gates
            elif isinstance(gate, _objs.LindbladOp):

                # Only display coeffs for gates that correspond to *new*
                # (not yet displayed) parameters.
                params = set(gate.gpindices_as_array())
                if not params.issubset(displayed_params):
                    displayed_params.update(params)

                    Ldict, basisDict = gate.get_errgen_coeffs()
                    if len(basisDict) > 0:
                        sparse = _sps.issparse(list(basisDict.values())[0])
                    else: sparse = False

                    #Try to find good labels for these basis elements
                    # (so far, just try to match with "pp" basis els)
                    ref_basis = _objs.BuiltinBasis("pp", gate.dim, sparse=sparse)
                    basisLbls = {}
                    for bl1, mx in basisDict.items():
                        for bl2, mx2 in zip(ref_basis.labels, ref_basis.elements):
                            if (sparse and _tools.sparse_equal(mx, mx2)) or (not sparse and _np.allclose(mx, mx2)):
                                basisLbls[bl1] = bl2
                                break
                        else:
                            basisLbls[bl1] = bl1

                    pre_rows.append((lbl, comppos_prefix, sslbls, Ldict, basisLbls))
            else:
                raise ValueError("Unknown gate type for NQubitErrgenTable: %s" % str(type(gate)))

        def get_plot_info(Ldict, basisLbls, typ):
            # for now just make a 1D plot - can get fancy later...
            ylabels = [""]
            xlabels = []
            coeffs = []
            for termInfo, coeff in Ldict.items():
                termtyp = termInfo[0]
                if termtyp not in ("H", "S", "A"): raise ValueError("Unknown terminfo: ", termInfo)
                if (termtyp == "H" and typ == "hamiltonian") or \
                   (termtyp == "S" and typ == "stochastic") or \
                   (termtyp == "A" and typ == "affine"):
                    assert(len(termInfo) == 2), "Non-diagonal terms not suppoted (yet)!"
                    xlabels.append(basisLbls[termInfo[1]])
                    coeffs.append(coeff)
            return _np.array([coeffs]), xlabels, ylabels

        #Do computation, so shared color scales can be computed
        if isinstance(model, _objs.ExplicitOpModel):
            for gl in opLabels:
                process_gate(gl, model.operations[gl], (), None)
        elif isinstance(model, _objs.ImplicitOpModel):  # process primitive op error
            for gl in opLabels:
                process_gate(gl, model.operation_blks['cloudnoise'][gl], (), None)
        else:
            raise ValueError("Unrecognized type of model: %s" % str(type(model)))

        #get min/max
        if len(pre_rows) > 0:
            M = max((max(map(abs, Ldict.values())) for _, _, _, Ldict, _ in pre_rows))
            m = -M
        else:
            M = m = 0

        #Now pre_rows is filled, so we just need to create the plots:
        for gl, comppos, sslbls, Ldict, basisLbls in pre_rows:
            row_data = [gl, str(comppos), str(sslbls)]
            row_formatters = [None, None, None]

            for disp in display:
                if disp == "H":
                    hamCoeffs, xlabels, ylabels = get_plot_info(Ldict, basisLbls, "hamiltonian")
                    if display_as == "boxes":
                        #m,M = getMinMax(coeffsM,_np.max(_np.abs(hamCoeffs)))
                        hamCoeffs_fig = _wp.MatrixPlot(
                            self.ws, hamCoeffs, m, M, xlabels, ylabels,
                            boxLabels=True, prec="compacthp")  # May need to add EB code and/or title to MatrixPlot in FUTURE
                        row_data.append(hamCoeffs_fig)  # HERE
                        row_formatters.append('Figure')
                    else:
                        row_data.append(hamCoeffs)
                        row_formatters.append('Brackets')

                if disp == "S":
                    stoCoeffs, xlabels, ylabels = get_plot_info(Ldict, basisLbls, "stochastic")
                    if display_as == "boxes":
                        #m,M = getMinMax(coeffsM,_np.max(_np.abs(stoCoeffs)))
                        stoCoeffs_fig = _wp.MatrixPlot(
                            self.ws, stoCoeffs, m, M, xlabels, ylabels,
                            boxLabels=True, prec="compacthp")  # May need to add EB code and/or title to MatrixPlot in FUTURE
                        row_data.append(stoCoeffs_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(stoCoeffs)
                        row_formatters.append('Brackets')

                if disp == "A":
                    affCoeffs, xlabels, ylabels = get_plot_info(Ldict, basisLbls, "affine")
                    if display_as == "boxes":
                        #m,M = getMinMax(coeffsM,_np.max(_np.abs(effCoeffs)))
                        affCoeffs_fig = _wp.MatrixPlot(
                            self.ws, affCoeffs, m, M, xlabels, ylabels,
                            boxLabels=True, prec="compacthp")  # May need to add EB code and/or title to MatrixPlot in FUTURE
                        row_data.append(affCoeffs_fig)
                        row_formatters.append('Figure')
                    else:
                        row_data.append(affCoeffs)
                        row_formatters.append('Brackets')

            table.addrow(row_data, row_formatters)

        table.finish()
        return table


class old_RotationAxisVsTargetTable(WorkspaceTable):
    """ Old 1-qubit-only gate rotation axis table """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None):
        """
        Create a table comparing the rotation axes of the single-qubit gates in
        `model` with those in `targetModel`.  Differences are shown as
        angles between the rotation axes of corresponding gates.

        Parameters
        ----------
        model, targetModel : Model
            The models to compare.  Must be single-qubit.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(old_RotationAxisVsTargetTable, self).__init__(
            ws, self._create, model, targetModel, confidenceRegionInfo)

    def _create(self, model, targetModel, confidenceRegionInfo):

        opLabels = model.get_primitive_op_labels()  # operation labels

        colHeadings = ('Gate', "Angle between|rotation axes")
        formatters = (None, 'Conversion')

        anglesList = [_ev(_reportables.Model_model_angles_btwn_axes(
            model, targetModel, gl), confidenceRegionInfo) for gl in opLabels]

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        formatters = [None] + ['Pi']

        for gl, angle in zip(opLabels, anglesList):
            rowData = [gl] + [angle]
            table.addrow(rowData, formatters)

        table.finish()
        return table


class GateDecompTable(WorkspaceTable):
    """ Table of angle & axis decompositions of a Model's gates """

    def __init__(self, ws, model, targetModel, confidenceRegionInfo=None):
        """
        Create table for decomposing a model's gates.

        This table interprets the Hamiltonian projection of the log
        of the operation matrix to extract a rotation angle and axis.

        Parameters
        ----------
        model : Model
            The estimated model.

        targetModel : Model
            The target model, used to help disambiguate the matrix
            logarithms that are used in the decomposition.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(GateDecompTable, self).__init__(ws, self._create, model,
                                              targetModel, confidenceRegionInfo)

    def _create(self, model, targetModel, confidenceRegionInfo):
        opLabels = model.get_primitive_op_labels()  # operation labels

        colHeadings = ('Gate', 'Ham. Evals.', 'Rotn. angle', 'Rotn. axis', 'Log Error') \
            + tuple(["Axis angle w/%s" % str(gl) for gl in opLabels])
        tooltips = ('Gate', 'Hamiltonian Eigenvalues', 'Rotation angle', 'Rotation axis',
                    'Taking the log of a gate may be performed approximately.  This is '
                    + 'error in that estimate, i.e. norm(G - exp(approxLogG)).') + \
            tuple(["Angle between the rotation axis of %s and the gate of the current row"
                   % str(gl) for gl in opLabels])
        formatters = [None] * len(colHeadings)

        table = _ReportTable(colHeadings, formatters,
                             colHeadingLabels=tooltips, confidenceRegionInfo=confidenceRegionInfo)
        formatters = (None, 'Pi', 'Pi', 'Figure', 'Normal') + ('Pi',) * len(opLabels)

        decomp = _ev(_reportables.General_decomposition(
            model, targetModel), confidenceRegionInfo)

        for gl in opLabels:
            gl = str(gl)  # Label -> str for decomp-dict keys
            axis, axisEB = decomp[gl + ' axis'].get_value_and_err_bar()
            axisFig = _wp.ProjectionsBoxPlot(self.ws, axis, model.basis, -1.0, 1.0,
                                             boxLabels=True, EBmatrix=axisEB)
            decomp[gl + ' hamiltonian eigenvalues'].scale(1.0 / _np.pi)  # scale evals to units of pi
            rowData = [gl, decomp[gl + ' hamiltonian eigenvalues'],
                       decomp[gl + ' angle'], axisFig,
                       decomp[gl + ' log inexactness']]

            for gl_other in opLabels:
                gl_other = str(gl_other)
                rotnAngle = decomp[gl + ' angle'].get_value()
                rotnAngle_other = decomp[gl_other + ' angle'].get_value()

                if gl_other == gl:
                    rowData.append("")
                elif abs(rotnAngle) < 1e-4 or abs(rotnAngle_other) < 1e-4:
                    rowData.append("--")
                else:
                    rowData.append(decomp[gl + ',' + gl_other + ' axis angle'])

            table.addrow(rowData, formatters)

        table.finish()
        return table


class old_GateDecompTable(WorkspaceTable):
    """ 1-qubit-only table of gate decompositions """

    def __init__(self, ws, model, confidenceRegionInfo=None):
        """
        Create table for decomposing a single-qubit model's gates.

        This table interprets the eigenvectors and eigenvalues of the
        gates to extract a rotation angle, axis, and various decay
        coefficients.

        Parameters
        ----------
        model : Model
            A single-qubit `Model`.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(old_GateDecompTable, self).__init__(ws, self._create, model, confidenceRegionInfo)

    def _create(self, model, confidenceRegionInfo):

        opLabels = model.get_primitive_op_labels()  # operation labels
        colHeadings = ('Gate', 'Eigenvalues', 'Fixed pt', 'Rotn. axis', 'Diag. decay', 'Off-diag. decay')
        formatters = [None] * 6

        assert(isinstance(model, _objs.ExplicitOpModel)), "old_GateDecompTable only works with explicit models"
        decomps = [_reportables.decomposition(model.operations[gl]) for gl in opLabels]
        decompNames = ('fixed point',
                       'axis of rotation',
                       'decay of diagonal rotation terms',
                       'decay of off diagonal rotation terms')

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        formatters = (None, 'Vec', 'Normal', 'Normal', 'Normal', 'Normal')

        for decomp, gl in zip(decomps, opLabels):
            evals = _ev(_reportables.Gate_eigenvalues(model, gl))
            decomp, decompEB = decomp.get_value_and_err_bar()  # OLD

            rowData = [gl, evals] + [decomp.get(x, 'X') for x in decompNames[0:2]] + \
                [(decomp.get(x, 'X'), decompEB) for x in decompNames[2:4]]

            table.addrow(rowData, formatters)

        table.finish()
        return table


class old_RotationAxisTable(WorkspaceTable):
    """ 1-qubit-only table of gate rotation angles and axes """

    def __init__(self, ws, model, confidenceRegionInfo=None, showAxisAngleErrBars=True):
        """
        Create a table of the angle between a gate rotation axes for
        gates belonging to a single-qubit model.

        Parameters
        ----------
        model : Model
            A single-qubit `Model`.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        showAxisAngleErrBars : bool, optional
            Whether or not table should include error bars on the angles
            between rotation axes (doing so makes the table take up more
            space).

        Returns
        -------
        ReportTable
        """
        super(old_RotationAxisTable, self).__init__(ws, self._create, model, confidenceRegionInfo, showAxisAngleErrBars)

    def _create(self, model, confidenceRegionInfo, showAxisAngleErrBars):

        opLabels = model.get_primitive_op_labels()

        assert(isinstance(model, _objs.ExplicitOpModel)), "old_RotationAxisTable only works with explicit models"
        decomps = [_reportables.decomposition(model.operations[gl]) for gl in opLabels]

        colHeadings = ("Gate", "Angle") + tuple(["RAAW(%s)" % gl for gl in opLabels])
        nCols = len(colHeadings)
        formatters = [None] * nCols

        table = "tabular"
        latex_head = "\\begin{%s}[l]{%s}\n\hline\n" % (table, "|c" * nCols + "|")
        latex_head += "\\multirow{2}{*}{Gate} & \\multirow{2}{*}{Angle} & " + \
                      "\\multicolumn{%d}{c|}{Angle between Rotation Axes} \\\\ \cline{3-%d}\n" % (len(opLabels), nCols)
        latex_head += " & & %s \\\\ \hline\n" % (" & ".join(map(str, opLabels)))

        table = _ReportTable(colHeadings, formatters,
                             customHeader={'latex': latex_head}, confidenceRegionInfo=confidenceRegionInfo)

        formatters = [None, 'Pi'] + ['Pi'] * len(opLabels)

        rotnAxisAnglesQty = _ev(_reportables.Angles_btwn_rotn_axes(model),
                                confidenceRegionInfo)
        rotnAxisAngles, rotnAxisAnglesEB = rotnAxisAnglesQty.get_value_and_err_bar()

        for i, gl in enumerate(opLabels):
            decomp, decompEB = decomps[i].get_value_and_err_bar()  # OLD
            rotnAngle = decomp.get('pi rotations', 'X')

            angles_btwn_rotn_axes = []
            for j, gl_other in enumerate(opLabels):
                decomp_other, _ = decomps[j].get_value_and_err_bar()  # OLD
                rotnAngle_other = decomp_other.get('pi rotations', 'X')

                if gl_other == gl:
                    angles_btwn_rotn_axes.append(("", None))
                elif str(rotnAngle) == 'X' or abs(rotnAngle) < 1e-4 or \
                        str(rotnAngle_other) == 'X' or abs(rotnAngle_other) < 1e-4:
                    angles_btwn_rotn_axes.append(("--", None))
                elif not _np.isnan(rotnAxisAngles[i, j]):
                    if showAxisAngleErrBars and rotnAxisAnglesEB is not None:
                        angles_btwn_rotn_axes.append((rotnAxisAngles[i, j], rotnAxisAnglesEB[i, j]))
                    else:
                        angles_btwn_rotn_axes.append((rotnAxisAngles[i, j], None))
                else:
                    angles_btwn_rotn_axes.append(("X", None))

            if confidenceRegionInfo is None or decompEB is None:  # decompEB is None when gate decomp failed
                rowData = [gl, (rotnAngle, None)] + angles_btwn_rotn_axes
            else:
                rowData = [gl, (rotnAngle, decompEB.get('pi rotations', 'X'))] + angles_btwn_rotn_axes
            table.addrow(rowData, formatters)

        table.finish()
        return table


class GateEigenvalueTable(WorkspaceTable):
    """ Table displaying, in a variety of ways, the eigenvalues of a
        Model's gates """

    def __init__(self, ws, model, targetModel=None,
                 confidenceRegionInfo=None,
                 display=('evals', 'rel', 'log-evals', 'log-rel', 'polar', 'relpolar'),
                 virtual_ops=None):
        """
        Create table which lists and displays (using a polar plot)
        the eigenvalues of a model's gates.

        Parameters
        ----------
        model : Model
            The Model

        targetModel : Model, optional
            The target model.  If given, the target's eigenvalue will
            be plotted alongside `model`'s gate eigenvalue, the
            "relative eigenvalues".

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        display : tuple
            A tuple of one or more of the allowed options (see below) which
            specify which columns are displayed in the table.  If
            `targetModel` is None, then `"target"`, `"rel"`, `"log-rel"`
            `"relpolar"`, `"gidm"`, and `"giinf"` will be silently ignored.

            - "evals" : the gate eigenvalues
            - "target" : the target gate eigenvalues
            - "rel" : the relative-gate eigenvalues
            - "log-evals" : the (complex) logarithm of the eigenvalues
            - "log-rel" : the (complex) logarithm of the relative eigenvalues
            - "polar": a polar plot of the gate eigenvalues
            - "relpolar" : a polar plot of the relative-gate eigenvalues
            - "absdiff-evals" : absolute difference w/target eigenvalues
            - "infdiff-evals" : 1-Re(z0.C*z) difference w/target eigenvalues
            - "absdiff-log-evals" : Re & Im differences in eigenvalue logarithms
            - "evdm" : the gauge-invariant "eigenvalue diamond norm" metric
            - "evinf" : the gauge-invariant "eigenvalue infidelity" metric

        virtual_ops : list, optional
            If not None, a list of `Circuit` objects specifying additional "gates"
            (i.e. processes) to compute eigenvalues of.  Length-1 operation sequences are
            automatically discarded so they are not displayed twice.

        Returns
        -------
        ReportTable
        """
        super(GateEigenvalueTable, self).__init__(ws, self._create, model,
                                                  targetModel,
                                                  confidenceRegionInfo, display,
                                                  virtual_ops)

    def _create(self, model, targetModel,
                confidenceRegionInfo, display,
                virtual_ops):

        opLabels = model.get_primitive_op_labels()  # operation labels
        assert(isinstance(model, _objs.ExplicitOpModel)), "GateEigenvalueTable only works with explicit models"

        colHeadings = ['Gate'] if (virtual_ops is None) else ['Gate or Germ']
        formatters = [None]
        for disp in display:
            if disp == "evals":
                colHeadings.append('Eigenvalues ($E$)')
                formatters.append(None)

            elif disp == "target":
                colHeadings.append('Target Evals. ($T$)')
                formatters.append(None)

            elif disp == "rel":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('Rel. Evals ($R$)')
                    formatters.append(None)

            elif disp == "log-evals":
                colHeadings.append('Re log(E)')
                colHeadings.append('Im log(E)')
                formatters.append('MathText')
                formatters.append('MathText')

            elif disp == "log-rel":
                colHeadings.append('Re log(R)')
                colHeadings.append('Im log(R)')
                formatters.append('MathText')
                formatters.append('MathText')

            elif disp == "polar":
                colHeadings.append('Eigenvalues')  # Note: make sure header is *distinct* for pandas conversion
                formatters.append(None)

            elif disp == "relpolar":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('Rel. Evals')  # Note: make sure header is *distinct* for pandas conversion
                    formatters.append(None)

            elif disp == "absdiff-evals":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('|E - T|')
                    formatters.append('MathText')

            elif disp == "infdiff-evals":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('1.0 - Re(\\bar{T}*E)')
                    formatters.append('MathText')

            elif disp == "absdiff-log-evals":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('|Re(log E) - Re(log T)|')
                    colHeadings.append('|Im(log E) - Im(log T)|')
                    formatters.append('MathText')
                    formatters.append('MathText')

            elif disp == "evdm":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('Eigenvalue Diamond norm')
                    formatters.append('Conversion')

            elif disp == "evinf":
                if(targetModel is not None):  # silently ignore
                    colHeadings.append('Eigenvalue infidelity')
                    formatters.append(None)
            else:
                raise ValueError("Invalid display element: %s" % disp)

        table = _ReportTable(colHeadings, formatters, confidenceRegionInfo=confidenceRegionInfo)

        if virtual_ops is None:
            iterOver = opLabels
        else:
            iterOver = opLabels + tuple((v for v in virtual_ops if len(v) > 1))

        for gl in iterOver:
            #Note: gl may be a operation label (a string) or a Circuit
            row_data = [str(gl)]
            row_formatters = [None]

            #import time as _time #DEBUG
            #tStart = _time.time() #DEBUG
            fn = _reportables.Gate_eigenvalues if \
                isinstance(gl, _objs.Label) or _tools.isstr(gl) else \
                _reportables.Circuit_eigenvalues
            evals = _ev(fn(model, gl), confidenceRegionInfo)
            #tm = _time.time() - tStart #DEBUG
            #if tm > 0.01: print("DB: Gate eigenvalues in %gs" % tm) #DEBUG

            evals = evals.reshape(evals.size, 1)
            #OLD: format to 2-columns - but polar plots are big, so just stick to 1col now
            #try: evals = evals.reshape(evals.size//2, 2) #assumes len(evals) is even!
            #except: evals = evals.reshape(evals.size, 1)

            if targetModel is not None:
                #TODO: move this to a reportable qty to get error bars?

                if isinstance(gl, _objs.Label) or _tools.isstr(gl):
                    target_evals = _np.linalg.eigvals(targetModel.operations[gl].todense())  # no error bars
                else:
                    target_evals = _np.linalg.eigvals(targetModel.product(gl))  # no error bars

                if any([(x in display) for x in ('rel', 'log-rel', 'relpolar')]):
                    if isinstance(gl, _objs.Label) or _tools.isstr(gl):
                        rel_evals = _ev(_reportables.Rel_gate_eigenvalues(model, targetModel, gl), confidenceRegionInfo)
                    else:
                        rel_evals = _ev(_reportables.Rel_circuit_eigenvalues(model, targetModel, gl), confidenceRegionInfo)

                # permute target eigenvalues according to min-weight matching
                _, pairs = _tools.minweight_match(evals.get_value(), target_evals, lambda x, y: abs(x - y))
                matched_target_evals = target_evals.copy()
                for i, j in pairs:
                    matched_target_evals[i] = target_evals[j]
                target_evals = matched_target_evals
                target_evals = target_evals.reshape(evals.value.shape)
                # b/c evals have shape (x,1) and targets (x,),
                # which causes problems when we try to subtract them

            for disp in display:
                if disp == "evals":
                    row_data.append(evals)
                    row_formatters.append('Normal')

                elif disp == "target" and targetModel is not None:
                    row_data.append(target_evals)
                    row_formatters.append('Normal')

                elif disp == "rel" and targetModel is not None:
                    row_data.append(rel_evals)
                    row_formatters.append('Normal')

                elif disp == "log-evals":
                    logevals = evals.log()
                    row_data.append(logevals.real())
                    row_data.append(logevals.imag() / _np.pi)
                    row_formatters.append('Normal')
                    row_formatters.append('Pi')

                elif disp == "log-rel":
                    log_relevals = rel_evals.log()
                    row_data.append(log_relevals.real())
                    row_data.append(log_relevals.imag() / _np.pi)
                    row_formatters.append('Vec')
                    row_formatters.append('Pi')

                elif disp == "absdiff-evals":
                    absdiff_evals = evals.absdiff(target_evals)
                    row_data.append(absdiff_evals)
                    row_formatters.append('Vec')

                elif disp == "infdiff-evals":
                    infdiff_evals = evals.infidelity_diff(target_evals)
                    row_data.append(infdiff_evals)
                    row_formatters.append('Vec')

                elif disp == "absdiff-log-evals":
                    log_evals = evals.log()
                    re_diff, im_diff = log_evals.absdiff(_np.log(target_evals.astype(complex)), separate_re_im=True)
                    row_data.append(re_diff)
                    row_data.append((im_diff / _np.pi).mod(2.0))
                    row_formatters.append('Vec')
                    row_formatters.append('Pi')

                elif disp == "evdm":
                    if targetModel is not None:
                        fn = _reportables.Eigenvalue_diamondnorm if \
                            isinstance(gl, _objs.Label) or _tools.isstr(gl) else \
                            _reportables.Circuit_eigenvalue_diamondnorm
                        gidm = _ev(fn(model, targetModel, gl), confidenceRegionInfo)
                        row_data.append(gidm)
                        row_formatters.append('Normal')

                elif disp == "evinf":
                    if targetModel is not None:
                        fn = _reportables.Eigenvalue_entanglement_infidelity if \
                            isinstance(gl, _objs.Label) or _tools.isstr(gl) else \
                            _reportables.Circuit_eigenvalue_entanglement_infidelity
                        giinf = _ev(fn(model, targetModel, gl), confidenceRegionInfo)
                        row_data.append(giinf)
                        row_formatters.append('Normal')

                elif disp == "polar":
                    evals_val = evals.get_value()
                    if targetModel is None:
                        fig = _wp.PolarEigenvaluePlot(
                            self.ws, [evals_val], ["blue"], centerText=str(gl))
                    else:
                        fig = _wp.PolarEigenvaluePlot(
                            self.ws, [target_evals, evals_val],
                            ["black", "blue"], ["target", "gate"], centerText=str(gl))
                    row_data.append(fig)
                    row_formatters.append('Figure')

                elif disp == "relpolar" and targetModel is not None:
                    rel_evals_val = rel_evals.get_value()
                    fig = _wp.PolarEigenvaluePlot(
                        self.ws, [rel_evals_val], ["red"], ["rel"], centerText=str(gl))
                    row_data.append(fig)
                    row_formatters.append('Figure')
            table.addrow(row_data, row_formatters)
        table.finish()
        return table


class DataSetOverviewTable(WorkspaceTable):
    """ Table giving a summary of the properties of `dataset`. """

    def __init__(self, ws, dataset, maxLengthList=None):
        """
        Create a table that gives a summary of the properties of `dataset`.

        Parameters
        ----------
        dataset : DataSet
            The DataSet

        maxLengthList : list of ints, optional
            A list of the maximum lengths used, if available.

        Returns
        -------
        ReportTable
        """
        super(DataSetOverviewTable, self).__init__(ws, self._create, dataset, maxLengthList)

    def _create(self, dataset, maxLengthList):

        colHeadings = ('Quantity', 'Value')
        formatters = (None, None)

        table = _ReportTable(colHeadings, formatters)

        minN = round(min([row.total for row in dataset.values()]))
        maxN = round(max([row.total for row in dataset.values()]))
        cntStr = "[%d,%d]" % (minN, maxN) if (minN != maxN) else "%d" % round(minN)

        table.addrow(("Number of strings", str(len(dataset))), (None, None))
        table.addrow(("Gate labels", ", ".join([str(gl) for gl in dataset.get_gate_labels()])), (None, None))
        table.addrow(("Outcome labels", ", ".join(map(str, dataset.get_outcome_labels()))), (None, None))
        table.addrow(("Counts per string", cntStr), (None, None))

        if maxLengthList is not None:
            table.addrow(("Max. Lengths", ", ".join(map(str, maxLengthList))), (None, None))
        if hasattr(dataset, 'comment') and dataset.comment is not None:
            commentLines = dataset.comment.split('\n')
            for i, commentLine in enumerate(commentLines, start=1):
                table.addrow(("User comment %d" % i, commentLine), (None, 'Verbatim'))

        table.finish()
        return table


class FitComparisonTable(WorkspaceTable):
    """ Table showing how the goodness-of-fit evolved over GST iterations """

    def __init__(self, ws, Xs, gssByX, modelByX, dataset, objective="logl",
                 Xlabel='L', NpByX=None, comm=None, wildcard=None):
        """
        Create a table showing how the chi^2 or log-likelihood changed with
        successive GST iterations.

        Parameters
        ----------
        Xs : list of integers
            List of X-values. Typically these are the maximum lengths or
            exponents used to index the different iterations of GST.

        gssByX : list of LsGermsStructure
            Specifies the set (& structure) of the operation sequences used at each X.

        modelByX : list of Models
            `Model`s corresponding to each X value.

        dataset : DataSet
            The data set to compare each model against.

        objective : {"logl", "chi2"}, optional
            Whether to use log-likelihood or chi^2 values.

        Xlabel : str, optional
            A label for the 'X' variable which indexes the different models.
            This string will be the header of the first table column.

        NpByX : list of ints, optional
            A list of parameter counts to use for each X.  If None, then
            the number of non-gauge parameters for each model is used.

        comm : mpi4py.MPI.Comm, optional
            When not None, an MPI communicator for distributing the computation
            across multiple processors.

        wildcard : TODO: docstring


        Returns
        -------
        ReportTable
        """
        super(FitComparisonTable, self).__init__(ws, self._create, Xs, gssByX, modelByX,
                                                 dataset, objective, Xlabel, NpByX, comm, wildcard)

    def _create(self, Xs, gssByX, modelByX, dataset, objective, Xlabel, NpByX, comm, wildcard):

        if objective == "chi2":
            colHeadings = {
                'latex': (Xlabel, '$\\chi^2$', '$k$', '$\\chi^2-k$', '$\sqrt{2k}$',
                          '$N_\\sigma$', '$N_s$', '$N_p$', 'Rating'),
                'html': (Xlabel, '&chi;<sup>2</sup>', 'k', '&chi;<sup>2</sup>-k',
                         '&radic;<span style="text-decoration:overline;">2k</span>',
                         'N<sub>sigma</sub>', 'N<sub>s</sub>', 'N<sub>p</sub>', 'Rating'),
                'python': (Xlabel, 'chi^2', 'k', 'chi^2-k', 'sqrt{2k}', 'N_{sigma}', 'N_s', 'N_p', 'Rating')
            }

        elif objective == "logl":
            colHeadings = {
                'latex': (Xlabel, '$2\Delta\\log(\\mathcal{L})$', '$k$', '$2\Delta\\log(\\mathcal{L})-k$',
                          '$\sqrt{2k}$', '$N_\\sigma$', '$N_s$', '$N_p$', 'Rating'),
                'html': (Xlabel, '2&Delta;(log L)', 'k', '2&Delta;(log L)-k',
                         '&radic;<span style="text-decoration:overline;">2k</span>',
                         'N<sub>sigma</sub>', 'N<sub>s</sub>', 'N<sub>p</sub>', 'Rating'),
                'python': (Xlabel, '2*Delta(log L)', 'k', '2*Delta(log L)-k', 'sqrt{2k}',
                           'N_{sigma}', 'N_s', 'N_p', 'Rating')
            }
        else:
            raise ValueError("Invalid `objective` argument: %s" % objective)

        if NpByX is None:
            try:
                NpByX = [mdl.num_nongauge_params() for mdl in modelByX]
            except _np.linalg.LinAlgError:
                _warnings.warn(("LinAlgError when trying to compute the number"
                                " of non-gauge parameters.  Using total"
                                " parameters instead."))
                NpByX = [mdl.num_params() for mdl in modelByX]
            except (NotImplementedError, AttributeError):
                _warnings.warn(("FitComparisonTable could not obtain number of"
                                "*non-gauge* parameters - using total params instead"))
                NpByX = [mdl.num_params() for mdl in modelByX]

        tooltips = ('', 'Difference in logL', 'number of degrees of freedom',
                    'difference between observed logl and expected mean',
                    'std deviation', 'number of std deviation', 'dataset dof',
                    'number of model parameters', '1-5 star rating (like Netflix)')
        table = _ReportTable(colHeadings, None, colHeadingLabels=tooltips)

        for X, mdl, gss, Np in zip(Xs, modelByX, gssByX, NpByX):
            Nsig, rating, fitQty, k, Ns, Np = self._ccompute(
                _ph.ratedNsigma, dataset, mdl, gss,
                objective, Np, wildcard, returnAll=True,
                comm=comm, smartc=self.ws.smartCache)
            table.addrow((str(X), fitQty, k, fitQty - k, _np.sqrt(2 * k), Nsig, Ns, Np, "<STAR>" * rating),
                         (None, 'Normal', 'Normal', 'Normal', 'Normal', 'Rounded', 'Normal', 'Normal', 'Conversion'))

        table.finish()
        return table


class CircuitTable(WorkspaceTable):
    """ Table which simply displays list(s) of operation sequences """

    def __init__(self, ws, gsLists, titles, nCols=1, commonTitle=None):
        """
        Creates a table of enumerating one or more sets of operation sequences.

        Parameters
        ----------
        gsLists : Circuit list or list of Circuit lists
            List(s) of operation sequences to put in table.

        titles : string or list of strings
            The title(s) for the different string lists.  These are displayed in
            the relevant table columns containing the strings.

        nCols : int, optional
            The number of *data* columns, i.e. those containing
            operation sequences, for each string list.

        commonTitle : string, optional
            A single title string to place in a cell spanning across
            all the other column headers.

        Returns
        -------
        ReportTable
        """
        super(CircuitTable, self).__init__(ws, self._create, gsLists, titles,
                                           nCols, commonTitle)

    def _create(self, gsLists, titles, nCols, commonTitle):

        if len(gsLists) == 0:
            gsLists = [[]]
        elif isinstance(gsLists[0], _objs.Circuit) or \
                (isinstance(gsLists[0], tuple) and _tools.isstr(gsLists[0][0])):
            gsLists = [gsLists]

        if _tools.isstr(titles): titles = [titles] * len(gsLists)

        colHeadings = (('#',) + tuple(titles)) * nCols
        formatters = (('Conversion',) + ('Normal',) * len(titles)) * nCols

        if commonTitle is None:
            table = _ReportTable(colHeadings, formatters)
        else:
            table = "tabular"
            colHeadings = ('\\#',) + tuple(titles)
            latex_head = "\\begin{%s}[l]{%s}\n\hline\n" % (table, "|c" * len(colHeadings) + "|")
            latex_head += " & \multicolumn{%d}{c|}{%s} \\\\ \hline\n" % (len(colHeadings) - 1, commonTitle)
            latex_head += "%s \\\\ \hline\n" % (" & ".join(colHeadings))

            colHeadings = ('#',) + tuple(titles)
            html_head = '<table class="%(tableclass)s" id="%(tableid)s" ><thead>'
            html_head += '<tr><th></th><th colspan="%d">%s</th></tr>\n' % (len(colHeadings) - 1, commonTitle)
            html_head += "<tr><th> %s </th></tr>" % (" </th><th> ".join(colHeadings))
            html_head += "</thead><tbody>"
            table = _ReportTable(colHeadings, formatters,
                                 customHeader={'latex': latex_head,
                                               'html': html_head})

        formatters = (('Normal',) + ('Circuit',) * len(gsLists)) * nCols

        maxListLength = max(list(map(len, gsLists)))
        nRows = (maxListLength + (nCols - 1)) // nCols  # ceiling

        #for i in range( max([len(gsl) for gsl in gsLists]) ):
        for i in range(nRows):
            rowData = []
            for k in range(nCols):
                l = i + nRows * k  # index of circuit
                rowData.append(l + 1)
                for gsList in gsLists:
                    if l < len(gsList):
                        rowData.append(gsList[l])
                    else:
                        rowData.append(None)  # empty string
            table.addrow(rowData, formatters)

        table.finish()
        return table


class GatesSingleMetricTable(WorkspaceTable):
    """ Table that compares the gates of many Models which share the same gate
        labels to target Models using a single metric, so that the Model
        titles can be used as the row and column headers."""

    def __init__(self, ws, metric, models, targetModels, titles,
                 rowtitles=None, tableTitle=None, opLabel=None,
                 confidenceRegionInfo=None):
        """
        Create a table comparing the gates of various models (`models`) to
        those of `targetModels` using the metric named by `metric`.

        If `models` and `targetModels` are 1D lists, then `rowtitles` and
        `opLabel` should be left as their default values so that the
        operation labels are used as row headers.

        If `models` and `targetModels` are 2D (nested) lists, then
        `rowtitles` should specify the row-titles corresponding to the outer list
        elements and `opLabel` should specify a single operation label that names
        the gate being compared throughout the entire table.

        Parameters
        ----------
        metric : str
            The abbreviation for the metric to use.  Allowed values are:

            - "inf" :     entanglement infidelity
            - "agi" :     average gate infidelity
            - "trace" :   1/2 trace distance
            - "diamond" : 1/2 diamond norm distance
            - "nuinf" :   non-unitary entanglement infidelity
            - "nuagi" :   non-unitary entanglement infidelity
            - "evinf" :     eigenvalue entanglement infidelity
            - "evagi" :     eigenvalue average gate infidelity
            - "evnuinf" :   eigenvalue non-unitary entanglement infidelity
            - "evnuagi" :   eigenvalue non-unitary entanglement infidelity
            - "evdiamond" : eigenvalue 1/2 diamond norm distance
            - "evnudiamond" : eigenvalue non-unitary 1/2 diamond norm distance
            - "frob" :    frobenius distance

        models : list
            A list or nested list-of-lists of models to compare with
            corresponding elements of `targetModels`.

        targetModels : list
            A list or nested list-of-lists of models to compare with
            corresponding elements of `models`.

        titles : list of strs
            A list of column titles used to describe elements of the
            innermost list(s) in `models`.

        rowtitles : list of strs, optional
            A list of row titles used to describe elements of the
            outer list in `models`.  If None, then the operation labels
            are used.

        tableTitle : str, optional
            If not None, text to place in a top header cell which spans all the
            columns of the table.

        opLabel : str, optional
            If not None, the single operation label to use for all comparisons
            computed in this table.  This should be set when (and only when)
            `models` and `targetModels` are 2D (nested) lists.

        confidenceRegionInfo : ConfidenceRegion, optional
            If not None, specifies a confidence-region
            used to display error intervals.

        Returns
        -------
        ReportTable
        """
        super(GatesSingleMetricTable, self).__init__(
            ws, self._create, metric, models, targetModels, titles,
            rowtitles, tableTitle, opLabel, confidenceRegionInfo)

    def _create(self, metric, models, targetModels, titles,
                rowtitles, tableTitle, opLabel, confidenceRegionInfo):

        if rowtitles is None:
            assert(opLabel is None), "`opLabel` must be None when `rowtitles` is"
            colHeadings = ("Gate",) + tuple(titles)
        else:
            colHeadings = ("",) + tuple(titles)

        nCols = len(colHeadings)
        formatters = [None] * nCols  # [None] + ['ModelType']*(nCols-1)

        #latex_head =  "\\begin{tabular}[l]{%s}\n\hline\n" % ("|c" * nCols + "|")
        #latex_head += "\\multirow{2}{*}{Gate} & " + \
        #              "\\multicolumn{%d}{c|}{%s} \\\\ \cline{2-%d}\n" % (len(titles),niceNm,nCols)
        #latex_head += " & " + " & ".join([mknice(t) for t in titles]) + "\\\\ \hline\n"
        #
        #html_head = '<table class="%(tableclass)s" id="%(tableid)s" ><thead>'
        #html_head += '<tr><th rowspan="2"></th>' + \
        #             '<th colspan="%d">%s</th></tr>\n' % (len(titles),niceNm)
        #html_head += "<tr><th>" +  " </th><th> ".join([mknice(t) for t in titles]) + "</th></tr>\n"
        #html_head += "</thead><tbody>"

        if tableTitle:
            latex_head = "\\begin{tabular}[l]{%s}\n\hline\n" % ("|c" * nCols + "|")
            latex_head += "\\multicolumn{%d}{c|}{%s} \\\\ \cline{1-%d}\n" % (nCols, tableTitle, nCols)
            latex_head += " & ".join(colHeadings) + "\\\\ \hline\n"

            html_head = '<table class="%(tableclass)s" id="%(tableid)s" ><thead>'
            html_head += '<tr><th colspan="%d">%s</th></tr>\n' % (nCols, tableTitle)
            html_head += "<tr><th>" + " </th><th> ".join(colHeadings) + "</th></tr>\n"
            html_head += "</thead><tbody>"

            table = _ReportTable(colHeadings, formatters,
                                 customHeader={'latex': latex_head,
                                               'html': html_head})
        else:
            table = _ReportTable(colHeadings, formatters)

        row_formatters = [None] + ['Normal'] * len(titles)

        if rowtitles is None:
            assert(isinstance(targetModels[0], _objs.ExplicitOpModel)), "%s only works with explicit models" % str(type(self))
            for gl in targetModels[0].operations:  # use first target's operation labels
                row_data = [gl]
                for mdl, gsTarget in zip(models, targetModels):
                    if mdl is None or gsTarget is None:
                        qty = _objs.reportableqty.ReportableQty(_np.nan)
                    else:
                        qty = _reportables.evaluate_opfn_by_name(
                            metric, mdl, gsTarget, gl, confidenceRegionInfo)
                    row_data.append(qty)
                table.addrow(row_data, row_formatters)
        else:
            for rowtitle, gsList, tgsList in zip(rowtitles, models, targetModels):
                row_data = [rowtitle]
                for mdl, gsTarget in zip(gsList, tgsList):
                    if mdl is None or gsTarget is None:
                        qty = _objs.reportableqty.ReportableQty(_np.nan)
                    else:
                        qty = _reportables.evaluate_opfn_by_name(
                            metric, mdl, gsTarget, opLabel, confidenceRegionInfo)
                    row_data.append(qty)
                table.addrow(row_data, row_formatters)

        table.finish()
        return table


class StandardErrgenTable(WorkspaceTable):
    """ A table showing what the standard error generators' superoperator
        matrices look like."""

    def __init__(self, ws, model_dim, projection_type,
                 projection_basis):
        """
        Create a table of the "standard" gate error generators, such as those
        which correspond to Hamiltonian or Stochastic errors.  Each generator
        is shown as grid of colored boxes.

        Parameters
        ----------
        model_dim : int
            The dimension of the model, which equals the number of
            rows (or columns) in a operation matrix (e.g., 4 for a single qubit).

        projection_type : {"hamiltonian", "stochastic"}
            The type of error generator projectors to create a table for.
            If "hamiltonian", then use the Hamiltonian generators which take a
            density matrix rho -> -i*[ H, rho ] for basis matrix H.
            If "stochastic", then use the Stochastic error generators which take
            rho -> P*rho*P for basis matrix P (recall P is self adjoint).

        projection_basis : {'std', 'gm', 'pp', 'qt'}
          Which basis is used to construct the error generators.  Allowed
          values are Matrix-unit (std), Gell-Mann (gm), Pauli-product (pp)
          and Qutrit (qt).

        Returns
        -------
        ReportTable
        """
        super(StandardErrgenTable, self).__init__(
            ws, self._create, model_dim, projection_type,
            projection_basis)

    def _create(self, model_dim, projection_type,
                projection_basis):

        d2 = model_dim  # number of projections == dim of gate
        d = int(_np.sqrt(d2))  # dim of density matrix
        nQubits = _np.log2(d)

        #Get a list of the d2 generators (in corresspondence with the
        #  given basis matrices)
        lindbladMxs = _tools.std_error_generators(d2, projection_type,
                                                  projection_basis)  # in std basis

        if not _np.isclose(round(nQubits), nQubits):
            #Non-integral # of qubits, so just show as a single row
            yd, xd = 1, d
            xlabel = ""
            ylabel = ""
        elif nQubits == 1:
            yd, xd = 1, 2  # y and x pauli-prod *basis* dimensions
            xlabel = "Q1"
            ylabel = ""
        elif nQubits == 2:
            yd, xd = 2, 2
            xlabel = "Q2"
            ylabel = "Q1"
        else:
            assert(d % 2 == 0)
            yd, xd = 2, d // 2
            xlabel = "Q*"
            ylabel = "Q1"

        topright = "%s \\ %s" % (ylabel, xlabel) if (len(ylabel) > 0) else ""
        colHeadings = [topright] + \
            [("%s" % x) if len(x) else ""
             for x in _tools.basis_element_labels(projection_basis, xd**2)]
        rowLabels = [("%s" % x) if len(x) else ""
                     for x in _tools.basis_element_labels(projection_basis, yd**2)]

        xLabels = _tools.basis_element_labels(projection_basis, xd**2)
        yLabels = _tools.basis_element_labels(projection_basis, yd**2)

        table = _ReportTable(colHeadings, ["Conversion"] + [None] * (len(colHeadings) - 1))

        iCur = 0
        for i, ylabel in enumerate(yLabels):
            rowData = [rowLabels[i]]
            rowFormatters = [None]

            for xlabel in xLabels:
                projector = lindbladMxs[iCur]
                iCur += 1
                projector = _tools.change_basis(projector, "std", projection_basis)
                m, M = -_np.max(_np.abs(projector)), _np.max(_np.abs(projector))
                fig = _wp.GateMatrixPlot(self.ws, projector, m, M,
                                         projection_basis, d)
                rowData.append(fig)
                rowFormatters.append('Figure')

            table.addrow(rowData, rowFormatters)

        table.finish()
        return table


class GaugeOptParamsTable(WorkspaceTable):
    """ Table of gauge optimization parameters """

    def __init__(self, ws, gaugeOptArgs):
        """
        Create a table displaying a list of gauge
        optimzation parameters.

        Parameters
        ----------
        gaugeOptArgs : dict or list
            A dictionary or list of dictionaries specifying values for
            zero or more of the *arguments* of pyGSTi's
            :func:`gaugeopt_to_target` function.

        Returns
        -------
        ReportTable
        """
        super(GaugeOptParamsTable, self).__init__(ws, self._create, gaugeOptArgs)

    def _create(self, gaugeOptArgs):

        colHeadings = ('G-Opt Param', 'Value')
        formatters = ('Bold', 'Bold')

        if gaugeOptArgs == False:  # signals *no* gauge optimization
            goargs_list = [{'Method': "No gauge optimization was performed"}]
        else:
            goargs_list = [gaugeOptArgs] if hasattr(gaugeOptArgs, 'keys') \
                else gaugeOptArgs

        table = _ReportTable(colHeadings, formatters)

        for i, goargs in enumerate(goargs_list):
            pre = ("%d: " % i) if len(goargs_list) > 1 else ""
            if 'method' in goargs:
                table.addrow(("%sMethod" % pre, str(goargs['method'])), (None, None))
            if 'cptp_penalty_factor' in goargs and goargs['cptp_penalty_factor'] != 0:
                table.addrow(("%sCP penalty factor" % pre, str(goargs['cptp_penalty_factor'])), (None, None))
            if 'spam_penalty_factor' in goargs and goargs['spam_penalty_factor'] != 0:
                table.addrow(("%sSPAM penalty factor" % pre, str(goargs['spam_penalty_factor'])), (None, None))
            if 'gatesMetric' in goargs:
                table.addrow(("%sMetric for gate-to-target" % pre, str(goargs['gatesMetric'])), (None, None))
            if 'spamMetric' in goargs:
                table.addrow(("%sMetric for SPAM-to-target" % pre, str(goargs['spamMetric'])), (None, None))
            if 'itemWeights' in goargs:
                if goargs['itemWeights']:
                    table.addrow(("%sItem weights" % pre, ", ".join([("%s=%.2g" % (k, v))
                                                                     for k, v in goargs['itemWeights'].items()])), (None, None))
            if 'gauge_group' in goargs:
                table.addrow(("%sGauge group" % pre, goargs['gauge_group'].name), (None, None))

        table.finish()
        return table


class MetadataTable(WorkspaceTable):
    """ Table of raw parameters, often taken directly from a `Results` object"""

    def __init__(self, ws, model, params):
        """
        Create a table of parameters and options from a `Results` object.

        Parameters
        ----------
        model : Model
            The model (usually the final estimate of a GST computation) to
            show information for (e.g. the types of its gates).

        params: dict
            A parameter dictionary to display

        Returns
        -------
        ReportTable
        """
        super(MetadataTable, self).__init__(ws, self._create, model, params)

    def _create(self, model, params_dict):

        colHeadings = ('Quantity', 'Value')
        formatters = ('Bold', 'Bold')

        #custom latex header for maximum width imposed on 2nd col
        latex_head = "\\begin{tabular}[l]{|c|p{3in}|}\n\hline\n"
        latex_head += "\\textbf{Quantity} & \\textbf{Value} \\\\ \hline\n"
        table = _ReportTable(colHeadings, formatters,
                             customHeader={'latex': latex_head})

        for key in sorted(list(params_dict.keys())):
            if key in ['L,germ tuple base string dict', 'weights', 'profiler']: continue  # skip these
            if key == 'gaugeOptParams':
                if isinstance(params_dict[key], dict):
                    val = params_dict[key].copy()
                    if 'targetModel' in val:
                        del val['targetModel']  # don't print this!

                elif isinstance(params_dict[key], list):
                    val = []
                    for go_param_dict in params_dict[key]:
                        if isinstance(go_param_dict, dict):  # to ensure .copy() exists
                            val.append(go_param_dict.copy())
                            if 'targetModel' in val[-1]:
                                del val[-1]['targetModel']  # don't print this!
            else:
                val = params_dict[key]
            table.addrow((key, str(val)), (None, 'Verbatim'))

        if isinstance(self, _objs.ExplicitOpModel):
            for lbl, vec in model.preps.items():
                if isinstance(vec, _objs.StaticSPAMVec): paramTyp = "static"
                elif isinstance(vec, _objs.FullSPAMVec): paramTyp = "full"
                elif isinstance(vec, _objs.TPSPAMVec): paramTyp = "TP"
                elif isinstance(vec, _objs.ComplementSPAMVec): paramTyp = "Comp"
                else: paramTyp = "unknown"  # pragma: no cover
                table.addrow((lbl + " parameterization", paramTyp), (None, 'Verbatim'))

            for povmlbl, povm in model.povms.items():
                if isinstance(povm, _objs.UnconstrainedPOVM): paramTyp = "unconstrained"
                elif isinstance(povm, _objs.TPPOVM): paramTyp = "TP"
                elif isinstance(povm, _objs.TensorProdPOVM): paramTyp = "TensorProd"
                else: paramTyp = "unknown"  # pragma: no cover
                table.addrow((povmlbl + " parameterization", paramTyp), (None, 'Verbatim'))

                for lbl, vec in povm.items():
                    if isinstance(vec, _objs.StaticSPAMVec): paramTyp = "static"
                    elif isinstance(vec, _objs.FullSPAMVec): paramTyp = "full"
                    elif isinstance(vec, _objs.TPSPAMVec): paramTyp = "TP"
                    elif isinstance(vec, _objs.ComplementSPAMVec): paramTyp = "Comp"
                    else: paramTyp = "unknown"  # pragma: no cover
                    table.addrow(("> " + lbl + " parameterization", paramTyp), (None, 'Verbatim'))

            for gl, gate in model.operations.items():
                if isinstance(gate, _objs.StaticDenseOp): paramTyp = "static"
                elif isinstance(gate, _objs.FullDenseOp): paramTyp = "full"
                elif isinstance(gate, _objs.TPDenseOp): paramTyp = "TP"
                elif isinstance(gate, _objs.LinearlyParamDenseOp): paramTyp = "linear"
                elif isinstance(gate, _objs.EigenvalueParamDenseOp): paramTyp = "eigenvalue"
                elif isinstance(gate, _objs.LindbladDenseOp):
                    paramTyp = "Lindblad"
                    if gate.errorgen.param_mode == "cptp": paramTyp += " CPTP "
                    paramTyp += "(%d, %d params)" % (gate.errorgen.ham_basis_size, gate.errorgen.other_basis_size)
                else: paramTyp = "unknown"  # pragma: no cover
                table.addrow((gl + " parameterization", paramTyp), (None, 'Verbatim'))

        table.finish()
        return table


class SoftwareEnvTable(WorkspaceTable):
    """ Table showing details about the current software environment """

    def __init__(self, ws):
        """
        Create a table displaying the software environment relevant to pyGSTi.

        Returns
        -------
        ReportTable
        """
        super(SoftwareEnvTable, self).__init__(ws, self._create)

    def _create(self):

        import platform

        def get_version(moduleName):
            """ Extract the current version of a python module """
            if moduleName == "cvxopt":
                #special case b/c cvxopt can be weird...
                try:
                    mod = __import__("cvxopt.info")
                    return str(mod.info.version)
                except Exception: pass  # try the normal way below

            try:
                mod = __import__(moduleName)
                return str(mod.__version__)
            except ImportError:     # pragma: no cover
                return "missing"    # pragma: no cover
            except AttributeError:  # pragma: no cover
                return "ver?"       # pragma: no cover
            except Exception:       # pragma: no cover
                return "???"        # pragma: no cover

        colHeadings = ('Quantity', 'Value')
        formatters = ('Bold', 'Bold')

        #custom latex header for maximum width imposed on 2nd col
        latex_head = "\\begin{tabular}[l]{|c|p{3in}|}\n\hline\n"
        latex_head += "\\textbf{Quantity} & \\textbf{Value} \\\\ \hline\n"
        table = _ReportTable(colHeadings, formatters,
                             customHeader={'latex': latex_head})

        #Python package information
        from .._version import __version__ as pyGSTi_version
        table.addrow(("pyGSTi version", str(pyGSTi_version)), (None, 'Verbatim'))

        packages = ['numpy', 'scipy', 'matplotlib', 'ply', 'cvxopt', 'cvxpy',
                    'nose', 'PIL', 'psutil']
        for pkg in packages:
            table.addrow((pkg, get_version(pkg)), (None, 'Verbatim'))

        #Python information
        table.addrow(("Python version", str(platform.python_version())), (None, 'Verbatim'))
        table.addrow(("Python type", str(platform.python_implementation())), (None, 'Verbatim'))
        table.addrow(("Python compiler", str(platform.python_compiler())), (None, 'Verbatim'))
        table.addrow(("Python build", str(platform.python_build())), (None, 'Verbatim'))
        table.addrow(("Python branch", str(platform.python_branch())), (None, 'Verbatim'))
        table.addrow(("Python revision", str(platform.python_revision())), (None, 'Verbatim'))

        #Platform information
        (system, _, release, version, machine, processor) = platform.uname()
        table.addrow(("Platform summary", str(platform.platform())), (None, 'Verbatim'))
        table.addrow(("System", str(system)), (None, 'Verbatim'))
        table.addrow(("Sys Release", str(release)), (None, 'Verbatim'))
        table.addrow(("Sys Version", str(version)), (None, 'Verbatim'))
        table.addrow(("Machine", str(machine)), (None, 'Verbatim'))
        table.addrow(("Processor", str(processor)), (None, 'Verbatim'))

        table.finish()
        return table


class ProfilerTable(WorkspaceTable):
    """ Table of profiler timing information """

    def __init__(self, ws, profiler, sortBy="time"):
        """
        Create a table of profiler timing information.

        Parameters
        ----------
        profiler : Profiler
            The profiler object to extract timings from.

        sortBy : {"time", "name"}
            What the timer values should be sorted by.
        """
        super(ProfilerTable, self).__init__(ws, self._create, profiler, sortBy)

    def _create(self, profiler, sortBy):

        colHeadings = ('Label', 'Time (sec)')
        formatters = ('Bold', 'Bold')

        #custom latex header for maximum width imposed on 2nd col
        latex_head = "\\begin{tabular}[l]{|c|p{3in}|}\n\hline\n"
        latex_head += "\\textbf{Label} & \\textbf{Time} (sec) \\\\ \hline\n"
        table = _ReportTable(colHeadings, formatters,
                             customHeader={'latex': latex_head})

        if profiler is not None:
            if sortBy == "name":
                timerNames = sorted(list(profiler.timers.keys()))
            elif sortBy == "time":
                timerNames = sorted(list(profiler.timers.keys()),
                                    key=lambda x: -profiler.timers[x])
            else:
                raise ValueError("Invalid 'sortBy' argument: %s" % sortBy)

            for nm in timerNames:
                table.addrow((nm, profiler.timers[nm]), (None, None))

        table.finish()
        return table


class ExampleTable(WorkspaceTable):
    """ Table used just as an example of what tables can do/look like for use
        within the "Help" section of reports. """

    def __init__(self, ws):
        """A table showing how to use table features."""
        super(ExampleTable, self).__init__(ws, self._create)

    def _create(self):
        colHeadings = ["Hover over me...", "And me!", "Click the pig"]
        tooltips = ["This tooltip can give more information about what this column displays",
                    "Unfortunately, we can't show nicely formatted math in these tooltips (yet)",
                    "Click on the pyGSTi logo below to create the non-automatically-generated plot;"
                    + " then hover over the colored boxes."]
        example_mx = _np.array([[1.0, 1 / 3, -1 / 3, -1.0],
                                [1 / 3, 1.0, 0.0, -1 / 5],
                                [-1 / 3, 0.0, 1.0, 1 / 6],
                                [-1.0, -1 / 5, 1 / 6, 1.0]])
        example_ebmx = _np.abs(example_mx) * 0.05
        example_fig = _wp.GateMatrixPlot(self.ws, example_mx, -1.0, 1.0,
                                         "pp", EBmatrix=example_ebmx)

        table = _ReportTable(colHeadings, None, colHeadingLabels=tooltips)
        table.addrow(("Pi", _np.pi, example_fig), ('Normal', 'Normal', 'Figure'))
        table.finish()
        return table
