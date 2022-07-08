from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext

def run_workflow(workflow,lookup=None,context=None):
   p = Parser()
   c = Compiler()
   model = p.parse(workflow)
   flow = c.compile(model)

   runner = Runner()
   if context is None:
      context = Context(flow,task_context=FunctionTaskContext(lookup))
   else:
      context.task_context = task_context

   runner.start(context)

   while not context.ending.empty():
      runner.next(context,context.ending.get())
