from littleflow import run_workflow

workflow = """
A → {
  B → C
  D
} → E
"""

def A(input):
   print('Hello ',end='')

def B(input):
   print('workflow ',end='')

def D(input):
   print('world, ',end='')

def C(input):
   print('how are ',end='')

def E(input):
   print('you?')

run_workflow(workflow,locals())
