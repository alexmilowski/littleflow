import json

import yaml

from .model import Workflow, SubFlow, Task, LiteralSource, Start, End
from .flow import Flow, Source, Sink, InvokeTask, InvokeFlow

def compile_literal(text,media_type=None):
   text = text.strip()
   if len(text)==0:
      return {}
   value = None
   if media_type is None:
      errors = {}
      try:
         value = yaml.load(text,Loader=yaml.Loader)
      except yaml.YAMLError as ex:
         errors['yaml'] = ex
      if value is None:
         try:
            value = json.loads('{' + text + '}')
         except json.JSONDecodeError as ex:
            errors['json'] = ex
      if len(errors)>0:
         raise ValueError(f'Guesing at type failed - cannot parse literal: as YAML - {errors["yaml"]}; as JSON - {errors["json"]}')
   elif media_type=='JSON' or media_type=='application/json':
      try:
         value = json.loads('{' + text + '}')
      except json.JSONDecodeError as ex:
         raise ValueError(f'Cannot parse JSON literal: {ex}')
   elif media_type=='YAML' or media_type=='application/yaml':
      try:
         value = yaml.load(text,Loader=yaml.Loader)
      except yaml.YAMLError as ex:
         raise ValueError(f'Cannot parse YAML literal: {ex}')
   else:
      raise ValueError(f'Unrecognized literal type {media_type}')

   return value

class Compiler:

   def __init__(self):
      pass

   def compile(self,model):

      size = len(model.indexed)
      flow = Flow(size)

      for index, step in enumerate(model.indexed):
         if isinstance(step,Task):
            value = {}
            if step.parameters is not None:
               try:
                  value = compile_literal(step.parameters.value,step.parameters.media_type)
               except ValueError as ex:
                  raise ValueError(f'{step.parameters.line}:{step.parameters.column} {ex}')
            flow[index] = InvokeTask(step.name,value)
         elif isinstance(step,LiteralSource):
            try:
               value = compile_literal(step.parameters.value,step.parameters.media_type)
               flow[index] = Source(value)
            except ValueError as ex:
               raise ValueError(f'{step.parameters.line}:{step.parameters.column} {ex}')
         elif isinstance(step,SubFlow):
            flow[index] = InvokeFlow()
         elif isinstance(step,Start):
            flow[index] = Source({})
         elif isinstance(step,End):
            flow[index] = Sink()
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
