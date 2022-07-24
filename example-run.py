from littleflow import run_workflow

workflow = """
A → B :x → C;
:x → D
"""

def A(input):
   print('A')

def B(input):
   print('B')

def C(input):
   print('C')

def D(input):
   print('D')

run_workflow(workflow,locals())
