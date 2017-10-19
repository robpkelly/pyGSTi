from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
""" GaugeGroup and derived objects, used primarily in gauge optimization """

import numpy as _np

class GaugeGroup(object):
    def __init__(self, name):
        self.name = name

    def num_params(self):
        return 0

    def get_element(self, param_vec):
        return GaugeGroupElement()

    def get_initial_params(self):
        return _np.array([],'d')

class GaugeGroupElement(object):
    def __init__(self): pass
    def get_transform_matrix(self): return None
    def get_transform_matrix_inverse(self): return None
    def deriv_wrt_params(self,wrtFilter=None): return None
    def to_vector(self): return _np.array([],'d')
    def from_vector(self,v): pass
    def num_params(self): return 0

    
class GateGaugeGroup(GaugeGroup):
    def __init__(self, gate, elementcls, name):
        self.gate = gate
        self.element = elementcls
        GaugeGroup.__init__(self,name)

    def num_params(self):
        return self.gate.num_params()

    def get_element(self, param_vec):
        elgate = self.gate.copy()
        elgate.from_vector(param_vec)
        return self.element(elgate)
    
    def get_initial_params(self):
        return self.gate.to_vector()

class GateGaugeGroupElement(GaugeGroupElement):
    def __init__(self, gate):  
        self.gate = gate
        self._inv_matrix = None
        GaugeGroupElement.__init__(self)

    def get_transform_matrix(self): 
        return _np.asarray(self.gate)

    def get_transform_matrix_inverse(self): 
        if self._inv_matrix is None:
            self._inv_matrix = _np.linalg.inv(_np.asarray(self.gate))
        return self._inv_matrix

    def deriv_wrt_params(self, wrtFilter=None):
        return self.gate.deriv_wrt_params(wrtFilter)

    def to_vector(self):
        return self.gate.to_vector()

    def from_vector(self,v):
        self.gate.from_vector(v)
        self._inv_matrix = None

    def num_params(self):
        return self.gate.num_params()



class FullGaugeGroup(GateGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        gate = _gate.FullyParameterizedGate(_np.identity(dim,'d'))
        GateGaugeGroup.__init__(self, gate, FullGaugeGroupElement, "Full")

class FullGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)


class TPGaugeGroup(GateGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        gate = _gate.TPParameterizedGate(_np.identity(dim,'d'))
        GateGaugeGroup.__init__(self, gate, TPGaugeGroupElement, "TP")

class TPGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)

    def get_transform_matrix_inverse(self): 
        if self._inv_matrix is None:
            self._inv_matrix = _np.linalg.inv(_np.asarray(self.gate))
            self._inv_matrix[0,:] = 0.0 #ensure invers is *exactly* TP
            self._inv_matrix[0,0] = 1.0 # as otherwise small variations can get amplified
        return self._inv_matrix


class DiagGaugeGroup(GateGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        ltrans = _np.identity(dim,'d')
        rtrans = _np.identity(dim,'d')
        baseMx = _np.identity(dim,'d')
        parameterArray = _np.zeros(dim, 'd')
        parameterToBaseIndicesMap = { i: [(i,i)] for i in range(dim) }
        gate = _gate.LinearlyParameterizedGate(baseMx, parameterArray,
                                               parameterToBaseIndicesMap,
                                               ltrans, rtrans, real=True)
        GateGaugeGroup.__init__(self, gate, DiagGaugeGroupElement, "Diagonal")

class DiagGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)


class TPDiagGaugeGroup(TPGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        ltrans = _np.identity(dim,'d')
        rtrans = _np.identity(dim,'d')
        baseMx = _np.identity(dim,'d')
        parameterArray = _np.zeros(dim-1, 'd')
        parameterToBaseIndicesMap = { i: [(i+1,i+1)] for i in range(dim-1) }
        gate = _gate.LinearlyParameterizedGate(baseMx, parameterArray,
                                               parameterToBaseIndicesMap,
                                               ltrans, rtrans, real=True)
        GateGaugeGroup.__init__(self, gate, TPDiagGaugeGroupElement, "TP Diagonal")

class TPDiagGaugeGroupElement(TPGaugeGroupElement):
    def __init__(self, gate):
        TPGaugeGroupElement.__init__(self,gate)


class UnitaryGaugeGroup(GateGaugeGroup):
    def __init__(self, dim, basis):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        gate = _gate.LindbladParameterizedGate(None, _np.identity(dim,'d'),
                                               cptp=True, nonham_basis=[],
                                               ham_basis=basis, mxBasis=basis)
        GateGaugeGroup.__init__(self, gate, UnitaryGaugeGroupElement, "Unitary")

class UnitaryGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)


class SpamGaugeGroup(GateGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        ltrans = _np.identity(dim,'d')
        rtrans = _np.identity(dim,'d')
        baseMx = _np.identity(dim,'d')
        parameterArray = _np.zeros(2, 'd')
        parameterToBaseIndicesMap = { 0: [(0,0)],
                                      1: [(i,i) for i in range(1,dim)] }
        gate = _gate.LinearlyParameterizedGate(baseMx, parameterArray,
                                               parameterToBaseIndicesMap,
                                               ltrans, rtrans, real=True)
        GateGaugeGroup.__init__(self, gate, SpamGaugeGroupElement, "Spam")

class SpamGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)


class TPSpamGaugeGroup(GateGaugeGroup):
    def __init__(self, dim):
        from . import gate as _gate #b/c gate.py imports gaugegroup
        ltrans = _np.identity(dim,'d')
        rtrans = _np.identity(dim,'d')
        baseMx = _np.identity(dim,'d')
        parameterArray = _np.zeros(1, 'd')
        parameterToBaseIndicesMap = { 0: [(i,i) for i in range(1,dim)] }
        gate = _gate.LinearlyParameterizedGate(baseMx, parameterArray,
                                               parameterToBaseIndicesMap,
                                               ltrans, rtrans, real=True)
        GateGaugeGroup.__init__(self, gate, TPSpamGaugeGroupElement, "TP Spam")

class TPSpamGaugeGroupElement(GateGaugeGroupElement):
    def __init__(self, gate):
        GateGaugeGroupElement.__init__(self,gate)
