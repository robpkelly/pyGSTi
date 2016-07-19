import unittest
import warnings
import pygsti
import numpy as np
import os

class StdInputParserTestCase(unittest.TestCase):

    def setUp(self):
        # move working directories
        self.old = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        #Set GateSet objects to "strict" mode for testing
        pygsti.objects.GateSet._strict = True

    def tearDown(self):
        os.chdir(self.old)

    def assertArraysAlmostEqual(self,a,b):
        self.assertAlmostEqual( np.linalg.norm(a-b), 0 )

    def assertWarns(self, callable, *args, **kwds):
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter('always')
            result = callable(*args, **kwds)
            self.assertTrue(len(warning_list) > 0)
        return result


class TestStdInputParser(StdInputParserTestCase):

    def test_strings(self):
        lkup = { '1': ('G1',),
                 '2': ('G1','G2'),
                 '3': ('G1','G2','G3','G4','G5','G6','G7','G8','G9','G10') }

        string_tests = [ ("{}", ()),
                         ("G1", ('G1',)),
                         ("G1G2G3", ('G1','G2','G3')),
                         ("G1(G2)G3", ('G1','G2','G3')),
                         ("G1(G2)^3G3", ('G1','G2','G2','G2','G3')),
                         ("G1(G2G3)^2", ('G1','G2','G3','G2','G3')),
                         ("G1*G2*G3", ('G1','G2','G3')),
                         ("G1 * G2", ('G1','G2')),
                         ("S[1]",('G1',)),
                         ("S[2]",('G1','G2')),
                         ("G1S[1]G3",('G1','G1','G3')),
                         ("S[3][0:4]",('G1', 'G2', 'G3', 'G4')),
                         ("G_my_xG_my_y", ('G_my_x', 'G_my_y')),
                         ("G_my_x*G_my_y", ('G_my_x', 'G_my_y')),
                         ("G_my_x G_my_y", ('G_my_x', 'G_my_y')) ]

        std = pygsti.io.StdInputParser()

        #print "String Tests:"
        for s,expected in string_tests:
            #print "%s ==> " % s, result
            result = std.parse_gatestring(s, lookup=lkup)
            self.assertEqual(result, expected)

        with self.assertRaises(ValueError):
            std.parse_gatestring("FooBar")


    def test_lines(self):
        dataline_tests = [ "G1G2G3           0.1 100",
                           "G1 G2 G3         0.798 100",
                           "G1 (G2 G3)^2 G4  1.0 100" ]

        dictline_tests = [ "1  G1G2G3",
                           "MyFav (G1G2)^3" ]

        std = pygsti.io.StdInputParser()

        self.assertEqual( std.parse_dataline(dataline_tests[0]), (('G1', 'G2', 'G3'), 'G1G2G3', [0.1, 100.0]))
        self.assertEqual( std.parse_dataline(dataline_tests[1]), (('G1', 'G2', 'G3'), 'G1 G2 G3', [0.798, 100.0]))
        self.assertEqual( std.parse_dataline(dataline_tests[2]), (('G1', 'G2', 'G3', 'G2', 'G3', 'G4'), 'G1 (G2 G3)^2 G4', [1.0, 100.0]))
        self.assertEqual( std.parse_dataline("G1G2G3 0.1 100 2.0", expectedCounts=2),
                          (('G1', 'G2', 'G3'), 'G1G2G3', [0.1, 100.0])) #extra col ignored

        with self.assertRaises(ValueError):
            std.parse_dataline("G1G2G3  1.0", expectedCounts=2) #too few cols == error
        with self.assertRaises(ValueError):
            std.parse_dataline("1.0 2.0") #just data cols (no gatestring col!)


        self.assertEqual( std.parse_dictline(dictline_tests[0]), ('1', ('G1', 'G2', 'G3'), 'G1G2G3'))
        self.assertEqual( std.parse_dictline(dictline_tests[1]), ('MyFav', ('G1', 'G2', 'G1', 'G2', 'G1', 'G2'), '(G1G2)^3'))

        #print "Dataline Tests:"
        #for dl in dataline_tests:
        #    print "%s ==> " % dl, std.parse_dataline(dl)
        #print " Dictline Tests:"
        #for dl in dictline_tests:
        #    print "%s ==> " % dl, std.parse_dictline(dl)


    def test_files(self):
        stringfile_test = \
