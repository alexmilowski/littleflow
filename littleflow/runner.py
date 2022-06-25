import numpy as np
from .flow import Flow

class Context:
   def __init__(self,flow,state=None,activation=None):
      self._flow = flow
      self._A = activation if activation is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._a = np.ones((self.F.shape[0],1),dtype=int)
      self._initial = np.zeros((self.F.shape[0],1),dtype=int)
      self._initial[0] = 1
      self._S = state if state is not None else np.zeros((self.F.shape[0],1),dtype=int)

   @property
   def flow(self):
      return self._flow

   @property
   def initial(self):
      return self._initial

   @property
   def F(self):
      return self._flow.F

   @property
   def S(self):
      return self._S

   @property
   def A(self):
      return self._A

   @property
   def a(self):
      return self._a

   def start(self,tasks):
      pass

class Runner:

   def __init__(self):
      pass

   def next(self,context,E):
      context._A = context._A + context.F.T.dot(E)
      N = context.A >= context.a
      context._A = context.A - 1*N * context.a
      context._S = context.S - E + 1*N
      # Guarantee positive semi-definite
      context._S = context._S + np.multiply(context._S,-1*(context._S<0))
      context.start(N)
      return context.S.sum()>0
