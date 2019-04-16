from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
"""
Variables for working with the 2-qubit model containing the gates
I*X(pi/2), I*Y(pi/2), X(pi/2)*I, Y(pi/2)*I, and CNOT.
"""

import numpy as _np
import sys as _sys
from . import circuitconstruction as _strc
from . import modelconstruction as _setc
from . import stdtarget as _stdtarget
from ..tools import optools as _gt

description = "I*X(pi/2), I*Y(pi/2), X(pi/2)*I, Y(pi/2)*I, and CNOT gates"

gates = ['Gix', 'Giy', 'Gxi', 'Gyi', 'Gcnot']

fiducials16 = _strc.circuit_list(
    [(), ('Gix',), ('Giy',), ('Gix', 'Gix'),
     ('Gxi',), ('Gxi', 'Gix'), ('Gxi', 'Giy'), ('Gxi', 'Gix', 'Gix'),
     ('Gyi',), ('Gyi', 'Gix'), ('Gyi', 'Giy'), ('Gyi', 'Gix', 'Gix'),
     ('Gxi', 'Gxi'), ('Gxi', 'Gxi', 'Gix'), ('Gxi', 'Gxi', 'Giy'), ('Gxi', 'Gxi', 'Gix', 'Gix')])

fiducials36 = _strc.circuit_list(
    [(), ('Gix',), ('Giy',), ('Gix', 'Gix'), ('Gix', 'Gix', 'Gix'), ('Giy', 'Giy', 'Giy'),
     ('Gxi',), ('Gxi', 'Gix'), ('Gxi', 'Giy'), ('Gxi', 'Gix',
                                                'Gix'), ('Gxi', 'Gix', 'Gix', 'Gix'), ('Gxi', 'Giy', 'Giy', 'Giy'),
     ('Gyi',), ('Gyi', 'Gix'), ('Gyi', 'Giy'), ('Gyi', 'Gix',
                                                'Gix'), ('Gyi', 'Gix', 'Gix', 'Gix'), ('Gyi', 'Giy', 'Giy', 'Giy'),
     ('Gxi', 'Gxi'), ('Gxi', 'Gxi', 'Gix'), ('Gxi', 'Gxi', 'Giy'), ('Gxi',
                                                                    'Gxi', 'Gix', 'Gix'), ('Gxi', 'Gxi', 'Gix', 'Gix', 'Gix'),
     ('Gxi', 'Gxi', 'Giy', 'Giy', 'Giy'), ('Gxi', 'Gxi', 'Gxi'), ('Gxi', 'Gxi', 'Gxi', 'Gix'), ('Gxi', 'Gxi', 'Gxi', 'Giy'),
     ('Gxi', 'Gxi', 'Gxi', 'Gix', 'Gix'), ('Gxi', 'Gxi', 'Gxi', 'Gix',
                                           'Gix', 'Gix'), ('Gxi', 'Gxi', 'Gxi', 'Giy', 'Giy', 'Giy'),
     ('Gyi', 'Gyi', 'Gyi'), ('Gyi', 'Gyi', 'Gyi', 'Gix'), ('Gyi',
                                                           'Gyi', 'Gyi', 'Giy'), ('Gyi', 'Gyi', 'Gyi', 'Gix', 'Gix'),
     ('Gyi', 'Gyi', 'Gyi', 'Gix', 'Gix', 'Gix'), ('Gyi', 'Gyi', 'Gyi', 'Giy', 'Giy', 'Giy')])

fiducials = fiducials16
prepStrs = fiducials16

effectStrs = _strc.circuit_list(
    [(), ('Gix',), ('Giy',),
     ('Gix', 'Gix'), ('Gxi',),
     ('Gyi',), ('Gxi', 'Gxi'),
     ('Gxi', 'Gix'), ('Gxi', 'Giy'),
     ('Gyi', 'Gix'), ('Gyi', 'Giy')])


