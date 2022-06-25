from .model import Workflow, SubFlow, Task, LiteralSource
from .flow import Flow


class FlowCompiler:

   def __init__(self):
      pass

   def compile(self,model):

      size = len(model.indexed)
      flow = Flow(size)

      for index, step in enumerate(model.indexed):
         flow[index] = step

      for subflow in model.flows:
         for statement in subflow.statements:
            current = subflow.index
            if statement.source is not None:
               named = subflow.named_outputs.get(statement.source)
               if named is None:
                  raise ValueError(f'Unknown output label {statement.source}')
               current = named.index

            for step in statement.steps:
               if not isinstance(step,Task) and not isinstance(step,LiteralSource) and not isinstance(step,SubFlow):
                  raise NotImplementedError(f'Support for {step.__class__.__name__} not implemented')
               assert flow.F[current,step.index]==0, f'Transition from {current}->{step.index} already exists.'
               flow.F[current,step.index] = 1
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
