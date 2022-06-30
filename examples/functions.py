from littleflow import run_workflow, invoker

def A(input,say):
   print(say,end='')

def B(input):
   print(' World',end='')

@invoker
def C(input,parameters):
   print('!')

workflow = """
A (- say: Hello -)  → B  → C
"""

run_workflow(workflow,locals())
