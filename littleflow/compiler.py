from .model import Workflow, SubFlow, Task, LiteralSource, Start
from .flow import Flow


class Compiler:

   def __init__(self):
      pass

   def compile(self,model):

      size = len(model.indexed)
      flow = Flow(size)

      for index, step in enumerate(model.indexed):
         flow[index] = step

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
               if not isinstance(step,Task) and not isinstance(step,LiteralSource) and not isinstance(step,SubFlow) and not isinstance(step,Start):
                  raise NotImplementedError(f'Support for {step.__class__.__name__} not implemented')
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
