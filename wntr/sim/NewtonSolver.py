import numpy as np
import scipy.sparse as sp
import copy
import time
import warnings
import logging

# Ideas:
#    scale variables
#    fraction to the boundary rule
#    better line search
#    Incorrect jacobian

warnings.filterwarnings("error",'Matrix is exactly singular',sp.linalg.MatrixRankWarning)
np.set_printoptions(precision=3, threshold=10000, linewidth=300)

logger = logging.getLogger('wntr.sim.NewtonSolver')

class NewtonSolver(object):
    def __init__(self, num_nodes, num_links, num_leaks, model, options={}):
        self._options = options
        self.num_nodes = num_nodes
        self.num_links = num_links
        self.num_leaks = num_leaks
        self.model = model

        if 'MAXITER' not in self._options:
            self.maxiter = 100
        else:
            self.maxiter = self._options['MAXITER']

        if 'TOL' not in self._options:
            self.tol = 1e-6
        else:
            self.tol = self._options['TOL']

        if 'BT_RHO' not in self._options:
            self.rho = 0.5
        else:
            self.rho = self._options['BT_RHO']

        if 'BT_MAXITER' not in self._options:
            self.bt_maxiter = 20
        else:
            self.bt_maxiter = self._options['BT_MAXITER']

        if 'BACKTRACKING' not in self._options:
            self.bt = True
        else:
            self.bt = self._options['BACKTRACKING']

        if 'BT_START_ITER' not in self._options:
            self.bt_start_iter = 2
        else:
            self.bt_start_iter = self._options['BT_START_ITER']


    def solve(self, Residual, Jacobian, x0):

        x = np.array(x0)

        use_r_ = False

        # MAIN NEWTON LOOP
        for iter in xrange(self.maxiter):
            if use_r_:
                r = r_
                r_norm = new_norm
            else:
                r,b1,b2,b3,b4 = Residual(x)
                r_norm = np.max(abs(r))

            #if iter<self.bt_start_iter:
            #    logger.debug('iter: {0:<4d} norm: {1:<10.2e}'.format(iter, r_norm))

            if r_norm < self.tol:
                return [x, iter, 1]

            A,B,C,D,E,F,G_inv,H,I,AinvB,AinvC = Jacobian(x)
            big_matrix = E*AinvC*H + D + E*AinvB*G_inv*F
            big_rhs = E*AinvC*b4 + b2 + E*AinvB*G_inv*b3 - b1
            
            # Call Linear solver
            try:
                d_head = -sp.linalg.spsolve(big_matrix,big_rhs)
            except sp.linalg.MatrixRankWarning:
                logger.warning('Jacobian is singular.')
                return [x, iter, 0]

            d_flow = G_inv*b3-G_inv*F*d_head
            d_leak = b4 - H*d_head
            d_demand = E*b2 - E*D*d_head
            d_head, d_demand, d_flow, d_leak = self.model.correct_step(d_head,d_demand,d_flow,d_leak,x)
            d = np.concatenate((d_head,d_demand,d_flow,d_leak))

            # Backtracking
            alpha = 1.0
            if self.bt and iter>=self.bt_start_iter:
                use_r_ = True
                for iter_bt in xrange(self.bt_maxiter):
                    x_ = x + alpha*d
                    r_,b1,b2,b3,b4 = Residual(x_)
                    new_norm = np.max(abs(r_))
                    if new_norm < (1.0-0.0001*alpha)*r_norm:
                        x = x_
                        break
                    else:
                        alpha = alpha*self.rho

                if iter_bt+1 >= self.bt_maxiter:
                    logger.debug('Backtracking failed.')
                    return [x,iter,0]
                #logger.debug('iter: {0:<4d} norm: {1:<10.2e} alpha: {2:<10.2e}'.format(iter, new_norm, alpha))
            else:
                x += d
            

        logger.debug('Reached maximum number of iterations.')
        return [x, iter, 0]



