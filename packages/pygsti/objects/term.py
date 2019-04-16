""" Defines classes which represent terms in gate expansions """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
import itertools as _itertools
import numbers as _numbers
from .polynomial import Polynomial as _Polynomial
from . import replib

LARGE = 1000000000  # a large number such that LARGE is
# a very high term weight which won't help (at all) a
# path get included in the selected set of paths.


def compose_terms(terms):
    """
    Compose a sequence of terms.

    Composition is done with *time* ordered left-to-right. Thus composition
    order is NOT the same as usual matrix order.
    E.g. if there are three terms:
    `terms[0]` = T0: rho -> A*rho*A
    `terms[1]` = T1: rho -> B*rho*B
    `terms[2]` = T2: rho -> C*rho*C
    Then the resulting term T = T0*T1*T2 : rho -> CBA*rho*ABC, so
    that term[0] is applied *first* not last to a state.

    Parameters
    ----------
    terms : list
        A list of terms to compose.

    Returns
    -------
    RankOneTerm
    """
    if len(terms) == 0:
        return RankOneTerm(1.0, None, None)
    ret = terms[0].copy()
    for t in terms[1:]:
        ret.compose(t)
    return ret


def exp_terms(terms, orders, postterm=None, order_base=None):
    """
    Exponentiate a list of terms, collecting those terms of the orders given
    in `orders`. Optionally post-multiplies the single term `postterm` (so this
    term actually acts *before* the exponential-derived terms).

    Parameters
    ----------
    terms : list
        The list of terms to exponentiate.  All these terms are
        considered "first order" terms.

    orders : list
        A list of integers specifying all the orders to collect.  These are
        the keys of the returned dictionary.

    postterm : RankOneTerm, optional
        A term that is composed *first* (so "post" in the sense of matrix
        multiplication, not composition).

    order_base : float
        What constitutes 1 order of magnitude.  If None, then
        polynomial coefficients are used.

    Returns
    -------
    dict
        Keys are the integer order values in `orders`.  Values are lists of
        :class:`RankOneTerm` objects giving the terms at that order.
    """

    #FUTURE: add "term_order" argument to specify what order a term in `terms`
    # is considered to be (not all necessarily = 1)

    #create terms for each order from terms and base action
    final_terms = {}
    if postterm is not None:
        Uterm_tup = (postterm,)
    else: Uterm_tup = ()

    for order in orders:  # expand exp(L) = I + L + 1/2! L^2 + ... (n-th term 1/n! L^n)
        if order == 0:
            final_terms[order] = [Uterm_tup[0]]; continue
        #TODO REMOVE
        #if order_base is not None:
        #    coeff_threshold = order_base**order
        one_over_factorial = 1 / _np.math.factorial(order)

        # expand 1/n! L^n into a list of rank-1 terms
        #termLists = [terms]*order
        final_terms[order] = []
        #for factors in _itertools.product(*termLists):
        #    factors_to_compose = Uterm_tup + factors # apply Uterm first
        #    #TODO REMOVE
        #    #if order_base is not None:
        #    #    coeff = _np.product([t.coeff for t in factors_to_compose])
        #        #LATER (will cause J=0 if we're not careful): if abs(coeff) < coeff_threshold: continue # don't include small terms
        #        # TODO: create new function that looks at all/many taylor orders and bins into order_base orders?
        #    final_terms[order].append( one_over_factorial * compose_terms(factors_to_compose) )

        #Alternate method
        test_terms = []

        def add_terms(term_list_index, composed_factors_so_far):
            if term_list_index == order:
                final_terms[order].append(composed_factors_so_far)
                return
            for factor in terms:  # termLists[term_list_index]:
                add_terms(term_list_index + 1, compose_terms((composed_factors_so_far, factor)))

        add_terms(0, one_over_factorial * Uterm_tup[0])

    return final_terms