germs = _strc.circuit_list(
    [('Gii',),
     ('Gxi',),
     ('Gyi',),
     ('Gix',),
     ('Giy',),
     ('Gcnot',),
     ('Gxi', 'Gyi'),
     ('Gix', 'Giy'),
     ('Giy', 'Gyi'),
     ('Gix', 'Gxi'),
     ('Gix', 'Gyi'),
     ('Giy', 'Gxi'),
     ('Giy', 'Gcnot'),
     ('Gyi', 'Gcnot'),
     ('Gxi', 'Gcnot'),
     ('Gix', 'Gcnot'),
     ('Gii', 'Gix'),
     ('Gii', 'Giy'),
     ('Gii', 'Gyi'),
     ('Gii', 'Gcnot'),
     ('Gxi', 'Gxi', 'Gyi'),
     ('Gix', 'Gix', 'Giy'),
     ('Gxi', 'Gyi', 'Gyi'),
     ('Gix', 'Giy', 'Giy'),
     ('Giy', 'Gxi', 'Gxi'),
     ('Giy', 'Gxi', 'Gyi'),
     ('Gix', 'Gxi', 'Giy'),
     ('Gix', 'Gyi', 'Gxi'),
     ('Gix', 'Gyi', 'Giy'),
     ('Gix', 'Giy', 'Gyi'),
     ('Gix', 'Giy', 'Gxi'),
     ('Giy', 'Gyi', 'Gxi'),
     ('Giy', 'Gcnot', 'Gxi'),
     ('Gix', 'Gix', 'Gcnot'),
     ('Gxi', 'Gcnot', 'Gcnot'),
     ('Giy', 'Gyi', 'Gcnot'),
     ('Gyi', 'Gcnot', 'Gcnot'),
     ('Gix', 'Giy', 'Gcnot'),
     ('Giy', 'Gcnot', 'Gcnot'),
     ('Gxi', 'Gyi', 'Gii'),
     ('Gxi', 'Gii', 'Gyi'),
     ('Gxi', 'Gii', 'Gii'),
     ('Gyi', 'Gii', 'Gii'),
     ('Gix', 'Giy', 'Gii'),
     ('Gix', 'Gii', 'Giy'),
     ('Gix', 'Gii', 'Gii'),
     ('Giy', 'Gii', 'Gii'),
     ('Gii', 'Gix', 'Gyi'),
     ('Gii', 'Giy', 'Gyi'),
     ('Gii', 'Gyi', 'Gix'),
     ('Gcnot', 'Gix', 'Gxi', 'Gxi'),
     ('Gyi', 'Gix', 'Gxi', 'Giy'),
     ('Gix', 'Giy', 'Gxi', 'Gyi'),
     ('Gix', 'Gix', 'Gix', 'Giy'),
     ('Gxi', 'Gyi', 'Gyi', 'Gyi'),
     ('Gyi', 'Gyi', 'Giy', 'Gyi'),
     ('Gyi', 'Gix', 'Gix', 'Gix'),
     ('Gxi', 'Gyi', 'Gix', 'Gix'),
     ('Gcnot', 'Gyi', 'Gcnot', 'Gxi'),
     ('Gcnot', 'Gix', 'Gcnot', 'Giy'),
     ('Gix', 'Gxi', 'Gcnot', 'Giy'),
     ('Gix', 'Giy', 'Gxi', 'Gcnot'),
     ('Gxi', 'Gyi', 'Gyi', 'Gii'),
     ('Gix', 'Giy', 'Giy', 'Gii'),
     ('Giy', 'Gxi', 'Gii', 'Gii'),
     ('Gix', 'Gii', 'Gii', 'Gxi'),
     ('Giy', 'Gyi', 'Gxi', 'Gxi', 'Giy'),
     ('Gxi', 'Gxi', 'Giy', 'Gyi', 'Giy'),
     ('Giy', 'Gix', 'Gxi', 'Gix', 'Gxi'),
     ('Gyi', 'Giy', 'Gyi', 'Gix', 'Gix'),
     ('Giy', 'Gxi', 'Gix', 'Giy', 'Gyi'),
     ('Giy', 'Giy', 'Gxi', 'Gyi', 'Gxi'),
     ('Gyi', 'Gcnot', 'Giy', 'Giy', 'Gxi'),
     ('Gxi', 'Gix', 'Giy', 'Gxi', 'Giy', 'Gyi'),
     ('Gxi', 'Giy', 'Gix', 'Gyi', 'Gix', 'Gix'),
     ('Gyi', 'Giy', 'Gxi', 'Gyi', 'Gxi', 'Gcnot'),
     ('Gxi', 'Gxi', 'Gyi', 'Gxi', 'Gyi', 'Gyi'),
     ('Gix', 'Gix', 'Giy', 'Gix', 'Giy', 'Giy'),
     ('Gyi', 'Gxi', 'Gix', 'Giy', 'Gxi', 'Gix'),
     ('Gyi', 'Gxi', 'Gix', 'Gxi', 'Gix', 'Giy'),
     ('Gxi', 'Gix', 'Giy', 'Giy', 'Gxi', 'Gyi'),
     ('Gix', 'Giy', 'Giy', 'Gix', 'Gxi', 'Gxi'),
     ('Gyi', 'Giy', 'Gxi', 'Giy', 'Giy', 'Giy'),
     ('Gyi', 'Gyi', 'Gyi', 'Giy', 'Gyi', 'Gix'),
     ('Giy', 'Giy', 'Gxi', 'Giy', 'Gix', 'Giy'),
     ('Giy', 'Gix', 'Gyi', 'Gyi', 'Gix', 'Gxi', 'Giy'),
     ('Gyi', 'Gxi', 'Giy', 'Gxi', 'Gix', 'Gxi', 'Gyi', 'Giy'),
     ('Gix', 'Gix', 'Gyi', 'Gxi', 'Giy', 'Gxi', 'Giy', 'Gyi')
     ])

germs_lite = _strc.circuit_list(
    [('Gii',),
     ('Gxi',),
     ('Gyi',),
     ('Gix',),
     ('Giy',),
     ('Gcnot',),
     ('Gxi', 'Gyi'),
     ('Gix', 'Giy'),
     ('Gxi', 'Gxi', 'Gyi'),
     ('Gix', 'Gix', 'Giy'),
     ('Gcnot', 'Gix', 'Gxi', 'Gxi'),
     ('Gxi', 'Gix', 'Giy', 'Gxi', 'Giy', 'Gyi'),
     ('Gxi', 'Giy', 'Gix', 'Gyi', 'Gix', 'Gix'),
     ('Gyi', 'Giy', 'Gxi', 'Gyi', 'Gxi', 'Gcnot'),
     ('Gyi', 'Gxi', 'Giy', 'Gxi', 'Gix', 'Gxi', 'Gyi', 'Giy')
     ])


legacy_effectStrs = _strc.circuit_list(
    [(), ('Gix',), ('Giy',), ('Gxi',), ('Gyi',),
     ('Gix', 'Gxi'), ('Gxi', 'Giy'), ('Gyi', 'Gix'),
     ('Gyi', 'Giy'), ('Gxi', 'Gxi')])

