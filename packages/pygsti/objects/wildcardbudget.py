"""Functions related to computation of the log-likelihood."""
from __future__ import division, print_function, absolute_import, unicode_literals
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import numpy as _np
from .. import tools as _tools


class WildcardBudget(object):
    """
    Encapsulates a fixed amount of "wildcard budget" that allows each circuit
    an amount "slack" in its outcomes probabilities.  The way in which this
    slack is computed - or "distributed", though it need not necessarily sum to
    a fixed total - per circuit depends on each derived class's implementation
    of the :method:`circuit_budget` method.  Goodness-of-fit quantities such as
    the log-likelihood or chi2 can utilize a `WildcardBudget` object to compute
    a value that shifts the circuit outcome probabilities within their allowed
    slack (so `|p_used - p_actual| <= slack`) to achieve the best goodness of
    fit.  For example, see the `wildcard` argument of :function:`two_delta_logl_terms`.

    This is a base class, which must be inherited from in order to obtain a
    full functional wildcard budge (the `circuit_budget` method must be
    implemented and usually `__init__` should accept more customized args).
    """

    def __init__(self, Wvec):
        """
        Create a new WildcardBudget.

        Parameters
        ----------
        Wvec : numpy array
            The "wildcard vector" which stores the parameters of this budget
            which can be varied when trying to find an optimal budget (similar
            to the parameters of a :class:`Model`).
        """
        self.wildcard_vector = Wvec

    def to_vector(self):
        """
        Get the parameters of this wildcard budget.

        Returns
        -------
        numpy array
        """
        return self.wildcard_vector

    def from_vector(self, Wvec):
        """
        Set the parameters of this wildcard budge.

        Parameters
        ----------
        Wvec : numpy array
            A vector of parameter values.

        Returns
        -------
        None
        """
        self.wildcard_vector = Wvec

    def circuit_budget(self, circuit):
        """
        Get the amount of wildcard budget, or "outcome-probability-slack"
        for `circuit`.

        Parameters
        ----------
        circuit : Circuit

        Returns
        -------
        float
        """
        raise NotImplementedError("Derived classes must implement `circuit_budget`")

    def get_descriptive_dict(self):
        """
        Return the contents of this budget in a dictionary containing
        (description, value) pairs for each element name.

        Returns
        -------
        dict
        """
        raise NotImplementedError("Derived classes must implement `to_descriptive_dict`")

    #def compute_circuit_wildcard_budget(c, Wvec):
    #    #raise NotImplementedError("TODO!!!")
    #    #for now, assume Wvec is a length-1 vector
    #    return abs(Wvec[0]) * len(c)

    def update_probs(self, probs_in, probs_out, freqs, circuits, elIndices):
        """
        Update a set of circuit outcome probabilities, `probs_in`, into a
        corresponding set, `probs_out`, which uses the slack alloted to each
        outcome probability to match (as best as possible) the data frequencies
        in `freqs`.  In particular, it computes this best-match in a way that
        maximizes the likelihood between `probs_out` and `freqs`. This method is
        the core function of a :class:`WildcardBudget`.

        Parameters
        ----------
        probs_in : numpy array
            The input probabilities, usually computed by a :class:`Model`.

        probs_out : numpy array
            The output probabilities: `probs_in`, adjusted according to the
            slack allowed by this wildcard budget, in order to maximize
            `logl(probs_out, freqs)`.  Note that `probs_out` may be the same
            array as `probs_in` for in-place updating.

        freqs : numpy array
            An array of frequencies corresponding to each of the
            outcome probabilites in `probs_in` or `probs_out`.

        circuits : list
            A list of :class:`Circuit` objects giving the circuits that
            `probs_in` contains the outcome probabilities of.  Typically
            there are multiple outcomes per circuit, so `len(circuits)`
            is less than `len(probs_in)` - see `elIndices` below.

        elIndices : list or numpy array
            A list of the element indices corresponding to each circuit in
            `circuits`.  Thus, `probs_in[elIndices[i]]` must give the
            probabilities corresponding to `circuits[i]`, and `elIndices[i]`
            can be any valid index for a numpy array (an integer, a slice,
            or an integer-array).  Similarly, `freqs[elIndices[i]]` gives
            the corresponding frequencies.

        Returns
        -------
        None
        """

        #For these helper functions, see Robin's notes
        def computeTVD(A, B, alpha, beta, q, f):
            # TVD = 0.5 * (qA - alpha*SA + beta*SB - qB)  - difference between p=[alpha|beta]*f and q (no contrib from set C)
            ret = 0.5 * (sum(q[A] - alpha * f[A]) + sum(beta * f[B] - q[B]))
            return ret

        def compute_alpha(A, B, C, TVD, q, f):
            # beta = (1-alpha*SA - qC)/SB
            # 2*TVD = qA - alpha*SA + [(1-alpha*SA - qC)/SB]*SB - qB
            # 2*TVD = qA - alpha(SA + SA) + (1-qC) - qB
            # alpha = [ qA-qB + (1-qC) - 2*TVD ] / 2*SA
            # But if SB == 0 then 2*TVD = qA - alpha*SA - qB => alpha = (qA-qB-2*TVD)/SA
            if sum(f[B]) == 0:
                return (sum(q[A]) - sum(q[B]) - 2 * TVD) / sum(f[A])
            return (sum(q[A]) - sum(q[B]) + 1.0 - sum(q[C]) - 2 * TVD) / (2 * sum(f[A]))

        def compute_beta(A, B, C, TVD, q, f):
            # alpha = (1-beta*SB - qC)/SA
            # 2*TVD = qA - [(1-beta*SB - qC)/SA]*SA + beta*SB - qB
            # 2*TVD = qA - (1-qC) + beta(SB + SB) - qB
            # beta = -[ qA-qB - (1-qC) - 2*TVD ] / 2*SB
            # But if SA == 0 then 2*TVD = qA + beta*SB - qB => beta = -(qA-qB-2*TVD)/SB
            if sum(f[A]) == 0:
                return -(sum(q[A]) - sum(q[B]) - 2 * TVD) / sum(f[B])
            return -(sum(q[A]) - sum(q[B]) - 1.0 + sum(q[C]) - 2 * TVD) / (2 * sum(f[B]))

        def compute_pvec(alpha, beta, A, B, C, q, f):
            p = f.copy()
            #print("Fill pvec alpha=%g, beta=%g" % (alpha,beta))
            #print("f = ",f, " A = ",A, "B=",B," C=",C)
            p[A] = alpha * f[A]
            p[B] = beta * f[B]
            p[C] = q[C]
            return p

        def alpha_fn(beta, A, B, C, q, f):
            if len(A) == 0: return _np.nan  # this can be ok, but mark it
            return (1.0 - beta * sum(f[B]) - sum(q[C])) / sum(f[A])

        def beta_fn(alpha, A, B, C, q, f):
            # beta * SB = 1 - alpha * SA - qC   => 1 = alpha*SA + beta*SB + qC (probs sum to 1)
            # also though, beta must be > 0 so (alpha*SA + qC) < 1.0
            if len(B) == 0: return _np.nan  # this can be ok, but mark it
            return (1.0 - alpha * sum(f[A]) - sum(q[C])) / sum(f[B])

        def get_minalpha_breakpoint(remaining_indices, A, B, C, qvec):
            k,r = sorted([(kx,rx) for kx, rx in enumerate(ratio_vec) if kx in remaining_indices], key=lambda x: abs(1.0-x[1]))[0]
            if k in A:
                alpha_break = r
                beta_break = beta_fn(alpha_break, A, B, C, qvec, fvec)
                #print("alpha-break = %g -> beta-break = %g" % (alpha_break,beta_break))
                AorBorC = "A"
            elif k in B:
                beta_break = r
                alpha_break = alpha_fn(beta_break, A, B, C, qvec, fvec)
                #print("beta-break = %g -> alpha-break = %g" % (beta_break,alpha_break))
                AorBorC = "B"
            else:
                alpha_break = beta_break = 1e100 # sentinel so it gets sorted at end
                AorBorC = "C"
            if debug: print("chksum = ",chk_sum(alpha_break, beta_break))
            return (k, alpha_break, beta_break, AorBorC)


        def chk_sum(alpha,beta):
            return alpha * sum(fvec[A]) + beta * sum(fvec[B]) + sum(fvec[C])

        #Special case where f_k=0, since ratio is ill-defined. One might think
        # we shouldn't don't bother wasting any TVD on these since the corresponding
        # p_k doesn't enter the likelihood. ( => treat these components as if f_k == q_k (ratio = 1))
        # BUT they *do* enter in poisson-picture logl... so set freqs very small so ratio is large (and probably not chosen)
        zero_inds = _np.where(freqs == 0.0)[0]
        if len(zero_inds) > 0:
            freqs = freqs.copy()  # copy for now instead of doing something more clever
            freqs[zero_inds] = 1e-8
            #freqs[zero_inds] = probs_in[zero_inds]  # OLD (use this if f_k=0 terms don't enter likelihood)

        for i, circ in enumerate(circuits):
            elInds = elIndices[i]
            qvec = probs_in[elInds]
            fvec = freqs[elInds]
            W = self.circuit_budget(circ)

            initialTVD = 0.5 * sum(_np.abs(qvec - fvec))
            if initialTVD <= W:  # TVD is already "in-budget" for this circuit - can adjust to fvec exactly
                _tools.matrixtools._fas(probs_out, (elInds,), fvec)
                continue

            A = _np.where(qvec > fvec)[0]
            B = _np.where(qvec < fvec)[0]
            C = _np.where(qvec == fvec)[0]

            debug = False #(i == 827)

            if debug:
                print("Circuit %d: %s" % (i,circ))
                print(" inds = ",elInds, "q = ",qvec, " f = ",fvec)
                print(" budget = ",W, " A=",A," B=",B," C=",C)

            #Note: need special case for fvec == 0
            ratio_vec = qvec / fvec  # TODO: replace with more complex condition:
            if debug: print("  Ratio vec = ", ratio_vec)

            remaining_indices = list(range(len(ratio_vec)))
            
            while len(remaining_indices) > 0:
                j, alpha0, beta0, AorBorC = get_minalpha_breakpoint(remaining_indices, A, B, C, qvec)
                remaining_indices.remove(j)
                
                # will keep getting smaller with each iteration
                TVD_at_breakpt = computeTVD(A, B, alpha0, beta0, qvec, fvec)
                #Note: does't matter if we move j from A or B -> C before calling this, as alpha0 is set so results is
                #the same

                if debug: print("break: j=",j," alpha=",alpha0," beta=",beta0," A?=",AorBorC, " TVD = ",TVD_at_breakpt)
                tol = 1e-6  # for instance, when W==0 and TVD_at_breakpt is 1e-17
                if TVD_at_breakpt <= W + tol:
                    break  # exit loop

                #Move
                if AorBorC == "A":
                    if debug:
                        beta_chk1 = beta_fn(alpha0, A, B, C, qvec, fvec)
                    Alst = list(A); del Alst[Alst.index(j)]; A = _np.array(Alst, int)
                    Clst = list(C); Clst.append(j); C = _np.array(Clst, int)  # move A -> C
                    if debug:
                        beta_chk2 = beta_fn(alpha0, A, B, C, qvec, fvec)
                        print("CHKA: ",alpha0, beta0, beta_chk1, beta_chk2)
                    
                elif AorBorC == "B":
                    if debug:
                        alpha_chk1 = alpha_fn(beta0, A, B, C, qvec, fvec)
                    Blst = list(B); del Blst[Blst.index(j)]; B = _np.array(Blst, int)
                    Clst = list(C); Clst.append(j); C = _np.array(Clst, int)  # move B -> C
                    if debug:
                        alpha_chk2 = alpha_fn(beta0, A, B, C, qvec, fvec)
                        print("CHKB: ",alpha0, beta0, alpha_chk1, alpha_chk2)

                else:
                    pass
                
                if debug: TVD_at_breakpt_chk = computeTVD(A, B, alpha0, beta0, qvec, fvec)
                if debug: print(" --> A=",A," B=",B," C=",C, " chk = ",TVD_at_breakpt_chk)

            else:
                assert(False), "TVD should eventually reach zero (I think)!"

            #Now A,B,C are fixed to what they need to be for our given W
            if debug: print("Final A=",A,"B=",B,"C=",C,"W=",W,"qvec=",qvec,'fvec=',fvec)
            if len(A) > 0:
                alpha = compute_alpha(A, B, C, W, qvec, fvec)
                beta = beta_fn(alpha, A, B, C, qvec, fvec)
                if debug and len(B) > 0:
                    abeta = compute_beta(A, B, C, W, qvec, fvec)
                    aalpha = alpha_fn(beta, A, B, C, qvec, fvec)
                    print("ALT final alpha,beta = ",aalpha,abeta)
            else:  # fall back to this when len(A) == 0
                beta = compute_beta(A, B, C, W, qvec, fvec)
                alpha = alpha_fn(beta, A, B, C, qvec, fvec)
            if debug:
                print("Computed final alpha,beta = ",alpha,beta)
                print("CHECK SUM = ",chk_sum(alpha,beta))
                print("DB: probs_in = ",probs_in[elInds])
            _tools.matrixtools._fas(probs_out, (elInds,), compute_pvec(alpha, beta, A, B, C, qvec, fvec))
            if debug:
                print("DB: probs_out = ",probs_out[elInds])
            #print("TVD = ",computeTVD(A,B,alpha,beta_fn(alpha,A,B,C,fvec),qvec,fvec))
            compTVD = computeTVD(A, B, alpha, beta, qvec, fvec)
            #print("compare: ",W,compTVD)
            assert(abs(W - compTVD) < 1e-3), "TVD mismatch!"
            #assert(_np.isclose(W, compTVD)), "TVD mismatch!"

        return


