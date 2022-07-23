# A little flow language

## A brief introduction

Workflows are tasks that occur within some set of relationships. That
is, a workflow forms a graph where the nodes are tasks and the edges are the
relationships. The relationships in the graph provide ordering of which tasks
occur in what order by the preceding tasks they may depend upon and other
criteria (e.g., conditionals).

By the nature, *workflows are not DAGs* as some have cycles and partitions. As
such, in this context, a workflow is a graph that:

 1. Every node represents a task in the workflow.
 1. Every edge is a directed edge.
 1. For any two distinct nodes A and B, there is only a single directed edge from A to B.

With this definition, a few observations:

 * Nodes are not required to be connected.
 * A workflow can consist of disconnected subgraphs
 * Cycles are allowed

As the edges are directed, each subgraph in the workflow has a maximal join that can be considered the starting point of the subgraph. In the diagram below, `A` and `E` are the start of each subgraph as they are the maximal joins:

```mermaid
stateDiagram-v2
    A --> B
    A --> C
    C --> D
    E --> F
    E --> G
```

Given the maximal elements, we can infer a start and end to the workflow from the subgraphs:

```mermaid
stateDiagram-v2
    [*] --> A
    A --> B
    B --> [*]
    A --> C
    C --> D
    D --> [*]
    [*] --> E
    E --> F
    E --> G
    F --> [*]
    G --> [*]
```

A workflow is a *flow* of information from task to the next. The workflow has a single input that is passes to each starting tasks. These tasks may produce a single output. This output
flows over the edge connecting two tasks.

For example, in the following workflow, task `A` receives the workflow input and
produces its output. That output is fed into tasks `B` and `C` and the output of task `C` is fed into task `D`. At the end, the meet of tasks `B` and `D` in the workflow, the final output of the workflow is the collection of the output of tasks `B` and `D` (e.g., a list containing the two outputs).

```mermaid
stateDiagram-v2
    [*] --> A
    A --> B
    B --> [*]
    A --> C
    C --> D
    D --> [*]
```


**The purpose of the inputs and outputs are to provide tasks with execution context.** Typically,
this is not the main purpose of the workflow but information (e.g., metadata) needed to
locate information in the environemtn. For example, the input to the pipeline might be
a reference to customer record or data object sufficient for the workflow tasks to
retrieve information from a database.

As long as tasks pass the context along, possibly enhancing the context with additional information, the following tasks will have sufficient information to proceed. This enables the construction of workflows that are more generic. That is, instead of specializing a workflow with parameters specific to the invocation, the context for the invocation is the input to the workflow.

As such, over the edge flows information. Each task receives inputs over incoming edges and outputs information over outgoing edges. This information provides subsequent tasks the ability to evaluate what and whether they can perform their own task.

## What are tasks?

A task follows these rules:

 * may consume a single input and produce a single output.
 * may have side effects in the execution environment. That is, it does not have to be completely functional
 * may have additional parameters

While conceptually a task can be anything:

 * a function that receipts instructions via the input and parameters and product outputs without side-effects
 * an external process whose arguments a combination of the parameters and the input that affects the state of the world (e.g., by producing some number of artifacts)
 * an invocation of a service via an API
 * interaction with a person or intelligent device (e.g., a robot)

Concretely, a task is invoked by a workflow engine that feeds the task its context (i.e., parmaeters and input) and receives an output. Once complete, the engine determines the next step in computation and feeds outputs to inputs. Tasks are "black boxes" with metadata, an input, and an output.

## Technical foundation

A flow represents a workflow as a graph that:

 1. Nodes represent tasks.
 1. Edges are directed.
 1. An edge from A to B means that A occurs before B.
 1. Two distinct nodes A and B are only connected by one edge from A to B.
 1. Nodes in the graph may have the same label. This means they are the same task but in a different invocation context.

A sequence of structured information flows between nodes over directed edges. A task may choose how to interpret such information from all incoming edges.