legacy_germs = _strc.circuit_list(
    [('Gii',),
     ('Gxi',),
     ('Gyi',),
     ('Gix',),
     ('Giy',),
     ('Gcnot',),
     ('Gxi', 'Gyi'),
     ('Gix', 'Giy'),
     ('Giy', 'Gyi'),
     ('Gix', 'Gyi'),
     ('Gyi', 'Gcnot'),
     ('Giy', 'Gcnot'),
     ('Gxi', 'Gyi', 'Gii'),
     ('Gxi', 'Gii', 'Gyi'),
     ('Gxi', 'Gii', 'Gii'),
     ('Gyi', 'Gii', 'Gii'),
     ('Gix', 'Giy', 'Gii'),
     ('Gix', 'Gii', 'Giy'),
     ('Gix', 'Gii', 'Gii'),
     ('Giy', 'Gii', 'Gii'),
     ('Gxi', 'Gcnot', 'Gcnot'),
     ('Giy', 'Gxi', 'Gcnot'),
     ('Giy', 'Gcnot', 'Gyi'),
     ('Giy', 'Gyi', 'Gcnot'),
     ('Gix', 'Gxi', 'Gcnot'),
     ('Giy', 'Giy', 'Gcnot'),
     ('Giy', 'Gcnot', 'Gxi'),
     ('Gix', 'Giy', 'Gcnot'),
     ('Giy', 'Gxi', 'Gyi'),
     ('Gix', 'Giy', 'Gyi'),
     ('Gii', 'Gii', 'Gcnot'),
     ('Gii', 'Giy', 'Gxi'),
     ('Gxi', 'Gxi', 'Gii', 'Gyi'),
     ('Gxi', 'Gyi', 'Gyi', 'Gii'),
     ('Gix', 'Gix', 'Gii', 'Giy'),
     ('Gix', 'Giy', 'Giy', 'Gii'),
     ('Gyi', 'Gyi', 'Gyi', 'Gxi'),
     ('Giy', 'Giy', 'Giy', 'Gix'),
     ('Gxi', 'Gyi', 'Gix', 'Giy'),
     ('Gcnot', 'Gix', 'Gyi', 'Gyi'),
     ('Gcnot', 'Gix', 'Gix', 'Gcnot'),
     ('Gxi', 'Gcnot', 'Gyi', 'Gyi'),
     ('Gyi', 'Gyi', 'Gyi', 'Gix'),
     ('Gii', 'Giy', 'Gxi', 'Gcnot'),
     ('Giy', 'Gii', 'Gcnot', 'Gii'),
     ('Gix', 'Gix', 'Giy', 'Gcnot', 'Gcnot'),
     ('Gcnot', 'Giy', 'Giy', 'Gix', 'Giy'),
     ('Gyi', 'Gcnot', 'Gix', 'Giy', 'Gyi'),
     ('Giy', 'Gxi', 'Gcnot', 'Gxi', 'Gcnot'),
     ('Gyi', 'Gcnot', 'Gxi', 'Gcnot', 'Gxi'),
     ('Gxi', 'Gxi', 'Gyi', 'Gxi', 'Gyi', 'Gyi'),
     ('Gix', 'Gix', 'Giy', 'Gix', 'Giy', 'Giy'),
     ('Gyi', 'Gxi', 'Gyi', 'Gxi', 'Gxi', 'Gxi'),
     ('Gyi', 'Gxi', 'Gyi', 'Gyi', 'Gxi', 'Gxi'),
     ('Gyi', 'Gyi', 'Gyi', 'Gxi', 'Gyi', 'Gxi'),
     ('Giy', 'Gix', 'Giy', 'Gix', 'Gix', 'Gix'),
     ('Giy', 'Gix', 'Giy', 'Giy', 'Gix', 'Gix'),
     ('Giy', 'Giy', 'Giy', 'Gix', 'Giy', 'Gix'),
     ('Gcnot', 'Gyi', 'Giy', 'Gxi', 'Gix', 'Gcnot'),
     ('Gxi', 'Giy', 'Gxi', 'Gcnot', 'Gyi', 'Gix'),
     ('Gxi', 'Giy', 'Giy', 'Giy', 'Gcnot', 'Gxi'),
     ('Gcnot', 'Gxi', 'Gcnot', 'Gxi', 'Giy', 'Gix'),
     ('Gyi', 'Gix', 'Gyi', 'Gix', 'Gxi', 'Gxi'),
     ('Gix', 'Gcnot', 'Gxi', 'Gix', 'Gxi', 'Gcnot'),
     ('Gxi', 'Giy', 'Gyi', 'Gxi', 'Gcnot', 'Gcnot'),
     ('Gix', 'Gix', 'Giy', 'Gcnot', 'Giy', 'Gcnot', 'Gxi'),
     ('Giy', 'Gxi', 'Gcnot', 'Gix', 'Gix', 'Giy', 'Giy'),
     ('Gxi', 'Gcnot', 'Giy', 'Gyi', 'Gxi', 'Gix', 'Giy'),
     ('Gcnot', 'Gcnot', 'Gix', 'Gxi', 'Giy', 'Gxi', 'Gxi'),
     ('Gxi', 'Gix', 'Giy', 'Gyi', 'Gix', 'Gix', 'Gix'),
     ('Gxi', 'Gix', 'Gyi', 'Gix', 'Gyi', 'Giy', 'Gyi'),
     ('Gix', 'Gix', 'Gix', 'Gix', 'Gxi', 'Gxi', 'Gyi'),
     ('Gyi', 'Gii', 'Giy', 'Gyi', 'Gcnot', 'Gxi', 'Gii'),
     ('Giy', 'Gcnot', 'Gxi', 'Gyi', 'Gyi', 'Gcnot', 'Gix', 'Gcnot'),
     ('Gxi', 'Gyi', 'Gxi', 'Giy', 'Gxi', 'Giy', 'Gix', 'Giy'),
     ('Giy', 'Giy', 'Gyi', 'Gix', 'Gcnot', 'Gxi', 'Gyi', 'Gyi'),
     ('Gxi', 'Gix', 'Gcnot', 'Gyi', 'Gix', 'Gcnot', 'Gix', 'Giy'),
     ('Gix', 'Gxi', 'Gxi', 'Giy', 'Gxi', 'Gyi', 'Gix', 'Gcnot'),
     ('Gix', 'Gix', 'Gyi', 'Gxi', 'Giy', 'Gix', 'Gcnot', 'Gyi'),
     ('Gix', 'Giy', 'Gix', 'Gxi', 'Gix', 'Giy', 'Gxi', 'Gxi'),
     ('Giy', 'Gix', 'Gcnot', 'Gxi', 'Gcnot', 'Gxi', 'Gcnot', 'Gyi'),
     ('Gxi', 'Giy', 'Gix', 'Gix', 'Gxi', 'Giy', 'Gxi', 'Gcnot'),
     ('Gyi', 'Gyi', 'Gyi', 'Gyi', 'Gix', 'Giy', 'Gix', 'Gyi'),
     ('Gcnot', 'Gii', 'Gxi', 'Gxi', 'Giy', 'Gii', 'Gii', 'Gix'),
     ('Gix', 'Gii', 'Gxi', 'Gix', 'Gii', 'Giy', 'Gxi', 'Gii')
     ])


