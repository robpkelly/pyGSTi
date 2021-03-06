""" Custom implementation of the Levenberg-Marquardt Algorithm """
from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import time as _time
import numpy as _np
import scipy as _scipy
import signal as _signal
#from scipy.optimize import OptimizeResult as _optResult

from ..tools import mpitools as _mpit
from ..baseobjs import VerbosityPrinter as _VerbosityPrinter

#Make sure SIGINT will generate a KeyboardInterrupt (even if we're launched in the background)
_signal.signal(_signal.SIGINT, _signal.default_int_handler)

#constants
MACH_PRECISION = 1e-12
#MU_TOL1 = 1e10 # ??
#MU_TOL2 = 1e3  # ??


def custom_leastsq(obj_fn, jac_fn, x0, f_norm2_tol=1e-6, jac_norm_tol=1e-6,
                   rel_ftol=1e-6, rel_xtol=1e-6, max_iter=100, num_fd_iters=0,
                   max_dx_scale=1.0, comm=None, verbosity=0, profiler=None):
    """
    An implementation of the Levenberg-Marquardt least-squares optimization
    algorithm customized for use within pyGSTi.  This general purpose routine
    mimic to a large extent the interface used by `scipy.optimize.leastsq`,
    though it implements a newer (and more robust) version of the algorithm.

    Parameters
    ----------
    obj_fn : function
        The objective function.  Must accept and return 1D numpy ndarrays of
        length N and M respectively.  Same form as scipy.optimize.leastsq.

    jac_fn : function
        The jacobian function (not optional!).  Accepts a 1D array of length N
        and returns an array of shape (M,N).

    x0 : numpy.ndarray
        Initial evaluation point.

    f_norm2_tol : float, optional
        Tolerace for `F^2` where `F = `norm( sum(obj_fn(x)**2) )` is the
        least-squares residual.  If `F**2 < f_norm2_tol`, then mark converged.

    jac_norm_tol : float, optional
        Tolerance for jacobian norm, namely if `infn(dot(J.T,f)) < jac_norm_tol`
        then mark converged, where `infn` is the infinity-norm and
        `f = obj_fn(x)`.

    rel_ftol : float, optional
        Tolerance on the relative reduction in `F^2`, that is, if
        `d(F^2)/F^2 < rel_ftol` then mark converged.

    rel_xtol : float, optional
        Tolerance on the relative value of `|x|`, so that if
        `d(|x|)/|x| < rel_xtol` then mark converged.

    max_iter : int, optional
        The maximum number of (outer) interations.

    num_fd_iters : int optional
        Internally compute the Jacobian using a finite-difference method
        for the first `num_fd_iters` iterations.  This is useful when `x0`
        lies at a special or singular point where the analytic Jacobian is
        misleading.

    max_dx_scale : float, optional
        If not None, impose a limit on the magnitude of the step, so that
        `|dx|^2 < max_dx_scale^2 * len(dx)` (so elements of `dx` should be,
        roughly, less than `max_dx_scale`).

    comm : mpi4py.MPI.Comm, optional
        When not None, an MPI communicator for distributing the computation
        across multiple processors.

    verbosity : int, optional
        Amount of detail to print to stdout.

    profiler : Profiler, optional
        A profiler object used for to track timing and memory usage.


    Returns
    -------
    x : numpy.ndarray
        The optimal solution.
    converged : bool
        Whether the solution converged.
    msg : str
        A message indicating why the solution converged (or didn't).
    """

    printer = _VerbosityPrinter.build_printer(verbosity, comm)

    msg = ""
    converged = False
    x = x0
    f = obj_fn(x)
    norm_f = _np.dot(f, f)  # _np.linalg.norm(f)**2
    half_max_nu = 2**62  # what should this be??
    tau = 1e-3
    nu = 2
    mu = 0  # initialized on 1st iter
    my_cols_slice = None

    # don't let any component change by more than ~max_dx_scale
    if max_dx_scale:
        max_norm_dx = (max_dx_scale**2) * x.size
    else: max_norm_dx = None

    if not _np.isfinite(norm_f):
        msg = "Infinite norm of objective function at initial point!"

    # DB: from ..tools import matrixtools as _mt
    # DB: print("DB F0 (%s)=" % str(f.shape)); _mt.print_mx(f,prec=0,width=4)
    # num_fd_iters = 1000000 # DEBUG: use finite difference iterations instead
    # print("DEBUG: setting num_fd_iters == 0!");  num_fd_iters = 0 # DEBUG
    try:

        for k in range(max_iter):  # outer loop
            # assume x, f, fnorm hold valid values

            #t0 = _time.time() # REMOVE
            if len(msg) > 0:
                break  # exit outer loop if an exit-message has been set

            if norm_f < f_norm2_tol:
                msg = "Sum of squares is at most %g" % f_norm2_tol
                converged = True; break

            #printer.log("--- Outer Iter %d: norm_f = %g, mu=%g" % (k,norm_f,mu))

            if profiler: profiler.mem_check("custom_leastsq: begin outer iter *before de-alloc*")
            Jac = None; JTJ = None; JTf = None

            #printer.log("PT1: %.3fs" % (_time.time()-t0)) # REMOVE
            if profiler: profiler.mem_check("custom_leastsq: begin outer iter")
            if k >= num_fd_iters:
                Jac = jac_fn(x)
            else:
                eps = 1e-7
                Jac = _np.empty((len(f), len(x)), 'd')
                for i in range(len(x)):
                    x_plus_dx = x.copy()
                    x_plus_dx[i] += eps
                    Jac[:, i] = (obj_fn(x_plus_dx) - f) / eps
            #printer.log("PT2: %.3fs" % (_time.time()-t0)) # REMOVE

            #DEBUG: compare with analytic jacobian (need to uncomment num_fd_iters DEBUG line above too)
            #Jac_analytic = jac_fn(x)
            #if _np.linalg.norm(Jac_analytic-Jac) > 1e-6:
            #    print("JACDIFF = ",_np.linalg.norm(Jac_analytic-Jac)," per el=",
            #          _np.linalg.norm(Jac_analytic-Jac)/Jac.size," sz=",Jac.size)

            # DB: from ..tools import matrixtools as _mt
            # DB: print("DB JAC (%s)=" % str(Jac.shape)); _mt.print_mx(Jac,prec=0,width=4); assert(False)
            if profiler: profiler.mem_check("custom_leastsq: after jacobian:"
                                            + "shape=%s, GB=%.2f" % (str(Jac.shape),
                                                                     Jac.nbytes / (1024.0**3)))

            Jnorm = _np.linalg.norm(Jac)
            printer.log("--- Outer Iter %d: norm_f = %g, mu=%g, |J|=%g" % (k, norm_f, mu, Jnorm))

            #assert(_np.isfinite(Jac).all()), "Non-finite Jacobian!" # NaNs tracking
            #assert(_np.isfinite(_np.linalg.norm(Jac))), "Finite Jacobian has inf norm!" # NaNs tracking
            scaleFctr = 1.0  # _np.linalg.norm(Jac)
            Jac /= scaleFctr
            f /= scaleFctr
            #assert(_np.isfinite(Jac).all()), "Post-scaled non-finite Jacobian!" # NaNs tracking
            #assert(_np.isfinite(_np.linalg.norm(Jac))), "Post-scaled Jacobian has inf norm!" # NaNs tracking

            tm = _time.time()
            if my_cols_slice is None:
                my_cols_slice = _mpit.distribute_for_dot(Jac.shape[0], comm)
            #printer.log("PT3: %.3fs" % (_time.time()-t0)) # REMOVE
            JTJ = _mpit.mpidot(Jac.T, Jac, my_cols_slice, comm)  # _np.dot(Jac.T,Jac)
            #printer.log("PT4: %.3fs" % (_time.time()-t0)) # REMOVE
            JTf = _np.dot(Jac.T, f)
            #printer.log("PT5: %.3fs" % (_time.time()-t0)) # REMOVE
            if profiler: profiler.add_time("custom_leastsq: dotprods", tm)
            #assert(not _np.isnan(JTJ).any()), "NaN in JTJ!" # NaNs tracking
            #assert(not _np.isinf(JTJ).any()), "inf in JTJ! norm Jac = %g" % _np.linalg.norm(Jac) # NaNs tracking
            #assert(_np.isfinite(JTJ).all()), "Non-finite JTJ!" # NaNs tracking
            #assert(_np.isfinite(JTf).all()), "Non-finite JTf!" # NaNs tracking

            idiag = _np.diag_indices_from(JTJ)
            norm_JTf = _np.linalg.norm(JTf, ord=_np.inf)
            norm_x = _np.dot(x, x)  # _np.linalg.norm(x)**2
            undampled_JTJ_diag = JTJ.diagonal().copy()
            #printer.log("PT6: %.3fs" % (_time.time()-t0)) # REMOVE

            if norm_JTf < jac_norm_tol:
                msg = "norm(jacobian) is at most %g" % jac_norm_tol
                converged = True; break

            if k == 0:
                #mu = tau # initial damping element
                mu = tau * _np.max(undampled_JTJ_diag)  # initial damping element
                #mu = min(mu, MU_TOL1)

            #determing increment using adaptive damping
            while True:  # inner loop

                if profiler: profiler.mem_check("custom_leastsq: begin inner iter")
                JTJ[idiag] += mu / scaleFctr**2  # augment normal equations
                #JTJ[idiag] *= (1.0 + mu) # augment normal equations

                #assert(_np.isfinite(JTJ).all()), "Non-finite JTJ (inner)!" # NaNs tracking
                #assert(_np.isfinite(JTf).all()), "Non-finite JTf (inner)!" # NaNs tracking

                try:
                    if profiler: profiler.mem_check("custom_leastsq: before linsolve")
                    tm = _time.time()
                    success = True
                    #dx = _np.linalg.solve(JTJ, -JTf)
                    #NEW scipy: dx = _scipy.linalg.solve(JTJ, -JTf, assume_a='pos') #or 'sym'
                    dx = _scipy.linalg.solve(JTJ, -JTf, sym_pos=True)
                    if profiler: profiler.add_time("custom_leastsq: linsolve", tm)
                #except _np.linalg.LinAlgError:
                except _scipy.linalg.LinAlgError:
                    success = False

                if profiler: profiler.mem_check("custom_leastsq: after linsolve")
                if success:  # linear solve succeeded
                    new_x = x + dx
                    norm_dx = _np.dot(dx, dx)  # _np.linalg.norm(dx)**2

                    #ensure dx isn't too large - don't let any component change by more than ~max_dx_scale
                    if max_norm_dx and norm_dx > max_norm_dx:
                        dx *= _np.sqrt(max_norm_dx / norm_dx)
                        new_x = x + dx
                        norm_dx = _np.dot(dx, dx)  # _np.linalg.norm(dx)**2

                    printer.log("  - Inner Loop: mu=%g, norm_dx=%g" % (mu, norm_dx), 2)

                    if norm_dx < (rel_xtol**2) * norm_x:  # and mu < MU_TOL2:
                        msg = "Relative change in |x| is at most %g" % rel_xtol
                        converged = True; break

                    if norm_dx > (norm_x + rel_xtol) / (MACH_PRECISION**2):
                        msg = "(near-)singular linear system"; break

                    new_f = obj_fn(new_x)
                    # DB: from ..tools import matrixtools as _mt
                    # DB: print("DB XNEW (%s)=" % str(new_x.shape)); print(new_x)
                    # DB: print("DB FNEW (%s)=" % str(new_f.shape)); print(new_f); assert(False)

                    if profiler: profiler.mem_check("custom_leastsq: after obj_fn")
                    norm_new_f = _np.dot(new_f, new_f)  # _np.linalg.norm(new_f)**2
                    if not _np.isfinite(norm_new_f):  # avoid infinite loop...
                        msg = "Infinite norm of objective function!"; break

                    dL = _np.dot(dx, mu * dx - JTf)  # expected decrease in ||F||^2 from linear model
                    dF = norm_f - norm_new_f      # actual decrease in ||F||^2

                    printer.log("      (cont): norm_new_f=%g, dL=%g, dF=%g, reldL=%g, reldF=%g" %
                                (norm_new_f, dL, dF, dL / norm_f, dF / norm_f), 2)

                    if dL / norm_f < rel_ftol and dF >= 0 and dF / norm_f < rel_ftol and dF / dL < 2.0:
                        msg = "Both actual and predicted relative reductions in the" + \
                            " sum of squares are at most %g" % rel_ftol
                        converged = True; break

                    if profiler: profiler.mem_check("custom_leastsq: before success")

                    if dL > 0 and dF > 0:
                        # reduction in error: increment accepted!
                        t = 1.0 - (2 * dF / dL - 1.0)**3  # dF/dL == gain ratio
                        mu *= max(t, 1.0 / 3.0)
                        nu = 2
                        x, f, norm_f = new_x, new_f, norm_new_f
                        printer.log("      Accepted! gain ratio=%g  mu * %g => %g"
                                    % (dF / dL, max(t, 1.0 / 3.0), mu), 2)

                        #assert(_np.isfinite(x).all()), "Non-finite x!" # NaNs tracking
                        #assert(_np.isfinite(f).all()), "Non-finite f!" # NaNs tracking

                        ##Check to see if we *would* switch to Q-N method in a hybrid algorithm
                        #new_Jac = jac_fn(new_x)
                        #new_JTf = _np.dot(new_Jac.T,new_f)
                        #print(" CHECK: %g < %g ?" % (_np.linalg.norm(new_JTf,
                        #    ord=_np.inf),0.02 * _np.linalg.norm(new_f)))

                        break  # exit inner loop normally
                else:
                    printer.log("LinSolve Failure!!", 2)

                # if this point is reached, either the linear solve failed
                # or the error did not reduce.  In either case, reject increment.

                #Increase damping (mu), then increase damping factor to
                # accelerate further damping increases.
                mu *= nu
                if nu > half_max_nu:  # watch for nu getting too large (&overflow)
                    msg = "Stopping after nu overflow!"; break
                nu = 2 * nu
                printer.log("      Rejected!  mu => mu*nu = %g, nu => 2*nu = %g"
                            % (mu, nu), 2)

                JTJ[idiag] = undampled_JTJ_diag  # restore diagonal
            #end of inner loop

            #printer.log("PT7: %.3fs" % (_time.time()-t0)) # REMOVE
        #end of outer loop
        else:
            #if no break stmt hit, then we've exceeded maxIter
            msg = "Maximum iterations (%d) exceeded" % max_iter
            converged = True  # call result "converged" even in this case, but issue warning:
            printer.warning("Treating result as *converged* after maximum iterations (%d) were exceeded." % max_iter)

    except KeyboardInterrupt:
        if comm is not None:
            # ensure all procs agree on what x is (in case the interrupt occurred around x being updated)
            comm.Bcast(x, root=0)
            printer.log("Rank %d caught keyboard interrupt!  Returning the current solution as being *converged*."
                        % comm.Get_rank())
        else:
            printer.log("Caught keyboard interrupt!  Returning the current solution as being *converged*.")
        msg = "Keyboard interrupt!"
        converged = True

    #JTJ[idiag] = undampled_JTJ_diag #restore diagonal
    return x, converged, msg
    #solution = _optResult()
    #solution.x = x; solution.fun = f
    #solution.success = converged
    #solution.message = msg
    #return solution