def embed_term(term, stateSpaceLabels, targetLabels):
    """
    Embed a term to it acts within a larger state space.

    Internally, this simply converts a term's gate operators to embedded gate
    operations.

    Parameters
    ----------
    term : RankOneTerm
        The term to embed

    stateSpaceLabels : a list of tuples
        This argument specifies the density matrix space upon which the
        constructed term will act.  Each tuple corresponds to a block of a
        density matrix in the standard basis (and therefore a component of
        the direct-sum density matrix space).

    targetLabels : list
        The labels contained in `stateSpaceLabels` which demarcate the
        portions of the state space acted on by `term`.

    Returns
    -------
    RankOneTerm
    """
    from . import operation as _op
    ret = RankOneTerm(term.coeff, None, None, term.typ)
    ret.pre_ops = [_op.EmbeddedOp(stateSpaceLabels, targetLabels, op)
                   for op in term.pre_ops]
    ret.post_ops = [_op.EmbeddedOp(stateSpaceLabels, targetLabels, op)
                    for op in term.post_ops]
    return ret


class RankOneTerm(object):
    """
    An operation, like a gate, that maps a density matrix to another density
    matrix but in a more restricted way.  While a RankOneTerm doesn't have to
    map pure states to pure states, its action can be written:

    `rho -> A*rho*B`

    Where `A` and `B` are unitary state operations.  This means that if `rho`
    can be written `rho = |psi1><psi2|` then the action of a RankOneTerm
    preserves the separable nature or `rho` (which need not always be a valid
    density matrix since it can be just a portion of one).

    A RankOneTerm anticipates its application to "separable" (as defined above)
    states, and can even be used to represent such a separable state or an
    analagous POVM effect.  This occurs when the first element of `pre_ops` and
    `post_ops` is a preparation or POVM effect vector instead of a gate operation.

    Note that operations are stored in *composition (time) order* rather than
    matrix order, and that adjoint operations are stored in `post_ops` so that
    they can be applied directly to the adjoint of the "bra" part of the state
    (which is a "ket" - a usual state).

    Finally, a coefficient (usually a number or a :class:`Polynomial`) is held,
    representing the prefactor for this term as a part of a larger density
    matrix evolution.
    """
    import_cache = None  # to avoid slow re-importing withing RankOneTerm.__init__

    # For example, a term for the action:
    #
    # rho -> 5.0 * CBA * rho * AD
    #
    # will have members:
    # coeff = 5.0
    # pre_ops = [A, B, C]
    # post_ops = [ A^dag, D^dag ]

    # TODO: change typ to evotype and maybe allow "auto"?  should only need/allow "statevec" and "stabilizer" types?
    def __init__(self, coeff, pre_op, post_op, typ="dense"):
        """
        Initialize a new RankOneTerm.

        Parameters
        ----------
        coeff : object
            The coefficient of this term.

        pre_op : object
            Typically a LinearOperator- or SPAMVec-derived object giving the
            left-hand ("pre-rho") unitary action, pure state, or projection of
            the term.  Can be None to indicate no operation/state.

        post_op : object
            Typically a LinearOperator- or SPAMVec-derived object giving the *adjoint* of
            the right-hand ("post-rho") unitary action, pure state, or
            projection of the term. Can be None to indicate no operation/state.

        typ : {"dense", "clifford"}
            The type of operations being stored, either dense state-vector
            propagation or stabilizer state propagation

        """
        if self.__class__.import_cache is None:
            # slows function down significantly if don't put these in an if-block (surprisingly)
            from . import modelmember as _mm
            from . import operation as _op
            from . import spamvec as _spamvec
            self.__class__.import_cache = (_mm, _op, _spamvec)
        else:
            _mm, _op, _spamvec = self.__class__.import_cache

        self.coeff = coeff  # potentially a Polynomial
        if isinstance(self.coeff, _numbers.Number):
            self.magnitude = abs(coeff)
            self.logmagnitude = _np.log10(self.magnitude) if self.magnitude > 0 else -LARGE
        else:
            self.magnitude = 1.0
            self.logmagnitude = 0.0

        self.pre_ops = []  # list of ops to perform - in order of operation to a ket
        self.post_ops = []  # list of ops to perform - in order of operation to a bra
        self.typ = typ

        #NOTE: self.post_ops holds the *adjoints* of the actual post-rho-operators, so that
        #evolving a bra with the post_ops can be accomplished by flipping the bra -> ket and
        #applying the stored adjoints in the order stored in self.post_ops (similar to
        #acting with pre_ops in-order on a ket

        if pre_op is not None:
            if not isinstance(pre_op, _mm.ModelMember):
                try:
                    if typ == "dense":
                        pre_op = _op.StaticDenseOp(pre_op)
                    elif typ == "clifford":
                        pre_op = _op.CliffordOp(pre_op)
                    else: assert(False), "Invalid `typ` argument: %s" % typ
                except ValueError:  # raised when size/shape is wrong
                    if typ == "dense":
                        pre_op = _spamvec.StaticSPAMVec(pre_op)  # ... or spam vecs
                    else: assert(False), "No default vector for typ=%s" % typ
            self.pre_ops.append(pre_op)
        if post_op is not None:
            if not isinstance(post_op, _mm.ModelMember):
                try:
                    if typ == "dense":
                        post_op = _op.StaticDenseOp(post_op)
                    elif typ == "clifford":
                        post_op = _op.CliffordOp(post_op)
                    else: assert(False), "Invalid `typ` argument: %s" % typ
                except ValueError:  # raised when size/shape is wrong
                    if typ == "dense":
                        post_op = _spamvec.StaticSPAMVec(post_op)  # ... or spam vecs
                    else: assert(False), "No default vector for typ=%s" % typ
            self.post_ops.append(post_op)

    def __mul__(self, x):
        """ Multiply by scalar """
        ret = self.copy()
        ret.coeff *= x
        return ret

    def __rmul__(self, x):
        return self.__mul__(x)

    def set_magnitude(self, mag):
        """
        Sets the "magnitude" of this term used in path-pruning.  Sets
        both .magnitude and .logmagnitude attributes of this object.

        Parameters
        ----------
        mag : float
            The magnitude to set.

        Returns
        -------
        None
        """
        self.magnitude = mag
        self.logmagnitude = _np.log10(mag) if mag > 0 else -LARGE

    def compose(self, term):
        """
        Compose with `term`, which since it occurs to the *right*
        of this term, is applied *after* this term.

        Parameters
        ----------
        term : RankOneTerm
            The term to compose with.

        Returns
        -------
        None
        """
        self.coeff *= term.coeff
        self.pre_ops.extend(term.pre_ops)
        self.post_ops.extend(term.post_ops)

    def collapse(self):
        """
        Returns a copy of this term with all pre & post ops by reduced
        ("collapsed") by matrix composition, so that resulting
        term has only a single pre/post op. Ops must be compatible with numpy
        dot products.

        Returns
        -------
        RankOneTerm
        """
        if self.typ != "dense":
            raise NotImplementedError("Term collapse for types other than 'dense' are not implemented yet!")

        if len(self.pre_ops) >= 1:
            pre = self.pre_ops[0]  # .to_matrix() FUTURE??
            for B in self.pre_ops[1:]:
                pre = _np.dot(B, pre)  # FUTURE - something more general (compose function?)
        else: pre = None

        if len(self.post_ops) >= 1:
            post = self.post_ops[0]
            for B in self.post_ops[1:]:
                post = _np.dot(B, post)
        else: post = None

        return RankOneTerm(self.coeff, pre, post)

    #FUTURE: maybe have separate GateRankOneTerm and SPAMRankOneTerm which
    # derive from RankOneTerm, and only one collapse() function (also
    # this would avoid try/except logic elsewhere).
    def collapse_vec(self):
        """
        Returns a copy of this term with all pre & post ops by reduced
        ("collapsed") by action of LinearOperator ops on an initial SPAMVec.  This results
        in a term with only a single pre/post op which are SPAMVecs.

        Returns
        -------
        RankOneTerm
        """

        if self.typ != "dense":
            raise NotImplementedError("Term collapse_vec for types other than 'dense' are not implemented yet!")

        if len(self.pre_ops) >= 1:
            pre = self.pre_ops[0].todense()  # first op is a SPAMVec
            for B in self.pre_ops[1:]:  # and the rest are Gates
                pre = B.acton(pre)
        else: pre = None

        if len(self.post_ops) >= 1:
            post = self.post_ops[0].todense()  # first op is a SPAMVec
            for B in self.post_ops[1:]:  # and the rest are Gates
                post = B.acton(post)
        else: post = None

        return RankOneTerm(self.coeff, pre, post)

    def copy(self):
        """
        Copy this term.

        Returns
        -------
        RankOneTerm
        """
        coeff = self.coeff if isinstance(self.coeff, _numbers.Number) \
            else self.coeff.copy()
        copy_of_me = RankOneTerm(coeff, None, None, self.typ)
        copy_of_me.pre_ops = self.pre_ops[:]
        copy_of_me.post_ops = self.post_ops[:]
        return copy_of_me

    def map_indices_inplace(self, mapfn):
        """
        Performs a bulk find & replace on the coefficient polynomial's variable
        indices.  This function should only be called when this term's
        coefficient is a :class:`Polynomial`.

        Parameters
        ----------
        mapfn : function
            A function that takes as input an "old" variable-index-tuple
            (a key of this Polynomial) and returns the updated "new"
            variable-index-tuple.

        Returns
        -------
        None
        """
        assert(hasattr(self.coeff, 'map_indices_inplace')), \
            "Coefficient (type %s) must implements `map_indices_inplace`" % str(type(self.coeff))
        self.coeff.map_indices_inplace(mapfn)

    def torep(self, max_poly_order, max_poly_vars, typ):
        """
        Construct a representation of this term.

        "Representations" are lightweight versions of objects used to improve
        the efficiency of intensely computational tasks, used primarily
        internally within pyGSTi.

        Parameters
        ----------
        max_poly_order : int
            The maximum order (degree) for the coefficient polynomial's
            representation.

        max_num_vars : int
            The maximum number of variables for the coefficient polynomial's
            represenatation.

        typ : { "prep", "effect", "gate" }
            What type of representation is needed (these correspond to
            different types of representation objects).  Given the type of
            operations stored within a term, only one of "gate" and
            "prep"/"effect" is appropriate.

        Returns
        -------
        SVTermRep or SBTermRep
        """
        #Note: typ == "prep" / "effect" / "gate"
        # whereas self.typ == "dense" / "clifford" (~evotype)
        if isinstance(self.coeff, _numbers.Number):
            coeffrep = self.coeff
            RepTermType = replib.SVTermDirectRep if (self.typ == "dense") \
                else replib.SBTermDirectRep
        else:
            coeffrep = self.coeff.torep(max_poly_order, max_poly_vars)
            RepTermType = replib.SVTermRep if (self.typ == "dense") \
                else replib.SBTermRep

        if typ == "prep":  # first el of pre_ops & post_ops is a state vec
            return RepTermType(coeffrep, self.magnitude, self.logmagnitude,
                               self.pre_ops[0].torep("prep"),
                               self.post_ops[0].torep("prep"), None, None,
                               [op.torep() for op in self.pre_ops[1:]],
                               [op.torep() for op in self.post_ops[1:]])
        elif typ == "effect":  # first el of pre_ops & post_ops is an effect vec
            return RepTermType(coeffrep, self.magnitude, self.logmagnitude,
                               None, None, self.pre_ops[0].torep("effect"),
                               self.post_ops[0].torep("effect"),
                               [op.torep() for op in self.pre_ops[1:]],
                               [op.torep() for op in self.post_ops[1:]])
        else:
            assert(typ == "gate"), "Invalid typ argument to torep: %s" % typ
            return RepTermType(coeffrep, self.magnitude, self.logmagnitude,
                               None, None, None, None,
                               [op.torep() for op in self.pre_ops],
                               [op.torep() for op in self.post_ops])

    def evaluate_coeff(self, variable_values):
        """
        Evaluate this term's polynomial coefficient for a given set of variable values.

        Parameters
        ----------
        variable_values : array-like
            An object that can be indexed so that `variable_values[i]` gives the
            numerical value for i-th variable (x_i) in this term's coefficient.

        Returns
        -------
        RankOneTerm
            A shallow copy of this object with floating-point coefficient
        """
        coeff = self.coeff.evaluate(variable_values)
        copy_of_me = RankOneTerm(coeff, None, None, self.typ)
        copy_of_me.pre_ops = self.pre_ops[:]
        copy_of_me.post_ops = self.post_ops[:]
        return copy_of_me
