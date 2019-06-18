import numpy as np
from ..util import BaseCase, unittest

from pygsti.construction import std1Q_XYI as std
from pygsti.objects import slowreplib

try:
    from pygsti.objects import fastreplib
    _FASTREPLIB_LOADED = True
except ImportError:
    _FASTREPLIB_LOADED = False


class ReplibBase:
    def test_DMStateRep(self):
        x = np.zeros(4, 'd')
        staterep = self.replib.DMStateRep(x)  # state rep
        # TODO assert correctness

    def test_DMEffectRep_Dense(self):
        x = np.zeros(4, 'd')
        staterep = self.replib.DMStateRep(x)
        erep = self.replib.DMEffectRep_Dense(x)
        self.assertAlmostEqual(erep.probability(staterep), 0.0)

    def test_DMOpRep_Dense(self):
        x = np.zeros(4, 'd')
        staterep = self.replib.DMStateRep(x)
        g = np.zeros((4, 4), 'd')
        grep = self.replib.DMOpRep_Dense(g)
        staterep2 = grep.acton(staterep)
        self.assertEqual(type(staterep2), self.replib.DMStateRep)


class SlowReplibTester(ReplibBase, BaseCase):
    replib = slowreplib


@unittest.skipUnless(_FASTREPLIB_LOADED, "`pygsti.objects.fastreplib` not built")
class FastReplibTester(ReplibBase, BaseCase):
    @classmethod
    def setUpClass(cls):
        # bind replib during test setup
        # class should still be defined without fastreplib, so it can be shown as skipped
        cls.replib = fastreplib
