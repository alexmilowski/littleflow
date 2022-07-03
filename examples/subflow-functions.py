from littleflow import run_workflow

workflow = """
A → {
  B → C
  D
} → E
"""

def A():
   print('Hello ',end='')

def B():
   print('workflow ',end='')

def D():
   print('world, ',end='')

def C():
   print('how are ',end='')

def E():
   print('you?')

run_workflow(workflow,locals())