#Wikipedia-version of LM algorithm, testing mu and mu/nu damping params and taking
# mu/nu => new_mu if acceptable...  This didn't seem to perform well, but maybe just
# needs some tweaking, so leaving it commented here for reference
#def custom_leastsq_wikip(obj_fn, jac_fn, x0, f_norm_tol=1e-6, jac_norm_tol=1e-6,
#                   rel_tol=1e-6, max_iter=100, comm=None, verbosity=0, profiler=None):
#    msg = ""
#    converged = False
#    x = x0
#    f = obj_fn(x)
#    norm_f = _np.linalg.norm(f)
#    tau = 1e-3 #initial mu
#    nu = 1.3
#    my_cols_slice = None
#
#
#    if not _np.isfinite(norm_f):
#        msg = "Infinite norm of objective function at initial point!"
#
#    for k in range(max_iter): #outer loop
#        # assume x, f, fnorm hold valid values
#
#        if len(msg) > 0:
#            break #exit outer loop if an exit-message has been set
#
#        if norm_f < f_norm_tol:
#            msg = "norm(objectivefn) is small"
#            converged = True; break
#
#        if verbosity > 0:
#            print("--- Outer Iter %d: norm_f = %g" % (k,norm_f))
#
#        if profiler: profiler.mem_check("custom_leastsq: begin outer iter *before de-alloc*")
#        Jac = None; JTJ = None; JTf = None
#
#        if profiler: profiler.mem_check("custom_leastsq: begin outer iter")
#        Jac = jac_fn(x)
#        if profiler: profiler.mem_check("custom_leastsq: after jacobian:"
#                                        + "shape=%s, GB=%.2f" % (str(Jac.shape),
#                                                        Jac.nbytes/(1024.0**3)) )
#
#        tm = _time.time()
#        if my_cols_slice is None:
#            my_cols_slice = _mpit.distribute_for_dot(Jac.shape[0], comm)
#        JTJ = _mpit.mpidot(Jac.T,Jac,my_cols_slice,comm)   #_np.dot(Jac.T,Jac)
#        JTf = _np.dot(Jac.T,f)
#        if profiler: profiler.add_time("custom_leastsq: dotprods",tm)
#
#        idiag = _np.diag_indices_from(JTJ)
#        norm_JTf = _np.linalg.norm(JTf) #, ord='inf')
#        norm_x = _np.linalg.norm(x)
#        undampled_JTJ_diag = JTJ.diagonal().copy()
#
#        if norm_JTf < jac_norm_tol:
#            msg = "norm(jacobian) is small"
#            converged = True; break
#
#        if k == 0:
#            mu = tau #* _np.max(undampled_JTJ_diag) # initial damping element
#        #mu = tau #* _np.max(undampled_JTJ_diag) # initial damping element
#
#        #determing increment using adaptive damping
#        while True:  #inner loop
#
#            ### Evaluate with mu' = mu / nu
#            mu = mu / nu
#            if profiler: profiler.mem_check("custom_leastsq: begin inner iter")
#            JTJ[idiag] *= (1.0 + mu) # augment normal equations
#            #JTJ[idiag] += mu # augment normal equations
#
#            try:
#                if profiler: profiler.mem_check("custom_leastsq: before linsolve")
#                tm = _time.time()
#                success = True
#                dx = _np.linalg.solve(JTJ, -JTf)
#                if profiler: profiler.add_time("custom_leastsq: linsolve",tm)
#            except _np.linalg.LinAlgError:
#                success = False
#
#            if profiler: profiler.mem_check("custom_leastsq: after linsolve")
#            if success: #linear solve succeeded
#                new_x = x + dx
#                norm_dx = _np.linalg.norm(dx)
#
#                #if verbosity > 1:
#                #    print("--- Inner Loop: mu=%g, norm_dx=%g" % (mu,norm_dx))
#
#                if norm_dx < rel_tol*norm_x: #use squared qtys instead (speed)?
#                    msg = "relative change in x is small"
#                    converged = True; break
#
#                if norm_dx > (norm_x+rel_tol)/MACH_PRECISION:
#                    msg = "(near-)singular linear system"; break
#
#                new_f = obj_fn(new_x)
#                if profiler: profiler.mem_check("custom_leastsq: after obj_fn")
#                norm_new_f = _np.linalg.norm(new_f)
#                if not _np.isfinite(norm_new_f): # avoid infinite loop...
#                    msg = "Infinite norm of objective function!"; break
#
#                dF = norm_f - norm_new_f
#                if dF > 0: #accept step
#                    #print("      Accepted!")
#                    x,f, norm_f = new_x, new_f, norm_new_f
#                    nu = 1.3
#                    break # exit inner loop normally
#                else:
#                    mu *= nu #increase mu
#            else:
#                #Linear solve failed:
#                mu *= nu #increase mu
#                nu = 2*nu
#
#            JTJ[idiag] = undampled_JTJ_diag #restore diagonal for next inner loop iter
#        #end of inner loop
#    #end of outer loop
#    else:
#        #if no break stmt hit, then we've exceeded maxIter
#        msg = "Maximum iterations (%d) exceeded" % max_iter
#
#    return x, converged, msg
