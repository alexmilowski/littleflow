---
title: 'The Flow Algorithm'
date: 2022-03-03
documentclass: article
#classoption:
#- acmsmall
geometry:
- paper=a4paper
- margin=2.5cm
#mainfont: Arial Unicode MS
#fontenc: true
author:
- "Alex Miłowski, Stitch Fix \\<alex.milowski@stitchfix.com\\>"
abstract: |
  There are many descriptions of workflows nominally as graphs of dependencies and consequences but their implementations is via an imperative interpretation of the state changes. This paper descriptions an
  algorithm for encoding workflows as graphs and executing workflows
  from these graphical descriptions without the need of subjective
  interpretations.
references:
- id: BPEL2003
  title: Web Services Business Process Execution Language
  author:
  - given: Alexandre
    family: Alves
  - given: Assaf
    family: Arkin
  - given: Sid
    family: Askary
  - given: Charlton
    family: Barreto
  - given: Ben
    family: Bloch
  - given: Francisco
    family: Curbera
  - given: Mark
    family: Ford
  - given: Yaron
    family: Goland
  - given: Alejandro
    family: Guízar
  - given: Neelakantan
    family: Kartha
  - given: Canyang Kevin
    family: Liu
  - given: Rania
    family: Khalaf
  - given: Dieter
    family: König
  - given: Mike
    family: Marin
  - given: Vinkesh
    family: Mehta
  - given: Satish
    family: Thatte
  - given: Danny van der
    family: Rijn
  - given: Prasad
    family: Yendluri
  - given: Alex
    family: Yiu
  URL: 'http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html'
  publisher: OASIS
  type: standard
  issued:
    year: 2003
    month: 4  
- id: taverna
  title: "The Taverna workflow suite: designing and executing workflows of Web Services on the desktop, web or in the cloud"
  author:
  - family: Wolstencroft
    given: Katherine
  - family: Haines
    given: Robert
  - family: Fellows
    given: Donal
  - family: Williams
    given: Alan
  - family: Withers
    given: David
  - family: Owen
    given: Stuart
  - family: Soiland-Reyes
    given: Stian
  - family: Dunlop
    given: Ian
  - family: Nenadic
    given: Aleksandra
  - family: Fisher
    given: Paul
  - family: Bhagat
    given: Jiten
  - family: Belhajjame
    given: Kalid
  - family: Bacall
    given: Finn
  - given: Alex
    family: Hardisty
  - given: Abraham
    family: Nieva de la Hidalga
  - given: Maria P. Balcazar
    family: Vargas
  - given: Shoaib
    family: Sufi
  - given: Carole
    family: Goble
  URL: 'http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html'
  DOI: doi:10.1093/nar/gkt328
  container-title: Nucleic Acids Research
  type: article-journal
  page: W557-W561
  volume: 41
  issue: W1
  issued:
    year: 2013
    month: 7
- id: airflow
  title: Airflow
  URL: http://airflow.apache.org/
  type: software
  publisher: Apache Software Foundation
  issued:
    year: 2015
    month: 6
  author:
  - given: Maxime
    family: Beauchemin
- id: xproc2010
  type: standard
  title: "XProc: an XML pipeline language"
  publisher: World Wide Web Consortium
  container-title: World Wide Web Consortium
  URL: http://www. w3. org/TR/2010/REC-xproc-20100511
  issued:
    year: 2010
    month: 5
  author:
  - family: Walsh
    given: Norman
  - family: Miłowski
    given: Alex
  - family: Thompson
    given: Henry S
---

# Workflow systems in practice

Workflow systems have been developed to address the needs of users within application domains to orchestrate tasks to accomplish larger goals. Within certain communities of use, systems and description languages have been developed such as the description of business processes via BPEL [@BPEL2003], e-science processes via Taverna Workflows [@taverna], document pipelines via XProc [@xproc2010], machine learning and data science pipelines via Apache Airflow [@airflow]. Some of these are merely descriptions of workflows (BPEL, XProc) while others, others are the systems for implementing workflows (Apache Airflow), and some are both (Taverna).

A description alone is subject to the quality of the implementing system. The semantics of the description are encapsulated in the standard by which implementing systems must be evaluated. The result is the portability of the workflow is only as good as the specificity of the standard. Without a definitive algorithm, the interpretation of the workflow may be different within systems or deployment versions.

Similarly, systems that build workflows from constituent parts (e.g., code that implements a task in the workflow) are subject to some architectural component that holds the state. For example, Apache Airflow is centered around the orchestration of tasks. The current context in the overall workflow is dependent on the running task. If the knowledge of what is currently running or what has recently completed is lost due to some system failure, the workflow is lost.

