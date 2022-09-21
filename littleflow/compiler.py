import json

import yaml

from .model import Workflow, SubFlow, Task, LiteralSource, Start, End, LiteralType
from .flow import Flow, Source, Sink, InvokeTask, InvokeFlow, StartFlow

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
      assert size>2, 'The workflow contains no flows.'
      flow = Flow(size,name=model.name)

      for index, step in enumerate(model.indexed):
         if isinstance(step,Task):
            decl = model.declarations.get(('task',step.name))
            value = {}
            if decl is not None:
               if decl.parameters is not None:
                  try:
                     value = compile_literal(decl.parameters.value,decl.parameters.type)
                  except ValueError as ex:
                     raise ValueError(f'{decl.parameters.line}:{decl.parameters.column} {ex}')
            if step.parameters is not None:
               try:
                  invocation_value = compile_literal(step.parameters.value,step.parameters.type)
                  if len(value)==0:
                     value = invocation_value
                  elif type(value)!=type(invocation_value):
                     raise ValueError(f'{step.parameters.line}:{step.parameters.column} the type of the declaration parameters ({type(value)}) does not match the type of the invocation parameters ({type(invocation_value)})')
                  elif type(value)==list:
                     value = invocation_value
                  elif type(value)==dict:
                     for key, value in invocation_value.items():
                        value[key] = value
                  else:
                     value = invocation_value

               except ValueError as ex:
                  raise ValueError(f'{step.parameters.line}:{step.parameters.column} {ex}')
            flow[index] = InvokeTask(index,step.name,value,merge=step.merge)
            if decl is not None:
               flow[index].doc = decl.doc
               flow[index].base = decl.base
         elif isinstance(step,LiteralSource):
            try:
               value = compile_literal(step.value,step.type)
               flow[index] = Source(index,value)
            except ValueError as ex:
               raise ValueError(f'{step.line}:{step.column} {ex}')
         elif isinstance(step,SubFlow):
            flow[index] = InvokeFlow(index,merge=step.merge)
         elif isinstance(step,Start):
            flow[index] = StartFlow(index)
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
                  raise ValueError(f'Unknown output label {statement.source} at {statement.line}:{statement.column}: {statement}')
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
                  raise ValueError(f'Unknown input label {statement.destination} at {statement.line}:{statement.column}: {statement}')
               flow[named.index].merge = flow[named.index].merge or statement.merge_destination
               flow.F[current,named.index] = 1
            else:
               named = subflow.named_inputs.get('end')
               assert named is not None, 'The end destination is missing for the subflow'
               flow.F[current,named.index] = 1
         # fixup for inputs and outputs within the flow
         for name, source in subflow.named_outputs.items():
            if name=='start':
               continue
            target = subflow.named_inputs.get(name)
            if target is not None:
               flow.F[source.index,target.index] = 1
      return flow
