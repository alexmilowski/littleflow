# Futura Flow

<img src='dabbing-unicorn.png' width='150'/>

## Overview

Futura Flow is a workflow engine that can handle:

 * DAG-oriented workflows
 * cycles
 * conditional tasks
 * conditional cycles

The implementation does not:

 * handle how tasks in the workflow are accomplished
 * schedule when workflow or tasks occur

but it does:

 * compute what comes next give a state
 * provide a invocation point of task execution
 * trace the complete execution of a workflow and the algorithm state
 * provide a complete autonomous algorithm for workflow execution

There is a formal write-up of the workflow engine, flows, and the algorithm in [docs/content/flowalg.pdf](docs/content/flowalg.pdf).

## Concepts

A *workflow* is a directed graph of tasks with the following properties:

 1. A workflow is a graph that consists of tasks and decisions nodes.
 1. There is a starting task (e.g., labeled __start__)
 1. There is an ending task (e.g., labeled __end__)
 1. Tasks and decisions in the graph are connected by directed edges.
 1. The origin of a directed edge occurs before the destination.
 1. All nodes are accessible via a path from the starting task.
 1. A node may have multiple incoming and outgoing nodes.
 1. The end task has no outgoing edges.
 1. The start task may not have an edge to itself.
 1. A node may not have an edge to any other node if it has an edge to the end.

From the above properties, the follow are valid workflows:

 * a workflow that contains a cycle.
 * a workflow with no path to the ending task.

A *task* is an abstract unit of work. Nominally, it has a start time and an
end time.

A *decision* is choice within a graph where some number (including zero) of
outgoing edges are chosen. If no outgoing edges are chosen, there is an
implicit connection to the ending task.

### The Algorithm

A execution of a workflow is a DAG  called a trace. Each node in the
DAG represents the start or end of task or decision. A complete execution
always starts with a start task (labeled `__start__`) and ends with a
end task (labeled `__end__`). These start and end tasks are in name only and do
not perform any real work.

The trace, T, is represented by a sequence of column vectors. Each row position
corresponds to a task in the workflow and records a start
or end of a task or decision. In the vector, a -1 indicates a start of a task,
a 1 indicates an end of a task, and a 0 indicates nothing happened with the task.

Additionally, we will assume that every task execution will occur at a
unique timestamp (e.g., either by force or happen stance). Thus, a trace
vector has only a single -1 or 1 entry. Events that occur nominally at the
same time will be ordered monotonically.

A graph 𝜞(N) encodes all the transitions between all tasks and the number N
is the total number of tasks including the start and end tasks. A transition
between tasks is a directed edge from the ending task to the task that follows.

A activation threshold vector, 𝝉, of dimension N, of integers representing the
number of transitions necessary to start a following task.

A column vector, 𝜶, of dimension N of tasks to be activated:

> 𝜶(A,𝝉)[t] = [ 1 if A[t][i]>=𝝉[i]; 0 otherwise | i ∈ 1, ... N ]

A column vector, 𝝎, of dimension N of terminating tasks:

> 𝝎[t] = [ 1 if T[t][i]==1; 0 otherwise | i ∈ 1, ... N ]

The vectors 𝝎[t] are also the selection of the positive vectors of the trace, T[t].

A column vector, A, that is the accumulation of activations resulting from tasks terminating.

For a task (k) to be activated, a function vector F<sub>k</sub> is applied to A[t]. This vector is defined as a function for each task (ordered with start
at the beginning and end at the end):

> F<sub>k</sub> = [𝑓<sub>1</sub>, ..., 𝑓<sub>i</sub>, ..., f<sub>N</sub>]

where f<sub>N</sub> is always:

> 1 if `__terminate__` is true; x otherwise

and 𝑓<sub>i</sub> is either the function:

> 0 if `__terminate__` is true; x otherwise

or, when encoding a conditional expression in the workflow, a function of the form:

>0 if `__terminate__` is true or conditional expression fails; x otherwise

The function vector F is applied by element-wise composition:

> F∘v = [ 𝑓<sub>i</sub>(v<sub>i</sub>) | i ∈ 1, ... N ]

The algorithm for running a workflow assumes a queue of task terminations and works as follows:

1. 𝝎[0] = 0, T[0] = 0, A[0] = [1,0,...], 𝜶(A,𝝉)[0] = A[0], S[0] = 0, t = 0
1. While T[t][N] != 1
   1. starts = { k | 𝜶(A,𝝉)[k]>0, k ∈ 1, ... N }
   1. For k in starts:
      1. t = t + 1
      1. start task k
      1. 𝝎[t] = 0
      1. T[t] = [ -1 if i==k; 0 otherwise | i ∈ 1, ... N ]
      1. A[t] = A[t-1] + T[t]⊙𝝉
      1. 𝜶(A,𝝉)[t] = 𝜶(A,𝝉)[t-1] + T[t]
      1. S[t] = S[t-1] - T[t]
   1. Wait for a single task k in termination queue:
      1. t = t + 1
      1. 𝝎[t] = [ 1 if i==k; 0 otherwise | i ∈ 1, ... N ]
      1. T[t] = 𝝎[t]
      1. A[t] = A[t-1] + F<sub>k</sub>∘𝜞<sup>T</sup>𝝎[t]
      1. 𝜶(A,𝝉)[t] = [ 1 if A[t][i]>=𝝉[i]; 0 otherwise | i ∈ 1, ... N ]
      1. S[t] = S[t-1] - 𝝎[t]

### G1 - A straight execution chain

```
__start__ → A → B → __end__
```

𝜞:

```
0 1 0 0  __start__
0 0 1 0  A
0 0 0 1  B
0 0 0 0  __end__
```

Activation threshold 𝝉:

```
1  __start__
1  A
1  B
1  __end__
```

Trace:

```
E(__start__) → S(A) → E(A) → S(B) → E(B) → S(__end__)
```

𝝎[t]:

```
0  0  1  0  0  0  0  0  0  __start__
0  0  0  0  1  0  0  0  0  A
0  0  0  0  0  0  1  0  0  B
0  0  0  0  0  0  0  0  1  __end__
```

T[t]:
```
0 -1  1  0  0  0  0  0  0  __start__
0  0  0 -1  1  0  0  0  0  A
0  0  0  0  0 -1  1  0  0  B
0  0  0  0  0  0  0 -1  1  __end__
```

A[t]:

```
1  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  A
0  0  0  0  1  0  0  0  0  B
0  0  0  0  0  0  1  0  0  __end__
```

𝜶(A,𝝉)[t]:

```
1  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  A
0  0  0  0  1  0  0  0  0  B
0  0  0  0  0  0  1  0  0  __end__
```

S[t]:

```
0  1  0  0  0  0  0  0  0  __start__
0  0  0  1  0  0  0  0  0  A
0  0  0  0  0  1  0  0  0  B
0  0  0  0  0  0  0  1  0  __end__
```

### G2 - Fan out (join)

```
__start__ → A | B
```

𝜞:

```
0 1 1 0  __start__
0 0 0 1  A
0 0 0 1  B
0 0 0 0  __end__
```

Activation threshold 𝝉:

```
1  __start__
1  A
1  B
2  __end__
```

Trace:

```
E(__start__) → S(A) → E(A) → S(__end__)
            \→ S(B) → E(B) → S(__end__)
```

𝝎[t]:

```
0  0  1  0  0  0  0  0  0  __start__
0  0  0  0  0  0  1  0  0  A
0  0  0  0  0  1  0  0  0  B
0  0  0  0  0  0  0  0  1  __end__
```

T[t]:

```
0 -1  1  0  0  0  0  0  0  __start__
0  0  0 -1  0  0  1  0  0  A
0  0  0  0 -1  1  0  0  0  B
0  0  0  0  0  0  0 -1  1 __end__
```

A[t]:

```
1  0  0  0  0  0  0  0  0
0  0  1  0  0  0  0  0  0
0  0  1  1  0  0  0  0  0
0  0  0  0  0  1  2  0  0
```

𝜶(A,𝝉)[t]:

```
1  0  0  0  0  0  0  0  0
0  0  1  0  0  0  0  0  0
0  0  1  1  0  0  0  0  0
0  0  0  0  0  0  1  0  0
```

S[t]

```
0  1  0  0  0  0  0  0  0
0  0  0  1  1  1  0  0  0
0  0  0  0  1  0  0  0  0
0  0  0  0  0  0  0  1  0
```



### G3  - Fan in (meet)

```
__start__ → A | B → C
```

𝜞:
```
0 1 1 0 0  __start__
0 0 0 1 0  A
0 0 0 1 0  B
0 0 0 0 1  C
0 0 0 0 0  __end__
```

Activation threshold 𝝉:

```
1  __start__
1  A
1  B
2  C
1  __end__
```

Trace:

```
E(__start__) → S(A) → E(A) → S(C) → E(C) → S(__end__)
            \→ S(B) → E(B) → S(C)/
```

𝝎[t]:

```
0  0  1  0  0  0  0  0  0  0  0  __start__
0  0  0  0  0  1  0  0  0  0  0  A
0  0  0  0  0  0  1  0  0  0  0  B
0  0  0  0  0  0  0  0  1  0  0  C
0  0  0  0  0  0  0  0  0  0  1  __end__
```

T[t]:

```
0 -1  1  0  0  0  0  0  0  0  0  __start__
0  0  0 -1  0  1  0  0  0  0  0  A
0  0  0  0 -1  0  1  0  0  0  0  B
0  0  0  0  0  0  0 -1  1  0  0  C
0  0  0  0  0  0  0  0  0 -1  1  __end__
```

A[t]:
```
1  0  0  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  0  0  A
0  0  1  1  0  0  0  0  0  0  0  B
0  0  0  0  0  1  2  0  0  0  0  C
0  0  0  0  0  0  0  0  1  0  0  __end__
```

𝜶(A,𝝉)[t]:
```
1  0  0  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  0  0  A
0  0  1  1  0  0  0  0  0  0  0  B
0  0  0  0  0  0  1  0  0  0  0  C
0  0  0  0  0  0  0  0  1  0  0  __end__
```

S[t]:
```
0  1  0  0  0  0  0  0  0  0  0  __start__
0  0  0  1  1  0  0  0  0  0  0  A
0  0  0  0  1  1  0  0  0  0  0  B
0  0  0  0  0  0  0  1  0  0  0  C
0  0  0  0  0  0  0  0  0  1  0  __end__
```

### G4 - cycle:

```
__start__ → A → B → A
```

𝜞:

```
0 1 0 0  __start__
0 0 1 0  A
0 1 0 0  B
0 0 0 0  __end__
```
Activation threshold 𝝉:

```
1  __start__
1  A
1  B
0  __end__
```

Trace:

```
E(__start__) → S(A) → E(A) → S(B) → E(B) → S(A) → E(A) → ...
```

𝝎[t]:

```
0  0  1  0  0  0  0  0      __start__
0  0  0  0  1  0  0  0      A
0  0  0  0  0  0  1  0      B
0  0  0  0  0  0  0  0  ... __end__
```

T[t]:

```
0 -1  1  0  0  0  0  0      __start__
0  0  0 -1  1  0  0 -1      A
0  0  0  0  0 -1  1  0      B
0  0  0  0  0  0  0  0  ... __end__
```

A[t]:

```
1  0  0  0  0  0  0  0      __start__
0  0  1  0  0  0  1  0      A
0  0  0  0  1  0  0  0      B
0  0  0  0  0  0  0  0  ... __end__
```

