""" Defines the Circuit class """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numbers as _numbers
import numpy as _np
import copy as _copy
import sys as _sys
import itertools as _itertools
import warnings as _warnings

from . import labeldicts as _ld
from ..baseobjs import Label as _Label
from ..baseobjs.label import CircuitLabel as _CircuitLabel
from ..baseobjs import CircuitParser as _CircuitParser
from ..tools import internalgates as _itgs
from ..tools import compattools as _compat
from ..tools import slicetools as _slct


#Internally:
# when static: a tuple of Label objects labelling each top-level circuit layer
# when editable: a list of lists, one per top-level layer, holding just
# the non-LabelTupTup (non-compound) labels.

#Externally, we'd like to do thinks like:
# c = Circuit( LabelList )
# c.append_line("Q0")
# c.append_layer(layer_label)
# c[2]['Q0'] = 'Gx'  # puts Gx:Q0 into circuit (at 3rd layer)
# c[2,'Q0'] = 'Gx'
# c[2,('Q0','Q1')] = Label('Gcnot') # puts Gcnot:Q0:Q1 into circuit
# c[2,('Q1','Q0')] = 'Gcnot'        # puts Gcnot:Q1:Q0 into circuit
# c[2] = (Label('Gx','Q0'), Label('Gy','Q1')) # assigns a circuit layer
# c[2,:] = (Label('Gx','Q0'), Label('Gy','Q1')) # assigns a circuit layer
# del c[2]
# c.insert(2, (Label('Gx','Q0'), Label('Gy','Q1')) ) # inserts a layer
# c[:,'Q0'] = ('Gx','Gy','','Gx') # assigns the Q0 line
# c[1:3,'Q0'] = ('Gx','Gy') # assigns to a part of the Q0 line

def _label_to_nested_lists_of_simple_labels(lbl, default_sslbls=None, always_return_list=True):
    """ Convert lbl into nested lists of *simple* labels """
    if not isinstance(lbl, _Label):  # if not a Label, make into a label,
        lbl = _Label(lbl)  # e.g. a string or list/tuple of labels, etc.
    if lbl.issimple():  # a *simple* label - the elements of our lists
        if lbl.sslbls is None and default_sslbls is not None:
            lbl = _Label(lbl.name, default_sslbls)
        return [lbl] if always_return_list else lbl
    return [_label_to_nested_lists_of_simple_labels(l, default_sslbls, False)
            for l in lbl.components]  # a *list*


def _sslbls_of_nested_lists_of_simple_labels(obj, labels_to_ignore=None):
    """ Get state space labels from a nested lists of simple (not compound) Labels. """
    if isinstance(obj, _Label):
        if labels_to_ignore and (obj in labels_to_ignore):
            return ()
        return obj.sslbls
    else:
        sub_sslbls = [_sslbls_of_nested_lists_of_simple_labels(sub, labels_to_ignore) for sub in obj]
        return None if (None in sub_sslbls) else set(_itertools.chain(*sub_sslbls))


def _accumulate_explicit_sslbls(obj):
    """
    Get all the explicitly given state-space labels within `obj`,
    which can be a Label or a list/tuple of labels.  Returns a *set*.
    """
    ret = set()
    if isinstance(obj, _Label):
        if not obj.issimple():
            for lbl in obj.components:
                ret.update(_accumulate_explicit_sslbls(lbl))
        else:  # a simple label
            if obj.sslbls is not None:  # don't know how to interpet None sslbls
                return set(obj.sslbls)
    else:  # things that aren't labels we assume are iterable
        for lbl in obj:
            ret.update(_accumulate_explicit_sslbls(lbl))
    return ret


def _opSeqToStr(seq, line_labels):
    """ Used for creating default string representations. """
    if len(seq) == 0: return "{}"  # special case of empty operation sequence
    def process_lists(el): return el if not isinstance(el, list) else \
        ('[%s]' % ''.join(map(str, el)) if (len(el) != 1) else str(el[0]))

    if line_labels is None or line_labels == ('*',):
        return ''.join(map(str, map(process_lists, seq)))
    else:
        return ''.join(map(str, map(process_lists, seq))) \
            + "@(" + ','.join(map(str, line_labels)) + ")"


def toLabel(x):
    """ Helper function for converting `x` to a single Label object """
    if isinstance(x, _Label): return x
    # # do this manually when desired, as it "boxes" a circuit being inserted
    #elif isinstance(x,Circuit): return x.to_circuit_label()
    else: return _Label(x)


