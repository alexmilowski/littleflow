from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext

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

   runner.start(context,input=input)

   while not context.ending.empty():
      runner.next(context,context.ending.get())

   return context.input_for(len(flow)-1), context