Information flowing between tasks is limited to tree-structured information that typically be represented in a JSON [1] or YAML [2] data format.

A task:

 * receives a sequence of input data, possibly empty, over incoming edges
 * produces a single output, possibly empty, over outgoing edges
 * may create side-effects

A *side effect* is typically an artifact or change in state of the world. For example, a task may write data to database, notify a user, or invoke actions in the physical world.

Within the workflow itself, only the data flowing over the edges is explicitly know by the workflow engine for each task. Task writers by choose to convey information via the data flow or via side effects. Any information outside of the inputs and outputs is out of scope for the workflow engine execution.

A task in a workflow is not a replacement for a general purpose programming language. It
is simply a representation of a task that is implemented in some language or system. The workflow engine must pass the input and any parameters to that system. When the task completes, the workflow engineer receives an output which can then be used for following tasks.

## A syntax for workflows

The goals of this syntax are:

 1. A compact representation of the workflow graph
 1. A representation of tasks and their metadata operations
 1. Enabling common expressions over metadata between tasks (e.g., subflows, interation, conditionals)

A workflow is a sequence of whitespace separated statements. Each statement starts with a label or task name, a sequence of arrow operations, and ends with a label or task name.

### Flow statements

The graph is constructed with a single arrow operator (i.e., `→` U+2192 or `->`) to connect two tasks.

A flow statement is a sequence of arrow operations:

```
transform → inference → store
```

Statements can by multiline as the newline has no effect. This flow statement is
equivalent to the above:

```
transform →
inference →
store
```

Two flow statement are simply separated by the lack of connecting arrows:

##### Example 1

```
A → B → D
C → D
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "D" as D.3
  state "C" as C.4
  state "D" as D.5
  [*]-->A.1
  [*]-->C.4
  A.1-->B.2
  B.2-->D.3
  D.3-->[*]
  C.4-->D.5
  D.5-->[*]
```

A flow statement may be terminated with a semicolon and may be necessary to
disambiguate certain graph structures:

```
A → B → D;
C → D
```

When constructing more complex graphs, different flow statements can be combined with a label that prefixed with a colon:

##### Example 2

```
A :x → B → C;
:x → D
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  state "D" as D.4
  [*]-->A.1
  A.1-->B.2
  A.1-->D.4
  B.2-->C.3
  C.3-->[*]
  D.4-->[*]

```

In the above example, note how the first flow statement requires a terminating
semicolon. Without this semicolon, you will get an error for the same output label
as it is the same as this single flow statement:

```
A :x → B → C :x → D
```

which should generate an error for a duplicate output label 'x'. But the same label can be used in one statement as long as the role changes from output to input:

```
A :x → B → C → :x D
```

which produces the graph:

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  state "D" as D.4
  [*]-->A.1
  A.1-->B.2
  A.1-->D.4
  B.2-->C.3
  C.3-->D.4
  D.4-->[*]
```


A label may start a flow statement:

```
:x → A
```

It may follow a task to label the output:

```
A :x
```

And it may precede a task to label the input:

```
:x A
```

For example, inputs may be explictly connected:

##### Example 3

```
A → :x;
B → :x;
:x C
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  [*]-->A.1
  [*]-->B.2
  [*]-->C.3
  A.1-->C.3
  B.2-->C.3
  C.3-->[*]
```

In the above, it should be noted how the flow statement `x: C` has both a label to allow the connection from tasks `A` and `B` but also has a connection from the start. To remove that connection, you would need to do:

```
A → :x C;
B → :x;
```

The workflow graph has meets where two or more outputs may converge on a single task and this may require labeling a particular edge to attached another task outcome.

For example, to have the output of A and B meet at C:

##### Example 4
```
A → :meet C → D → E
B → :meet
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "C" as C.2
  state "D" as D.3
  state "E" as E.4
  state "B" as B.5
  [*]-->A.1
  [*]-->B.5
  A.1-->C.2
  C.2-->D.3
  D.3-->E.4
  E.4-->[*]
  B.5-->C.2