#Construct the target model
_target_model = _setc.build_explicit_model(
    [('Q0', 'Q1')], ['Gii', 'Gix', 'Giy', 'Gxi', 'Gyi', 'Gcnot'],
    ["I(Q0):I(Q1)", "I(Q0):X(pi/2,Q1)", "I(Q0):Y(pi/2,Q1)", "X(pi/2,Q0):I(Q1)", "Y(pi/2,Q0):I(Q1)", "CNOT(Q0,Q1)"],
    effectLabels=['00', '01', '10', '11'], effectExpressions=["0", "1", "2", "3"])

_gscache = {("full", "auto"): _target_model}


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
    return _stdtarget._copy_target(_sys.modules[__name__], parameterization_type,
                                   sim_type, _gscache)


#Wrong CNOT (bad 1Q phase factor)
legacy_gs_target = _setc.build_explicit_model(
    [('Q0', 'Q1')], ['Gix', 'Giy', 'Gxi', 'Gyi', 'Gcnot'],
    ["I(Q0):X(pi/2,Q1)", "I(Q0):Y(pi/2,Q1)", "X(pi/2,Q0):I(Q1)", "Y(pi/2,Q0):I(Q1)", "CX(pi,Q0,Q1)"],
    effectLabels=['00', '01', '10', '11'], effectExpressions=["0", "1", "2", "3"])

global_fidPairs = [
    (2, 0), (2, 1), (2, 2), (2, 10), (3, 10), (4, 2), (4, 9),
    (5, 1), (5, 7), (6, 10), (7, 1), (7, 6), (7, 7), (8, 0),
    (8, 7), (9, 6), (9, 8), (10, 5), (10, 10), (12, 5), (13, 1),
    (13, 4), (14, 1), (14, 7)]