𝜶(A,𝝉)[t]:

```
1  0  0  0  0  0  0  0      __start__
0  0  1  0  0  0  1  0      A
0  0  0  0  1  0  0  0      B
0  0  0  0  0  0  0  0  ... __end__
```

S[t]:

```
0  1  0  0  0  0  0  0      __start__
0  0  0  1  0  0  0  1      A
0  0  0  0  0  1  0  0      B
0  0  0  0  0  0  0  0  ... __end__
```


### G5 - conditional

```
__start__ → A → if `.status==0` then B
                if `.status==1` then C
                else D
```

𝜞:

```
0 1 0 0 0 0 0 0 0  __start__
0 0 1 0 1 0 1 0 0  A
0 0 0 1 0 0 0 0 0  [B]
0 0 0 0 0 0 0 0 1  B
0 0 0 0 0 1 0 0 0  [C]
0 0 0 0 0 0 0 0 1  C
0 0 0 0 0 0 0 1 0  [D]
0 0 0 0 0 0 0 0 1  D
0 0 0 0 0 0 0 0 0  __end__
```

Activation threshold 𝝉:

```
1  _start__
1  A
1  [B]
1  B
1  [C]
1  C
1  [D]
1  D
1  __end__
```

F<sub>2</sub>, 𝑓<sub>3</sub>(x) = { x if x>0 and not `__terminate__` and `.status==0`; 0 otherwise }\
F<sub>4</sub>,𝑓<sub>5</sub>(x) = { x if x>0 and not `__terminate__` and `.status==1`; 0 otherwise }\
F<sub>6</sub>, 𝑓<sub>7</sub>(x) = { x if x>0 and not `__terminate__` and not (`.status==0`) and not (`.status==1`); 0 otherwise }

Trace:
```
E(__start__) → S(A) → E(A) → [B]
                          \→ [C] → S(C) → E(C) → S(__end__)
                          \→ [D]
```

𝝎[t]:

```
0  0  1  0  0  0  0  0  0  __start__
0  0  0  0  1  0  0  0  0  A
0  0  0  0  0  0  0  0  0  [B]
0  0  0  0  0  0  0  0  0  B
0  0  0  0  0  0  0  0  0  [C]
0  0  0  0  0  0  1  0  0  C
0  0  0  0  0  0  0  0  0  [D]
0  0  0  0  0  0  0  0  0  D
0  0  0  0  0  0  0  0  1  __end__
```

T[t]:

```
0 -1  1  0  0  0  0  0  0  __start__
0  0  0 -1  1  0  0  0  0  A
0  0  0  0  0  0  0  0  0  [B]
0  0  0  0  0  0  0  0  0  B
0  0  0  0  0  0  0  0  0  [C]
0  0  0  0  0 -1  1  0  0  C
0  0  0  0  0  0  0  0  0  [D]
0  0  0  0  0  0  0  0  0  D
0  0  0  0  0  0  0 -1  1  __end__
```

A[t]:

```
1  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  A
0  0  0  0  0  0  0  0  0  [B]
0  0  0  0  0  0  0  0  0  B
0  0  0  0  1  0  0  0  0  [C]
0  0  0  0  0  0  0  0  0  C
0  0  0  0  0  0  0  0  0  [D]
0  0  0  0  0  0  0  0  0  D
0  0  0  0  0  0  1  0  0  __end__
            ^
            F∘[0 0 1 0 1 0 1 0 0]
```

𝑓<sub>3</sub>(1) = 0,
𝑓<sub>5</sub>(1) = 1,
𝑓<sub>7</sub>(1) = 0


𝜶(A,𝝉)[t]:

