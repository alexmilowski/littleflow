from queue import SimpleQueue
import types

import numpy as np
from .flow import Flow, Source, Sink, InvokeTask

class InputCache:

   def append_input_for(self,source,target,value):
      pass

   def input_for(self,index):
      return {}

class MemoryInputCache(InputCache):

   def __init__(self):
      self._cache = {}

   def append_input_for(self,source,target,value):
      input = self._cache.get(target)
      if input is None:
         self._cache[target] = value
      elif type(input)==dict:
         if len(input)==0:
            self._cache[target] = value
         else:
            self._cache[target] = [input,value]
      else:
         input.append(value)

   def input_for(self,index):
      input = self._cache.get(index)
      if input is not None:
         del self._cache[index]
         return input
      return {}

class TaskContext:

   def invoke(self,context,invocation,input):
      immediate = np.zeros(context.S.shape,dtype=int)
      immediate[invocation.index] = 1
      context.ending.put(immediate)

def pass_parameters(func):
   if hasattr(func,'__invocation__'):
      getattr(func,'__invocation__').append('raw_parameters')
   else:
      setattr(func,'__invocation__',['raw_parameters'])
   return func

def pass_input(func):
   if hasattr(func,'__invocation__'):
      getattr(func,'__invocation__').append('input')
   else:
      setattr(func,'__invocation__',['input'])
   return func

class FunctionTaskContext(TaskContext):

   def __init__(self,lookup):
      self._lookup = lookup

   def invoke(self,context,invocation,input):
      f = self._lookup.get(invocation.name)
      if f is None:
         raise ValueError(f'Cannot find task {invocation.name} in function lookup.')
      if not isinstance(f,types.FunctionType):
         raise ValueError(f'Task {invocation.name} resolves to non-function')
      options = getattr(f,'__invocation__') if hasattr(f,'__invocation__') else []
      args = [input] if 'input' in options else []
      keywords = {}
      if invocation.parameters is not None:
         if 'raw_parameters' not in options:
            if type(invocation.parameters)==dict:
               for key,value in invocation.parameters.items():
                  keywords[key] = value
            elif type(invocation.parameters)==list:
               args += list
         else:
            args.append(invocation.parameters)

      output = f(*args,**keywords)

      if output is None:
         output = {}
      elif type(output)!=dict and type(output)!=list:
         output = [output]

      context.output_for(invocation.index,output)
      immediate = np.zeros(context.S.shape,dtype=int)
      immediate[invocation.index] = 1
      context.ending.put(immediate)


class Context:
   def __init__(self,flow,state=None,activation=None,cache=MemoryInputCache(),task_context=TaskContext()):
      self._flow = flow
      self._A = activation if activation is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._a = flow.F.sum(axis=0)
      self._a[0] = 1
      self._a = self._a.reshape((self.F.shape[0],1))
      self._initial = np.zeros((self.F.shape[0],1),dtype=int)
      self._initial[0] = 1
      self._initial = self._initial>0
      # TODO: do we really need to compute S?
      self._S = state if state is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._S[0] = 1
      self._ends = SimpleQueue()
      self._cache = cache
      self._task_context = task_context

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

   @property
   def ending(self):
      return self._ends

   @property
   def cache(self):
      return self._cache

   @property
   def task_context(self):
      return self._task_context

   @task_context.setter
   def task_context(self,value):
      self._task_context = value

   def start(self,tasks):
      """
      Called when steps are started. The tasks argument is a boolean vector
      whose position correspond to the indexed steps that should be started.
      The default implementation immediately ends tasks.
      """
      immediate = np.zeros(tasks.shape,dtype=int)
      for index,task in enumerate(tasks.flatten()):
         if task:
            invocation = self.flow[index]
            input = self.input_for(index)
            assert input is not None, f'None value return for {index}'
            if isinstance(invocation,InvokeTask):
               self.start_task(invocation,input)
            elif isinstance(invocation,Source):
               self.output_for(index,invocation.value)
               immediate[index] = 1
            elif isinstance(invocation,Sink):
               self.output_for(index,input)
               immediate[index] = 1
            else:
               immediate[index] = 1

      if immediate.sum()>0:
         self.ending.put(immediate)

   def end(self,tasks):
      """
      Called when steps end. The tasks argument is a boolean vector
      whose position correspond to the indexed steps that have finished.
      """
      pass

   def output(self,value):
      pass

   def output_for(self,index,value):
      for target, transition in enumerate(self.F[index].flatten()):
         if transition > 0:
            self.append_input_for(index,target,value)
      if index==(self.F.shape[0]-1):
         self.output(value)

   def append_input_for(self,source,target,value):
      self._cache.append_input_for(source,target,value)

   def input_for(self,index):
      return self._cache.input_for(index)

   def start_task(self,invocation,input):
      self._task_context.invoke(self,invocation,input)

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
      if (1*N).sum()>0:
         context.start(N)
      return context.S.sum()>0