class PrimitiveOpsWildcardBudget(WildcardBudget):
    """
    A wildcard budget containing one parameter per "primitive operation".

    A parameter's absolute value gives the amount of "slack", or
    "wildcard budget" that is allocated per that particular primitive
    operation.

    Primitive operations are the components of circuit layers, and so
    the wilcard budget for a circuit is just the sum of the (abs vals of)
    the parameters corresponding to each primitive operation in the circuit.
    """

    def __init__(self, primitiveOpLabels, add_spam=True, start_budget=0.0):
        """
        Create a new PrimitiveOpsWildcardBudget.

        Parameters
        ----------
        primitiveOpLabels : iterable
            A list of primitive-operation labels, e.g. `Label('Gx',(0,))`,
            which give all the possible primitive ops (components of circuit
            layers) that will appear in circuits.  Each one of these operations
            will be assigned it's own independent element in the wilcard-vector.

        add_spam : bool, optional
            Whether an additional "SPAM" budget should be included, which is
            simply a uniform budget added to each circuit.

        start_budget : float, optional
            An initial value to set all the parameters to.
        """
        self.primOpLookup = {lbl: i for i, lbl in enumerate(primitiveOpLabels)}
        nPrimOps = len(self.primOpLookup)
        if add_spam:
            nPrimOps += 1
            self.spam_index = nPrimOps-1  #last element is SPAM
        else:
            self.spam_index = None

        Wvec = _np.array([start_budget] * nPrimOps)
        super(PrimitiveOpsWildcardBudget, self).__init__(Wvec)

    def circuit_budget(self, circuit):
        """
        Get the amount of wildcard budget, or "outcome-probability-slack"
        for `circuit`.

        Parameters
        ----------
        circuit : Circuit

        Returns
        -------
        float
        """
        Wvec = self.wildcard_vector
        budget = 0 if (self.spam_index is None) else abs(Wvec[self.spam_index])
        for layer in circuit:
            for component in layer.components:
                budget += abs(Wvec[self.primOpLookup[component]])
        return budget

    def get_descriptive_dict(self):
        """
        Return the contents of this budget in a dictionary containing
        (description, value) pairs for each element name.

        Returns
        -------
        dict
        """
        wildcardDict = {}
        for lbl, index in self.primOpLookup.items():
            wildcardDict[lbl] = ('budget per each instance %s' % lbl, abs(self.wildcard_vector[index]))
        if self.spam_index is not None:
            wildcardDict['SPAM'] = ('uniform per-circuit SPAM budget', abs(self.wildcard_vector[self.spam_index]))
        return wildcardDict

    def get_op_budget(self, op_label):
        """
        Retrieve the budget amount correponding to primitive op `op_label`.

        This is just the absolute value of this wildcard budget's parameter
        that corresponds to `op_label`.

        Parameters
        ----------
        op_label : Label

        Returns
        -------
        float
        """
        return abs(self.wildcard_vector[self.primOpLookup[op_label]])

    def __str__(self):
        wildcardDict = {lbl: abs(self.wildcard_vector[index]) for lbl, index in self.primOpLookup.items()}
        if self.spam_index is not None: wildcardDict['SPAM'] = abs(self.wildcard_vector[self.spam_index])
        return "Wildcard budget: " + str(wildcardDict)
