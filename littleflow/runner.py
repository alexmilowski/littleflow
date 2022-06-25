import numpy as np
from .flow import Flow

class Context:
   def __init__(self,flow,state=None,activation=None):
      self._flow = flow
      self._A = activation if activation is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._a = flow.F.sum(axis=0)
      self._a[0] = 1
      self._a = self._a.reshape((self.F.shape[0],1))
      self._initial = np.zeros((self.F.shape[0],1),dtype=int)
      self._initial[0] = 1
      # TODO: do we really need to compute S?
      self._S = state if state is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._S[0] = 1

   @property
   def flow(self):
      """
      The workflow for the context
      """
      return self._flow

   @property
   def initial(self):
      """
      The start vector for the workflow
      """
      return self._initial

   @property
   def F(self):
      """
      The step transition matrix.
      """
      return self._flow.F

   @property
   def S(self):
      """
      Indicates which steps are currently active.
      """
      return self._S

   @property
   def A(self):
      """
      The currently accumulated activations
      """
      return self._A

   @property
   def a(self):
      """
      The activation threshold
      """
      return self._a

   def start(self,tasks):
      """
      Called when steps are started. The tasks argument is a boolean vector
      whose position correspond to the indexed steps that should be started.
      """
      pass

   def end(self,tasks):
      """
      Called when steps end. The tasks argument is a boolean vector
      whose position correspond to the indexed steps that have finished.
      """
      pass

class Runner:

   def __init__(self):
      pass

   def next(self,context,E):
      """
      Runs the algorithm forward from a vector representing steps that have ended.

      context - The flow context
      E - a zero/one or boolean vector indicating which steps have ended
      """
      # allow array of booleans
      E = 1*E
      context._A = context._A + context.F.T.dot(E)
      context.end(E>0)
      # TODO: should we allow more than zero/one vectorss
      N = context.A >= context.a
      context._A = context.A - 1*N * context.a
      context._S = context.S - E + 1*N
      # Guarantee positive semi-definite
      context._S = context._S + np.multiply(context._S,-1*(context._S<0))
      context.start(N)
      return context.S.sum()>0
