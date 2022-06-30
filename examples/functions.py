from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext, invoker

def A(input,say):
   print(say,end='')

def B(input):
   print(' World',end='')

@invoker
def C(input,parameters):
   return [], {}, lambda : print('!')

workflow = """
A (- say: Hello -)  → B  → C
"""

p = Parser()
c = Compiler()
model = p.parse(workflow)
flow = c.compile(model)

runner = Runner()
context = Context(flow,task_context=FunctionTaskContext(locals()))
context.start(context.initial)

while not context.ending.empty():
   runner.next(context,context.ending.get())
