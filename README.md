# littleflow

A little flow language with simple objectives:

 * an expression language for defining the flow of tasks
 * a core algorithm for invocation of workflows and tasks
 * flows are independent of task implementation or workflow deployments

## Getting started

In this example we can compile and run a workflow:

```python
from littleflow import Parser, Compiler, Context, Runner

workflow = """
A → {
  B → C
  D
} → E
"""

p = Parser()
c = Compiler()

model = p.parse(workflow)
flow = c.compile(model)

context = Context(flow)
runner = Runner()

runner.start(context)

while not context.ending.empty():
   runner.next(context,context.ending.get())
```

This is further simplified with a utility function that also supports function lookups for tasks:

```python
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

```

Tasks are ordered by execution invocation. While some may be run in parallel,
this relative to task invocation innovation.

Typically, a real usage would implement both the `start()` and `end()` methods
on `FlowContext` that will start tasks and notify when these tasks end. Also, at task ends,
the loop for execution would likely be asynchronous based on end task event
notification.

## Writing workflows

Workflows are specify in a [declarative mini-language called littleflow](littleflow.md). This
language allows you to describe the flow of steps and instructions between steps.

## Running workflows

These workflows are compiled into a graph that can be executed asynchronously. The
state of the workflow is stored in a few simply vectors. This allows a simple
stateless library to executed a workflow once those vectors are restored from
storage.

## Deployment

Littleflow is integrated with Redis and Kubernetes for distributed execution. See [deployment](deployment) for more information.
