import json

import numpy as np
from dataclasses import dataclass, field
from jsonpath2.path import Path

@dataclass
class Invocation:
   index : int

@dataclass
class Source(Invocation):
   value : 'typing.Any'

@dataclass
class StartFlow(Invocation):
   pass

@dataclass
class Sink(Invocation):
   merge: bool = False

@dataclass
class InvokeTask(Invocation):
   name: str
   parameters : 'typing.Any' = None
   base: str = None
   doc: str = None
   merge: bool = False
   guard: Path = None

@dataclass
class InvokeFlow(Invocation):
   end: int
   merge: bool = False
   guard: Path = None

class Guard:
   def __init__(self,source,expression):
      try:
         self._repr = expression
         self._expr = Path.parse_str(expression)
      except ValueError as ex:
         raise ValueError(f'{source.line}:{source.column} Cannot parse guard `{expression}`: {ex}')

   def __repr__(self):
      return f'`{self._repr}`'

   def matches(self,obj):
      return [m.current_value for m in self._expr.match(obj)]
   
   def should_execute(self,obj):
      return len(self.matches(obj))>0


class Flow:

   __classes = {
      'Source' : Source,
      'Sink' : Sink,
      'InvokeTask' : InvokeTask,
      'InvokeFlow' : InvokeFlow,
      'StartFlow' : StartFlow
   }

   def __init__(self,size=0,serialized=None,name=None):
      self._name = name
      if serialized is None:
         assert size>0
         self._F = np.zeros((size,size),dtype=int)
         self._tasks = [None]*size
      else:
         self._F = np.array(serialized['F'])
         self._tasks = [Flow.__classes[T[0]](**T[1]) for T in serialized['T']]

   @property
   def name(self):
      return self._name

   @name.setter
   def name(self,value):
      self._name = value

   @property
   def F(self):
      return self._F

   def __getitem__(self,index):
      return self._tasks[index]

   def __setitem__(self,index,value):
      self._tasks[index] = value

   def __len__(self):
      return len(self._tasks)

   def __str__(self):
      return json.dumps(self.save())

   def save(self):
      R = {
         'F' : self._F.tolist(),
         'T' : [[T.__class__.__name__,T.__dict__] for T in self._tasks]
      }
      return R
