"""Functions related to computation of the log-likelihood."""
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import numpy as _np
from .. import tools as _tools


class WildcardBudget(object):
    """ TODO: docstring for entire module """

    def __init__(self, Wvec):
        self.wildcard_vector = Wvec

    def to_vector(self):
        return self.wildcard_vector

    def from_vector(self, Wvec):
        self.wildcard_vector = Wvec

    def circuit_budget(self, circuit):
        raise NotImplementedError("Derived classes must implement `circuit_budget`")

    #def compute_circuit_wildcard_budget(c, Wvec):
    #    #raise NotImplementedError("TODO!!!")
    #    #for now, assume Wvec is a length-1 vector
    #    return abs(Wvec[0]) * len(c)

    def update_probs(self, probs_in, probs_out, freqs, circuits, elIndices):
        """ Note: probs_in can == probs_out for in-place updating """

        def computeTVD(A, B, alpha, beta, q, f):
            ret = 0.5 * (sum(q[A] - alpha * f[A]) + sum(beta * f[B] - q[B]))
            return ret

        def compute_alpha(A, B, C, TVD, q, f):
            # beta = (1-alpha*SA - SC)/SB
            # 2*TVD = qA - alpha*SA + [(1-alpha*SA - SC)/SB]*SB - qB
            # 2*TVD = qA - alpha(SA + SA) + (1-SC) - qB
            # alpha = [ qA-qB + (1-SC) - 2*TVD ] / 2*SA
            return (sum(q[A]) - sum(q[B]) + 1.0 - sum(f[C]) - 2 * TVD) / (2 * sum(f[A]))

        def compute_beta(A, B, C, TVD, q, f):
            # alpha = (1-beta*SB - SC)/SA
            # 2*TVD = qA - [(1-beta*SB - SC)/SA]*SA + beta*SB - qB
            # 2*TVD = qA - (1-SC) + beta(SB + SB) - qB
            # beta = -[ qA-qB - (1-SC) - 2*TVD ] / 2*SB
            return -(sum(q[A]) - sum(q[B]) - 1.0 + sum(f[C]) - 2 * TVD) / (2 * sum(f[B]))

        def compute_pvec(alpha, beta, A, B, C, q, f):
            p = f.copy()
            #print("Fill pvec alpha=%g, beta=%g" % (alpha,beta))
            #print("f = ",f, " A = ",A, "B=",B," C=",C)
            p[A] = alpha * f[A]
            p[B] = beta * f[B]
            p[C] = q[C]
            return p

        def alpha_fn(beta, A, B, C, f):
            if len(A) == 0: return _np.nan  # this can be ok, but mark it
            return (1.0 - beta * sum(f[B]) - sum(f[C])) / sum(f[A])

        def beta_fn(alpha, A, B, C, f):
            if len(B) == 0: return _np.nan  # this can be ok, but mark it
            return (1.0 - alpha * sum(f[A]) - sum(f[C])) / sum(f[B])

        #Special case where f_k=0 - then don't bother wasting any TVD on
        # these since the corresponding p_k doesn't enter the likelihood.
        # => treat these components as if f_k == q_k (ratio = 1)
        zero_inds = _np.where(freqs == 0.0)[0]
        if len(zero_inds) > 0:
            freqs = freqs.copy()  # copy for now instead of doing something more clever
            freqs[zero_inds] = probs_in[zero_inds]

        for i, circ in enumerate(circuits):
            elInds = elIndices[i]
            #outLbls = outcomes_lookup[i] # needed?
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

            #print("Circuit %d: %s" % (i,circ))
            #print(" inds = ",elInds, "q = ",qvec, " f = ",fvec)
            #print(" budget = ",W, " A=",A," B=",B," C=",C)

            #Note: need special case for fvec == 0
            ratio_vec = qvec / fvec  # TODO: replace with more complex condition:
            #print("  Ratio vec = ", ratio_vec)

            breaks = []
            for k, r in enumerate(ratio_vec):
                if k in A:
                    alpha_break = r
                    beta_break = beta_fn(alpha_break, A, B, C, fvec)
                    #print("alpha-break = %g -> beta-break = %g" % (alpha_break,beta_break))
                    AorB = True
                elif k in B:
                    beta_break = r
                    alpha_break = alpha_fn(beta_break, A, B, C, fvec)
                    #print("beta-break = %g -> alpha-break = %g" % (beta_break,alpha_break))
                    AorB = False
                breaks.append((k, alpha_break, beta_break, AorB))
            #print("Breaks = ",breaks)

            sorted_breaks = sorted(breaks, key=lambda x: x[1])
            for j, alpha0, beta0, AorB in sorted_breaks:
                # will keep getting smaller with each iteration
                TVD_at_breakpt = computeTVD(A, B, alpha0, beta0, qvec, fvec)
                #Note: does't matter if we move j from A or B -> C before calling this, as alpha0 is set so results is
                #the same

                #print("break: j=",j," alpha=",alpha0," beta=",beta0," A?=",AorB, " TVD = ",TVD_at_breakpt)
                tol = 1e-6  # for instance, when W==0 and TVD_at_breakpt is 1e-17
                if TVD_at_breakpt <= W + tol:
                    break  # exit loop

                #Move
                if AorB:  # A
                    Alst = list(A); del Alst[Alst.index(j)]; A = _np.array(Alst, int)
                    Clst = list(C); Clst.append(j); C = _np.array(Clst, int)  # move A -> C
                else:  # B
                    Blst = list(B); del Blst[Blst.index(j)]; B = _np.array(Blst, int)
                    Clst = list(C); Clst.append(j); C = _np.array(Clst, int)  # move B -> C
                    #B.remove(j); C.add(j) # move A -> C
                #print(" --> A=",A," B=",B," C=",C)
            else:
                assert(False), "TVD should eventually reach zero (I think)!"

            #Now A,B,C are fixed to what they need to be for our given W
            if len(A) > 0:
                alpha = compute_alpha(A, B, C, W, qvec, fvec)
                beta = beta_fn(alpha, A, B, C, fvec)
            else:  # fall back to this when len(A) == 0
                beta = compute_beta(A, B, C, W, qvec, fvec)
                alpha = alpha_fn(beta, A, B, C, fvec)
            _tools.matrixtools._fas(probs_out, (elInds,), compute_pvec(alpha, beta, A, B, C, qvec, fvec))
            #print("TVD = ",computeTVD(A,B,alpha,beta_fn(alpha,A,B,C,fvec),qvec,fvec))
            compTVD = computeTVD(A, B, alpha, beta, qvec, fvec)
            #print("compare: ",W,compTVD)
            assert(abs(W - compTVD) < 1e-3), "TVD mismatch!"
            #assert(_np.isclose(W, compTVD)), "TVD mismatch!"

        return


class PrimitiveOpsWildcardBudget(WildcardBudget):
    """ TODO: docstring """

    def __init__(self, primitiveOpLabels, start_budget=0.01):
        self.primOpLookup = {lbl: i for i, lbl in enumerate(primitiveOpLabels)}
        nPrimOps = len(self.primOpLookup)
        Wvec = _np.array([start_budget] * nPrimOps) + start_budget / 10.0 * \
            _np.arange(nPrimOps)  # 2nd term to slightly offset initial values
        super(PrimitiveOpsWildcardBudget, self).__init__(Wvec)

    def circuit_budget(self, circuit):
        Wvec = self.wildcard_vector
        budget = 0
        for layer in circuit:
            for component in layer.components:
                budget += abs(Wvec[self.primOpLookup[component]])
        return budget

    def get_op_budget(self, op_label):
        return abs(self.wildcard_vector[self.primOpLookup[op_label]])

    def __str__(self):
        wildcardDict = {lbl: abs(self.wildcard_vector[index]) for lbl, index in self.primOpLookup.items()}
        return "Wildcard budget: " + str(wildcardDict)
