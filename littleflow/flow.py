import numpy as np
from dataclasses import dataclass, field

@dataclass
class Invocation:
   pass

@dataclass
class Source(Invocation):
   value : 'typing.Any'

@dataclass
class Sink(Invocation):
   pass

@dataclass
class InvokeTask(Invocation):
   name: str
   parameters : 'typing.Any' = None

@dataclass
class InvokeFlow(Invocation):
   pass

class Flow:

   def __init__(self,size : int):
      self._F = np.zeros((size,size),dtype=int)
      self._tasks = [None]*size

   @property
   def F(self):
      return self._F

   def __getitem__(self,index):
      return self._tasks[index]

   def __setitem__(self,index,value):
      self._tasks[index] = value
