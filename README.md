# littleflow

A flow language

## Getting started

This simple example can compile and run a workflow:

```python
from littleflow import Parser, Compiler, FlowContext, Runner

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

class NonExecutingContext(Context):

   def __init__(self,flow):
      super().__init__(flow)
      self._E = None

   def start(self,tasks):
      self._E = 1*tasks

   @property
   def E(self):
      return self._E


context = FlowContext(flow)
runner = Runner()

context.start(context.initial)
while not context.ending.empty():
   runner.next(context,context.ending.get())
```

Typically, a real usage would implement both the `start()` and `end()` methods
on `FlowContext` that will start tasks and notify when these tasks end. Also, theAt the end,
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