pergerm_fidPairsDict = {
    ('Gix',): [
        (0, 5), (1, 0), (1, 1), (2, 2), (2, 5), (2, 9), (3, 3),
        (3, 4), (3, 8), (4, 0), (4, 2), (4, 7), (4, 8), (4, 10),
        (5, 0), (5, 1), (5, 2), (5, 6), (5, 8), (6, 7), (6, 8),
        (6, 9), (7, 0), (7, 4), (8, 5), (8, 9), (9, 5), (10, 8),
        (10, 10), (12, 2), (12, 4), (12, 7), (13, 2), (13, 3),
        (13, 9), (14, 0), (14, 5), (14, 6), (15, 5), (15, 8),
        (15, 9)],
    ('Gcnot',): [
        (0, 7), (1, 0), (2, 4), (4, 3), (5, 5), (5, 10), (6, 1),
        (6, 10), (7, 8), (8, 2), (8, 5), (8, 6), (9, 0), (9, 4),
        (9, 6), (9, 9), (10, 2), (10, 4), (10, 5), (11, 5), (12, 2),
        (13, 7), (14, 1), (14, 2), (14, 3), (14, 6), (15, 8),
        (15, 10)],
    ('Giy',): [
        (0, 0), (0, 7), (1, 1), (3, 5), (3, 6), (4, 2), (4, 4),
        (4, 5), (5, 3), (5, 7), (7, 1), (7, 8), (8, 5), (9, 4),
        (9, 5), (9, 9), (10, 5), (11, 5), (11, 6), (11, 8), (11, 10),
        (12, 0), (12, 3), (13, 10), (14, 0), (14, 5), (14, 6),
        (14, 7), (15, 0), (15, 6), (15, 9)],
    ('Gyi',): [
        (3, 1), (4, 1), (4, 2), (5, 0), (5, 1), (5, 7), (6, 0),
        (6, 8), (7, 2), (7, 4), (7, 9), (8, 0), (8, 7), (9, 2),
        (9, 3), (10, 9), (10, 10), (14, 7), (14, 9), (15, 10)],
    ('Gii',): [
        (0, 8), (1, 0), (1, 1), (1, 3), (1, 10), (2, 5), (2, 9),
        (3, 3), (3, 9), (4, 3), (4, 8), (5, 0), (5, 5), (5, 7),
        (6, 4), (6, 6), (6, 8), (6, 10), (7, 0), (7, 2), (7, 3),
        (7, 4), (7, 6), (7, 10), (8, 3), (8, 5), (9, 3), (9, 4),
        (9, 5), (9, 6), (9, 8), (9, 9), (10, 3), (10, 9), (10, 10),
        (11, 1), (11, 5), (12, 5), (12, 7), (12, 9), (13, 0),
        (13, 10), (14, 0), (14, 1), (14, 2), (14, 6), (15, 0),
        (15, 5), (15, 6), (15, 7), (15, 8)],
    ('Gxi',): [
        (0, 7), (1, 1), (1, 7), (2, 7), (3, 3), (4, 9), (5, 4),
        (7, 2), (7, 10), (8, 2), (9, 2), (9, 8), (9, 9), (10, 1),
        (10, 10), (11, 2), (11, 5), (11, 6), (13, 2), (14, 7),
        (15, 2), (15, 3)],
    ('Giy', 'Gyi'): [
        (0, 6), (0, 8), (0, 10), (1, 0), (1, 1), (1, 3), (2, 9),
        (3, 8), (4, 4), (4, 7), (5, 7), (6, 1), (7, 0), (7, 8),
        (9, 10), (10, 5), (11, 5), (12, 5), (12, 6), (14, 0),
        (15, 0), (15, 6), (15, 8)],
    ('Giy', 'Gxi'): [
        (1, 1), (2, 8), (3, 0), (3, 2), (3, 6), (4, 7), (7, 2),
        (8, 6), (9, 1), (9, 7), (9, 9), (10, 2), (10, 10), (11, 8),
        (12, 6), (13, 2), (13, 7), (14, 2), (15, 5)],
    ('Gii', 'Giy'): [
        (0, 0), (0, 7), (1, 1), (3, 5), (3, 6), (4, 2), (4, 4),
        (4, 5), (5, 3), (5, 7), (7, 1), (7, 8), (8, 5), (9, 4),
        (9, 5), (9, 9), (10, 5), (11, 5), (11, 6), (11, 8), (11, 10),
        (12, 0), (12, 3), (13, 10), (14, 0), (14, 5), (14, 6),
        (14, 7), (15, 0), (15, 6), (15, 9)],
    ('Gix', 'Giy'): [
        (1, 0), (1, 10), (4, 0), (4, 4), (4, 7), (4, 8), (5, 5),
        (7, 6), (8, 9), (9, 9), (10, 2), (10, 8), (11, 10), (12, 6),
        (12, 9), (13, 9), (15, 1)],
    ('Gii', 'Gcnot'): [
        (0, 7), (1, 0), (2, 4), (4, 3), (5, 5), (5, 10), (6, 1),
        (6, 10), (7, 8), (8, 2), (8, 5), (8, 6), (9, 0), (9, 4),
        (9, 6), (9, 9), (10, 2), (10, 4), (10, 5), (11, 5), (12, 2),
        (13, 7), (14, 1), (14, 2), (14, 3), (14, 6), (15, 8),
        (15, 10)],
    ('Gyi', 'Gcnot'): [
        (0, 2), (1, 0), (1, 4), (1, 9), (3, 10), (4, 3), (5, 7),
        (7, 4), (7, 7), (7, 8), (8, 7), (8, 9), (9, 2), (9, 6),
        (10, 3), (14, 10), (15, 4)],
    ('Gix', 'Gxi'): [
        (0, 0), (1, 5), (2, 4), (3, 3), (3, 5), (5, 2), (6, 1),
        (6, 8), (6, 10), (8, 6), (10, 2), (10, 8), (10, 10),
        (11, 8), (12, 1), (13, 1), (13, 4), (13, 6), (13, 10),
        (14, 8), (15, 3)],
    ('Gii', 'Gyi'): [
        (3, 1), (4, 1), (4, 2), (5, 0), (5, 1), (5, 7), (6, 0),
        (6, 8), (7, 2), (7, 4), (7, 9), (8, 0), (8, 7), (9, 2),
        (9, 3), (10, 9), (10, 10), (14, 7), (14, 9), (15, 10)],
    ('Gix', 'Gyi'): [
        (0, 5), (0, 9), (1, 6), (3, 1), (3, 2), (5, 0), (5, 4),
        (6, 0), (6, 8), (9, 7), (10, 9), (11, 1), (11, 4), (14, 4),
        (14, 9), (15, 5), (15, 7)],
    ('Gix', 'Gcnot'): [
        (2, 2), (3, 1), (4, 5), (4, 7), (4, 8), (5, 3), (5, 4),
        (8, 5), (9, 4), (9, 6), (10, 10), (12, 0), (13, 0), (14, 5),
        (15, 1), (15, 7), (15, 10)],
    ('Gii', 'Gix'): [
        (0, 5), (1, 0), (1, 1), (2, 2), (2, 5), (2, 9), (3, 3),
        (3, 4), (3, 8), (4, 0), (4, 2), (4, 7), (4, 8), (4, 10),
        (5, 0), (5, 1), (5, 2), (5, 6), (5, 8), (6, 7), (6, 8),
        (6, 9), (7, 0), (7, 4), (8, 5), (8, 9), (9, 5), (10, 8),
        (10, 10), (12, 2), (12, 4), (12, 7), (13, 2), (13, 3),
        (13, 9), (14, 0), (14, 5), (14, 6), (15, 5), (15, 8),
        (15, 9)],
    ('Giy', 'Gcnot'): [
        (0, 2), (1, 0), (1, 4), (1, 9), (3, 10), (4, 3), (5, 7),
        (7, 4), (7, 7), (7, 8), (8, 7), (8, 9), (9, 2), (9, 6),
        (10, 3), (14, 10), (15, 4)],
    ('Gxi', 'Gyi'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gxi', 'Gcnot'): [
        (0, 1), (0, 5), (1, 3), (2, 4), (2, 10), (3, 8), (5, 5),
        (7, 0), (9, 3), (9, 9), (9, 10), (10, 8), (12, 2), (12, 6),
        (14, 6), (15, 0), (15, 5)],
    ('Gyi', 'Gii', 'Gii'): [
        (3, 1), (4, 1), (4, 2), (5, 0), (5, 1), (5, 7), (6, 0),
        (6, 8), (7, 2), (7, 4), (7, 9), (8, 0), (8, 7), (9, 2),
        (9, 3), (10, 9), (10, 10), (14, 7), (14, 9), (15, 10)],
    ('Giy', 'Gcnot', 'Gxi'): [
        (0, 1), (0, 5), (1, 3), (2, 4), (2, 10), (3, 8), (5, 5),
        (7, 0), (9, 3), (9, 9), (9, 10), (10, 8), (12, 2), (12, 6),
        (14, 6), (15, 0), (15, 5)],
    ('Gix', 'Giy', 'Gii'): [
        (1, 0), (1, 10), (4, 0), (4, 4), (4, 7), (4, 8), (5, 5),
        (7, 6), (8, 9), (9, 9), (10, 2), (10, 8), (11, 10), (12, 6),
        (12, 9), (13, 9), (15, 1)],
    ('Gix', 'Gxi', 'Giy'): [
        (0, 6), (3, 0), (5, 0), (6, 7), (7, 1), (8, 3), (9, 9),
        (10, 4), (10, 9), (12, 9), (13, 2), (14, 5), (14, 8),
        (14, 10), (15, 6)],
    ('Gxi', 'Gii', 'Gii'): [
        (0, 7), (1, 1), (1, 7), (2, 7), (3, 3), (4, 9), (5, 4),
        (7, 2), (7, 10), (8, 2), (9, 2), (9, 8), (9, 9), (10, 1),
        (10, 10), (11, 2), (11, 5), (11, 6), (13, 2), (14, 7),
        (15, 2), (15, 3)],
    ('Gix', 'Gyi', 'Gxi'): [
        (1, 10), (2, 10), (4, 8), (5, 5), (5, 6), (6, 10), (7, 0),
        (7, 5), (7, 6), (7, 8), (8, 5), (12, 5), (13, 0), (13, 2),
        (14, 1)],
    ('Gix', 'Giy', 'Gyi'): [
        (0, 1), (4, 2), (4, 7), (6, 7), (8, 3), (9, 5), (9, 7),
        (10, 0), (10, 4), (10, 5), (11, 2), (11, 9), (14, 6),
        (14, 8), (15, 3)],
    ('Giy', 'Gii', 'Gii'): [
        (0, 0), (0, 7), (1, 1), (3, 5), (3, 6), (4, 2), (4, 4),
        (4, 5), (5, 3), (5, 7), (7, 1), (7, 8), (8, 5), (9, 4),
        (9, 5), (9, 9), (10, 5), (11, 5), (11, 6), (11, 8), (11, 10),
        (12, 0), (12, 3), (13, 10), (14, 0), (14, 5), (14, 6),
        (14, 7), (15, 0), (15, 6), (15, 9)],
    ('Gxi', 'Gyi', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Gxi', 'Gxi'): [
        (1, 7), (2, 2), (4, 8), (7, 2), (7, 10), (8, 6), (9, 8),
        (9, 9), (10, 1), (11, 4), (11, 9), (12, 8), (12, 9),
        (13, 0), (13, 1), (13, 9)],
    ('Gii', 'Gix', 'Gyi'): [
        (0, 5), (0, 9), (1, 6), (3, 1), (3, 2), (5, 0), (5, 4),
        (6, 0), (6, 8), (9, 7), (10, 9), (11, 1), (11, 4), (14, 4),
        (14, 9), (15, 5), (15, 7)],
    ('Giy', 'Gcnot', 'Gcnot'): [
        (0, 0), (0, 7), (1, 1), (3, 5), (3, 6), (4, 2), (4, 4),
        (4, 5), (5, 3), (5, 7), (7, 1), (7, 8), (8, 5), (9, 4),
        (9, 5), (9, 9), (10, 5), (11, 5), (11, 6), (11, 8), (11, 10),
        (12, 0), (12, 3), (13, 10), (14, 0), (14, 5), (14, 6),
        (14, 7), (15, 0), (15, 6), (15, 9)],
    ('Gix', 'Gyi', 'Giy'): [
        (3, 0), (4, 4), (5, 1), (5, 8), (6, 5), (7, 3), (8, 6),
        (8, 7), (9, 5), (10, 3), (11, 4), (14, 0), (14, 6), (14, 9),
        (15, 5)],
    ('Gxi', 'Gii', 'Gyi'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gix', 'Gix', 'Gcnot'): [
        (0, 6), (0, 7), (2, 2), (2, 3), (2, 5), (2, 9), (4, 4),
        (4, 9), (6, 1), (8, 10), (12, 3), (12, 9), (13, 3), (14, 10),
        (15, 3)],
    ('Gix', 'Giy', 'Giy'): [
        (0, 4), (0, 5), (0, 7), (1, 1), (1, 6), (2, 3), (4, 10),
        (5, 4), (6, 8), (7, 4), (7, 10), (8, 8), (8, 9), (10, 5),
        (11, 5), (11, 6), (11, 9), (13, 10), (14, 1), (14, 9)],
    ('Gxi', 'Gyi', 'Gii'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gyi', 'Gcnot', 'Gcnot'): [
        (3, 1), (4, 1), (4, 2), (5, 0), (5, 1), (5, 7), (6, 0),
        (6, 8), (7, 2), (7, 4), (7, 9), (8, 0), (8, 7), (9, 2),
        (9, 3), (10, 9), (10, 10), (14, 7), (14, 9), (15, 10)],
    ('Gix', 'Gix', 'Giy'): [
        (0, 0), (0, 6), (1, 0), (1, 10), (4, 0), (4, 4), (4, 7),
        (4, 8), (5, 5), (6, 7), (7, 6), (8, 9), (9, 9), (10, 2),
        (10, 8), (11, 10), (12, 6), (12, 9), (13, 1), (13, 9),
        (15, 1)],
    ('Gii', 'Giy', 'Gyi'): [
        (0, 6), (0, 8), (0, 10), (1, 0), (1, 1), (1, 3), (2, 9),
        (3, 8), (4, 4), (4, 7), (5, 7), (6, 1), (7, 0), (7, 8),
        (9, 10), (10, 5), (11, 5), (12, 5), (12, 6), (14, 0),
        (15, 0), (15, 6), (15, 8)],
    ('Giy', 'Gxi', 'Gyi'): [
        (0, 9), (1, 1), (1, 9), (2, 7), (3, 4), (4, 4), (4, 10),
        (6, 0), (6, 3), (7, 0), (9, 4), (11, 5), (12, 4), (13, 7),
        (14, 0)],
    ('Giy', 'Gyi', 'Gxi'): [
        (0, 9), (1, 1), (1, 9), (2, 7), (3, 4), (4, 4), (4, 10),
        (6, 0), (6, 3), (7, 0), (9, 4), (11, 5), (12, 4), (13, 7),
        (14, 0)],
    ('Gii', 'Gyi', 'Gix'): [
        (0, 5), (0, 9), (1, 6), (3, 1), (3, 2), (5, 0), (5, 4),
        (6, 0), (6, 8), (9, 7), (10, 9), (11, 1), (11, 4), (14, 4),
        (14, 9), (15, 5), (15, 7)],
    ('Gix', 'Giy', 'Gxi'): [
        (0, 6), (3, 0), (5, 0), (6, 7), (7, 1), (8, 3), (9, 9),
        (10, 4), (10, 9), (12, 9), (13, 2), (14, 5), (14, 8),
        (14, 10), (15, 6)],
    ('Gix', 'Giy', 'Gcnot'): [
        (0, 3), (1, 0), (1, 4), (3, 10), (4, 3), (5, 7), (7, 2),
        (7, 4), (7, 7), (7, 8), (8, 1), (8, 5), (8, 7), (8, 9),
        (9, 2), (9, 6), (10, 3), (14, 10), (15, 4)],
    ('Giy', 'Gyi', 'Gcnot'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (7, 8), (9, 3), (9, 9), (9, 10),
        (10, 8), (12, 2), (12, 6), (14, 6), (15, 0), (15, 4),
        (15, 5)],
    ('Gxi', 'Gcnot', 'Gcnot'): [
        (0, 7), (1, 1), (1, 7), (2, 7), (3, 3), (4, 9), (5, 4),
        (7, 2), (7, 10), (8, 2), (9, 2), (9, 8), (9, 9), (10, 1),
        (10, 10), (11, 2), (11, 5), (11, 6), (13, 2), (14, 7),
        (15, 2), (15, 3)],
    ('Gix', 'Gii', 'Giy'): [
        (1, 0), (1, 10), (4, 0), (4, 4), (4, 7), (4, 8), (5, 5),
        (7, 6), (8, 9), (9, 9), (10, 2), (10, 8), (11, 10), (12, 6),
        (12, 9), (13, 9), (15, 1)],
    ('Gix', 'Gii', 'Gii'): [
        (0, 5), (1, 0), (1, 1), (2, 2), (2, 5), (2, 9), (3, 3),
        (3, 4), (3, 8), (4, 0), (4, 2), (4, 7), (4, 8), (4, 10),
        (5, 0), (5, 1), (5, 2), (5, 6), (5, 8), (6, 7), (6, 8),
        (6, 9), (7, 0), (7, 4), (8, 5), (8, 9), (9, 5), (10, 8),
        (10, 10), (12, 2), (12, 4), (12, 7), (13, 2), (13, 3),
        (13, 9), (14, 0), (14, 5), (14, 6), (15, 5), (15, 8),
        (15, 9)],
    ('Gxi', 'Gxi', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gix', 'Gxi', 'Gcnot', 'Giy'): [
        (0, 1), (0, 2), (0, 5), (0, 10), (1, 3), (1, 7), (2, 1),
        (2, 7), (3, 6), (5, 1), (6, 10), (7, 0), (7, 6), (9, 0),
        (9, 2), (10, 4), (11, 7), (11, 9), (13, 7), (14, 3),
        (14, 7), (15, 5), (15, 10)],
    ('Gyi', 'Gix', 'Gxi', 'Giy'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gix', 'Gii', 'Gii', 'Gxi'): [
        (0, 0), (1, 5), (2, 4), (3, 3), (3, 5), (5, 2), (6, 1),
        (6, 8), (6, 10), (8, 6), (10, 2), (10, 8), (10, 10),
        (11, 8), (12, 1), (13, 1), (13, 4), (13, 6), (13, 10),
        (14, 8), (15, 3)],
    ('Gix', 'Giy', 'Gxi', 'Gyi'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Giy', 'Gxi', 'Gii', 'Gii'): [
        (1, 1), (2, 8), (3, 0), (3, 2), (3, 6), (4, 7), (7, 2),
        (8, 6), (9, 1), (9, 7), (9, 9), (10, 2), (10, 10), (11, 8),
        (12, 6), (13, 2), (13, 7), (14, 2), (15, 5)],
    ('Gyi', 'Gix', 'Gix', 'Gix'): [
        (0, 5), (0, 9), (1, 6), (3, 1), (3, 2), (5, 0), (5, 4),
        (6, 0), (6, 8), (9, 7), (10, 9), (11, 1), (11, 4), (14, 4),
        (14, 9), (15, 5), (15, 7)],
    ('Gyi', 'Gyi', 'Giy', 'Gyi'): [
        (0, 2), (1, 1), (1, 4), (2, 1), (2, 10), (3, 10), (4, 0),
        (5, 3), (5, 7), (6, 4), (6, 10), (8, 2), (8, 3), (9, 0),
        (10, 8), (11, 1), (11, 7), (13, 1), (13, 8)],
    ('Gix', 'Giy', 'Gxi', 'Gcnot'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gix', 'Giy', 'Giy', 'Gii'): [
        (0, 4), (0, 5), (0, 7), (1, 1), (1, 6), (2, 3), (4, 10),
        (5, 4), (6, 8), (7, 4), (7, 10), (8, 8), (8, 9), (10, 5),
        (11, 5), (11, 6), (11, 9), (13, 10), (14, 1), (14, 9)],
    ('Gcnot', 'Gyi', 'Gcnot', 'Gxi'): [
        (0, 0), (1, 0), (1, 10), (4, 0), (4, 4), (5, 10), (7, 9),
        (8, 9), (9, 0), (9, 9), (10, 3), (10, 4), (10, 8), (11, 5),
        (12, 5), (12, 9), (13, 1), (13, 9), (15, 1)],
    ('Gcnot', 'Gix', 'Gcnot', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gcnot', 'Gix', 'Gxi', 'Gxi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gxi', 'Gyi', 'Gix', 'Gix'): [
        (1, 10), (2, 10), (4, 8), (5, 5), (5, 6), (6, 10), (7, 0),
        (7, 5), (7, 6), (7, 8), (8, 5), (12, 5), (13, 0), (13, 2),
        (14, 1)],
    ('Gxi', 'Gyi', 'Gyi', 'Gyi'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gix', 'Gix', 'Gix', 'Giy'): [
        (1, 0), (1, 10), (4, 0), (4, 4), (4, 7), (4, 8), (5, 5),
        (7, 6), (8, 9), (9, 9), (10, 2), (10, 8), (11, 10), (12, 6),
        (12, 9), (13, 9), (15, 1)],
    ('Gxi', 'Gyi', 'Gyi', 'Gii'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Giy', 'Gxi', 'Gyi', 'Gxi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gyi', 'Giy', 'Gyi', 'Gix', 'Gix'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Gyi', 'Gxi', 'Gxi', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Gxi', 'Gix', 'Giy', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gxi', 'Gxi', 'Giy', 'Gyi', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gyi', 'Gcnot', 'Giy', 'Giy', 'Gxi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Gix', 'Gxi', 'Gix', 'Gxi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gix', 'Giy', 'Giy', 'Gix', 'Gxi', 'Gxi'): [
        (1, 1), (2, 5), (4, 3), (5, 5), (6, 3), (7, 1), (10, 2),
        (10, 5), (11, 2), (11, 5), (12, 7), (12, 10), (13, 0),
        (13, 4), (14, 5)],
    ('Gyi', 'Giy', 'Gxi', 'Giy', 'Giy', 'Giy'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gxi', 'Giy', 'Gix', 'Gyi', 'Gix', 'Gix'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gyi', 'Giy', 'Gxi', 'Gyi', 'Gxi', 'Gcnot'): [
        (0, 1), (0, 2), (0, 5), (1, 3), (1, 9), (2, 4), (2, 10),
        (3, 8), (5, 5), (7, 0), (9, 3), (9, 9), (9, 10), (10, 8),
        (12, 2), (12, 6), (14, 6), (15, 0), (15, 5)],
    ('Gxi', 'Gix', 'Giy', 'Gxi', 'Giy', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gxi', 'Gix', 'Giy', 'Giy', 'Gxi', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gyi', 'Gxi', 'Gix', 'Giy', 'Gxi', 'Gix'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Giy', 'Gxi', 'Giy', 'Gix', 'Giy'): [
        (0, 4), (0, 6), (1, 1), (2, 2), (4, 1), (4, 3), (5, 1),
        (5, 3), (6, 10), (8, 2), (8, 8), (9, 4), (10, 7), (12, 1),
        (13, 2), (15, 6), (15, 9)],
    ('Gxi', 'Gxi', 'Gyi', 'Gxi', 'Gyi', 'Gyi'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gyi', 'Gyi', 'Gyi', 'Giy', 'Gyi', 'Gix'): [
        (0, 3), (1, 0), (1, 4), (3, 10), (4, 3), (5, 7), (7, 2),
        (7, 4), (7, 7), (7, 8), (8, 1), (8, 5), (8, 7), (8, 9),
        (9, 2), (9, 6), (10, 3), (14, 10), (15, 4)],
    ('Gix', 'Gix', 'Giy', 'Gix', 'Giy', 'Giy'): [
        (1, 0), (1, 10), (4, 0), (4, 4), (4, 7), (4, 8), (5, 5),
        (7, 6), (8, 9), (9, 9), (10, 2), (10, 8), (11, 10), (12, 6),
        (12, 9), (13, 9), (15, 1)],
    ('Gyi', 'Gxi', 'Gix', 'Gxi', 'Gix', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Giy', 'Gix', 'Gyi', 'Gyi', 'Gix', 'Gxi', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gyi', 'Gxi', 'Giy', 'Gxi', 'Gix', 'Gxi', 'Gyi', 'Giy'): [
        (0, 1), (0, 5), (1, 3), (3, 8), (5, 5), (7, 0), (9, 3),
        (9, 9), (9, 10), (10, 8), (12, 2), (12, 6), (14, 6),
        (15, 0), (15, 5)],
    ('Gix', 'Gix', 'Gyi', 'Gxi', 'Giy', 'Gxi', 'Giy', 'Gyi'): [
        (1, 1), (2, 5), (4, 3), (5, 5), (6, 3), (7, 1), (10, 2),
        (10, 5), (11, 2), (11, 5), (12, 7), (12, 10), (13, 0),
        (13, 4), (14, 5)],
}