Systems that attempt to both describe and execute, like Taverna or various XProc implementations, are fraught with scalability issues. Their descriptions focus on tightly coupled tasks that can be executed within a single process rather than orchestrating heterogeneous tasks over distributed systems.

What is common and essential to all these systems is:

 * workflows consist of tasks
 * tasks are connected by dependancies or ordering

A workflow is a graph tasks, connected by dependency ordering, through which the control of tasks flows. Information may flow between tasks, via backchannels, or via side effects. Regardless, the execution flow is the same.

The encoding and algorithm presented in this paper attempts to be agnostic
to the contrasting design decisions of the various workflow systems mentioned. Whether they choose to be monoliths or distributed, have tightly or loosely coupled tasks, or use data flows or imperative decisions, the core algorithm should prove useful. Rather, the focus is on the graph encoding of workflows and a cohesive algorithm for the execution of tasks, with deterministic outcomes, that lends itself well to "stateless" computation.

\newpage

# Concepts

## Graph flows

![Workflow A&B](flowalg-a-b-ind.svg){#fig:a-b-ind}

Consider a workflow with two independent tasks A and B. For the workflow to complete, we must initiate both tasks and they also must be completed (see figure {@fig:a-b-ind}). Implicit in this description is the start and end of the workflow.

We can transform this imprecise depiction of the workflow by adding an explicit start and end "tasks" and drawing directed edges between the task nodes. The start and end tasks perform no purpose other than to represented the start and end of the workflow. The flow within the graph represents the execution of tasks and transfer of state.

In the figure {@fig:a-b-start-end}, one can trace from the the start task (S) to each initial task to be performed (A & B). Once those tasks complete, the trace of the flow can continue to the end task (E). Once all the traces are complete at the end state, the flow in the graph terminates and the workflow has ended.

![Workflow A&B with Start/End tasks](flowalg-a-b-start-end.svg){#fig:a-b-start-end}

More complex flows can be built with additional meets and joins in graph. In figure {@fig:meets-joins}, the join of B to C and F represents a partial ordering in the workflow: B must occur before C and F. While via the link between C and D, B will also occur before D, the tasks A and B can occur in any order. The directed edges between nodes provide a partial ordering over the whole graph.

![Meets and Joins](flowalg-complex-graph.svg){#fig:meets-joins}


The addition of the start and end tasks in figure {@fig:meets-joins-start-end} does not change the ordering. The start and end tasks simply provide a starting point for every trace of flows through the graph. Critically, they also provide a way to determine when the workflow has completed.

![Meets and Joins with Start/End tasks](flowalg-complex-graph-start-end.svg){#fig:meets-joins-start-end}

## Activations

When a task completes, determining what follows in is a simple task of following the outward edges in the graph. These directed edges terminate on another task. When the graph is simple and there is only one incoming edge on a task, the decision to start that task is obvious.

Yet, in examining figure {@fig:meets-joins-start-end}, task (D) and the end task (E) have multiple incoming edges. If the graph truly represents a dependencies, a task should only execute if all the dependencies are met. Thus, (D) should only start when (A) and (C) have completed and (E) should only start (and end the workflow) when (D) and (F) have completed.

This can be solved by assigning each node in the graph an activation which must be met for the task to start. If we set this activation to the in-degree of the node in the graph, then (D) and (E) have an activation of 2. When the activation of (D) or (E) reaches 2 by the termination of (A), (B), or (F), these tasks may start.

From this there is the basis for an algorithm in that following the flow from a terminating task to a node adds 1 to an activation threshold. When the activation threshold meets or exceeds the activation of a task node, the task may start.

![Cycles](flowalg-cycle.svg){#fig:cycle}

A cycle presents a nuance for activation. In figure {@fig:cycle}, the (A) task
node has two inward edges. If the activation for (A) is set to the in-degree,
the task will never start. Instead, the activation remains 1 (shown in the box in the diagram) so that either the incoming flow from (S) or (B) will initiate (A).

The activation can also be used to encode other semantics. In figure {@fig:occurrences}, task (C) will start every 3rd cycle and the workflow will terminate after 9 iterations. This is because the activation of (C) is 3 and each invocation of (B) contributes one to the outward flows activations. Once the activation of (C) reaches 3, (C) is invoked and the activation is reduced by the threshold (3) which resets
the value to zero. A similar computation happens for the end task threshold of 9 in
this example.

![Cycles](flowalg-occurrences.svg){#fig:occurrences}


## Conditionals

![Conditionals](flowalg-cycle-cond.svg){#fig:cycle-cond}

While many systems discourage cycles, there are plenty of use cases from machine learning systems or human computation that justify cycles or conditional cycles (e.g., loop until a criteria is met) in a workflow. A cycle is simple enough to encode but requires conditionals to escape.

In figure {@fig:cycle-cond}, conceptually the cycle is between tasks (A) and (B) in the workflow. To prevent workflow from never completing, predicates are added to the outgoing
flow from (B) to decide whether the cycle continues (yes) or it completes (no). When the "no" verdict is determined, the end task is invoked and the workflow completes.

Such a conditional needs to be recast in terms of activations. When the answer is
"yes", the flow of activations from (B) to (A) must be 1 and from (B) to (E) must be 0.
When the answer is "no", the flow of activations must simply be reversed. To accomplish this, we must process the activation by some predicate function for each edge in the flow.

![Conditional functions](flowalg-cycle-cond-functions.svg){#fig:cycle-cond-functions}

In figure {@fig:cycle-cond-functions}, the structure of the graph remains the same
but the outward edges of (B) are labeled with functions. The input to these functions is the activation for the edge (a value of 1). If the predicate function is true,
the output should be the activation. If the predicate function is false, the output must be zero. To encode the original predicates, these functions are: for "yes", $f_1(1)=0$ and $f_2(1)$; for "no", $f_1(1)=1$ and $f_2(1)=0$.

Conceptually, each node has a set of functions, one for each outward edge, that processes the activation flowing to connected nodes. Normally, this function acts as the identity function. When a predicate is present, this function encodes the
outcome by either returning the activation or zero. When the activation that is pass along the flow in the graph is zero, the consequence is that the depending node does not reach its activation threshold and so will not be initiated.


## Tracing the flow

As tasks start and end, the flow of execution through the workflow can also be described as a graph. Consider the execution of tasks in the workflow depicted in figure {@fig:meets-joins} where each start and end of a task is represented by a node in the graph. The flow of execution can be traced from the start task, S, to the end task, E, where each start and end of a task is represented by a node tabled S(X) and E(X), respectively. Such a graph for figure {fig:meets-joins} is show in in figure {@fig:trace}.

![A trace flow execution](flowalg-trace.svg){#fig:trace}

In the graph layout of figure {@fig:trace}, time is represented left-to-right by the use of a "rail road diagram". The additional assumption is that every start and end of a task occurs at a separate time index. As such, we can vertically slice the graph into time periods where only one task starts and ends.

The vertical slicing of the trace graph can easily be encoded by a sequence of trace vectors. Each vector encodes the start of the task with a -1 and the end with a 1 in the position representing the task with zeros elsewhere. As such, the trace for figure {@fig:trace} can be represented as the follow vectors:

> ```
> S -1  1  0  0  0  0  0  0  0  0  0  0  0  0
> A  0  0 -1  0  1  0  0  0  0  0  0  0  0  0
> B  0  0  0 -1  0  1  0  0  0  0  0  0  0  0
> C  0  0  0  0  0  0 -1  0  1  0  0  0  0  0
> D  0  0  0  0  0  0  0  0  0 -1  0  1  0  0
> F  0  0  0  0  0  0  0 -1  0  0  1  0  0  0
> E  0  0  0  0  0  0  0  0  0  0  0  0 -1  1
> ```

![Encoding conditionals](flowalg-cycle-cond-encoded.svg){#fig:cycle-cond-encoded}

The graph of the trace lends itself as a nature tool for helping users understand the flow of execution. As such, we can encode concepts like conditional edges as non-computational nodes in the flow to enable their representation. For example, the conditional cycle in figure {@fig:cycle-cond} can be encoded with additional nodes as shown in figure {@fig:cycle-cond-encoded}.

The trace for the encoded conditional is show in figure {@fig:cycle-cond-encoded-trace} with the trace as follows:

> ```
> S -1  1  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
> A  0  0 -1  1  0  0  0  0  0  0 -1  1  0  0  0  0  0  0  0  0
> B  0  0  0  0 -1  1  0  0  0  0  0  0 -1  1  0  0  0  0  0  0
> Y  0  0  0  0  0  0  0  0 -1  1  0  0  0  0  0  0 -1  1  0  0
> N  0  0  0  0  0  0 -1  1  0  0  0  0  0  0 -1  1  0  0  0  0
> E  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0 -1  1
> ```

![A trace of encoding conditionals](flowalg-cycle-cond-encoded-trace.svg){#fig:cycle-cond-encoded-trace}



## Encoding rules

A workflow is encoded by an initial graph with the following properties:

 1. Every task is represented in the graph by a node.
 1. A dependency between tasks is represented by a directed edge from the "before" task to the "after" task.
 1. Conditionals are represented by predicates on the edge.

The graph is transformed with these rules:

 1. A start and end task are added to the graph.
 1. For any task without an inward edge, an edge from the start task to the task is added.
 1. For any task without an outward edge, an edge from the task to the end task is added.
 1. For each edge with a predicate, the corresponding function in $F_k[i]$ is updated to encode the predicate semantics.

Optional, each predicate edge can be transformed by replacing the $F_k[i]$ with the identity function, adding a new non-computation task node, $j$, between the transition from $k \rightarrow i$ that represents the predicate, and setting the $F_j[i]$ to the original predicate function. This essential performs the operation of adding the "Y" and "N" nodes in figure {@fig:cycle-cond-encoded} .

## Validation

The final graph must pass a few basic rules:

 1. There must be a path to every node from the start node.
 1. No node may have a self-connected edge (a cycle to itself).
 1. The start node may not have inward edges.
 1. The end node may not have outward edges.

These rules do not limit graphs in certain ways:

 * workflows with cycles that do not terminate are permitted
 * predicates may prematurely terminate workflows without activating the end task

The former may be desirable in certain applications of workflows. Otherwise, systems may detect and reject such cycles. Meanwhile, the latter is something an algorithm for running the workflow must detect and terminate the workflow. This may be considered an error in the workflow or simply early termination.

\newpage

# The Algorithm

## Definitions

A **graph $\Gamma(N)$** encodes all the transitions between all tasks and the number $N$
is the total number of tasks including the start task, end task, and all predicate encodings. A transition between tasks is a directed edge from the ending task to the task that follows.

The execution of a workflow called a **trace** (T) and forms a directed acyclic graph (DAG). Each node in the trace represents the start or end of a task. A complete execution always starts with a start task and ends with a
end task. These start and end tasks are in name only and do
not perform any real work.

The trace is represented by a sequence of column vectors. Each row position
corresponds to a task in the workflow and records a start
or end of a task or decision. In the vector, -1 indicates a start of a task,
1 indicates an end of a task, and 0 indicates nothing happened with the task.

Additionally, for the trace, we will assume that every task execution will occur at a
unique timestamp (e.g., either by force or happen stance). Thus, a trace
vector has only a single -1 or 1 entry. Events that occur nominally at the
same time will be ordered monotonically.

An **activation threshold vector (τ)**, of dimension N, of integers that represents the
number of transitions necessary to start a following task.

An **activated column vector (α)**, of dimension N, of tasks to be activated:

> $α(A,\tau)[t] = [ 1\ when\ A[t][i]>=\tau[i]; 0\ otherwise\ |\ i ∈ 1, ..., N ]$

A **terminating column vector (ω)**, of dimension N, of terminating tasks:

> $ω[t] = [ 1\ when\ T[t][i]==1; 0\ otherwise\ |\ i ∈ 1, ..., N ]$

The vectors ω[t] are also the selection of the positive vectors of the trace, T[t].

An **accumulation column vector (A)**, of dimension N, that is the accumulation (sum) of activations resulting from tasks terminating.

For each task $k$, a **function vector ($F_k$)**, of dimension N, that is applied to an activation values derived from $\Gamma^Tω[t]$. This vector is defined as a function for each task (ordered with start
at the beginning and end at the end):

> $F_k = [f_1, ..., f_i, ..., f_N]$

where f~N~ is always:

> 1 if terminate is true; x otherwise

and f~i~ is either the function:

> 0 if terminate is true; x otherwise

or, when encoding a predicate, a function of the form:

>0 if terminate is true or "conditional expression fails"; x otherwise

The function vector F is applied by element-wise composition:

> $F_k∘v = [ f_i(v_i) | i ∈ 1, ... N ]$

\newpage

## The flow algorithm

Assumes a queue of task terminations, the flow algorithm works as follows:

1. $ω[0] = 0, T[0] = 0, A[0] = [1,0,...], α(A,\tau)[0] = A[0], S[0] = 0, t = 0$
1. While $T[t][N] != 1$
   1. $starts = \{ k | α(A,\tau)[k]>0, k ∈ 1, ... N \}$
   1. For $k$ in $starts$:
      1. $t = t + 1$
      1. start task $k$
      1. $ω[t] = 0$
      1. $T[t] = [ -1\ when\ i==k; 0\ otherwise\ |\ i ∈ 1, ..., N ]$
      1. $A[t] = A[t-1] + T[t]⊙\tau$
      1. $α(A,\tau)[t] = α(A,\tau)[t-1] + T[t]$
      1. $S[t] = S[t-1] - T[t]$
   1. For $k$ in termination queue:
      1. $t = t + 1$
      1. $ω[t] = [ 1\ when\ i==k; 0\ otherwise\ |\ i ∈ 1, ..., N ]$
      1. $T[t] = ω[t]$
      1. $A[t] = A[t-1] + F_k∘\Gamma^Tω[t]$
      1. $α(A,\tau)[t] = [ 1\ when\ A[t][i]>=\tau[i]; 0\ otherwise\ |\ i ∈ 1, ..., N ]$
      1. $S[t] = S[t-1] - ω[t]$

# References

---
