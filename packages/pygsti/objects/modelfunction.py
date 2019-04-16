""" Defines the ModelFunction class """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************


class ModelFunction(object):
    """
    Encapsulates a "function of a Model" that one may want to compute
    confidence-interval error bars for based on a confidence region of
    the functions model argument.  The "function" may have other parameters,
    and the reason for defining it as a class is so that it can hold

    1. relevant "meta" arguments in addition to the central Model, and
    2. information to speed up function evaluations at nearby Model "points",
       for computing finite-difference derivatives.
    """

    def __init__(self, model, dependencies):
        """
        Creates a new ModelFunction object.

        Parameters
        ----------
        model : Model
            A sample model giving the constructor a template for what
            type/parameterization of model to expect in calls to
            :func:`evaluate`.

        dependencies : list
            A list of *type:label* strings, or the special strings `"all"` and
            `"spam"`, indicating which Model parameters the function depends
            upon. Here *type* can be `"gate"`, `"prep"`, `"povm"`, or
            `"instrument"`, and  *label* can be any of the corresponding labels
            found in the models being evaluated.  The reason for specifying
            this at all is to speed up computation of the finite difference
            derivative needed to find the error bars.
        """
        self.base_model = model
        self.dependencies = dependencies

    def evaluate(self, model):
        """ Evaluate this gate-set-function at `model`."""
        return None

    def evaluate_nearby(self, nearby_model):
        """
        Evaluate this gate-set-function at `nearby_model`, which can
        be assumed is very close to the `model` provided to the last
        call to :func:`evaluate`.
        """
        # do stuff assuming nearby_model is eps away from model
        return self.evaluate(nearby_model)

    def get_dependencies(self):
        """
        Return the dependencies of this gate-set-function.

        Returns
        -------
        list
            A list of *type:label* strings, or the special strings `"all"` and
            `"spam"`, indicating which Model parameters the function depends
            upon. Here *type* can be `"gate"`, `"prep"`, `"povm"`, or
            `"instrument"` and *label* can be any of the corresponding labels
            found in the models being evaluated.
        """
        return self.dependencies
        #determines which variations in model are used when computing confidence regions


