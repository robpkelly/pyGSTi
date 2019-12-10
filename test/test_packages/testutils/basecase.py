#Try to quiet-down matplotlib...
import logging
mpl_logger = logging.getLogger('matplotlib')
mpl_logger.setLevel(logging.WARNING)

import numpy as np
import unittest
import warnings
import pygsti
import sys
import os
#import psutil

temp_files    = 'temp_test_files'
compare_files = 'cmp_chk_files'

try:
    from PIL import Image, ImageChops # stackoverflow.com/questions/19230991/image-open-cannot-identify-image-file-python
    haveImageLibs = True
except ImportError:
    haveImageLibs = False

class BaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            basestring #Only defined in Python 2
            cls.versionsuffix = "" #Python 2
        except NameError:
            cls.versionsuffix = "v3" #Python 3

    def setUp(self):
        # move working directories
        try:
            self.old = os.getcwd()
        except OSError as e:
            #print("PSUTIL open files (%d) = " % len(psutil.Process().open_files()), psutil.Process().open_files())
            raise e

        # This will result in the same directory, even though when another module calls this, file points to toolsBaseCase.py
        # However, the result is the same..
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        os.chdir('..') # The test_packages directory

        print('Running tests from %s' % os.getcwd())

        #Set Model objects to "strict" mode for testing
        pygsti.objects.ExplicitOpModel._strict = True

        #enable extra paramter-vector integrity checking
        pygsti.objects.Model._pcheck = True

        #Moved to setUpClass so derived class setUpClass methods can use it.
        #try:
        #    basestring #Only defined in Python 2
        #    self.versionsuffix = "" #Python 2
        #except NameError:
        #    self.versionsuffix = "v3" #Python 3


    def tearDown(self):
        os.chdir(self.old)

    def assertArraysAlmostEqual(self,a,b,places=7):
        self.assertAlmostEqual( np.linalg.norm(a-b), 0, places=places )

    def assertArraysEqual(self,a,b,places=7):
        self.assertTrue(np.array_equal(a,b))

    def assertWarns(self, callable, *args, **kwds):
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter('always')
            result = callable(*args, **kwds)
            self.assertTrue(len(warning_list) > 0)
        return result

    def assertSingleElemArrayAlmostEqual(self, a, b):
        # Ex given an array [[ 0.095 ]] and 0.095, call assertAlmostEqual(0.095, 0.095)
        if a.size > 1:
            raise ValueError('assertSingleElemArrayAlmostEqual should only be used on single element arrays')
        self.assertAlmostEqual(float(a), float(b))

    def assertNoWarnings(self, callable, *args, **kwds):
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter('always')
            result = callable(*args, **kwds)
            self.assertTrue(len(warning_list) == 0)
        return result

    def runSilent(self, callable, *args, **kwds):
        orig_stdout = sys.stdout
        with open(temp_files + '/silent.txt', 'w') as sys.stdout:
            result = callable(*args, **kwds)
        sys.stdout = orig_stdout
        return result

    def assertEqualImages(self, fn1, fn2):
        if haveImageLibs:
            im1 = Image.open(fn1); im2 = Image.open(fn2)
            return ImageChops.difference(im1, im2).getbbox() is None
        else:
            warnings.warn("**** IMPORT: Cannot import Image and/or ImageChops" +
                          ", so Image comparisons in testAnalysis have been" +
                          " disabled.")
            return True

    def assertEqualDatasets(self, ds1, ds2):
        self.assertEqual(len(ds1),len(ds2))
        for circuit in ds1:
            for ol,cnt in ds1[circuit].counts.items():
                self.assertTrue( abs(cnt - ds2[circuit].counts[ol]) < 1.5 )
                #Let counts be off by 1 b/c of rounding
                #self.assertAlmostEqual( cnt, ds2[circuit].counts[ol], places=3 )

    def assertDictsAlmostEqual(self, d1, d2):
        self.assertEqual(set(d1.keys()), set(d2.keys()))
        for k in d1.keys():
            self.assertAlmostEqual(d1[k], d2[k])
