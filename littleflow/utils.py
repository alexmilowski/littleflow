from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext

class WorkflowFailure(Exception):
   pass

class TaskFailure(WorkflowFailure):
   def __init__(self, message, *args, task=None, **kwargs):
      if task is None:
         super().__init__(message,*args,**kwargs)
      else:
         super().__init__(f'Task {task} failed: {message}',*args,**kwargs)


def run_workflow(workflow,lookup=None,context=None,input=None):
   p = Parser()
   c = Compiler()
   model = p.parse(workflow)
   flow = c.compile(model)

   runner = Runner()
   if context is None:
      context = Context(flow,task_context=FunctionTaskContext(lookup))
   elif lookup is not None:
      context.task_context = FunctionTaskContext(lookup)

   try:
      runner.start(context,input=input)

      while not context.ending.empty():
         runner.next(context,context.ending.get())
   except TaskFailure as ex:
      raise WorkflowFailure('The workflow failed due to a task failure.') from ex
   except Exception as ex:
      raise WorkflowFailure('The workflow failed due to an exception.') from ex


   return context.input_for(len(flow)-1), context
