from queue import SimpleQueue
import types

import numpy as np
from .flow import Flow, Source, Sink, InvokeTask, InvokeFlow, StartFlow

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

def task(registry=None,apply=True):
   def register(func):
      if hasattr(func,'__invocation__'):
         getattr(func,'__invocation__').append('apply')
      else:
         setattr(func,'__invocation__',['apply'])
      if registry is not None:
         registry[func.__name__] = func
      return func
   return register

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
      if 'apply' in options:
         match input:
            case list():
               args = input
            case tuple():
               args = list(input)
            case _:
               args = [input]
      else:
         args = [input] if 'input' in options else [{}]
      keywords = {}
      if invocation.parameters is not None:
         if 'raw_parameters' not in options:
            if type(invocation.parameters)==dict:
               for key,value in invocation.parameters.items():
                  keywords[key] = value
            elif type(invocation.parameters)==list:
               args += invocation.parameters
         else:
            args.append(invocation.parameters)

      output = f(*args,**keywords)

      if output is None:
         output = {}
      elif type(output)==tuple:
         output = list(output)
      elif type(output)!=dict and type(output)!=list:
         output = [output]

      context.output_for(invocation.index,output)
      immediate = np.zeros(context.S.shape,dtype=int)
      immediate[invocation.index] = 1
      context.ending.put(immediate)

def merge(input):
   if type(input)!=list:
      return input
   result = {}
   for item in input:
      if type(item)!=dict:
         raise ValueError(f'Item in merge is not of type dict: {type(item)}')
      for key, value in item.items():
         result[key] = value
   return result

class Context:
   def __init__(self,flow,state=None,activation=None,cache={},task_context=TaskContext()):
      self._flow = flow
      self._A = activation if activation is not None else np.zeros((self.F.shape[0],1),dtype=int)
      self._T = flow.F.sum(axis=0)
      self._T[0] = 1
      self._T = self._T.reshape((self.F.shape[0],1))
      self._S = state if state is not None else np.zeros((self.F.shape[0],1),dtype=int)
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
   def T(self):
      """
      The activation threshold
      """
      return self._T

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

   def new_transition(self):
      return np.zeros((self.F.shape[0],1),dtype=int)

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
               if invocation.merge:
                  input = merge(input)
               if invocation.guard is not None:
                  if not invocation.guard.should_execute(input):
                     self.output_for(index,input)
                     immediate[index] = 1
                     continue

               self.start_task(invocation,input)
            elif isinstance(invocation,Source):
               self.output_for(index,invocation.value)
               immediate[index] = 1
            elif isinstance(invocation,Sink):
               if invocation.merge:
                  input = merge(input)
               self.output_for(index,input)
               immediate[index] = 1
            elif isinstance(invocation,InvokeFlow):
               if invocation.merge:
                  input = merge(input)
               if invocation.guard is not None:
                  if not invocation.guard.should_execute(input):
                     self.output_for(invocation.end,input)
                     immediate[invocation.end] = 1
                     continue

               self.output_for(index,input)
               immediate[index] = 1
            elif isinstance(invocation,StartFlow):
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

   def ended(self,value):
      pass

   def output_for(self,index,value):
      if value is None:
         return
      if type(value)!=list and type(value)!=dict:
         raise ValueError(f'The value of the input must be a list or dict: {type(value)}')
      self._cache[index] = value
      if index==(self.F.shape[0]-1):
         self.ended(value)

   def input_for(self,index):
      if index == 0:
         item = self._cache.get(-1)
         return {} if item is None else item
      value = []
      for target, transition in enumerate(self.F.T[index].flatten()):
         if transition > 0:
            item = self._cache.get(target)
            if item is not None:
               value.append(item)
      if len(value)==0:
         return {}
      elif len(value)==1:
         return value[0]
      else:
         return value

   def start_task(self,invocation,input):
      self._task_context.invoke(self,invocation,input)

   def accumulate(self,value):
      pass


class Runner:

   def __init__(self):
      pass

   def start(self,context,input=None):
      if input is not None:
         context.output_for(-1,input)
      context.A[0] = 1
      context.ending.put(context.new_transition())
      context.accumulate(context.A)


   def next(self,context,E):
      """
      Runs the algorithm forward from a vector representing steps that have ended.

      context - The flow context
      E - a zero/one or boolean vector indicating which steps have ended
      """
      # allow array of booleans
      E = 1*E
      activations = context.F.T.dot(E)
      context.accumulate(activations)
      context._A = context._A + activations
      if E.sum()>0:
         context.end(E>0)
      # TODO: should we allow more than zero/one vectorss
      N = context.A >= context.T
      context._A = context.A - 1*N * context.T
      context._S = context.S - E + 1*N
      # Guarantee positive semi-definite
      context._S = context._S + np.multiply(context._S,-1*(context._S<0))
      if (1*N).sum()>0:
         context.start(N)
      return context.S.sum()>0