def spamfn_factory(fn):
    """
    Ceates a class that evaluates
    `fn(preps,povms,...)`, where `preps` and `povms` are lists of the
    preparation SPAM vectors and POVMs of a Model, respectively,
    and `...` are additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the two parameters as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model, ...)` where `model` is a Model and `...` are optional
        additional arguments that are passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by spamfn_factory """

        def __init__(self, model, *args, **kwargs):
            """
            Creates a new ModelFunction dependent only on its Model
            argument's SPAM vectors.
            """
            self.args = args
            self.kwargs = kwargs
            ModelFunction.__init__(self, model, ["spam"])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            return fn(list(model.preps.values()),
                      list(model.povms.values()),
                      *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp

#Note: the 'basis' argument is unnecesary here, as it could be passed as an additional arg


def opfn_factory(fn):
    """
    Creates a class that evaluates `fn(gate,basis,...)`, where `gate` is a
    single operation matrix, `basis` describes what basis it's in, and `...` are
    additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the two parameters as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model, gl, ...)` where `model` is a Model, `gl` is a gate
        label, and `...` are optional additional arguments passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by opfn_factory """

        def __init__(self, model, gl, *args, **kwargs):
            """ Creates a new ModelFunction dependent on a single gate"""
            self.gl = gl
            self.args = args
            self.kwargs = kwargs
            ModelFunction.__init__(self, model, ["gate:" + str(gl)])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            return fn(model.operations[self.gl].todense(), model.basis,
                      *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp


#Note: the 'op2' and 'basis' arguments are unnecesary here, as they could be
# passed as additional args
def opsfn_factory(fn):
    """
    Creates a class that evaluates `fn(op1,op2,basis,...)`, where `op1`
    and `op2` are a single operation matrices, `basis` describes what basis they're
    in, and `...` are additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the two parameters as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model1, model2, gl, ...)` where `model1` and `model2` are
        Models (only `model1` and `op1` are varied when computing a
        confidence region), `gl` is a operation label, and `...` are optional
        additional arguments passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by opsfn_factory """

        def __init__(self, model1, model2, gl, *args, **kwargs):
            """ Creates a new ModelFunction dependent on a single gate"""
            self.other_model = model2
            self.gl = gl
            self.args = args
            self.kwargs = kwargs
            ModelFunction.__init__(self, model1, ["gate:" + str(gl)])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            return fn(model.operations[self.gl].todense(), self.other_model.operations[self.gl].todense(),
                      model.basis, *self.args, **self.kwargs)  # assume functions want *dense* gates

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp


def vecfn_factory(fn):
    """
    Creates a class that evaluates `fn(vec,basis,...)`, where `vec` is a
    single SPAM vector, `basis` describes what basis it's in, and `...` are
    additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the two parameters as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model, lbl, typ, ...)` where `model` is a Model, `lbl` is
        SPAM vector label, `typ` is either `"prep"` or `"effect"` (the type of
        the SPAM vector), and `...` are optional additional arguments
        passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by vecfn_factory """

        def __init__(self, model, lbl, typ, *args, **kwargs):
            """ Creates a new ModelFunction dependent on a single SPAM vector"""
            self.lbl = lbl
            self.typ = typ
            self.args = args
            self.kwargs = kwargs
            assert(typ in ['prep', 'effect']), "`typ` argument must be either 'prep' or 'effect'"
            if typ == 'effect':
                typ = "povm"
                lbl, _ = lbl.split(":")  # for "effect"-mode, lbl must == "povmLbl:ELbl"
                # and ModelFunction depends on entire POVM
            ModelFunction.__init__(self, model, [typ + ":" + str(lbl)])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            if self.typ == "prep":
                return fn(model.preps[self.lbl].todense(), model.basis,
                          *self.args, **self.kwargs)
            else:
                povmlbl, Elbl = self.lbl.split(":")  # for effect, lbl must == "povmLbl:ELbl"
                return fn(model.povms[povmlbl][Elbl].todense(), model.basis,
                          *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp


def vecsfn_factory(fn):
    """
    Creates a class that evaluates `fn(vec1, vec2, basis,...)`, where `vec1`
    and `vec2` are SPAM vectors, `basis` describes what basis they're in, and
    `...` are additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the two parameters as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model1, model2, lbl, typ, ...)` where `model1` and `model2`
        are Models (only `model1` and `vec1` are varied when computing a
        confidence region), `lbl` is a SPAM vector label, `typ` is either
        `"prep"` or `"effect"` (the type of the SPAM vector), and `...` are
        optional additional arguments passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by vecsfn_factory """

        def __init__(self, model1, model2, lbl, typ, *args, **kwargs):
            """ Creates a new ModelFunction dependent on a single SPAM vector"""
            self.other_model = model2
            self.lbl = lbl
            self.typ = typ
            self.args = args
            self.kwargs = kwargs
            assert(typ in ['prep', 'effect']), "`typ` argument must be either 'prep' or 'effect'"
            if typ == 'effect':
                typ = "povm"
                lbl, _ = lbl.split(":")  # for "effect"-mode, lbl must == "povmLbl:ELbl"
                # and ModelFunction depends on entire POVM
            self.other_vecsrc = self.other_model.preps if self.typ == "prep" \
                else self.other_model.povms
            ModelFunction.__init__(self, model1, [typ + ":" + str(lbl)])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            if self.typ == "prep":
                return fn(model.preps[self.lbl].todense(), self.other_vecsrc[self.lbl].todense(),
                          model.basis, *self.args, **self.kwargs)
            else:
                povmlbl, Elbl = self.lbl.split(":")  # for effect, lbl must == "povmLbl:ELbl"
                return fn(model.povms[povmlbl][Elbl].todense(), self.other_vecsrc[povmlbl][Elbl].todense(),
                          model.basis, *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp


def povmfn_factory(fn):
    """
    Ceates a class that evaluates
    `fn(model,...)` where `model` is the entire Model (and it is assumed
    that `fn` is only a function of the POVM effect elements of the model),
    and `...` are additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the one parameter as discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model, ...)` where `model` is a Model and `...` are optional
        additional arguments that are passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by povmfn_factory """

        def __init__(self, model, *args, **kwargs):
            """
            Creates a new ModelFunction dependent on all of its
            Model argument's effects
            """
            self.args = args
            self.kwargs = kwargs
            dps = ["povm:%s" % l for l in model.povms]
            ModelFunction.__init__(self, model, dps)

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            return fn(model, *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp


def modelfn_factory(fn):
    """
    Creates a class that evaluates `fn(model,...)`, where `model` is a
    `Model` object and `...` are additional arguments (see below).

    Parameters
    ----------
    fn : function
        A function of at least the single `model` parameter discussed above.

    Returns
    -------
    cls : class
        A :class:`ModelFunction`-derived class initialized by
        `cls(model, ...)` where `model` is a Model, and `...` are
        optional additional arguments passed to `fn`.
    """
    class GSFTemp(ModelFunction):
        """ ModelFunction class created by modelfn_factory """

        def __init__(self, model, *args, **kwargs):
            """
            Creates a new ModelFunction dependent on all of its Model
            argument's paramters
            """
            self.args = args
            self.kwargs = kwargs
            ModelFunction.__init__(self, model, ["all"])

        def evaluate(self, model):
            """ Evaluate this gate-set-function at `model`."""
            return fn(model, *self.args, **self.kwargs)

    GSFTemp.__name__ = fn.__name__ + str("_class")
    return GSFTemp