```

To use the output of A as the input to B:

##### Example 5

```
A :out →  C → D → E ;
:out → B  
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "C" as C.2
  state "D" as D.3
  state "E" as E.4
  state "B" as B.5
  [*]-->A.1
  A.1-->C.2
  A.1-->B.5
  C.2-->D.3
  D.3-->E.4
  E.4-->[*]
  B.5-->[*]
```

At the start of a flow statement, a label identifies the input:

##### Example 6

```
:before A → B → C
D → :before
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  state "D" as D.4
  [*]-->D.4
  A.1-->B.2
  B.2-->C.3
  C.3-->[*]
  D.4-->A.1
```

And the end of a flow statement, a label identifies the output:

```
A → B → C → :after
```

### Subflows

A set of flow statements may be contained in a curly brackets to indicate a subflow.
A subflow has its own implied start and end. The subflow is treated as if it
was a task invocation.

For example, the following subflow shows how meets and joins can be simplified
without labels:

##### Example 7

```
A → [ B C ] → D
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state _start_2_ <<fork>>
  state "B" as B.3
  state "C" as C.4
  state _end_5_ <<join>>
  state "D" as D.6
  [*]-->A.1
  A.1-->_start_2_
  _start_2_-->B.3
  _start_2_-->C.4
  B.3-->_end_5_
  C.4-->_end_5_
  _end_5_-->D.6
  D.6-->[*]
```

The `:start` and `:end` labels also refer to the start and end of the subflow:

##### Example 8
```
A → [ :start → B → C → :end ] → D
```

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state _start_2_ <<fork>>
  state "B" as B.3
  state "C" as C.4
  state _end_5_ <<join>>
  state "D" as D.6
  [*]-->A.1
  A.1-->_start_2_
  _start_2_-->B.3
  B.3-->C.4
  C.4-->_end_5_
  _end_5_-->D.6
  D.6-->[*]
```

### Resources

A resource by a URI reference in angle brackets:

```
<dataset.json> → inference → store
```

A resource is effectively an implicit task that loads the resource produces the content as its output. The URI is relative to the effective base URI of the workflow

Within a dataset, a resource may be in JSON or YAML syntax natively. An implementation is free to provide other syntax transformers.

A resource can also be a following task which commits the input to the resource:

```
load → score → <http://example.com/myservice/api/v1/store>
```

A resource may be parameterized to enable options like HTTP method, etc.:

```
load → score → <http://example.com/myscores.json>(- method: PUT -)
```

An implementation may provide parameters options for accessing resources that require specific credentials.

### Stitching the graph

Every task referenced in a flow statement is unique invocation. A task referenced more than once is a distinct invocation of the same task. The workflow graph is stitched together from all invocations of all the tasks by label references.

For example, this is workflow with two distinct and separate flows:

```
A → C
B → C
```

While this workflow has a single instance of task C:

```
A → :meet C
B → :meet
```

### Left and right tasks

Any task in a workflow has preceding tasks (those from incoming edges) and following tasks (those connected to outgoing edges). Assuming a left-is-preceding orientation, the left-most tasks are those without any preceding task and the right most is those without any following tasks.

The label `:start` is a reserved label for the start of the workflow and is the left-most task of all the tasks.

The label `:end` is a reserved label for the end of the workflow and is the the right-most task of all the tasks.

Thus, the workflow:

```
A → B → C
D → E
F → B
```

is equivalent to:

```
:start → A → B → C → :end
:start → D → E → :end
:start → F → B → :end
```

which is the graph:

```mermaid
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  state "D" as D.4
  state "E" as E.5
  state "F" as F.6
  state "B" as B.7
  [*]-->A.1
  [*]-->D.4
  [*]-->F.6
  A.1-->B.2
  B.2-->C.3
  C.3-->[*]
  D.4-->E.5
  E.5-->[*]
  F.6-->B.7
  B.7-->[*]
```