"""#My string file
G1
G1G2
G1(G2G3)^2
"""
        f = open("../temp_test_files/sip_test.list","w")
        f.write(stringfile_test)
        f.close()


        dictfile_test = \
"""#My Dictionary file
# You can't use lookups within this file.
1 G1
2 G1G2
3 G1G2G3G4G5G6
MyFav1 G1G1G1
MyFav2 G2^3
this1  G3*G3*G3
thatOne G1 G2 * G3
"""
        f = open("../temp_test_files/sip_test.dict","w")
        f.write(dictfile_test)
        f.close()

        datafile_test = \
"""#My Data file
#Get string lookup data from the file test.dict
## Lookup = sip_test.dict
## Columns = plus frequency, count total
# OLD Columns = plus count, minus count

#empty string
{}            1.0 100

#simple sequences
G1G2          0.098  100
G2 G3         0.2    100
(G1)^4        0.1   1000

#using lookups
G1 S[1]       0.9999 100
S[MyFav1]G2   0.23   100
G1S[2]^2      0.5     20
S[3][0:4]     0.2      5
G1G2G3G4      0.2      5

#different ways to concatenate gates
G_my_xG_my_y  0.5 24.0
G_my_x*G_my_y 0.5 24.0
G_my_x G_my_y 0.5 24.0
"""
        f = open("../temp_test_files/sip_test.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File without Header
{}            1.0 100
"""
        f = open("../temp_test_files/sip_test2.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with bad syntax
## Columns = plus frequency, count total
{}            1.0 100
G1            0.0 100
FooBar        0.4 100
G3            0.2 100
"""
        f = open("../temp_test_files/sip_test3.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with zero counts
## Columns = plus frequency, count total
{}            1.0 100
G1            0.0 100
G2            0   0
G3            0.2 100
"""
        f = open("../temp_test_files/sip_test4.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with bad columns
## Columns = plus frequency, minus frequency
{}            1.0 0.0
G1            0.0 1.0
G2            0   1.0
G3            0.2 0.8
"""
        f = open("../temp_test_files/sip_test5.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with bad frequency
## Columns = plus frequency, count total
{}            1.0 100
G1            0.0 100
G2            3.4 100
G3            0.2 100
"""
        f = open("../temp_test_files/sip_test6.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with bad counts
## Columns = plus count, count total
{}            30  100
G1            10  100
G2            0.2 100
G3            0.1 100
"""
        f = open("../temp_test_files/sip_test7.data","w")
        f.write(datafile_test)
        f.close()

        datafile_test = \
"""#Data File with bad syntax
## Columns = plus count, count total
{xx}            10  100
"""
        f = open("../temp_test_files/sip_test8.data","w")
        f.write(datafile_test)
        f.close()



        multidatafile_test = \
"""#Multi Data File
## Lookup = sip_test.dict
## Columns = ds1 plus count, ds1 count total, ds2 plus count, ds2 count total
{}            30  100  20 200
G1            10  100  10 200
G2            20  100  5  200
G3            10  100  80 200
"""
        f = open("../temp_test_files/sip_test.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File with default cols
{}            30  100
G1            10  100
G2            20  100
G3            10  100
"""
        f = open("../temp_test_files/sip_test2.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File syntax error
{}            30  100
FooBar        10  100
G2            20  100
"""
        f = open("../temp_test_files/sip_test3.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File bad columns
## Columns = ds1 plus frequency, ds1 minus frequency, ds2 plus count, ds2 count total
{}            0.3  0.4  20 200
G1            0.1  0.5  10 200
G2            0.2  0.3  5  200
"""
        f = open("../temp_test_files/sip_test4.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File frequency out of range and count before frequency
## Columns = ds1 count total, ds1 plus frequency, ds2 plus count, ds2 count total
{}            100  0.3  20 200
G1            100  10   10 200
G2            100  0.2  5  200
"""
        f = open("../temp_test_files/sip_test5.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File count out of range
## Columns = ds1 plus count, ds1 count total, ds2 plus count, ds2 count total
{}            0.3  100  20 200
G1            0.1   100  10 200
G2            20  100  5  200
"""
        f = open("../temp_test_files/sip_test6.multidata","w")
        f.write(multidatafile_test)
        f.close()

        multidatafile_test = \
"""#Multi Data File with bad syntax
## Columns = ds1 plus count, ds1 count total, ds2 plus count, ds2 count total
{xxx}         0.3  100  20 200
"""
        f = open("../temp_test_files/sip_test7.multidata","w")
        f.write(multidatafile_test)
        f.close()


        std = pygsti.io.StdInputParser()

        import pprint
        pp = pprint.PrettyPrinter(indent=4)

        #print " Stringfile Test:"
        strlist = std.parse_stringfile("../temp_test_files/sip_test.list")
        #print " ==> String list:"
        #pp.pprint(strlist)

        #print " Dictfile Test:"
        lkupDict = std.parse_dictfile("../temp_test_files/sip_test.dict")
        #print " ==> Lookup dictionary:"
        #pp.pprint(lkupDict)

        #print " Datafile Test:"
        ds = std.parse_datafile("../temp_test_files/sip_test.data")
        #print " ==> DataSet:\n", ds

        #test file with no header
        ds = std.parse_datafile("../temp_test_files/sip_test2.data")

        #test file with bad data
        with self.assertRaises(ValueError):
            std.parse_datafile("../temp_test_files/sip_test3.data")

        #test file with line(s) containing all zeros => ignore with warning
        self.assertWarns( std.parse_datafile, "../temp_test_files/sip_test4.data" )

        #test file with frequency columns but no count total
        with self.assertRaises(ValueError):
            std.parse_datafile("../temp_test_files/sip_test5.data")

        #test file with out-of-range frequency
        with self.assertRaises(ValueError):
            std.parse_datafile("../temp_test_files/sip_test6.data")

        #test file with out-of-range counts
        with self.assertRaises(ValueError):
            std.parse_datafile("../temp_test_files/sip_test7.data")

        #test file with bad syntax
        with self.assertRaises(ValueError):
            std.parse_datafile("../temp_test_files/sip_test8.data")



        #Multi-dataset tests
        mds = std.parse_multidatafile("../temp_test_files/sip_test.multidata")

        #test file with no header
        mds = std.parse_multidatafile("../temp_test_files/sip_test2.multidata")

        #test file with bad data
        with self.assertRaises(ValueError):
            std.parse_multidatafile("../temp_test_files/sip_test3.multidata")

        #test file with frequency columns but no count total
        with self.assertRaises(ValueError):
            std.parse_multidatafile("../temp_test_files/sip_test4.multidata")

        #test file with out-of-range frequency
        with self.assertRaises(ValueError):
            std.parse_multidatafile("../temp_test_files/sip_test5.multidata")

        #test file with out-of-range counts
        with self.assertRaises(ValueError):
            std.parse_multidatafile("../temp_test_files/sip_test6.multidata")

        #test file with bad syntax
        with self.assertRaises(ValueError):
            std.parse_multidatafile("../temp_test_files/sip_test7.multidata")


        #TODO: add asserts


    def test_GateSetFile(self):

        gatesetfile_test = \
"""#My Gateset file

rho
PauliVec
1.0/sqrt(2) 0 0 1.0/sqrt(2)

E
PauliVec
1.0/sqrt(2) 0 0 -1.0/sqrt(2)

G1
PauliMx
1 0 0 0
0 1 0 0
0 0 0 -1
0 0 1 0

G2
PauliMx
1 0 0 0
0 0 0 1
0 0 1 0
0 -1 0 0
"""

        gatesetfile_test2 = \
"""#My Gateset file specified using non-Pauli format

rho_up
StateVec
1 0

rho_dn
DensityMx
0 0
0 1

E
StateVec
0 1

#G1 = X(pi/2)
G1
UnitaryMx
 1/sqrt(2)   -1j/sqrt(2)
-1j/sqrt(2)   1/sqrt(2)

#G2 = Y(pi/2)
G2
UnitaryMxExp
0           -1j*pi/4.0
1j*pi/4.0  0

#G3 = X(pi)
G3
UnitaryMxExp
0          pi/2
pi/2      0


SPAMLABEL plus = rho_up E
"""

        gatesetfile_test3 = \
"""#My Gateset file with bad StateVec size

rho_up
StateVec
1 0 0

"""

        gatesetfile_test4 = \
"""#My Gateset file with bad DensityMx size

rho_dn
DensityMx
0 0 0
0 1 0
0 0 1

"""

        gatesetfile_test5 = \
"""#My Gateset file with bad UnitaryMx size

#G1 = X(pi/2)
G1
UnitaryMx
 1/sqrt(2)   -1j/sqrt(2)

"""

        gatesetfile_test6 = \
"""#My Gateset file with bad UnitaryMxExp size

#G2 = Y(pi/2)
G2
UnitaryMxExp
0           -1j*pi/4.0 0.0
1j*pi/4.0  0           0.0

"""

        gatesetfile_test7 = \
"""#My Gateset file with bad format spec

G2
FooBar
0   1
1   0

"""

        gatesetfile_test8 = \
"""#My Gateset file specifying 2-Qubit gates using non-Pauli format

rho_up
DensityMx
1 0 0 0
0 0 0 0
0 0 0 0
0 0 0 0

E
DensityMx
0 0 0 0
0 0 0 0
0 0 0 0
0 0 0 1

G1
UnitaryMx
 1/sqrt(2)   -1j/sqrt(2) 0 0
-1j/sqrt(2)   1/sqrt(2)  0 0
 0                0      1 0
 0                0      0 1

G2
UnitaryMxExp
0           -1j*pi/4.0 0 0
1j*pi/4.0  0           0 0
0          0           1 0
0          0           0 1

IDENTITYVEC 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
SPAMLABEL plus = rho_up E
"""




        f = open("../temp_test_files/sip_test.gateset1","w")
        f.write(gatesetfile_test); f.close()

        f = open("../temp_test_files/sip_test.gateset2","w")
        f.write(gatesetfile_test2); f.close()

        f = open("../temp_test_files/sip_test.gateset3","w")
        f.write(gatesetfile_test3); f.close()

        f = open("../temp_test_files/sip_test.gateset4","w")
        f.write(gatesetfile_test4); f.close()

        f = open("../temp_test_files/sip_test.gateset5","w")
        f.write(gatesetfile_test5); f.close()

        f = open("../temp_test_files/sip_test.gateset6","w")
        f.write(gatesetfile_test6); f.close()

        f = open("../temp_test_files/sip_test.gateset7","w")
        f.write(gatesetfile_test7); f.close()

        f = open("../temp_test_files/sip_test.gateset8","w")
        f.write(gatesetfile_test8); f.close()


        gs1 = pygsti.io.read_gateset("../temp_test_files/sip_test.gateset1")
        gs2 = pygsti.io.read_gateset("../temp_test_files/sip_test.gateset2")

        with self.assertRaises(ValueError):
            pygsti.io.read_gateset("../temp_test_files/sip_test.gateset3")
        with self.assertRaises(ValueError):
            pygsti.io.read_gateset("../temp_test_files/sip_test.gateset4")
        with self.assertRaises(ValueError):
            pygsti.io.read_gateset("../temp_test_files/sip_test.gateset5")
        with self.assertRaises(ValueError):
            pygsti.io.read_gateset("../temp_test_files/sip_test.gateset6")
        with self.assertRaises(ValueError):
            pygsti.io.read_gateset("../temp_test_files/sip_test.gateset7")

        gs8 = pygsti.io.read_gateset("../temp_test_files/sip_test.gateset8")

        #print " ==> gateset1:\n", gs1
        #print " ==> gateset2:\n", gs2

        rotXPi   = pygsti.construction.build_gate( [2],[('Q0',)], "X(pi,Q0)")
        rotXPiOv2   = pygsti.construction.build_gate( [2],[('Q0',)], "X(pi/2,Q0)")
        rotYPiOv2   = pygsti.construction.build_gate( [2],[('Q0',)], "Y(pi/2,Q0)")

        self.assertArraysAlmostEqual(gs1.gates['G1'],rotXPiOv2)
        self.assertArraysAlmostEqual(gs1.gates['G2'],rotYPiOv2)
        self.assertArraysAlmostEqual(gs1.preps['rho'], 1/np.sqrt(2)*np.array([1,0,0,1]).reshape(-1,1) )
        self.assertArraysAlmostEqual(gs1.effects['E'], 1/np.sqrt(2)*np.array([1,0,0,-1]).reshape(-1,1) )

        self.assertArraysAlmostEqual(gs2.gates['G1'],rotXPiOv2)
        self.assertArraysAlmostEqual(gs2.gates['G2'],rotYPiOv2)
        self.assertArraysAlmostEqual(gs2.gates['G3'],rotXPi)
        self.assertArraysAlmostEqual(gs2.preps['rho_up'], 1/np.sqrt(2)*np.array([1,0,0,1]).reshape(-1,1) )
        self.assertArraysAlmostEqual(gs2.effects['E'], 1/np.sqrt(2)*np.array([1,0,0,-1]).reshape(-1,1) )








if __name__ == "__main__":
    unittest.main(verbosity=2)
