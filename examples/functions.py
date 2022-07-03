from littleflow import run_workflow, pass_input, pass_parameters

def A(say):
   print(say,end='')

@pass_input
def B(input):
   print(' World',end='')

@pass_parameters
@pass_input
def C(input,parameters):
   print('!')

workflow = """
A (- say: Hello -)  → B  → C
"""

run_workflow(workflow,locals())