### Tasks

A task is identified by name which are alpha-numeric along with the hyphen (`-`), underscore (`_`), and colon (`:`) (e.g., `my:peel-banana`).

A task typically acts on inputs from within the pipeline but also may have parameters. Parameters are considered a single data structure that can be represented by JSON or YAML literals contained within paranthesis following the task name: `range(- {start: 1, end: 10} -)` (see the section on (Parameter iterals)[#parameter-literals] for more details).

A task is referred to by name and invoked with simple parameter values. As such, it is not necessary to declare a task. An implementation can determine the set of names and parameters used.

Within an implementation, the actual task definition may be far more complicated and implementation specific. That definition is out of scope for this specification.

A implementation can identify the tasks referred, the parameters used (and not used), and match the invocation to expected definitions and constraints. Subsequently, it can raise errors as necessary.

A task receives a set of inputs of structured information. If a preceding task produces no output or there is no preceding tasks, the input is a singleton empty object (i.e., `{}`). Similarly, if a task produces no explicit output upon completion, it defaults to produce a singleton empty object.

A task may only output one structured object as its output.

When two tasks are joined (e.g. `A → B`), the input is simply the output of the preceding task.

If there are more than two incoming edges, the inputs are aggregated via the following rules:

 1. All singleton empty objects are equivalent and merged into a single empty object.
 1. If a non-empty object is present, singleton empty objects are omitted.
 2. If multiple inputs are present, the input is a collection (e.g., a list).

A task may merge the collection into one object by the merge operator ('`>`'). For example,
in the following:

##### Example merge
```
A → :x B
C → :x
```

```
stateDiagram-v2
  direction LR
  state "A" as A.1
  state "B" as B.2
  state "C" as C.3
  [*]-->A.1
  [*]-->C.3
  A.1-->B.2
  B.2-->[*]
  C.3-->B.2
```

the task `B` would receive a collection of the outputs of `A` and `C`. If we want to merge these into a single object:

```
A → :x > B
C → :x
```

When the workflow is run, if the preceding steps produce no output, B would receive an empty singleton. Alternatively, if they both produce output, B would receive a collection. The use of the merge operator makes the input of B consistent.

For example, if A produces:

```JSON
{"fruit":"banana"}
```

and C produces:

```JSON
{"animal":"monkey"}
```

without the merge operator, `B` receives:

```JSON
[{"fruit":"banana"},{"animal":"monkey"}]
```

and with the merge operator, `B` receives:

```JSON
{"fruit":"banana","animal":"monkey"}
```


In short, inputs are merged into a single sequence of structured objects with duplicate empty objects merged or omitted when non-empty objects are present.

The left-most tasks (i.e., :start) are sent a singleton empty object. The outputs of all the right-most tasks are aggregated using the rules above. Where the output of the overall workflow is

### Parameter literals

A task may be explicitly parameterized within the workflow:

```
A (- delete: true -) → B ({"flush":true})
```

For parameter literals:

 * a YAML literal is contained within `(-` and `-)` delimiters
 * a JSON object is contained within `({` and `})` delimiters
 * a JSON array is contained within `([` and `])` delimiters

Note that an inline YAML may be specified in a single line:

```
(- {start: 10, end: 50} -)
```

or as a multiline:

```
(-
start: 10
end: 50
-)
```

where indentation is significant.  There is no preprocessing of the YAML literal
between the start and end delimiters.


### Resource literals

Flows may also start with a literal:

```
<- customer: C123 -> → A → B
```

For parameter literals:

 * a YAML literal is contained within `<-` and `->` delimiters
 * a JSON object is contained within `<{` and `}>` delimiters
 * a JSON array is contained within `<[` and `]>` delimiters

There is no preprocessing of the literal between the start and end delimiters.

### Declarations

A declaration provides metadata and defaults for the workflow. There are two
kinds of declarations:

 * flow declarations for the workflow itself
 * task declarations for tasks

Declarations are completely optional and only provide additional information such
as documentation or parmaeter defaults.

The general syntax is:

```
@type name (- ... -) ''' ... '''
```

where:

 * `@type` is one of `@flow` or `@task`
 * `name` is the name of the declared object (e.g., a task name)
 * `(- ... -)` is an optional default parameter literal
 * `''' ... '''` is an optional documentation comment which can use `'''` or `"""` as the delimiter and is also allowed to be mutliline.

#### Flow declarations

A flow delcaration provides the name and documentation for the worlflow. There can
only be one flow declaration per workflow.

```
@flow test '''
This is a test workflow.
'''
```

The use of parameters is implemetation defined as it has no semantics in the
flow language itself.

#### Task declarations

A task delcaration provides additional information about tasks.

```
@task A (- dry-run: false -) '''
Task A has a single parameter of `dry-run` which is a boolean value.
'''
```

The task parameters provided are the default values for the the task. An
implementation must merge the task default paraemters with the parameters
specified in the flow statements.


### Reserved words

A task may not have the following names:

 * if
 * then
 * else
 * elif

### Reserved labels

A label may have any name with the exception that `:start` and `:end` have special semantics. When used, `:start` must be the left-most task (the start of the workflow) and `:end` must be the right-most task (the end of the workflow). As a consequence, the `:start` and `:end` can only be used at the start and end of a flow statement.


## Extended features (future):

The following are planned features compatible with the underlying theory.

### Compact alternatives (or)

To facilitate meets and joins without labels, the vertical bar ('|') operator allows to list multiple tasks.

For example, a simple "fan in" or "meet" can be represented as:

```
A|B|C → D
```

is equivalent to:

```
A → :meet D
B → :meet ;
C → :meet
```

or

```
A → :meet ;
B → :meet ;
C → :meet ;
:meet → D
```


Also, a simple "fan out" or "join" can be represented as:

```
D → A|B|C
```

is equivalent to:

```
D :join → A ;
:join → B ;
:join → C
```

or

```
D → :join
:join → A ;
:join → B ;
:join → C
```

### Conditionals

Also, it can be useful to qualify whether a task should occur rather than have the decision within the task itself.

```
A → if `.status==0` then B
    else C
```

The expression is within back quotes and the preferred language is jsonpath [3]. The consequence of a conditional is a task invocation.

Stitching becomes more complicated with conditionals. Conditionals generate an implicit task-like node.

Consider:

```
A → if `.status==0` then B
    else C → D
```

The possible execution traces are:

```
A → B → D
A → C → D
```


### Iteration


Sometimes tasks output sequences of objects and the following tasks are intended for single inputs. In other cases, the sequence of objects are parameterization of parallelism (e.g., hyperparameters for a model).

By default, the input to a task is the whole sequence. To iterate over a the sequence, invoking the follow task for each item in the sequence, we use the multiple operator '*'.

For example, assume that `sequence.json` contains data in JSON-SEQ format (`application/json-seq`):

```JSON
{"x":12,"y":24}
{"x":3,"y":96}
{"x":7,"y":12}
{"x":7,"y":7}
```

The follow flow will invoke the task A for each object in the sequence:

```
<seqeuence.json> → * A
```

Similarly, a flow may require iteration or spreading outputs to a whole "sub-workflow". To facilitate brevity, a subflow can be contained in curly brackets:

```
A → {
  B → C
  D  
} → E
```

which is equivalent to:

```
A :out → B → C → :in E ;
:out → D → :in
```

Iteration is also available for subflows:

```
A → * {
  B → C
  D  
} → E
```

which is equivalent to:

```
A :out → * B → * C → :in E ;
:out → * D → :in
```