class Circuit(object):
    """
    A Circuit represents a quantum circuit, consisting of state preparation,
    gates, and measurement operations.  It is composed of some number of "lines",
    typically one per qubit, and stores the operations on these lines as a
    sequence of :class:`Label` objects, one per circuit layer, whose `.sslbls`
    members indicate which line(s) the label belongs on.  When a circuit is
    created with 'editable=True', a rich set of operations may be used to
    construct the circuit in place, after which `done_editing()` should be
    called so that the Circuit can be properly hashed as needed.
    """
    default_expand_subcircuits = True

    def __init__(self, layer_labels=(), line_labels='auto', num_lines=None, editable=False,
                 stringrep=None, name='', check=True, expand_subcircuits="default"):
        """
        TODO: docstring update
        Creates a new Circuit object, encapsulating a quantum circuit.

        You only need to supply the first `layer_labels` argument, though
        usually (except for just 1 or 2 qubits) you'll want to also supply
        `line_labels` or `num_lines`.  If you'll be adding to or altering
        the circuit before using it, you should set `editable=True`.

        Parameters
        ----------
        layer_labels : iterable of Labels
            This argument provides a list of the layer labels specifying the
            state preparations, gates, and measurements for the circuit.  This
            argument can also be a :class:`Circuit`.  Internally this will
            eventually be converted to a list of `Label` objects, one per layer,
            but it may be specified using anything that can be readily converted
            to a Label objects.  For example, any of the following are allowed:

            - `['Gx','Gx']` : X gate on each of 2 layers
            - `[Label('Gx'),Label('Gx')] : same as above
            - `[('Gx',0),('Gy',0)]` : X then Y on qubit 0 (2 layers)
            - `[[('Gx',0),('Gx',1)],[('Gy',0),('Gy',1)]]` : parallel X then Y on qubits 0 & 1

        line_labels : iterable, optional
            The (string valued) label for each circuit line.  If `'auto'`, then
            `line_labels` is taken to be the list of all state-space labels
            present within `layer_labels`.  If there are no such labels (e.g.
            if `layer_labels` contains just gate names like `('Gx','Gy')`), then
            the special value `'*'` is used as a single line label.

        num_lines : int, optional
            Specify this instead of `line_labels` to set the latter to the
            integers between 0 and `num_lines-1`.

        editable : bool, optional
            Whether the created `Circuit` is created in able to be modified.  If
            `True`, then you should call `done_editing()` once the circuit is
            completely assembled, as this makes the circuit read-only and
            allows it to be hashed.

        stringrep : string, optional
            A string representation for the circuit.  If `None` (the default),
            then this will be generated automatically when needed.  One
            reason you'd want to specify this is if you know of a nice compact
            string representation that you'd rather use, e.g. `"Gx^4"` instead
            of the automatically generated `"GxGxGxGx"`.  Another reason is if
            you want to initialize a `Circuit` entirely from a string
            representation you can set `layer_labels` to `None` and `stringrep`
            to any valid (one-line) circuit string.

        name : str, optional
            A name for this circuit (useful if/when used as a block within
            larger circuits).v

        check : bool, optional
            Whether `stringrep` should be checked against `layer_labels` to
            ensure they are consistent, and whether the labels in `layer_labels`
            are a subset of `line_labels`.  The only reason you'd want to set
            this to `False` is if you're absolutely sure `stringrep` and
            `line_labels` are consistent and want to save computation time.
        """
        layer_labels_objs = None  # layer_labels elements as Label objects (only if needed)
        if expand_subcircuits == "default":
            expand_subcircuits = Circuit.default_expand_subcircuits
        if expand_subcircuits and layer_labels is not None:
            layer_labels_objs = tuple(_itertools.chain(*[x.expand_subcircuits() for x in map(toLabel, layer_labels)]))
            #print("DB: Layer labels = ",layer_labels_objs)

        #Parse stringrep if needed
        if stringrep is not None and (layer_labels is None or check == True):
            cparser = _CircuitParser()
            cparser.lookup = None  # lookup - functionality removed as it wasn't used
            chk, chk_labels = cparser.parse(stringrep)  # tuple of Labels
            if expand_subcircuits and chk is not None:
                chk = tuple(_itertools.chain(*[x.expand_subcircuits() for x in map(toLabel, chk)]))
                #print("DB: Check Layer labels = ",chk)

            if layer_labels is None:
                layer_labels = chk
            else:  # check == True
                if layer_labels_objs is None:
                    layer_labels_objs = tuple(map(toLabel, layer_labels))
                if layer_labels_objs != tuple(chk):
                    #print("DB: ",layer_labels_objs,"VS",tuple(chk))
                    raise ValueError(("Error intializing Circuit: "
                                      " `layer_labels` and `stringrep` do not match: %s != %s\n"
                                      "(set `layer_labels` to None to infer it from `stringrep`)")
                                     % (layer_labels, stringrep))
            if chk_labels is not None:
                if line_labels == 'auto':
                    line_labels = chk_labels
                elif tuple(line_labels) != chk_labels:
                    raise ValueError(("Error intializing Circuit: "
                                      " `line_labels` and `stringrep` do not match: %s != %s (from %s)\n"
                                      "(set `line_labels` to None to infer it from `stringrep`)")
                                     % (line_labels, chk_labels, stringrep))

        if layer_labels is None:
            raise ValueError("Must specify `stringrep` when `layer_labels` is None")

        # Set self._line_labels
        if line_labels == 'auto':
            if layer_labels_objs is None:
                layer_labels_objs = tuple(map(toLabel, layer_labels))
            explicit_lbls = _accumulate_explicit_sslbls(layer_labels_objs)
            if len(explicit_lbls) == 0:
                if num_lines is not None:
                    assert(num_lines >= 0), "`num_lines` must be >= 0!"
                    if len(layer_labels) > 0:
                        assert(num_lines > 0), "`num_lines` must be > 0!"
                    self._line_labels = tuple(range(num_lines))
                elif len(layer_labels) > 0:
                    self._line_labels = ('*',)  # special single line-label when no line labels are given
                else:
                    self._line_labels = ()  # empty circuit can have zero line labels
            else:
                self._line_labels = tuple(sorted(explicit_lbls))
        else:
            explicit_lbls = None
            self._line_labels = tuple(line_labels)

        if (num_lines is not None) and (num_lines != len(self.line_labels)):
            if num_lines > len(self.line_labels) and \
               set(self.line_labels).issubset(set(range(num_lines))):
                # special case where we just add missing integer-labeled line(s)
                self._line_labels = tuple(range(num_lines))
            else:
                raise ValueError("`num_lines` was expected to be %d but equals %d!" %
                                 (len(self.line_labels), num_lines))

        if check:
            if explicit_lbls is None:
                if layer_labels_objs is None:
                    layer_labels_objs = tuple(map(toLabel, layer_labels))
                explicit_lbls = _accumulate_explicit_sslbls(layer_labels_objs)
            if not set(explicit_lbls).issubset(self.line_labels):
                raise ValueError("line labels must contain at least %s" % str(explicit_lbls))

        #Set self._labels, which is either a nested list of simple labels (non-static case)
        #  or a tuple of Label objects (static case)
        if not editable:
            if layer_labels_objs is None:
                layer_labels_objs = tuple(map(toLabel, layer_labels))
            self._labels = layer_labels_objs
        else:
            self._labels = [_label_to_nested_lists_of_simple_labels(layer_lbl)
                            for layer_lbl in layer_labels]

        #Set self._static, _reps, _name
        self._static = not editable
        #self._reps = reps # repetitions: default=1, which remains unless we initialize from a CircuitLabel...
        self._name = name  # can be None
        self._str = stringrep if self._static else None  # can be None (lazy generation)
        self._times = None  # for FUTURE expansion
        self.auxinfo = {}  # for FUTURE expansion / user metadata

        # # Special case: layer_labels can be a single CircuitLabel or Circuit
        # # (Note: a Circuit would work just fine, as a list of layers, but this performs some extra checks)
        # isCircuit = isinstance(layer_labels, _Circuit)
        # isCircuitLabel = isinstance(layer_labels, _CircuitLabel)
        # if isCircuitLabel:
        #    assert(line_labels is None or line_labels == "auto" or line_labels == expected_line_labels), \
        #        "Given `line_labels` (%s) are inconsistent with CircuitLabel's sslbls (%s)" \
        #        % (str(line_labels),str(layer_labels.sslbls))
        #    assert(num_lines is None or layer_labels.sslbls == tuple(range(num_lines))), \
        #        "Given `num_lines` (%d) is inconsistend with CircuitLabel's sslbls (%s)" \
        #        % (num_lines,str(layer_labels.sslbls))
        #    if name is None: name = layer_labels.name # Note: `name` can be used to rename a CircuitLabel

        #    self._line_labels = layer_labels.sslbls
        #    self._reps = layer_labels.reps
        #    self._name = name
        #    self._static = not editable

    def as_label(self, nreps=1):
        """TODO: docstring """
        eff_line_labels = None if self._line_labels == ('*',) else self._line_labels  # special case
        return _CircuitLabel(self._name, self._labels, eff_line_labels, nreps)

    @property
    def line_labels(self):
        return self._line_labels

    @line_labels.setter
    def line_labels(self, value):
        if value == self._line_labels: return
        #added_line_labels = set(value) - set(self._line_labels) # it's always OK to add lines
        removed_line_labels = set(self._line_labels) - set(value)
        if removed_line_labels:
            idling_line_labels = set(self.get_idling_lines())
            removed_not_idling = removed_line_labels - idling_line_labels
            if removed_not_idling and self._static:
                raise ValueError("Cannot remove non-idling lines %s from a read-only circuit!" %
                                 str(removed_not_idling))
            else:
                self.delete_lines(tuple(removed_not_idling))
        self._line_labels = value

    @property
    def name(self):
        return self._name

    #TODO REMOVE
    #@property
    #def reps(self):
    #    return self._reps

    @property
    def tup(self):
        """ This Circuit as a standard Python tuple of layer Labels."""
        if self._static:
            return self._labels
        else:
            return tuple([toLabel(layer_lbl) for layer_lbl in self._labels])

    @property
    def str(self):
        """ The Python string representation of this Circuit."""
        if self._str is None:
            generated_str = _opSeqToStr(self._labels, self.line_labels)  # lazy generation
            if self._static:  # if we're read-only then cache the string one and for all,
                self._str = generated_str  # otherwise keep generating it as needed (unless it's set by the user?)
            return generated_str
        else:
            return self._str

    def _labels_lines_str(self):
        """ Split the string representation up into layer-labels & line-labels parts """
        if '@' in self.str:
            return self.str.split('@')
        else:
            return self.str, None

    @str.setter
    def str(self, value):
        """ The Python string representation of this Circuit."""
        assert(not self._static), \
            ("Cannot edit a read-only circuit!  "
             "Set editable=True when calling pygsti.obj.Circuit to create editable circuit.")
        cparser = _CircuitParser()
        chk, chk_labels = cparser.parse(value)

        if not all([my_layer in (chk_lbl, [chk_lbl]) for chk_lbl, my_layer in zip(chk, self._labels)]):
            raise ValueError(("Cannot set .str to %s because it doesn't"
                              " evaluate to %s (this circuit)") %
                             (value, self.str))
        if chk_labels is not None:
            if tuple(self.line_labels) != chk_labels:
                raise ValueError(("Cannot set .str to %s because line labels evaluate to"
                                  " %s which is != this circuit's line labels (%s).") %
                                 (value, chk_labels, str(self.line_labels)))
        self._str = value

    def __hash__(self):
        if not self._static:
            _warnings.warn(("Editable circuit is being converted to read-only"
                            " mode in order to hash it.  You should call"
                            " circuit.done_editing() beforehand."))
            self.done_editing()
        return hash(self._labels)  # just hash the tuple of labels

    def __len__(self):
        return len(self._labels)

    def __iter__(self):
        return self._labels.__iter__()

    def __add__(self, x):
        if not isinstance(x, Circuit):
            raise ValueError("Can only add Circuits objects to other Circuit objects")
        if self.str is None or x.str is None:
            s = None
        else:
            mystr, _ = self._labels_lines_str()
            xstr, _ = x._labels_lines_str()

            if mystr != "{}":
                s = (mystr + xstr) if xstr != "{}" else mystr
            else: s = xstr

        editable = not self._static or not x._static
        added_labels = tuple([l for l in x.line_labels if l not in self.line_labels])
        new_line_labels = self.line_labels + added_labels
        if new_line_labels != ('*',):
            s += "@(" + ','.join(map(str, new_line_labels)) + ")"  # matches to _opSeqToStr in circuit.py!
        return Circuit(self.tup + x.tup, new_line_labels,
                       None, editable, s, check=False)

    def repeat(self, ntimes, expand="default"):
        if expand == "default": expand = Circuit.default_expand_subcircuits
        assert((_compat.isint(ntimes) or _np.issubdtype(ntimes, int)) and ntimes >= 0)
        mystr, mylines = self._labels_lines_str()
        if ntimes > 1: s = "(%s)^%d" % (mystr, ntimes)
        elif ntimes == 1: s = "(%s)" % mystr
        else: s = "{}"
        if mylines is not None:
            s += "@" + mylines  # add line labels
        if ntimes > 1 and expand == False:
            reppedCircuitLbl = self.as_label(nreps=ntimes)
            return Circuit((reppedCircuitLbl,), self.line_labels, None, not self._static, s, check=False)
        else:
            # just adds parens to string rep & copies
            return Circuit(self.tup * ntimes, self.line_labels, None, not self._static, s, check=False)

    def __mul__(self, x):
        return self.repeat(x)

    def __pow__(self, x):  # same as __mul__()
        return self.__mul__(x)

    def __eq__(self, x):
        if x is None: return False
        xtup = x.tup if isinstance(x, Circuit) else tuple(x)
        return self.tup == xtup  # better than x.tup since x can be a tuple

    def __lt__(self, x):
        return self.tup.__lt__(tuple(x))

    def __gt__(self, x):
        return self.tup.__gt__(tuple(x))

    def number_of_lines(self):
        """
        The number of lines in this circuit.

        Returns
        -------
        int
        """
        return len(self.line_labels)

    def copy(self, editable="auto"):
        """
        Returns a copy of the circuit.

        Parameters
        ----------
        editable : {True,False,"auto"}
            Whether returned copy is editable.  If `"auto"` is given,
            then the copy is editable if and only if this Circuit is.

        Returns
        -------
        Circuit
        """
        if editable == "auto": editable = not self._static
        return Circuit(self.tup, self.line_labels, None, editable, self._str, check=False)

    def clear(self):
        """
        Removes all the gates in a circuit (preserving the number of lines).
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        self._labels = []

    def _proc_layers_arg(self, layers):
        """ Pre-process the layers argument used by many methods """
        if layers is None:
            layers = list(range(len(self._labels)))
        elif isinstance(layers, slice):
            if layers.start is None and layers.stop is None:
                layers = ()
            else:
                layers = _slct.indices(layers, len(self._labels))
        elif not isinstance(layers, (list, tuple)):
            layers = (layers,)
        return layers

    def _proc_lines_arg(self, lines):
        """ Pre-process the lines argument used by many methods """
        if lines is None:
            lines = self.line_labels
        elif isinstance(lines, slice):
            if lines.start is None and lines.stop is None:
                lines = ()
            else:
                lines = _slct.indices(lines)
        elif not isinstance(lines, (list, tuple)):
            lines = (lines,)
        return lines

    def _proc_key_arg(self, key):
        """ Pre-process the key argument used by many methods """
        if isinstance(key, tuple):
            if len(key) != 2: return IndexError("Index must be of the form <layerIndex>,<lineIndex>")
            layers = key[0]
            lines = key[1]
        else:
            layers = key
            lines = None
        return layers, lines

    def _layer_components(self, ilayer):
        """ Get the components of the `ilayer`-th layer as a list/tuple. """
        #(works for static and non-static Circuits)
        if self._static:
            if self._labels[ilayer].issimple(): return [self._labels[ilayer]]
            else: return self._labels[ilayer].components
        else:
            return self._labels[ilayer] if isinstance(self._labels[ilayer], list) \
                else [self._labels[ilayer]]

    def _remove_layer_component(self, ilayer, indx):
        """ Removes the `indx`-th component from the `ilayer`-th layer """
        #(works for special case when layer is just a *single* component)
        assert(not self._static), "Cannot edit a read-only circuit!"
        if isinstance(self._labels[ilayer], list):
            del self._labels[ilayer][indx]
        else:
            assert(indx == 0), "Only index 0 exists for a single-simple-Label level"
            # don't remove *layer* - when final component is removed we're left with an empty layer
            self._labels[ilayer] = []

    def _append_layer_component(self, ilayer, val):
        """ Add `val` to the `ilayer`-th layer """
        #(works for special case when layer is just a *single* component)
        assert(not self._static), "Cannot edit a read-only circuit!"
        if isinstance(self._labels[ilayer], list):
            self._labels[ilayer].append(val)
        else:  # currently ilayer-th layer is a single component!
            self._labels[ilayer] = [self._labels[ilayer], val]

    def _replace_layer_component(self, ilayer, indx, val):
        assert(not self._static), "Cannot edit a read-only circuit!"
        """ Replace `indx`-th component of `ilayer`-th layer with `val` """
        #(works for special case when layer is just a *single* component)
        if isinstance(self._labels[ilayer], list):
            self._labels[ilayer][indx] = val
        else:
            assert(indx == 0), "Only index 0 exists for a single-simple-Label level"
            self._labels[ilayer] = val

    def get_labels(self, layers=None, lines=None, strict=True):
        """
        Get a subregion - a "rectangle" - of this Circuit.

        This can be used to select multiple layers and/or lines of this Circuit.
        The `strict` argument controls whether gates need to be entirely within
        the given rectangle or can be intersecting it.  If `layers` is a single
        integer then a :class:`Label` is returned (representing a layer or a
        part of a layer), otherwise a :class:`Circuit` is returned.

        Parameters
        ----------
        layers : int, slice, or list/tuple of ints
            Which layers to select (the horizontal dimension of the selection
            rectangle).  Layers are always selected by index, and this
            argument can be a single (integer) index - in which case a `Label`
            is returned - or multiple indices as given by a slice or list -
            in which case a `Circuit` is returned.  Note that, even though
            we speak of a "rectangle", layer indices do not need to be
            contiguous.  The special value `None` selects all layers.

        lines : str/int, slice, or list/tuple of strs/ints
            Which lines to select (the vertical dimension of the selection
            rectangle).  Lines are selected by their line-labels (elements
            of the circuit's `.line_labels` property), which can be strings
            and/or integers.  A single or multiple line-labels can be
            specified.  If the line labels are integers a slice can be used,
            otherwise a list or tuple of labels is the only way to select
            multiple of them.  Note that line-labels do not need to be
            contiguous. The special value `None` selects all lines.

        strict : bool, optional
            When `True`, only gates lying completely within the selected
            region are included in the return value.  If a gate straddles
            the region boundary (e.g. if we select just line `1` and the
            circuit contains `"Gcnot:1:2"`) then it is *silently* not-included
            in the returned label or circuit.  If `False`, then gates which
            straddle the region boundary *are* included.  Note that this may
            result in a `Label` or `Circuit` containing more line labels than
            where requested in the call to `get_labels(...)`..

        Returns
        -------
        Label or Circuit
            The requested portion of this circuit, given as a `Label` if
            `layers` is a single integer and as a `Circuit` otherwise.
            Note: if you want a `Circuit` when only selecting one layer,
            set `layers` to a slice or tuple containing just a single index.
        """

        nonint_layers = not isinstance(layers, int)
        layers = self._proc_layers_arg(layers)
        lines = self._proc_lines_arg(lines)
        if len(layers) == 0 or len(lines) == 0:
            return Circuit((), lines, None, not self._static, stringrep=None, check=False) \
                if nonint_layers else None  # zero-area region

        ret = []
        if self._static:
            def get_sslbls(lbl): return lbl.sslbls
        else:
            get_sslbls = _sslbls_of_nested_lists_of_simple_labels

        for i in layers:
            ret_layer = []
            for l in self._layer_components(i):  # loop over labels in this layer
                sslbls = get_sslbls(l)
                if sslbls is None:
                    ## add in special case of identity layer
                    #if (isinstance(l,_Label) and l.name == self.identity): # ~ is_identity_layer(l)
                    #    ret_layer.append(l); continue
                    sslbls = set(self.line_labels)  # otherwise, treat None sslbs as *all* labels
                else:
                    sslbls = set(sslbls)
                if (strict and sslbls.issubset(lines)) or \
                   (not strict and len(sslbls.intersection(lines)) >= 0):
                    ret_layer.append(l)
            ret.append(ret_layer)

        if nonint_layers:
            if not strict: lines = "auto"  # since we may have included lbls on other lines
            # don't worry about string rep for now...
            return Circuit(ret, lines, None, not self._static, stringrep=None, check=False)
        else:
            return _Label(ret[0])

    def set_labels(self, lbls, layers=None, lines=None):
        """
        Write `lbls`, which can be anything that can be interpreted as a
        :class:`Label` or list of labels to the block defined by the
        `layers` and `lines` arguments.

        Parameters
        ----------
        lbls : Label, list/tuple of Labels, or Circuit
            When `layers` is a single integer, `lbls` should be a single
            "layer label" of type `Label`.  Otherwise, `lbls` should be
            a list or tuple of `Label` objects with length equal to the
            number of layers being set.  A `Circuit` may also be used in this
            case.

        layers : int, slice, or list/tuple of ints
            Which layers to set (the horizontal dimension of the destination
            rectangle).  Layers are always selected by index, and this
            argument can be a single (integer) index  or multiple indices as
            given by a slice or list.  Note that these indices do not need to be
            contiguous.  The special value `None` stands for all layers.

        lines : str/int, slice, or list/tuple of strs/ints
            Which lines to set (the vertical dimension of the destination
            rectangle).  Lines are selected by their line-labels, which can be
            strings and/or integers.  A single or multiple line-labels can be
            specified.  If the line labels are integers a slice can be used,
            otherwise a list or tuple of labels is the only way to specify
            multiple of them.  The line-labels do not need to be contiguous.
            The special value `None` stands for all lines, and in this case
            new lines will be created if there are new state-space labels
            in `lbls` (when `lines` is not `None` an error is raised instead).

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        #Note: this means self._labels contains nested lists of simple labels

        #Convert layers to a list/tuple of layer indices
        all_layers = bool(layers is None)  # whether we're assigning to *all* layers
        int_layers = isinstance(layers, int)
        layers = self._proc_layers_arg(layers)

        #Convert lines to a list/tuple of line (state space) labels
        all_lines = bool(lines is None)  # whether we're assigning to *all* lines
        lines = self._proc_lines_arg(lines)

        #make lbls into either:
        # 1) a single Label (possibly compound) if layers is an int
        # 2) a tuple of Labels (possibly compound) otherwise
        if int_layers:
            lbls = toLabel(lbls)
            lbls_sslbls = None if (lbls.sslbls is None) else set(lbls.sslbls)
        else:
            if isinstance(lbls, Circuit):
                lbls = lbls.tup  # circuit layer labels as a tuple
            assert(isinstance(lbls, (tuple, list))), \
                ("When assigning to a layer range (even w/len=1) `lbls` "
                 "must be  a *list or tuple* of label-like items")
            lbls = tuple(map(toLabel, lbls))
            lbls_sslbls = None if any([l.sslbls is None for l in lbls]) \
                else set(_itertools.chain(*[l.sslbls for l in lbls]))

        if len(layers) == 0 or len(lines) == 0: return  # zero-area block

        #If we're assigning to multiple layers, then divide up lbls into pieces to place in each layer
        if all_layers:  # then we'll add new layers as needed
            while len(lbls) > len(self._labels):
                self._labels.append([])
        elif len(layers) > 1:
            assert(len(layers) == len(lbls)), \
                "Block width mismatch: assigning %d layers to %d layers" % (len(lbls), len(layers))

        # when processing `lbls`: if a label has sslbls == None, then applies to all
        # the lines being assigned.  If sslbl != None, then the labels must be
        # contained within the line labels being assigned (unless we're allowed to expand)
        if lbls_sslbls is not None:
            new_line_labels = set(lbls_sslbls) - set(self.line_labels)
            if all_lines:  # then allow new lines to be added
                if len(new_line_labels) > 0:
                    self._line_labels = self.line_labels + tuple(sorted(new_line_labels))  # sort?
            else:
                assert(len(new_line_labels) == 0), "Cannot add new lines %s" % str(new_line_labels)
                assert(set(lbls_sslbls).issubset(lines)), \
                    "Unallowed state space labels: %s" % str(set(lbls_sslbls) - set(lines))

        assert(set(lines).issubset(self.line_labels)), \
            ("Specified lines (%s) must be a subset of this circuit's lines"
             " (%s).") % (str(lines), str(self.line_labels))

        #remove all labels in block to be assigned
        self._clear_labels(layers, lines)

        def_sslbls = None if all_lines else lines
        if not int_layers:
            for i, lbls_comp in zip(layers, lbls):
                self._labels[i].extend(_label_to_nested_lists_of_simple_labels(lbls_comp, def_sslbls))
        else:  # single layer using integer layer index (so lbls is a single Label)
            self._labels[layers[0]].extend(_label_to_nested_lists_of_simple_labels(lbls, def_sslbls))

    def insert_idling_layers(self, insertBefore, numToInsert, lines=None):
        """
        Inserts into this circuit one or more idling (blank) layers.

        By default, complete layer(s) are inserted.  The `lines` argument
        allows you to insert partial layers (on only a subset of the lines).

        Parameters
        ----------
        insertBefore : int
            The layer index to insert the new layers before.  Can be from 0
            (insert at the beginning) to `len(self)-1` (insert at end), and
            negative indexing can be used to insert relative to the last layer.
            The special value `None` inserts at the end.

        numToInsert : int
            The number of new layers to insert.

        lines : str/int, slice, or list/tuple of strs/ints, optional
            Which lines should have new layers (blank circuit space)
            inserted into them.  A single or multiple line-labels can be
            specified, similarly as in :method:`get_labels`.  The default
            value `None` stands for *all* lines.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        if insertBefore is None: insertBefore = len(self._labels)
        elif insertBefore < 0: insertBefore = len(self._labels) + insertBefore

        if lines is None:  # insert complete layers
            for i in range(numToInsert):
                self._labels.insert(insertBefore, [])
        else:  # insert layers only on given lines - shift existing labels to right
            for i in range(numToInsert):
                self._labels.append([])  # add blank layers at end
            for i in range(insertBefore, insertBefore + numToInsert):
                # move labels on `lines` to layer i+numToInsert
                inds_to_delete = []
                for k, lbl in enumerate(self._labels[i]):
                    sslbls = _sslbls_of_nested_lists_of_simple_labels(lbl)
                    if len(sslbls.intersection(lines)) > 0:  # then we need to move this label
                        if not sslbls.issubset(lines):
                            raise ValueError("Cannot shift a block that is straddled by %s!" % _Label(lbl))
                            #FUTURE: recover from this error gracefully so we don't leave the circuit in an intermediate
                            #state?
                        inds_to_delete.append(k)  # remove it from current layer
                        self._labels[i + numToInsert].append(lbl)  # and put it in the destination layer
                for k in reversed(inds_to_delete):
                    del self._labels[i][k]

    def append_idling_layers(self, numToInsert, lines=None):
        """
        Adds one or more idling (blank) layers to the end of this circuit.

        By default, complete layer(s) are appended.  The `lines` argument
        allows you to add partial layers (on only a subset of the lines).

        Parameters
        ----------
        numToInsert : int
            The number of new layers to append.

        lines : str/int, slice, or list/tuple of strs/ints, optional
            Which lines should have new layers (blank circuit space)
            inserted into them.  A single or multiple line-labels can be
            specified, similarly as in :method:`get_labels`.  The default
            value `None` stands for *all* lines.

        Returns
        -------
        None
        """
        self.insert_idling_layers(None, numToInsert, lines)

    def insert_labels_into_layers(self, lbls, layerToInsertBefore, lines=None):
        """
        Inserts into this circuit the contents of `lbls` into new full or
        partial layers.

        By default, complete layer(s) are inserted.  The `lines` argument
        allows you to insert partial layers (on only a subset of the lines).

        Parameters
        ----------
        lbls : list/tuple of Labels, or Circuit
            The full or partial layer labels to insert.  The length of this
            list, tuple, or circuit determines the number of layers which are
            inserted.

        layerToInsertBefore : int
            The layer index to insert `lbls` before.  Can be from 0
            (insert at the beginning) to `len(self)-1` (insert at end), and
            negative indexing can be used to insert relative to the last layer.
            The special value `None` inserts at the end.

        lines : str/int, slice, or list/tuple of strs/ints, optional
            Which lines should have `lbls` inserted into them.  Currently
            this can only be a larger set than the set of line labels present
            in `lbls` (in future versions this may allow filtering of `lbls`).
            value `None` stands for *all* lines.

        Returns
        -------
        None
        """
        if isinstance(lbls, Circuit): lbls = lbls.tup
        # lbls is expected to be a list/tuple of Label-like items, one per inserted layer
        lbls = tuple(map(toLabel, lbls))
        numLayersToInsert = len(lbls)
        self.insert_idling_layers(layerToInsertBefore, numLayersToInsert, lines)  # make space
        self.set_labels(lbls, slice(layerToInsertBefore, layerToInsertBefore + numLayersToInsert), lines)
        #Note: set_labels expects lbls to be a list/tuple of Label-like items b/c it's given a layer *slice*

    def insert_idling_lines(self, insertBefore, line_labels):
        """
        Insert one or more idling (blank) lines into this circuit.

        Parameters
        ----------
        insertBefore : str or int
            The line label to insert new lines before.  The special value `None`
            inserts lines at the bottom of this circuit.

        line_labels : list or tuple
            A list or tuple of the new line labels to insert (can be integers
            and/or strings).

        Returns
        -------
        None
        """
        #assert(not self._static),"Cannot edit a read-only circuit!"
        # Actually, this is OK even for static circuits because it won't affect the hashed value (labels only)
        if insertBefore is None:
            i = len(self.line_labels)
        else:
            i = self.line_labels.index(insertBefore)
        self._line_labels = self.line_labels[0:i] + tuple(line_labels) + self.line_labels[i:]

    def append_idling_lines(self, line_labels):
        """
        Add one or more idling (blank) lines onto the bottom of this circuit.

        Parameters
        ----------
        line_labels : list or tuple
            A list or tuple of the new line labels to insert (can be integers
            and/or strings).

        Returns
        -------
        None
        """
        self.insert_idling_lines(None, line_labels)

    def insert_labels_as_lines(self, lbls, layerToInsertBefore=None, lineToInsertBefore=None, line_labels="auto"):
        """
        Inserts into this circuit the contents of `lbls` into new lines.

        By default, `lbls` is inserted at the beginning of the new lines(s). The
        `layerToInsertBefore` argument allows you to insert `lbls` beginning at
        a layer of your choice.

        Parameters
        ----------
        lbls : list/tuple of Labels, or Circuit
            A list of layer labels to insert as new lines.  The state-space
            (line) labels within `lbls` must not overlap with that of this
            circuit or an error is raised.  If `lbls` contains more layers
            than this circuit currently has, new layers are added automatically.

        layerToInsertBefore : int
            The layer index to insert `lbls` before.  Can be from 0
            (insert at the beginning) to `len(self)-1` (insert at end), and
            negative indexing can be used to insert relative to the last layer.
            The default value of `None` inserts at the beginning.

        lineToInsertBefore : str or int
            The line label to insert the new lines before.  The default value
            of `None` inserts lines at the bottom of the circuit.

        line_labels : list, tuple, or "auto"
            The labels of the new lines being inserted.  If `"auto"`, then
            these are inferred from `lbls`.

        Returns
        -------
        None
        """
        if layerToInsertBefore is None: layerToInsertBefore = 0
        elif layerToInsertBefore < 0: layerToInsertBefore = len(self._labels) + layerToInsertBefore

        if isinstance(lbls, Circuit):
            if line_labels == "auto": line_labels = lbls.line_labels
            lbls = lbls.tup
        elif line_labels == "auto":
            line_labels = tuple(sorted(_accumulate_explicit_sslbls(lbls)))

        existing_labels = set(line_labels).intersection(self.line_labels)
        if len(existing_labels) > 0:
            raise ValueError("Cannot insert line(s) labeled %s - they already exist!" % str(existing_labels))

        self.insert_idling_lines(lineToInsertBefore, line_labels)

        #add additional layers to end of circuit if new lines are longer than current circuit depth
        numLayersToInsert = len(lbls)
        if layerToInsertBefore + numLayersToInsert > len(self._labels):
            self.append_idling_layers(layerToInsertBefore + numLayersToInsert - len(self._labels))

        #Note: set_labels expects lbls to be a list/tuple of Label-like items b/c it's given a layer *slice*
        self.set_labels(lbls, slice(layerToInsertBefore, layerToInsertBefore + numLayersToInsert), line_labels)

    def append_labels_as_lines(self, lbls, layerToInsertBefore=None, line_labels="auto"):
        """
        Adds the contents of `lbls` as new lines at the bottom of this circuit.

        By default, `lbls` is inserted at the beginning of the new lines(s). The
        `layerToInsertBefore` argument allows you to insert `lbls` beginning at
        a layer of your choice.

        Parameters
        ----------
        lbls : list/tuple of Labels, or Circuit
            A list of layer labels to append as new lines.  The state-space
            (line) labels within `lbls` must not overlap with that of this
            circuit or an error is raised.  If `lbls` contains more layers
            than this circuit currently has, new layers are added automatically.

        layerToInsertBefore : int
            The layer index to insert `lbls` before.  Can be from 0
            (insert at the beginning) to `len(self)-1` (insert at end), and
            negative indexing can be used to insert relative to the last layer.
            The default value of `None` inserts at the beginning.

        line_labels : list, tuple, or "auto"
            The labels of the new lines being added.  If `"auto"`, then
            these are inferred from `lbls`.

        Returns
        -------
        None
        """
        return self.insert_labels_as_lines(lbls, layerToInsertBefore, None, line_labels)

    def _clear_labels(self, layers, lines, clear_straddlers=False):
        """ remove all labels in a block given by layers and lines
            Note: layers & lines must be lists/tuples of values; they can't be slices or single vals
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        for i in layers:
            new_layer = []
            for l in self._layer_components(i):  # loop over labels in this layer
                sslbls = _sslbls_of_nested_lists_of_simple_labels(l)
                sslbls = set(self.line_labels) if (sslbls is None) else set(sslbls)
                if len(sslbls.intersection(lines)) == 0:
                    new_layer.append(l)
                elif not clear_straddlers and not sslbls.issubset(lines):
                    raise ValueError("Cannot operate on a block that is straddled by %s!" % str(_Label(l)))
            self._labels[i] = new_layer

    def clear_labels(self, layers=None, lines=None, clear_straddlers=False):
        """
        Removes all the gates within the given circuit region.  Does not reduce
        the number of layers or lines.

        Parameters
        ----------
        layers : int, slice, or list/tuple of ints
            Defines the horizontal dimension of the region to clear.  See
            :method:`get_labels` for details.

        lines : str/int, slice, or list/tuple of strs/ints
            Defines the vertical dimension of the region to clear.  See
            :method:`get_labels` for details.

        clear_straddlers : bool, optional
            Whether or not gates which straddle cleared and non-cleared lines
            should be cleared.  If `False` and straddling gates exist, an error
            will be raised.

        Returns
        -------
        None
        """
        layers = self._proc_layers_arg(layers)
        lines = self._proc_lines_arg(lines)
        self._clear_labels(layers, lines, clear_straddlers)

    def delete_layers(self, layers=None):
        """
        Deletes one or more layers from the circuit.

        Parameters
        ----------
        layers : int, slice, or list/tuple of ints
            The layer index or indices to delete.  See :method:`get_labels`
            for details.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        layers = self._proc_layers_arg(layers)
        for i in reversed(sorted(layers)):
            del self._labels[i]

    def delete_lines(self, lines, delete_straddlers=False):
        """
        Deletes one or more lines from the circuit.

        Parameters
        ----------
        lines : str/int, slice, or list/tuple of strs/ints
            The line label(s) to delete.  See :method:`get_labels` for details.

        delete_straddlers : bool, optional
            Whether or not gates which straddle deleted and non-deleted lines
            should be removed.  If `False` and straddling gates exist, an error
            will be raised.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        lines = self._proc_lines_arg(lines)
        for i in range(len(self._labels)):
            new_layer = []
            for l in self._layer_components(i):  # loop over labels in this layer
                sslbls = _sslbls_of_nested_lists_of_simple_labels(l)
                if sslbls is None or len(set(sslbls).intersection(lines)) == 0:
                    new_layer.append(l)
                elif not delete_straddlers and not set(sslbls).issubset(lines):
                    raise ValueError(("Cannot remove a block that is straddled by "
                                      "%s when `delete_straddlers` == False!") % _Label(l))
            self._labels[i] = new_layer
        self._line_labels = tuple([x for x in self.line_labels if x not in lines])

    def __getitem__(self, key):
        layers, lines = self._proc_key_arg(key)
        return self.get_labels(layers, lines, strict=True)

    def __setitem__(self, key, val):
        layers, lines = self._proc_key_arg(key)
        return self.set_labels(val, layers, lines)

    def __delitem__(self, key):
        layers, lines = self._proc_key_arg(key)
        if layers is None:
            self.delete_lines(lines, delete_straddlers=True)
        elif lines is None:
            self.delete_layers(layers)
        else:
            raise IndexError("Can only delete entire layers or enire lines.")

    def to_pythonstr(self, opLabels):
        """
        Convert this circuit to a python string, where each operation label is
        represented as a **single** character, starting with 'A' and contining
        down the alphabet.  This can be useful for processing operation sequences
        using python's string tools (regex in particular).

        Parameters
        ----------
        opLabels : tuple
           An iterable containing at least all the layer-Labels that appear
           in this Circuit, and which will be mapped to alphabet
           characters, beginning with 'A'.

        Returns
        -------
        string
            The converted operation sequence.

        Examples
        --------
            ('Gx','Gx','Gy','Gx') => "AABA"
        """
        assert(len(opLabels) < 26)  # Complain if we go beyond 'Z'
        translateDict = {}; c = 'A'
        for opLabel in opLabels:
            translateDict[opLabel] = c
            c = chr(ord(c) + 1)
        return "".join([translateDict[opLabel] for opLabel in self.tup])

    @classmethod
    def from_pythonstr(cls, pythonString, opLabels):
        """
        Create a Circuit from a python string where each operation label is
        represented as a **single** character, starting with 'A' and contining
        down the alphabet.  This performs the inverse of to_pythonstr(...).

        Parameters
        ----------
        pythonString : string
            string whose individual characters correspond to the operation labels of a
            operation sequence.

        opLabels : tuple
           tuple containing all the operation labels that will be mapped from alphabet
           characters, beginning with 'A'.

        Returns
        -------
        Circuit

        Examples
        --------
            "AABA" => ('Gx','Gx','Gy','Gx')
        """
        assert(len(opLabels) < 26)  # Complain if we go beyond 'Z'
        translateDict = {}; c = 'A'
        for opLabel in opLabels:
            translateDict[c] = opLabel
            c = chr(ord(c) + 1)
        return cls(tuple([translateDict[c] for c in pythonString]))

    def serialize(self):
        """
        Construct a new Circuit whereby all layers containing multiple gates are
        converted to separate single-gate layers, effectively putting each
        elementary gate operation into its own layer.  Ordering is dictated by
        the ordering of the compound layer labels.

        Returns
        -------
        Circuit
        """
        serial_lbls = []
        for lbl in self.tup:
            if len(lbl.components) == 0:  # special case of an empty-layer label,
                serial_lbls.append(lbl)  # which we serialize as an atomic object
            for c in lbl.components:
                serial_lbls.append(c)
        return Circuit(serial_lbls, self.line_labels, editable=False, check=False)

    def parallelize(self, can_break_labels=True, adjacent_only=False):
        """
        Construct a circuit with the same underlying labels as this one,
        but with as many gates performed in parallel as possible (with
        some restrictions - see the Parameters section below).  Generally,
        gates are moved as far left (toward the start) of the circuit as
        possible.

        Parameters
        ----------
        can_break_labels : bool, optional
            Whether compound (parallel-gate) labels in this Circuit can be
            separated during the parallelization process.  For example, if
            `can_break_labels=True` then `"Gx:0[Gy:0Gy:1]" => "[Gx:0Gy:1]Gy:0"`
            whereas if `can_break_labels=False` the result would remain
            `"Gx:0[Gy:0Gy:1]"` because `[Gy:0Gy:1]` cannot be separated.

        adjacent_only : bool, optional
            It `True`, then operation labels are only allowed to move into an
            adjacent label, that is, they cannot move "through" other
            operation labels.  For example, if `adjacent_only=True` then
            `"Gx:0Gy:0Gy:1" => "Gx:0[Gy:0Gy:1]"` whereas if
            `adjacent_only=False` the result would be `"[Gx:0Gy:1]Gy:0`.
            Setting this to `True` is sometimes useful if you want to
            parallelize a serial string in such a way that subsequently
            calling `.serialize()` will give you back the original string.

        Returns
        -------
        Circuit
        """
        parallel_lbls = []
        cur_components = []
        first_free = {'*': 0}
        for lbl in self.tup:
            if can_break_labels:  # then process label components individually
                for c in lbl.components:
                    if c.sslbls is None:  # ~= acts on *all* sslbls
                        pos = max(list(first_free.values()))
                        #first position where all sslbls are free
                    else:
                        inds = [v for k, v in first_free.items() if k in c.sslbls]
                        pos = max(inds) if len(inds) > 0 else first_free['*']
                        #first position where all c.sslbls are free (uses special
                        # '*' "base" key if we haven't seen any of the sslbls yet)

                    if len(parallel_lbls) < pos + 1: parallel_lbls.append([])
                    assert(pos < len(parallel_lbls))
                    parallel_lbls[pos].append(c)  # add component in proper place

                    #update first_free
                    if adjacent_only:  # all labels/components following this one must at least be at 'pos'
                        for k in first_free: first_free[k] = pos
                    if c.sslbls is None:
                        for k in first_free: first_free[k] = pos + 1  # includes '*'
                    else:
                        for k in c.sslbls: first_free[k] = pos + 1

            else:  # can't break labels - treat as a whole
                if lbl.sslbls is None:  # ~= acts on *all* sslbls
                    pos = max(list(first_free.values()))
                    #first position where all sslbls are free
                else:
                    inds = [v for k, v in first_free.items() if k in lbl.sslbls]
                    pos = max(inds) if len(inds) > 0 else first_free['*']
                    #first position where all c.sslbls are free (uses special
                    # '*' "base" key if we haven't seen any of the sslbls yet)

                if len(parallel_lbls) < pos + 1: parallel_lbls.append([])
                assert(pos < len(parallel_lbls))
                for c in lbl.components:  # add *all* components of lbl in proper place
                    parallel_lbls[pos].append(c)

                #update first_free
                if adjacent_only:  # all labels/components following this one must at least be at 'pos'
                    for k in first_free: first_free[k] = pos
                if lbl.sslbls is None:
                    for k in first_free: first_free[k] = pos + 1  # includes '*'
                else:
                    for k in lbl.sslbls: first_free[k] = pos + 1

        return Circuit(parallel_lbls, self.line_labels, editable=False, check=False)

    def expand_subcircuits(self):
        """ TODO: docstring """
        assert(not self._static), "Cannot edit a read-only circuit!"

        #Iterate in reverse so we don't have to deal with
        # added layers.
        for i in reversed(range(len(self._labels))):
            circuits_to_expand = []
            layers_to_add = 0

            for l in self._layer_components(i):  # loop over labels in this layer
                if isinstance(l, _CircuitLabel):
                    circuits_to_expand.append(l)
                    layers_to_add = max(layers_to_add, l.depth() - 1)

            if layers_to_add > 0:
                self.insert_idling_layers(i + 1, layers_to_add)
            for subc in circuits_to_expand:
                self.clear_labels(slice(i, i + subc.depth()), subc.sslbls)  # remove the CircuitLabel
                self.set_labels(subc.components * subc.reps, slice(i, i + subc.depth()),
                                subc.sslbls)  # dump in the contents

    def factorize_repetitions(self):
        """ TODO: docstring """
        assert(not self._static), "Cannot edit a read-only circuit!"
        nLayers = self.num_layers()
        iLayersToRemove = []
        iStart = 0
        while iStart < nLayers - 1:
            iEnd = iStart + 1
            while iEnd < nLayers and self._labels[iStart] == self._labels[iEnd]:
                iEnd += 1
            nreps = iEnd - iStart
            #print("Start,End = ",iStart,iEnd)
            if nreps <= 1:  # just move to next layer
                iStart += 1; continue  # nothing to do

            #Construct a sub-circuit label that repeats layer[iStart] nreps times
            # and stick it at layer iStart
            #print("Constructing %d reps at %d" % (nreps, iStart))
            repCircuit = _CircuitLabel('', self._labels[iStart], None, nreps)
            self.clear_labels(iStart, None)  # remove existing labels (unnecessary?)
            self.set_labels(repCircuit, iStart, None)
            iLayersToRemove.extend(list(range(iStart + 1, iEnd)))
            iStart += nreps  # advance iStart to next unprocessed layer inde

        if len(iLayersToRemove) > 0:
            #print("Removing layers: ",iLayersToRemove)
            self.delete_layers(iLayersToRemove)


## DEPRECATED FUNCTIONS?

    #def replace_gate_with_circuit(self, circuit, q, j): #used in this module only TODO
    #    """
    #    Replace a gate with a circuit. This gate is replaced with an idle and
    #    the circuit is inserted between this layer and the following circuit layer.
    #    As such there is no restrictions on the lines on which this circuit can act non-trivially.
    #    `circuit` need not be a circuit over all the qubits in this circuit, but it must satisfying
    #    the requirements of the `insert_circuit()` method.
    #
    #    Parameters
    #    ----------
    #    circuit : A Circuit object
    #        The circuit to be inserted in place of the gate.
    #
    #    q : int
    #        The qubit on which the gate is to be replaced.
    #
    #    j : int
    #        The layer index (depth) of the gate to be replaced.
    #
    #    Returns
    #    -------
    #    None
    #    """
    #    assert(not self._static),"Cannot edit a read-only circuit!"
    #    gate_to_replace = self.line_items[q][j]
    #
    #    # Replace the gate with identity
    #    gate_qubits = self.line_labels if (gate_to_replace.qubits is None) \
    #                  else gate_to_replace.qubits
    #    for q in gate_qubits:
    #        self.line_items[self.line_labels.index(q)][j] = _Label(self.identity,q)
    #
    #    # Inserts the circuit after the layer this gate was in.
    #    self.insert_circuit(circuit,j+1)
    #
    #    self._tup_dirty = self._str_dirty = True


    def insert_layer(self, circuit_layer, j):
        """
        Inserts a single layer into a circuit.

        The input layer does not need to contain a gate that acts on
        every qubit, but it should not contain more than one gate on
        a qubit.

        Parameters
        ----------
        circuit_layer : Label
            The layer to insert.  A (possibly compound) Label object or
            something that can be converted into one, e.g.
            `(('Gx',0),('Gcnot',1,2))` or just `'Gx'`.

        j : int
            The layer index (depth) at which to insert the `circuit_layer`.

        Returns
        -------
        None
        """
        self.insert_labels_into_layers([circuit_layer], j)

    def insert_circuit(self, circuit, j):
        """
        Inserts a circuit into this circuit. The circuit to insert can be over
        more qubits than this circuit, as long as all qubits that are not part
        of this circuit are idling. In this case, the idling qubits are all
        discarded. The circuit to insert can also be on less qubits than this
        circuit: all other qubits are set to idling. So, the labels of the
        circuit to insert for all non-idling qubits must be a subset of the
        labels of this circuit.

        Parameters
        ----------
        circuit : Circuit
            The circuit to be inserted.

        j : int
            The layer index (depth) at which to insert the circuit.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        lines_to_insert = []
        for line_lbl in circuit.line_labels:
            if line_lbl in self.line_labels:
                lines_to_insert.append(line_lbl)
            else:
                assert(circuit.is_line_idling(line_lbl)), \
                    "There are non-idling lines in the circuit to insert that are *not* lines in this circuit!"

        labels_to_insert = circuit.get_labels(layers=None, lines=lines_to_insert)
        self.insert_labels_into_layers(labels_to_insert, j)

    def append_circuit(self, circuit):
        """
        Append a circuit to the end of this circuit. This circuit must satisfy
        the requirements of :method:`insert_circuit()`. See that method for
        more details.

        Parameters
        ----------
        circuit : A Circuit object
            The circuit to be appended.

        Returns
        -------
        None
        """
        self.insert_circuit(circuit, self.num_layers())

    def prefix_circuit(self, circuit):
        """
        Prefix a circuit to the beginning of this circuit. This circuit must
        satisfy the requirements of the :method:`insert_circuit()`. See that
        method for more details.

        Parameters
        ----------
        circuit : A Circuit object
            The circuit to be prefixed.

        Returns
        -------
        None
        """
        self.insert_circuit(circuit, 0)

    def tensor_circuit(self, circuit, line_order=None):
        """
        Tensors a circuit to this circuit. That is, it adds `circuit` to this
        circuit as new lines.  The line labels of `circuit` must be disjoint
        from the line labels of this circuit, as otherwise applying the circuits
        in parallel does not make sense.

        Parameters
        ----------
        circuit : A Circuit object
            The circuit to be tensored.

        line_order : List, optional
            A list of all the line labels specifying the order of the circuit in the updated
            circuit. If None, the lines of `circuit` are added below the lines of this circuit.
            Note that, for many purposes, the ordering of lines of the circuit is irrelevant.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        #assert(self.identity == circuit.identity), "The identity labels must be the same!"

        #Construct new line labels (of final circuit)
        overlap = set(self.line_labels).intersection(circuit.line_labels)
        if len(overlap) > 0:
            raise ValueError(
                "The line labels of `circuit` and this Circuit must be distinct, but overlap = %s!" % str(overlap))

        all_line_labels = set(self.line_labels + circuit.line_labels)
        if line_order is not None:
            line_order_set = set(line_order)
            if len(line_order_set) != len(line_order):
                raise ValueError("`line_order` == %s cannot contain duplicates!" % str(line_order))

            missing = all_line_labels - line_order_set
            if len(missing) > 0:
                raise ValueError("`line_order` is missing %s." % str(missing))

            extra = set(line_order) - all_line_labels
            if len(extra) > 0:
                raise ValueError("`line_order` had nonpresent line labels %s." % str(extra))

            new_line_labels = line_order
        else:
            new_line_labels = self.line_labels + circuit.line_labels

        #Add circuit's labels into this circuit
        self.insert_labels_as_lines(circuit._labels, line_labels=circuit.line_labels)
        self._line_labels = new_line_labels  # essentially just reorders labels if needed

    def replace_layer_with_circuit(self, circuit, j):
        """
        Replaces the `j`-th layer of this circuit with `circuit`.

        Parameters
        ----------
        circuit : Circuit
            The circuit to insert

        j : int
            The layer index to replace.

        Returns
        -------
        None
        """
        del self[j]
        self.insert_labels_into_layers(circuit, j)

    def replace_gatename_inplace(self, old_gatename, new_gatename):
        """
        Changes the *name* of a gate throughout this Circuit.

        Note that the "name" is only a part of the "label" identifying each
        gate, and doesn't include the lines (qubits) a gate acts upon.  For
        example, the "Gx:0" and "Gx:1" labels both have the same name but
        act on different qubits.

        Parameters
        ----------
        old_gatename, new_gatename : string
            The gate name to find and the gate name to replace the found
            name with.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        def replace(obj):  # obj is either a simple label or a list
            if isinstance(obj, _Label):
                if obj.name == old_gatename:
                    newobj = _Label(new_gatename, obj.sslbls)
                else: newobj = obj
            else:
                newobj = [replace(sub) for sub in obj]
            return newobj

        self._labels = replace(self._labels)

    def replace_gatename(self, old_gatename, new_gatename):
        """
        Returns a copy of this Circuit except that `old_gatename` is
        changed to `new_gatename`.

        Note that the "name" is only a part of the "label" identifying each
        gate, and doesn't include the lines (qubits) a gate acts upon.  For
        example, the "Gx:0" and "Gx:1" labels both have the same name but
        act on different qubits.

        Parameters
        ----------
        old_gatename, new_gatename : string
            The gate name to find and the gate name to replace the found
            name with.

        Returns
        -------
        Circuit
        """
        if not self._static:
            #Could to this in both cases, but is slow for large static circuits
            cpy = self.copy(editable=True)
            cpy.replace_gatename_inplace(old_gatename, new_gatename)
            cpy.done_editing()
            return cpy
        else:  # static case: so self._labels is a tuple of Labels
            return Circuit([lbl.replacename(old_gatename, new_gatename)
                            for lbl in self._labels], self.line_labels)

    def replace_layer(self, old_layer, new_layer):
        """
        Returns a copy of this Circuit except that `old_layer` is
        changed to `new_layer`.

        Parameters
        ----------
        old_layer, new_layer : string or Label
            The layer to find and the to replace.

        Returns
        -------
        Circuit
        """
        old_layer = toLabel(old_layer)
        new_layer = toLabel(new_layer)
        if not self._static:
            #Could to this in both cases, but is slow for large static circuits
            cpy = self.copy(editable=False)  # convert our layers to Labels
            return Circuit([new_layer if lbl == old_layer else lbl
                            for lbl in cpy._labels], self.line_labels)
        else:  # static case: so self._labels is a tuple of Labels
            return Circuit([new_layer if lbl == old_layer else lbl
                            for lbl in self._labels], self.line_labels)

    #def replace_identity(self, identity, convert_identity_gates = True): # THIS module only
    #    """
    #    Changes the *name* of the idle/identity gate in the circuit. This replaces
    #    the name of the identity element in the circuit by setting self.identity = identity.
    #    If `convert_identity_gates` is True, this also changes the names of all the gates that
    #    had the old self.identity name.
    #
    #    Parameters
    #    ----------
    #    identity : string
    #        The new name for the identity gate.
    #
    #    convert_identity_gates : bool, optional
    #        If True, all gates that had the old identity name are converted to the new identity
    #        name. Otherwise, they keep the old name, and the circuit nolonger considers them to
    #        be identity gates.
    #
    #    Returns
    #    -------
    #    None
    #    """
    #    if convert_identity_gates:
    #        self.replace_gatename(self.identity, identity)
    #
    #    self._tup_dirty = self._str_dirty = True
    #    self.identity = identity

    def change_gate_library(self, compilation, allowed_filter=None, allow_unchanged_gates=False, depth_compression=True,
                            oneQgate_relations=None):
        """
        Re-express a circuit over a different model.

        Parameters
        ----------
        compilation : dict or CompilationLibrary.
            If a dictionary, the keys are some or all of the gates that appear in the circuit, and the values are
            replacement circuits that are normally compilations for each of these gates (if they are not, the action
            of the circuit will be changed). The circuits need not be on all of the qubits, and need only satisfy
            the requirements of the `insert_circuit` method. There must be a key for every gate except the self.identity
            gate, unless `allow_unchanged_gates` is False. In that case, gate that aren't a key in this dictionary are
            left unchanged.

            If a CompilationLibrary, this will be queried via the get_compilation_of() method to find compilations
            for all of the gates in the circuit. So this CompilationLibrary must contain or be able to auto-generate
            compilations for the requested gates, except when `allow_unchanged_gates` is True. In that case, gates
            that a compilation is not returned for are left unchanged.

        allowed_filter : dict or set, optional
            Specifies which gates are allowed to be used when generating compilations from `compilation`. Can only be
            not None if `compilation` is a CompilationLibrary. If a `dict`, keys must be gate names (like `"Gcnot"`) and
            values :class:`QubitGraph` objects indicating where that gate (if it's present in the library) may be used.
            If a `set`, then it specifies a set of qubits and any gate in the current library that is confined within
            that set is allowed. If None, then all gates within the library are allowed.

        depth_compression : bool, optional
            Whether to perform depth compression after changing the gate library. If oneQgate_relations is None this
            will only remove idle layers and compress the circuit by moving everything as far forward as is possible
            without knowledge of the action of any gates other than self.identity. See the `depth_compression` method
            for more details. Under most circumstances this should be true; if it is False changing gate library will
            often result in a massive increase in circuit depth.

        oneQgate_relations : dict, optional
            Gate relations for the one-qubit gates in the new gate library, that are used in the depth compression, to
            cancel / combine gates. E.g., one key-value pair might be ('Gh','Gh') : 'I', to signify that two Hadamards c
            ompose to the idle gate 'Gi'. See the depth_compression() method for more details.


        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        # If it's a CompilationLibrary, it has this attribute. When it's a CompilationLibrary we use the
        # .get_compilation_of method, which will look to see if a compilation for a gate is already available (with
        # `allowed_filter` taken account of) and if not it will attempt to construct it.
        if hasattr(compilation, 'templates'):
            # The function we query to find compilations
            def get_compilation(gate):
                # Use try, because it will fail if it cannot construct a compilation, and this is fine under some
                # circumstances
                try:
                    circuit = compilation.get_compilation_of(gate, allowed_filter=allowed_filter, verbosity=0)
                    return circuit
                except:
                    return None
        # Otherwise, we assume it's a dict.
        else:
            assert(allowed_filter is None), \
                "`allowed_filter` can only been not None if the compilation is a CompilationLibrary!"
            # The function we query to find compilations

            def get_compilation(gate):
                return compilation.get(gate, None)

        for ilayer in range(self.num_layers() - 1, -1, -1):
            icomps_to_remove = []
            for icomp, l in enumerate(self._layer_components(ilayer)):  # loop over labels in this layer
                replacement_circuit = get_compilation(l)
                if replacement_circuit is not None:
                    # Replace the gate with a circuit: remove the gate and add insert
                    # the replacement circuit as the following layers.
                    icomps_to_remove.append(icomp)
                    self.insert_labels_into_layers(replacement_circuit, ilayer + 1)
                else:
                    # We never consider not having a compilation for the identity to be a failure.
                    if not allow_unchanged_gates:
                        raise ValueError(
                            "`compilation` does not contain, or cannot generate a compilation for {}!".format(l))

            for icomp in reversed(icomps_to_remove):
                self._remove_layer_component(ilayer, icomp)

        # If specified, perform the depth compression.
        # It is better to do this *after* the identity name has been changed.
        if depth_compression:
            self.compress_depth(oneQgate_relations=oneQgate_relations, verbosity=0)

    def map_names_inplace(self, mapper):
        """
        The names of all of the simple labels are updated in-place according to
        the mapping function `mapper`.

        Parameters
        ----------
        mapper : dict or function
            A dictionary whose keys are the existing gate name values
            and whose values are the new names (strings) or a function
            which takes a single (existing name) argument and returns a new name.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        # If the mapper is a dict, turn it into a function
        def mapper_func(gatename): return mapper.get(gatename, None) \
            if isinstance(mapper, dict) else mapper

        def map_names(obj):  # obj is either a simple label or a list
            if isinstance(obj, _Label):
                if obj.issimple():  # *simple* label
                    new_name = mapper_func(obj.name)
                    newobj = _Label(new_name, obj.sslbls) \
                        if (new_name is not None) else obj
                else:  # compound label
                    newobj = _Label([map_names(comp) for comp in obj.components])
            else:
                newobj = [map_names(sub) for sub in obj]
            return newobj
        self._labels = map_names(self._labels)

    def map_state_space_labels_inplace(self, mapper):
        """
        The labels of all of the lines (wires/qubits) are updated according to
        the mapping function `mapper`.

        Parameters
        ----------
        mapper : dict or function
            A dictionary whose keys are the existing self.line_labels values
            and whose values are the new labels (ints or strings), or a function
            which takes a single (existing label) argument and returns a new label.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        # If the mapper is a dict, turn it into a function
        def mapper_func(line_label): return mapper[line_label] \
            if isinstance(mapper, dict) else mapper

        self._line_labels = tuple((mapper_func(l) for l in self.line_labels))

        def map_sslbls(obj):  # obj is either a simple label or a list
            if isinstance(obj, _Label):
                new_sslbls = [mapper_func(l) for l in obj.sslbls] \
                    if (obj.sslbls is not None) else None
                newobj = _Label(obj.name, new_sslbls)
            else:
                newobj = [map_sslbls(sub) for sub in obj]
            return newobj
        self._labels = map_sslbls(self._labels)

    def map_state_space_labels(self, mapper):
        """
        Creates and returns a new Circuit whereby The names of all of the simple
        labels are updated according to the mapping function `mapper`.

        Parameters
        ----------
        mapper : dict or function
            A dictionary whose keys are the existing gate name values
            and whose values are the new names (strings) or a function
            which takes a single (existing name) argument and returns a new name.

        Returns
        -------
        Circuit
        """
        def mapper_func(line_label): return mapper[line_label] \
            if isinstance(mapper, dict) else mapper(line_label)
        mapped_line_labels = tuple(map(mapper_func, self.line_labels))
        return Circuit([l.map_state_space_labels(mapper_func) for l in self._labels],
                       mapped_line_labels, None, not self._static)

    def reorder_lines(self, order):
        """
        Reorders the lines (wires/qubits) of the circuit. Note that the ordering of the
        lines is not important for most purposes.

        Parameters
        ----------
        order : list
            A list containing all of the circuit line labels (self.line_labels) in the
            order that the should be converted to.

        Returns
        -------
        None
        """
        # OK even for static circuits because it won't affect the hashed value (labels only)
        assert(set(order) == set(self.line_labels)), "The line labels must be the same!"
        self._line_labels = tuple(order)

    def is_line_idling(self, line_label, idle_layer_labels=None):
        """
        Whether the line in question is idling in *every* circuit layer.

        Parameters
        ----------
        line_label : str or int
            The label of the line (i.e., "wire" or qubit).

        idle_layer_labels : iterable, optional
            A list or tuple of layer-labels that should be treated
            as idle operations, so their presence will not disqualify
            a line from being "idle".  E.g. `["Gi"]` will cause `"Gi"`
            layers to be considered idle layers.

        Returns
        -------
        bool
            True if the line is idling. False otherwise.
        """
        if self._static:
            layers = list(filter(lambda x: x not in idle_layer_labels, self._labels)) \
                if idle_layer_labels else self._labels
            all_sslbls = None if any([layer.sslbls is None for layer in layers]) \
                else set(_itertools.chain(*[layer.sslbls for layer in layers]))
        else:
            all_sslbls = _sslbls_of_nested_lists_of_simple_labels(self._labels, idle_layer_labels)  # None or a set

        if all_sslbls is None:
            return False  # no lines are idling
        return bool(line_label not in all_sslbls)

    def get_idling_lines(self, idle_layer_labels=None):
        """
        Returns the line labels corresponding to idling lines.

        Parameters
        ----------
        idle_layer_labels : iterable, optional
            A list or tuple of layer-labels that should be treated
            as idle operations, so their presence will not disqualify
            a line from being "idle".  E.g. `["Gi"]` will cause `"Gi"`
            layers to be considered idle layers.

        Returns
        -------
        tuple
        """
        if self._static:
            layers = list(filter(lambda x: x not in idle_layer_labels, self._labels)) \
                if idle_layer_labels else self._labels
            all_sslbls = None if any([layer.sslbls is None for layer in layers]) \
                else set(_itertools.chain(*[layer.sslbls for layer in layers]))
        else:
            all_sslbls = _sslbls_of_nested_lists_of_simple_labels(self._labels, idle_layer_labels)  # None or a set

        if all_sslbls is None:
            return ()
        else:
            return tuple([x for x in self.line_labels
                          if x not in all_sslbls])  # preserve order

    def delete_idling_lines(self, idle_layer_labels=None):
        """
        Removes from this circuit all lines that are idling at every layer.

        Parameters
        ----------
        idle_layer_labels : iterable, optional
            A list or tuple of layer-labels that should be treated
            as idle operations, so their presence will not disqualify
            a line from being "idle".  E.g. `["Gi"]` will cause `"Gi"`
            layers to be considered idle layers.

        Returns
        -------
        None
        """
        #assert(not self._static),"Cannot edit a read-only circuit!"
        # Actually, this is OK even for static circuits because it won't affect the hashed value (labels only)

        if idle_layer_labels:
            assert(all([toLabel(x).sslbls is None for x in idle_layer_labels])), "Idle layer labels must be *global*"

        if self._static:
            layers = list(filter(lambda x: x not in idle_layer_labels, self._labels)) \
                if idle_layer_labels else self._labels
            all_sslbls = None if any([layer.sslbls is None for layer in layers]) \
                else set(_itertools.chain(*[layer.sslbls for layer in layers]))
        else:
            all_sslbls = _sslbls_of_nested_lists_of_simple_labels(self._labels, idle_layer_labels)  # None or a set

        if all_sslbls is None:
            return  # no lines are idling

        #All we need to do is update line_labels since there aren't any labels
        # to remove in self._labels (as all the lines are idling)
        self._line_labels = tuple([x for x in self.line_labels
                                   if x in all_sslbls])  # preserve order

    def replace_with_idling_line(self, line_label, clear_straddlers=True):
        """
        Converts the specified line to an idling line, by removing all
        its gates. If there are any multi-qubit gates acting on this line,
        this function will raise an error when `clear_straddlers=False`.

        Parameters
        ----------
        line_label: str or int
            The label of the line to convert to an idling line.

        clear_straddlers : bool, optional
            Whether or not gates which straddle the `line_label` should also
            be cleared.  If `False` and straddling gates exist, an error
            will be raised.
        """
        self.clear_labels(lines=line_label, clear_straddlers=clear_straddlers)

    def reverse(self):
        """
        Reverses the order of the circuit.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        self._labels = list(reversed(self._labels))  # reverses the layer order
        #FUTURE: would need to reverse each layer too, if layer can have *sublayers*

    def combine_oneQgates(self, oneQgate_relations):
        """
        Compresses sequences of 1-qubit gates in the circuit, using the provided gate relations.
        One of the steps of the depth_compression() method, and in most cases that method will
        be more useful.

        Parameters
        ----------
        oneQgate_relations : dict
            Keys that are pairs of strings, corresponding to 1-qubit gate names, with values that are
            a single string, also corresponding to a 1-qubit gate name. Whenever a 1-qubit gate with
            name `name1` is followed in the circuit by a 1-qubit gate with `name2` then, if
            oneQgate_relations[name1,name2] = name3, name1 -> name3 and name2 -> self.identity, the
            identity name in the circuit. Moreover, this is still implemented when there are self.identity
            gates between these 1-qubit gates, and it is implemented iteratively in the sense that if there
            is a sequence of 1-qubit gates with names name1, name2, name3, ... and there are relations
            for all of (name1,name2) -> name12, (name12,name3) -> name123 etc then the entire sequence of
            1-qubit gates will be compressed into a single possibly non-idle 1-qubit gate followed by
            idle gates in place of the previous 1-qubit gates.  Note that `None` can be used as `name3`
            to signify that the result is the identity (no gate labels).

            If a ProcessorSpec object has been created for the gates/device in question, the
            ProcessorSpec.oneQgate_relations is the appropriate (and auto-generated) `oneQgate_relations`.

            Note that this function will not compress sequences of 1-qubit gates that cannot be compressed by
            independently inspecting sequential non-idle pairs (as would be the case with, for example,
            Gxpi Gzpi Gxpi Gzpi, if the relation did not know that (Gxpi,Gzpi) -> Gypi, even though the sequence
            is the identity).

        Returns
        -------
        bool
            False if the circuit is unchanged, and True otherwise.
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        # A flag that is turned to True if any non-trivial re-arranging is implemented by this method.
        compression_implemented = False

        # A flag telling us when to stop iterating
        productive = True

        while productive:  # keep iterating
            #print("BEGIN ITER")
            productive = False
            # Loop through all the qubits, to try and compress squences of 1-qubit gates on the qubit in question.
            for ilayer in range(0, len(self._labels) - 1):
                layerA_comps = self._layer_components(ilayer)
                layerB_comps = self._layer_components(ilayer + 1)
                applies = []
                for a, lblA in enumerate(layerA_comps):
                    if not isinstance(lblA, _Label) or (lblA.sslbls is None) \
                       or (len(lblA.sslbls) != 1): continue  # only care about 1-qubit simple labels within a layer
                    #FUTURE: could relax the != 1 condition?

                    for b, lblB in enumerate(layerB_comps):
                        if isinstance(lblB, _Label) and lblB.sslbls == lblA.sslbls:
                            #queue an apply rule if one exists
                            #print("CHECK for: ", (lblA.name,lblB.name))
                            if (lblA.name, lblB.name) in oneQgate_relations:
                                new_Aname = oneQgate_relations[lblA.name, lblB.name]
                                applies.append((a, b, new_Aname, lblA.sslbls))
                                break

                layerA_sslbls = _sslbls_of_nested_lists_of_simple_labels(self._labels[ilayer])
                for b, lblB in enumerate(layerB_comps):
                    if isinstance(lblB, _Label):
                        #see if layerA happens to *not* have anything on lblB.sslbls:
                        if layerA_sslbls is None or \
                           (lblB.sslbls is not None and
                                len(set(lblB.sslbls).intersection(layerA_sslbls)) == 0):
                            applies.append((-1, b, lblB.name, lblB.sslbls))  # shift label over
                            break

                if len(applies) > 0:
                    # Record that a compression has been implemented : the circuit has been changed.
                    compression_implemented = productive = True

                #execute queued applies (outside of above loops)
                sorted_applies = sorted(applies, key=lambda x: -x[1])  # sort in order of descending 'b' for removes
                ilayer_inds_to_remove = []
                for a, b, new_Aname, sslbls in sorted_applies:
                    if a == -1:  # Note: new_Aname cannot be None here
                        self._append_layer_component(ilayer, _Label(new_Aname, sslbls))
                    elif new_Aname is None:
                        ilayer_inds_to_remove.append(a)  # remove layer component - but wait to do so in order
                    else:
                        self._replace_layer_component(ilayer, a, _Label(new_Aname, sslbls))
                    self._remove_layer_component(ilayer + 1, b)

                for a in sorted(ilayer_inds_to_remove, reverse=True):
                    self._remove_layer_component(ilayer, a)

        # returns the flag that tells us whether the algorithm achieved anything.
        return compression_implemented

    def shift_gates_forward(self):
        """
        Shifted all gates forward (left) as far as is possible without any
        knowledge of what any of the gates are.  One of the steps of the
        `depth_compression()` method.

        Returns
        -------
        bool
            False if the circuit is unchanged, and True otherwise.
        """
        assert(not self._static), "Cannot edit a read-only circuit!"
        # Keeps track of whether any changes have been made to the circuit.
        compression_implemented = False

        #print("BEGIN")
        used_lines = {}
        for icurlayer in range(len(self._labels)):
            #print("LAYER ",icurlayer)
            #Slide labels in current layer to left ("forward")
            icomps_to_remove = []; used_lines[icurlayer] = set()
            for icomp, lbl in enumerate(self._layer_components(icurlayer)):
                #see if we can move this label forward
                #print("COMP%d: %s" % (icomp,str(lbl)))
                sslbls = _sslbls_of_nested_lists_of_simple_labels(lbl)
                if sslbls is None: sslbls = self.line_labels

                dest_layer = icurlayer
                while dest_layer > 0 and len(used_lines[dest_layer - 1].intersection(sslbls)) == 0:
                    dest_layer -= 1
                if dest_layer < icurlayer:
                    icomps_to_remove.append(icomp)  # remove this label from current layer
                    self._append_layer_component(dest_layer, lbl)  # add it to the destination layer
                    used_lines[dest_layer].update(sslbls)  # update used_lines at dest layer
                    #print(" <-- layer %d (used=%s)" % (dest_layer,str(used_lines[dest_layer])))
                else:
                    #can't move this label forward - update used_lines of current layer
                    used_lines[icurlayer].update(sslbls)  # update used_lines at dest layer
                    #print(" can't move: (cur layer used=%s)" % (str(used_lines[icurlayer])))

            #Remove components in current layer which were pushed forward
            #print("Removing ",icomps_to_remove," from layer ",icurlayer)
            for icomp in reversed(icomps_to_remove):
                self._remove_layer_component(icurlayer, icomp)

            if len(icomps_to_remove) > 0:  # keep track of whether we did anything
                compression_implemented = True

        # Only return the bool if requested
        return compression_implemented

    def delete_idle_layers(self):
        """
        Deletes all layers in this circuit that contain no gate operations. One
        of the steps of the `depth_compression()` method.

        Returns
        -------
        bool
            False if the circuit is unchanged, and True otherwise.
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        inds_to_remove = []
        for ilayer, layer_labels in enumerate(self._labels):
            if layer_labels == []:
                inds_to_remove.append(ilayer)
        for ilayer in reversed(inds_to_remove):
            del self._labels[ilayer]

        return bool(len(inds_to_remove) > 0)  # whether compression was implemented

    def compress_depth(self, oneQgate_relations=None, verbosity=0):
        """
        Compresses the depth of this circuit using very simple re-write rules.

        1. If `oneQgate_relations` is provided, all sequences of 1-qubit gates
           in the  circuit are compressed as far as is possible using only the
           pair-wise combination rules provided by this dict (see below).
        2. All gates are shifted forwarded as far as is possible without any
           knowledge of what any of the gates are.
        3. All idle-only layers are deleted.

        Parameters
        ----------
        oneQgate_relations : dict
            Keys that are pairs of strings, corresponding to 1-qubit gate names, with values that are
            a single string, also corresponding to a 1-qubit gate name. Whenever a 1-qubit gate with
            name `name1` is followed in the circuit by a 1-qubit gate with `name2` then, if
            oneQgate_relations[name1,name2] = name3, name1 -> name3 and name2 -> self.identity, the
            identity name in the circuit. Moreover, this is still implemented when there are self.identity
            gates between these 1-qubit gates, and it is implemented iteratively in the sense that if there
            is a sequence of 1-qubit gates with names name1, name2, name3, ... and there are relations
            for all of (name1,name2) -> name12, (name12,name3) -> name123 etc then the entire sequence of
            1-qubit gates will be compressed into a single possibly non-idle 1-qubit gate followed by
            idle gates in place of the previous 1-qubit gates.

            If a ProcessorSpec object has been created for the gates/device in question, the
            ProcessorSpec.oneQgate_relations is the appropriate (and auto-generated) `oneQgate_relations`.

            Note that this function will not compress sequences of 1-qubit gates that cannot be compressed by
            independently inspecting sequential non-idle pairs (as would be the case with, for example,
            Gxpi Gzpi Gxpi Gzpi, if the relation did not know that (Gxpi,Gzpi) -> Gypi, even though the sequence
            is the identity).

        verbosity : int, optional
            If > 0, information about the depth compression is printed to screen.

        Returns
        -------
        None
        """
        assert(not self._static), "Cannot edit a read-only circuit!"

        if verbosity > 0:
            print("- Implementing circuit depth compression")
            print("  - Circuit depth before compression is {}".format(self.num_layers()))

        flag1 = False
        if oneQgate_relations is not None:
            flag1 = self.combine_oneQgates(oneQgate_relations)
        flag2 = self.shift_gates_forward()
        flag3 = self.delete_idle_layers()

        if verbosity > 0:
            if not (flag1 or flag2 or flag3):
                print("  - Circuit unchanged by depth compression algorithm")
            print("  - Circuit depth after compression is {}".format(self.num_layers()))

    def get_layer(self, j):
        """
        Returns a tuple of the *components*, i.e. the (non-identity) gates,
        in the layer at depth `j`.

        These are the `.components` of the :class:`Label` returned by indexing
        this Circuit (using square brackets) with `j`, i.e. this returns
        `this_circuit[j].components`.

        Parameters
        ----------
        j : int
            The index (depth) of the layer to be returned

        Returns
        -------
        tuple
        """
        return tuple(self.get_layer_label(j).components)

    def get_layer_label(self, j):
        """
        Returns the layer, as a :class:`Label`, at depth j. This label contains
        as components all the (non-identity) gates in the layer..

        Parameters
        ----------
        j : int
            The index (depth) of the layer to be returned

        Returns
        -------
        Label
        """
        assert(j >= 0 and j < self.num_layers()
               ), "Circuit layer label invalid! Circuit is only of depth {}".format(self.num_layers())
        return self[j]

    def get_layer_with_idles(self, j, idleGateName='I'):
        """
        Returns a tuple of the components of the layer at depth `j`,
        *including* `idleGateName` gates wherever there is an
        identity operation.

        Parameters
        ----------
        j : int
            The index (depth) of the layer to be returned

        Returns
        -------
        tuple
        """
        return tuple(self.get_layer_label_with_idles(j, idleGateName).components)

    def get_layer_label_with_idles(self, j, idleGateName='I'):
        """
        Returns the layer, as a :class:`Label`, at depth j. This list contains
        all the gates in the layer *including* `idleGateName` gates wherever
        there is an identity operation.

        Parameters
        ----------
        j : int
            The index (depth) of the layer to be returned

        Returns
        -------
        Label
        """
        layer_lbl = self.get_layer_label(j)  # (a Label)
        if layer_lbl.sslbls is None:
            return layer_lbl  # all qubits used - no idles to pad

        components = list(layer_lbl.components)
        for line_lbl in self.line_labels:
            if line_lbl not in layer_lbl.sslbls:
                components.append(_Label(idleGateName, line_lbl))
        return _Label(components)

    def num_layers(self):
        """
        The number of circuit layers. In simple circuits, this is also the
        depth.  For circuits containing sub-circuit blocks, this gives the
        number of top-level layers in this circuit.

        Returns
        -------
        int
        """
        return len(self._labels)

    def depth(self):
        """
        The circuit depth. This is the number of layers in simple circuits.
        For circuits containing sub-circuit blocks, this includes the
        depth of sub-circuits.

        Returns
        -------
        int
        """
        if self._static:
            return sum([lbl.depth() for lbl in self._labels])
        else:
            return sum([_Label(layer_lbl).depth() for layer_lbl in self._labels])

    def size(self):
        """
        Returns the circuit size, which is the sum of the sizes of all the
        gates in the circuit. A gate that acts on n-qubits has a size of n,
        with the exception of the idle which has a size of 0. Hence, the
        circuit is given by: `size = depth * num_lines - num_1Q_idles`.

        Returns
        -------
        int
        """
        #TODO HERE -update from here down b/c of sub-circuit blocks
        if self._static:
            def size(lbl):  # obj a Label, perhaps compound
                if lbl.issimple():  # a simple label
                    return len(lbl.sslbls) if (lbl.sslbls is not None) else len(self.line_labels)
                else:
                    return sum([size(sublbl) for sublbl in lbl.components])
        else:
            def size(obj):  # obj is either a simple label or a list
                if isinstance(obj, _Label):  # all Labels are simple labels
                    return len(obj.sslbls) if (obj.sslbls is not None) else len(self.line_labels)
                else:
                    return sum([size(sub) for sub in obj])

        return sum([size(layer_lbl) for layer_lbl in self._labels])

    def twoQgate_count(self):
        """
        The number of two-qubit gates in the circuit. (Note that this cannot
        distinguish between "true" 2-qubit gates and gate that have been defined
        to act on two qubits but that represent some tensor-product gate.)

        Returns
        -------
        int
        """
        return self.nQgate_count(2)

    def nQgate_count(self, nQ):
        """
        The number of `nQ`-qubit gates in the circuit. (Note that this cannot
        distinguish between "true" `nQ`-qubit gates and gate that have been
        defined to act on `nQ` qubits but that represent some tensor-product
        gate.)

        Parameters
        ----------
        nQ : int
            The qubit-count of the gates to count.  For example, if `nQ == 3`,
            this function returns the number of 3-qubit gates.

        Returns
        -------
        int
        """
        if self._static:
            def cnt(lbl):  # obj a Label, perhaps compound
                if lbl.issimple():  # a simple label
                    return 1 if (lbl.sslbls is not None) and (len(lbl.sslbls) == nQ) else 0
                else:
                    return sum([cnt(sublbl) for sublbl in lbl.components])
        else:
            def cnt(obj):  # obj is either a simple label or a list
                if isinstance(obj, _Label):  # all Labels are simple labels
                    return 1 if (obj.sslbls is not None) and (len(obj.sslbls) == nQ) else 0
                else:
                    return sum([cnt(sub) for sub in obj])

        return sum([cnt(layer_lbl) for layer_lbl in self._labels])

    def multiQgate_count(self):
        """
        The number of multi-qubit (2+ qubits) gates in the circuit. (Note that
        this cannot distinguish between "true" multi-qubit gates and gate that
        have been defined to act on more than one qubit but that represent some
        tensor-product gate.)

        Returns
        -------
        int
        """
        if self._static:
            def cnt(lbl):  # obj a Label, perhaps compound
                if lbl.issimple():  # a simple label
                    return 1 if (lbl.sslbls is not None) and (len(lbl.sslbls) >= 2) else 0
                else:
                    return sum([cnt(sublbl) for sublbl in lbl.components])
        else:
            def cnt(obj):  # obj is either a simple label or a list
                if isinstance(obj, _Label):  # all Labels are simple labels
                    return 1 if (obj.sslbls is not None) and (len(obj.sslbls) >= 2) else 0
                else:
                    return sum([cnt(sub) for sub in obj])

        return sum([cnt(layer_lbl) for layer_lbl in self._labels])

    # UNUSED
    #def predicted_error_probability(self, gate_error_probabilities):
    #    """
    #    Predicts the probability that one or more errors occur in the circuit
    #    if the gates have the error probabilities specified by in the input
    #    dictionary. Given correct error rates for the gates and stochastic errors,
    #    this is predictive of the probability of an error in the circuit. But note
    #    that that is generally *not* the same as the probability that the circuit
    #    implemented is incorrect (e.g., stochastic errors can cancel).
    #
    #    Parameters
    #    ----------
    #    gate_error_probabilities : dict
    #        A dictionary where the keys are the labels that appear in the circuit, and
    #        the value is the error probability for that gate.
    #
    #    Returns
    #    -------
    #    float
    #        The probability that there is one or more errors in the circuit.
    #    """
    #    f = 1.
    #    depth = self.num_layers()
    #    for i in range(0,self.number_of_lines()):
    #        for j in range(0,depth):
    #            gatelbl = self.line_items[i][j]
    #
    #            # So that we don't include multi-qubit gates more than once.
    #            if gatelbl.qubits is None:
    #                if i == 0:
    #                    f = f*(1-gate_error_probabilities[gatelbl])
    #            elif gatelbl.qubits[0] == self.line_labels[i]:
    #                f = f*(1-gate_error_probabilities[gatelbl])
    #    return 1 - f

    def _togrid(self, identityName):
        """ return a list-of-lists rep? """
        d = self.num_layers()
        line_items = [[_Label(identityName, ll)] * d for ll in self.line_labels]

        for ilayer in range(len(self._labels)):
            for layercomp in self._layer_components(ilayer):
                if isinstance(layercomp, _Label):
                    comp_label = layercomp
                    if layercomp.issimple():
                        comp_sslbls = layercomp.sslbls
                    else:
                        #We can't intelligently flatten compound labels that occur within a layer-label yet...
                        comp_sslbls = layercomp.sslbls
                else:  # layercomp must be a list (and _static == False)
                    comp_label = _Label(layercomp)
                    comp_sslbls = _sslbls_of_nested_lists_of_simple_labels(layercomp)
                if comp_sslbls is None: comp_sslbls = self.line_labels
                for sslbl in comp_sslbls:
                    lineIndx = self.line_labels.index(sslbl)  # replace w/dict for speed...
                    line_items[lineIndx][ilayer] = comp_label
        return line_items

    def __str__(self):
        """
        A text rendering of the circuit.
        """

        # If it's a circuit over no lines, return an empty string
        if self.number_of_lines() == 0: return ''

        s = ''
        Ctxt = 'C'  # if _sys.version_info <= (3, 0) else '\u25CF' # No unicode in
        Ttxt = 'T'  # if _sys.version_info <= (3, 0) else '\u2295' #  Python 2
        identityName = 'I'  # can be anything that isn't used in circuit

        def abbrev(lbl, k):  # assumes a simple label w/ name & qubits
            """ Returns what to print on line 'k' for label 'lbl' """
            lbl_qubits = lbl.qubits if (lbl.qubits is not None) else self.line_labels
            nqubits = len(lbl_qubits)
            if nqubits == 1 and lbl.name is not None:
                if isinstance(lbl, _CircuitLabel):  # HACK
                    return "|" + str(lbl) + "|"
                else:
                    return lbl.name
            elif lbl.name in ('CNOT', 'Gcnot') and nqubits == 2:  # qubit indices = (control,target)
                if k == self.line_labels.index(lbl_qubits[0]):
                    return Ctxt + str(lbl_qubits[1])
                else:
                    return Ttxt + str(lbl_qubits[0])
            elif lbl.name in ('CPHASE', 'Gcphase') and nqubits == 2:
                if k == self.line_labels.index(lbl_qubits[0]):
                    otherqubit = lbl_qubits[1]
                else:
                    otherqubit = lbl_qubits[0]
                return Ctxt + str(otherqubit)
            elif isinstance(lbl, _CircuitLabel):
                return "|" + str(lbl) + "|"
            else:
                return str(lbl)

        line_items = self._togrid(identityName)
        max_labellen = [max([len(abbrev(line_items[i][j], i))
                             for i in range(0, self.number_of_lines())])
                        for j in range(0, self.num_layers())]

        max_linelabellen = max([len(str(llabel)) for llabel in self.line_labels])

        for i in range(self.number_of_lines()):
            s += 'Qubit {} '.format(self.line_labels[i]) + ' ' * \
                (max_linelabellen - len(str(self.line_labels[i]))) + '---'
            for j, maxlbllen in enumerate(max_labellen):
                if line_items[i][j].name == identityName:
                    # Replace with special idle print at some point
                    #s += '-'*(maxlbllen+3) # 1 for each pipe, 1 for joining dash
                    s += '|' + ' ' * (maxlbllen) + '|-'
                else:
                    lbl = abbrev(line_items[i][j], i)
                    pad = maxlbllen - len(lbl)
                    s += '|' + ' ' * int(_np.floor(pad / 2)) + lbl + ' ' * int(_np.ceil(pad / 2)) + '|-'  # + '-'*pad
            s += '--\n'

        return s

    def __repr__(self):
        return "Circuit(%s)" % self.str

    def write_Qcircuit_tex(self, filename):  # TODO
        """
        Writes this circuit into a file, containing LaTex that will diplay this circuit using the
        Qcircuit.tex LaTex import (running LaTex requires the Qcircuit.tex file).

        Parameters
        ----------
        filename : str
            The file to write the LaTex into. Should end with '.tex'

        Returns
        -------
        None
        """
        raise NotImplementedError("TODO: need to upgrade this method")
        n = self.number_of_lines()
        d = self.num_layers()

        f = open(filename, 'w')
        f.write("\documentclass{article}\n")
        f.write("\\usepackage{mathtools}\n")
        f.write("\\usepackage{xcolor}\n")
        f.write("\\usepackage[paperwidth=" + str(5. + d * .3) +
                "in, paperheight=" + str(2 + n * 0.2) + "in,margin=0.5in]{geometry}")
        f.write("\input{Qcircuit}\n")
        f.write("\\begin{document}\n")
        f.write("\\begin{equation*}\n")
        f.write("\Qcircuit @C=1.0em @R=0.5em {\n")

        for q in range(0, n):
            qstring = '&'
            # The quantum wire for qubit q
            circuit_for_q = self.line_items[q]
            for gate in circuit_for_q:
                gate_qubits = gate.qubits if (gate.qubits is not None) else self.line_labels
                nqubits = len(gate_qubits)
                if gate.name == self.identity:
                    qstring += ' \qw &'
                elif gate.name in ('CNOT', 'Gcnot') and nqubits == 2:
                    if gate_qubits[0] == q:
                        qstring += ' \ctrl{' + str(gate_qubits[1] - q) + '} &'
                    else:
                        qstring += ' \\targ &'
                elif gate.name in ('CPHASE', 'Gcphase') and nqubits == 2:
                    if gate_qubits[0] == q:
                        qstring += ' \ctrl{' + str(gate_qubits[1] - q) + '} &'
                    else:
                        qstring += ' \control \qw &'

                else:
                    qstring += ' \gate{' + str(gate.name) + '} &'

            qstring += ' \qw & \\' + '\\ \n'
            f.write(qstring)

        f.write("}\end{equation*}\n")
        f.write("\end{document}")
        f.close()

    def convert_to_quil(self,
                        gatename_conversion=None,
                        qubit_conversion=None,
                        readout_conversion=None,
                        block_between_layers=True,
                        block_idles=True):  # TODO
        """
        Converts this circuit to a quil string.

        Parameters
        ----------
        gatename_conversion : dict,
        optional
            If not None, a dictionary that converts the gatenames in the circuit to the
            gatenames that will appear in the quil output. If only standard pyGSTi names
            are used (e.g., 'Gh', 'Gp', 'Gcnot', 'Gcphase', etc) this dictionary need not
            be specified, and an automatic conversion to the standard quil names will be
            implemented.

            * Currently some standard pyGSTi names do not have an inbuilt conversion to quil names.
            This will be fixed in the future *

        qubit_conversion : dict, optional
            If not None, a dictionary converting the qubit labels in the circuit to the
            desired qubit labels in the quil output. Can be left as None if the qubit
            labels are either (1) integers, or (2) of the form 'Qi' for integer i. In
            this case they are converted to integers (i.e., for (1) the mapping is trivial,
            for (2) the mapping strips the 'Q').

        readout_conversion : dict, optional
            If not None, a dictionary converting the qubit labels mapped through qubit_conversion
            to the bit labels for readot.  E.g. Suppose only qubit 2 (on Rigetti hardware)
            is in use.  Then the pyGSTi string will have only one qubit (labeled 0); it
            will get remapped to 2 via qubit_conversion={0:2}.  At the end of the quil
            circuit, readout should go recorded in bit 0, so readout_conversion = {0:0}.
            (That is, qubit with pyGSTi label 0 gets read to Rigetti bit 0, even though
            that qubit has Rigetti label 2.)

        Returns
        -------
        str
            A quil string.
        """

        # create standard conversations.
        if gatename_conversion is None:
            gatename_conversion = _itgs.get_standard_gatenames_quil_conversions()
        if qubit_conversion is None:
            # To tell us whether we have found a standard qubit labelling type.
            standardtype = False
            # Must first check they are strings, because cannot query q[0] for int q.
            if all([isinstance(q, str) for q in self.line_labels]):
                if all([q[0] == 'Q' for q in self.line_labels]):
                    standardtype = True
                    qubit_conversion = {llabel: int(llabel[1:]) for llabel in self.line_labels}
            if all([isinstance(q, int) for q in self.line_labels]):
                qubit_conversion = {q: q for q in self.line_labels}
                standardtype = True
            if not standardtype:
                raise ValueError(
                    "No standard qubit labelling conversion is available! Please provide `qubit_conversion`.")

        # Init the quil string.
        quil = ''
        depth = self.num_layers()

        quil += 'DECLARE ro BIT[{0}]\n'.format(str(self.number_of_lines()))

        quil += 'RESET\n'

        quil += 'PRAGMA INITIAL_REWIRING "NAIVE"\n'

        # Go through the layers, and add the quil for each layer in turn.
        for l in range(depth):

            # Get the layer, without identity gates and containing each gate only once.
            layer = self.get_layer_label(l)
            # For keeping track of which qubits have a gate on them in the layer.
            qubits_used = []

            # Go through the (non-self.identity) gates in the layer and convert them to quil
            for gate in layer.components:
                gate_qubits = gate.qubits if (gate.qubits is not None) else self.line_labels
                assert(len(gate_qubits) <=
                       2 or gate.qubits is None), 'Gate on more than 2 qubits given; this is currently not supported!'

                # Find the quil for the gate.
                quil_for_gate = gatename_conversion[gate.name]

                #If gate.qubits is None, gate is assumed to be single-qubit gate
                #acting in parallel on all qubits.  If the gate is a global idle, then
                #Pragma blocks are inserted (for tests like idle tomography) even
                #if block_between_layers==False.  Set block_idles=False to disable this as well.
                if gate.qubits is None:
                    if quil_for_gate == 'I':
                        if block_idles:
                            quil += 'PRAGMA PRESERVE_BLOCK\n'
                        for q in gate_qubits:
                            quil += quil_for_gate + ' ' + str(qubit_conversion[q]) + '\n'
                        if block_idles:
                            quil += 'PRAGMA END_PRESERVE_BLOCK\n'
                    else:
                        for q in gate_qubits:
                            quil += quil_for_gate + ' ' + str(qubit_conversion[q]) + '\n'

                #If gate.qubits is not None, then apply the one- or multi-qubit gate to
                #the explicitly specified qubits.
                else:
                    for q in gate_qubits: quil_for_gate += ' ' + str(qubit_conversion[q])
                    quil_for_gate += '\n'
                    # Add the quil for the gate to the quil string.
                    quil += quil_for_gate

                # Keeps track of the qubits that have been accounted for, and checks that hadn't been used
                # although that should already be checked in the .get_layer_label(), which checks for its a valid
                # circuit layer.
                assert(not set(gate_qubits).issubset(set(qubits_used)))
                qubits_used.extend(gate_qubits)

            # All gates that don't have a non-idle gate acting on them get an idle in the layer.
            for q in self.line_labels:
                if q not in qubits_used:
                    quil += 'I' + ' ' + str(qubit_conversion[q]) + '\n'

            # Add in a barrier after every circuit layer if block_between_layers==True.
            # Including pragma blocks are critical for QCVV testing, as circuits should usually
            # experience minimal "behind-the-scenes" compilation (beyond necessary
            # conversion to native instructions)
            # To do: Add "barrier" as native pygsti circuit instruction, and use for indicating
            # where pragma blocks should be.
            if block_between_layers:
                quil += 'PRAGMA PRESERVE_BLOCK\nPRAGMA END_PRESERVE_BLOCK\n'

        # Add in a measurement at the end.
        if readout_conversion == None:
            for q in self.line_labels:
                #            quil += "MEASURE {0} [{1}]\n".format(str(qubit_conversion[q]),str(qubit_conversion[q]))
                quil += "MEASURE {0} ro[{1}]\n".format(str(qubit_conversion[q]), str(qubit_conversion[q]))
        else:
            for q in self.line_labels:
                quil += "MEASURE {0} ro[{1}]\n".format(str(qubit_conversion[q]), str(readout_conversion[q]))

        return quil

    def convert_to_openqasm(self, gatename_conversion=None, qubit_conversion=None, block_between_layers=True):  # TODO
        """
        Converts this circuit to an openqasm string.

        Parameters
        ----------
        gatename_conversion : dict, optional
            If not None, a dictionary that converts the gatenames in the circuit to the
            gatenames that will appear in the openqasm output. If only standard pyGSTi names
            are used (e.g., 'Gh', 'Gp', 'Gcnot', 'Gcphase', etc) this dictionary need not
            be specified, and an automatic conversion to the standard openqasm names will be
            implemented.

        qubit_conversion : dict, optional
            If not None, a dictionary converting the qubit labels in the circuit to the
            desired qubit labels in the openqasm output. Can be left as None if the qubit
            labels are either (1) integers, or (2) of the form 'Qi' for integer i. In
            this case they are converted to integers (i.e., for (1) the mapping is trivial,
            for (2) the mapping strips the 'Q').

        Returns
        -------
        str
            An openqasm string.
        """

        # create standard conversations.
        if gatename_conversion is None:
            gatename_conversion = _itgs.get_standard_gatenames_openqasm_conversions()
        if qubit_conversion is None:
            # To tell us whether we have found a standard qubit labelling type.
            standardtype = False
            # Must first check they are strings, because cannot query q[0] for int q.
            if all([isinstance(q, str) for q in self.line_labels]):
                if all([q[0] == 'Q' for q in self.line_labels]):
                    standardtype = True
                    qubit_conversion = {llabel: int(llabel[1:]) for llabel in self.line_labels}
            if all([isinstance(q, int) for q in self.line_labels]):
                qubit_conversion = {q: q for q in self.line_labels}
                standardtype = True
            if not standardtype:
                raise ValueError(
                    "No standard qubit labelling conversion is available! Please provide `qubit_conversion`.")

        num_qubits = len(self.line_labels)

        # Init the openqasm string.
        openqasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n\n'

        openqasm += 'qreg q[{0}];\n'.format(str(num_qubits))
        openqasm += 'creg cr[{0}];\n'.format(str(num_qubits))
        openqasm += '\n'

        depth = self.num_layers()

        # Go through the layers, and add the openqasm for each layer in turn.
        for l in range(depth):

            # Get the layer, without identity gates and containing each gate only once.
            layer = self.get_layer_label(l)
            # For keeping track of which qubits have a gate on them in the layer.
            qubits_used = []

            # Go through the (non-self.identity) gates in the layer and convert them to openqasm
            for gate in layer.components:
                gate_qubits = gate.qubits if (gate.qubits is not None) else self.line_labels
                assert(len(gate_qubits) <= 2), 'Gates on more than 2 qubits given; this is currently not supported!'

                # Find the openqasm for the gate.
                openqasm_for_gate = gatename_conversion[gate.name]

                #If gate.qubits is None, gate is assumed to be single-qubit gate
                #acting in parallel on all qubits.
                if gate.qubits is None:
                    for q in gate_qubits:
                        openqasm += openqasm_for_gate + ' q[' + str(qubit_conversion[q]) + '];\n'
                else:
                    for q in gate_qubits:
                        openqasm_for_gate += ' q[' + str(qubit_conversion[q]) + ']'
                        if q != gate_qubits[-1]:
                            openqasm_for_gate += ', '
                    openqasm_for_gate += ';\n'
                # Add the openqasm for the gate to the openqasm string.
                    openqasm += openqasm_for_gate

                # Keeps track of the qubits that have been accounted for, and checks that hadn't been used
                # although that should already be checked in the .get_layer_label(), which checks for its a valid
                # circuit layer.
                assert(not set(gate_qubits).issubset(set(qubits_used)))
                qubits_used.extend(gate_qubits)

            # All gates that don't have a non-idle gate acting on them get an idle in the layer.
            for q in self.line_labels:
                if q not in qubits_used:
                    openqasm += 'id' + ' q[' + str(qubit_conversion[q]) + '];\n'

            # Add in a barrier after every circuit layer if block_between_layers==True.
            # Including barriers is critical for QCVV testing, circuits should usually
            # experience minimal "behind-the-scenes" compilation (beyond necessary
            # conversion to native instructions).
            # To do: Add "barrier" as native pygsti circuit instruction, and use for indicating
            # where pragma blocks should be.
            if block_between_layers:
                openqasm += 'barrier '
                for q in self.line_labels[:-1]:
                    openqasm += 'q[{0}], '.format(str(qubit_conversion[q]))
                openqasm += 'q[{0}];\n'.format(str(qubit_conversion[self.line_labels[-1]]))
    #            openqasm += ';'

        # Add in a measurement at the end.
        for q in self.line_labels:
            openqasm += "measure q[{0}] -> cr[{1}];\n".format(str(qubit_conversion[q]), str(qubit_conversion[q]))

        return openqasm

    def simulate(self, model, return_all_outcomes=False):
        """
        Compute the outcome probabilities of this Circuit using `model` as a
        model for the gates. The order of the outcome strings (e.g., '0100') is
        w.r.t. to the ordering of the qubits in the circuit. That is, the ith
        element of the outcome string corresponds to the qubit with label
        `self.qubit_labels[i]`.

        Parameters
        ----------
        model : Model
            A description of the gate and SPAM operations corresponding to the
            labels stored in this Circuit. If this model is over more qubits
            than the circuit, the output will be the probabilities for the qubits
            in the circuit marginalized over the other qubits. But, the simulation
            is over the full set of qubits in the model, and so the time taken for
            the simulation scales with the number of qubits in the model. For
            models whereby "spectator" qubits do not affect the qubits in this
            circuit (such as with perfect gates), more efficient simulations will
            be obtained by first creating a model only over the qubits in this
            circuit.

        return_all_outcomes: bool, optional
            Whether to include outcomes in the returned dictionary that have zero
            probability. When False, the threshold for discarding an outcome as z
            ero probability is 10^-12.

        Returns
        -------
        probs : dictionary
            A dictionary with keys equal to all (`return_all_outcomes` is True) or
            possibly only some (`return_all_outcomes` is False) of the possible
            outcomes, and values that are float probabilities.
        """
        # These results is a dict with strings of outcomes (normally bits) ordered according to the
        # state space ordering in the model.
        results = model.probs(self)

        # Mapping from the state-space labels of the model to their indices.
        # (e.g. if model.state_space_labels is [('Qa','Qb')] then sslInds['Qb'] = 1
        # (and 'Qb' may be a circuit line label)
        sslInds = {sslbl: i for i, sslbl in enumerate(model.state_space_labels.labels[0])}
        # Note: we ignore all but the first tensor product block of the state space.

        def process_outcome(outcome):
            """Relabels an outcome tuple and drops state space labels not in the circuit."""
            processed_outcome = []
            for lbl in outcome:  # lbl is a string - an instrument element or POVM effect label, e.g. '010'
                relbl = ''.join([lbl[sslInds[ll]] for ll in self.line_labels])
                processed_outcome.append(relbl)
                #Note: above code *assumes* that each state-space label (and so circuit line label)
                # corresponds to a *single* letter of the instrument/POVM label `lbl`.  This is almost
                # always the case, as state space labels are usually qubits and so effect labels are
                # composed of '0's and '1's.
            return tuple(processed_outcome)

        processed_results = _ld.OutcomeLabelDict()
        for outcome, pr in results.items():
            if return_all_outcomes or pr > 1e-12:  # then process & accumulate pr
                p_outcome = process_outcome(outcome)  # rearranges and drops parts of `outcome`
                if p_outcome in processed_results:  # (may occur b/c processing can map many-to-one)
                    processed_results[p_outcome] += pr  # adding marginalizes the results.
                else:
                    processed_results[p_outcome] = pr

        return processed_results

    def done_editing(self):
        """
        Make this circuit read-only, so that it can be hashed (e.g. used as a
        dictionary key).

        This is done automatically when attempting to hash a :class:`Circuit`
        for the first time, so there's calling this function can usually be
        skipped (but it's good for code clarity).

        Returns
        -------
        None
        """
        if not self._static:
            self._static = True
            self._labels = tuple([_Label(layer_lbl) for layer_lbl in self._labels])


class CompressedCircuit(object):
    """
    A "compressed" Circuit class which reduces the memory or disk space
    required to hold the tuple part of a Circuit by compressing it.

    One place where CompressedCircuit objects can be useful is when saving
    large lists of long operation sequences in some non-human-readable format (e.g.
    pickle).  CompressedCircuit objects *cannot* be used in place of
    Circuit objects within pyGSTi, and so are *not* useful when manipulating
    and running algorithms which use operation sequences.
    """

    def __init__(self, circuit, minLenToCompress=20, maxPeriodToLookFor=20):
        """
        Create a new CompressedCircuit object

        Parameters
        ----------
        circuit : Circuit
            The operation sequence object which is compressed to create
            a new CompressedCircuit object.

        minLenToCompress : int, optional
            The minimum length string to compress.  If len(circuit)
            is less than this amount its tuple is returned.

        maxPeriodToLookFor : int, optional
            The maximum period length to use when searching for periodic
            structure within circuit.  Larger values mean the method
            takes more time but could result in better compressing.
        """
        if not isinstance(circuit, Circuit):
            raise ValueError("CompressedCircuits can only be created from existing Circuit objects")
        self._tup = CompressedCircuit.compress_op_label_tuple(
            circuit.tup, minLenToCompress, maxPeriodToLookFor)
        self._str = circuit.str
        self._line_labels = circuit.line_labels

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state_dict):
        for k, v in state_dict.items():
            if k == 'tup':
                self._tup = state_dict['tup']  # backwards compatibility
            elif k == 'str':
                self._str = state_dict['str']  # backwards compatibility
            else:
                if k == "line_labels": k = "_line_labels"  # add underscore
                self.__dict__[k] = v
        if '_line_labels' not in state_dict and "line_labels" not in state_dict:
            self._line_labels = ('*',)

    def expand(self):
        """
        Expands this compressed operation sequence into a Circuit object.

        Returns
        -------
        Circuit
        """
        tup = CompressedCircuit.expand_op_label_tuple(self._tup)
        return Circuit(tup, self._line_labels, editable=False, stringrep=self._str, check=False)

    @staticmethod
    def _getNumPeriods(circuit, periodLen):
        n = 0
        if len(circuit) < periodLen: return 0
        while circuit[0:periodLen] == circuit[n * periodLen:(n + 1) * periodLen]:
            n += 1
        return n

    @staticmethod
    def compress_op_label_tuple(circuit, minLenToCompress=20, maxPeriodToLookFor=20):
        """
        Compress a operation sequence.  The result is tuple with a special compressed-
        gate-string form form that is not useable by other GST methods but is
        typically shorter (especially for long operation sequences with a repetative
        structure) than the original operation sequence tuple.

        Parameters
        ----------
        circuit : tuple of operation labels or Circuit
            The operation sequence to compress.

        minLenToCompress : int, optional
            The minimum length string to compress.  If len(circuit)
            is less than this amount its tuple is returned.

        maxPeriodToLookFor : int, optional
            The maximum period length to use when searching for periodic
            structure within circuit.  Larger values mean the method
            takes more time but could result in better compressing.

        Returns
        -------
        tuple
            The compressed (or raw) operation sequence tuple.
        """
        circuit = tuple(circuit)  # converts from Circuit or list to tuple if needed
        L = len(circuit)
        if L < minLenToCompress: return tuple(circuit)
        compressed = ["CCC"]  # list for appending, then make into tuple at the end
        start = 0
        while start < L:
            #print "Start = ",start
            score = _np.zeros(maxPeriodToLookFor + 1, 'd')
            numperiods = _np.zeros(maxPeriodToLookFor + 1, _np.int64)
            for periodLen in range(1, maxPeriodToLookFor + 1):
                n = CompressedCircuit._getNumPeriods(circuit[start:], periodLen)
                if n == 0: score[periodLen] = 0
                elif n == 1: score[periodLen] = 4.1 / periodLen
                else: score[periodLen] = _np.sqrt(periodLen) * n
                numperiods[periodLen] = n
            bestPeriodLen = _np.argmax(score)
            n = numperiods[bestPeriodLen]
            bestPeriod = circuit[start:start + bestPeriodLen]
            #print "Scores = ",score
            #print "num per = ",numperiods
            #print "best = %s ^ %d" % (str(bestPeriod), n)
            assert(n > 0 and bestPeriodLen > 0)
            if start > 0 and n == 1 and compressed[-1][1] == 1:
                compressed[-1] = (compressed[-1][0] + bestPeriod, 1)
            else:
                compressed.append((bestPeriod, n))
            start = start + bestPeriodLen * n

        return tuple(compressed)

    @staticmethod
    def expand_op_label_tuple(compressedOpLabels):
        """
        Expand a compressed tuple created with compress_op_label_tuple(...)
        into a tuple of operation labels.

        Parameters
        ----------
        compressedOpLabels : tuple
            a tuple in the compressed form created by
            compress_op_label_tuple(...).

        Returns
        -------
        tuple
            A tuple of operation labels specifying the uncompressed operation sequence.
        """
        if len(compressedOpLabels) == 0: return ()
        if compressedOpLabels[0] != "CCC": return compressedOpLabels
        expandedString = []
        for (period, n) in compressedOpLabels[1:]:
            expandedString += period * n
        return tuple(expandedString)