```
1  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  0  A
0  0  0  0  0  0  0  0  0  [B]
0  0  0  0  0  0  0  0  0  B
0  0  0  0  1  0  0  0  0  [C]
0  0  0  0  0  0  0  0  0  C
0  0  0  0  0  0  0  0  0  [D]
0  0  0  0  0  0  0  0  0  D
0  0  0  0  0  0  1  0  0  __end__
```

S[t]:

```
0  1  0  0  0  0  0  0  0  __start__
0  0  0  1  0  0  0  0  0  A
0  0  0  0  0  0  0  0  0  [B]
0  0  0  0  0  0  0  0  0  B
0  0  0  0  0  0  0  0  0  [C]
0  0  0  0  0  1  0  0  0  C
0  0  0  0  0  0  0  0  0  [D]
0  0  0  0  0  0  0  0  0  D
0  0  0  0  0  0  0  1  0  __end__
```

### G6 - conditional cycle

```
__start__ → A → B → if `.remaining>0` then A
                    else __end__
```

𝜞:

```
0 1 0 0 0 0  __start__
0 0 1 0 0 0  A
0 0 0 1 1 0  B
0 1 0 0 0 0  [A]
0 0 0 0 0 1  [__end__]
0 0 0 0 0 0  __end__
```

Activation threshold 𝝉:
```
1  __start__
1  A
1  B
1  [A]
1  [__end__]
1  __end__
```
F<sub>3</sub>, 𝑓<sub>4</sub>(x) = { x if x>0 and not `__terminate__` and `.remaining>0`; 0 otherwise }\
F<sub>4</sub>, 𝑓<sub>5</sub>(x) = { x if x>0 and not `__terminate__` and not(`.remaining>0`); 0 otherwise }

Trace:
```
E(__start__) → S(A) → E(A) → S(B) → E(B) → [A] → S(A) → E(A) → S(B) → E(B) → [A]
                                        \→ [__end__]                      \→ [__end__] → S(__end__)
```

𝝎[t]:

```
0  0  1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  __start__
0  0  0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  A
0  0  0  0  0  0  1  0  0  0  0  0  1  0  0  0  0  B
0  0  0  0  0  0  0  0  1  0  0  0  0  0  0  0  0  [A]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  [__end__]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  __end__
```

T[t]:

```
0 -1  1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  __start__
0  0  0 -1  1  0  0  0  0 -1  1  0  0  0  0  0  0  A
0  0  0  0  0 -1  1  0  0  0  0 -1  1  0  0  0  0  B
0  0  0  0  0  0  0 -1  1  0  0  0  0  0  0  0  0  [A]
0  0  0  0  0  0  0  0  0  0  0  0  0 -1  1  0  0  [__end__]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  0 -1  1  __end__
```

A[t]:

```
1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  0  0  A
0  0  0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  B
0  0  0  0  0  0  1  0  0  0  0  0  0  0  0  0  0  [A]
0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  0  0  [__end__]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  __end__
                  ^                 ^
(1)  F∘[0 0 0 1 1 0]                |
(2)  F∘[0 0 0 1 1 0]----------------/
```

(1) 𝑓<sub>4</sub>(1) = 1, 𝑓<sub>5</sub>(1) = 0\
(2) 𝑓<sub>4</sub>(1) = 0, 𝑓<sub>5</sub>(1) = 1

𝜶(A,𝝉)[t]:

```
1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  __start__
0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  0  0  A
0  0  0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  B
0  0  0  0  0  0  1  0  0  0  0  0  0  0  0  0  0  [A]
0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  0  0  [__end__]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  __end__
```

S[t]:

```
0  1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  __start__
0  0  0  1  0  0  0  0  0  1  0  0  0  0  0  0  0  A
0  0  0  0  0  1  0  0  0  0  0  1  0  0  0  0  0  B
0  0  0  0  0  0  0  1  0  0  0  0  0  0  0  0  0  [A]
0  0  0  0  0  0  0  0  0  0  0  0  0  1  0  0  0  [__end__]
0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  1  0  __end__
```
