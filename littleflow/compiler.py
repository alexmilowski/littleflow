import json

import yaml

from .model import Workflow, SubFlow, Task, LiteralSource, Start, End, LiteralType
from .flow import Flow, Source, Sink, InvokeTask, InvokeFlow

def compile_literal(text,type=LiteralType.EMPTY):
   if type==LiteralType.EMPTY:
      return {}

   text = text.strip()

   if type==LiteralType.YAML:
      if len(text)==0:
         return {}
      try:
         value = yaml.load(text,Loader=yaml.Loader)
         return value
      except yaml.YAMLError as ex:
         raise ValueError(f'Cannot parse YAML literal: {ex}')
   elif type==LiteralType.JSON_ARRAY:
      if len(text)==0:
         return []
      try:
         value = json.loads('[' + text + ']')
         return value
      except json.JSONDecodeError as ex:
         raise ValueError(f'Cannot parse JSON array literal: {ex}')

   elif type==LiteralType.JSON_OBJECT:
      if len(text)==0:
         return {}
      try:
         value = json.loads('{' + text + '}')
         return value
      except json.JSONDecodeError as ex:
         raise ValueError(f'Cannot parse JSON object literal: {ex}')


class Compiler:

   def __init__(self):
      pass

   def compile(self,model):

      size = len(model.indexed)
      assert size>2, 'The workflow contains now flows.'
      flow = Flow(size)

      for index, step in enumerate(model.indexed):
         if isinstance(step,Task):
            value = {}
            if step.parameters is not None:
               try:
                  value = compile_literal(step.parameters.value,step.parameters.type)
               except ValueError as ex:
                  raise ValueError(f'{step.parameters.line}:{step.parameters.column} {ex}')
            flow[index] = InvokeTask(index,step.name,value)
         elif isinstance(step,LiteralSource):
            try:
               value = compile_literal(step.value,step.type)
               flow[index] = Source(index,value)
            except ValueError as ex:
               raise ValueError(f'{step.line}:{step.column} {ex}')
         elif isinstance(step,SubFlow):
            flow[index] = InvokeFlow(index)
         elif isinstance(step,Start):
            flow[index] = Source(index,{})
         elif isinstance(step,End):
            flow[index] = Sink(index)
         else:
            raise NotImplementedError(f'Support for {step.__class__.__name__} not implemented')

      flows = [(0,model.flows[0])]
      while len(flows)>0:
         prior, subflow = flows.pop()
         for statement in subflow.statements:
            current = prior
            if statement.source is not None:
               named = subflow.named_outputs.get(statement.source)
               if named is None:
                  raise ValueError(f'Unknown output label {statement.source}')
               current = named.index

            for step in statement.steps:
               assert flow.F[current,step.index]==0, f'Transition from {current}->{step.index} already exists.'
               flow.F[current,step.index] = 1
               if isinstance(step,SubFlow):
                  flows.append((step.index,step))
                  current = step.named_inputs.get('end').index
               else:
                  current = step.index

            if statement.destination is not None:
               named = subflow.named_inputs.get(statement.destination)
               if named is None:
                  raise ValueError(f'Unknown input label {statement.destination}')
               flow.F[current,named.index] = 1
            else:
               named = subflow.named_inputs.get('end')
               assert named is not None, 'The end destination is missing for the subflow'
               flow.F[current,named.index] = 1
      return flow
