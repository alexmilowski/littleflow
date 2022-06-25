from lark import Lark, Token, Tree

from .model import Workflow, SubFlow, Statement, Start, End, Iterate, Task, LiteralSource, ResourceSource, ResourceSink, ParameterLiteral

grammar = r"""
flow: flow_statement+
flow_statement: (source ARROW)? step (ARROW step)* (ARROW destination)? ";"?
step: LABEL? STAR? (task_list | subflow | conditional) LABEL?
task_list : task (OR task)*
task: NAME parameter_literal?
subflow: "[" flow_statement+ "]"
conditional: "if" EXPR "then" step ("elif" EXPR "then" step)* ("else" step)?
source: LABEL | resource | parameter_literal
destination: LABEL | resource
resource: URI parameter_literal?
parameter_literal: media_type_literal? "{{" PARAMETER_BODY? "}}"
media_type_literal: EXPR
ARROW: "→" | "->"
STAR: "*"
OR: "|"
LABEL: ":" NAME
NAME: /[a-zA-Z_]\w*/
DEC_NUMBER: /0|[1-9][\d_]*/i
EXPR: /`[^`]*`/
STRING: /("(?!"").*?(?<!\\)(\\\\)*?"|'(?!'').*?(?<!\\)(\\\\)*?')/i
URI: /<[^>]*>/
PARAMETER_BODY: /([^}]+|(}[^}]))+/
%import common.WS
%ignore WS
"""

def iter_tree(top):
   context = [(True,top,[child for child in top.children if isinstance(child,Tree)])]
   while len(context)>0:
      first, current, subtrees = context.pop()

      if not first:
         yield first, current
         continue

      yield first, current

      context.append((False,current,[]))
      subtrees.reverse()
      for subtree in subtrees:
         context.append((True,subtree,[child for child in subtree.children if isinstance(child,Tree)]))

class Parser:

   def __init__(self):
      self._parser = Lark(grammar,parser='lalr',start='flow',propagate_positions=True)

   def parse(self,source):
      if type(source)!=str:
         source = source.read()
      ast = self._parser.parse(source)

      from_start = []

      workflow = Workflow()

      flow = None
      statement = None
      iterate = False
      subject = None
      source = None
      media_tyope = None
      input_label = None
      output_label = None
      ancestors = []

      def realize_step(step):
         if statement is not None:
            statement.steps.append(step)
         workflow.indexed.append(step)
         if input_label is not None:
            label = input_label.value[1:]
            if label in ['start','end']:
               raise ValueError(f'{input_label.line}:{input_label.column} {label} is a reserved label')
            if label in flow.named_inputs:
               raise ValueError(f'{input_label.line}:{input_label.column} input label {label} already exists')
            flow.named_inputs[label] = step
         if output_label is not None:
            label = output_label.value[1:]
            if label in ['start','end']:
               raise ValueError(f'{output_label.line}:{output_label.column} {label} is a reserved label')
            if label in flow.named_outputs:
               raise ValueError(f'{output_label.line}:{output_label.column} output label {label} already exists')
            flow.named_outputs[label] = step

      for at_start, item in iter_tree(ast):
         if not at_start:
            if item.data=='subflow':
               sub = SubFlow(start.index)
               index += 1
               end.index = index
               workflow.indexed.append(end)

               flow, statement = ancestors.pop()
               end = flow.named_inputs['end']
               start = flow.named_outputs['start']
            continue

         if item.data=='flow':
            index = 0
            flow = SubFlow(index)
            workflow.flows.append(flow)
            start = Start(index)
            workflow.indexed.append(start)

            flow.named_outputs['start'] = start

            end = End(-1)
            flow.named_inputs['end'] = end
            flow.named_inputs['start'] = start
         elif item.data=='subflow':
            ancestors.append((flow,statement))
            index += 1
            flow = SubFlow(index)
            workflow.flows.append(flow)
            start = Start(index)
            flow.named_outputs['start'] = start
            workflow.indexed.append(start)
            end = End(-1)
            flow.named_inputs['end'] = end
            flow.named_inputs['start'] = start
         elif item.data=='flow_statement':
            iterate = False
            step = None
            source = None
            statement = Statement()
            flow.statements.append(statement)
         elif item.data=='step':
            subject = None

            input_label = None
            output_label = None
            before = True
            iterate = False
            for child in item.children:
               if isinstance(child,Token) and child.type=='STAR':
                  iterate = True
               elif isinstance(child,Token) and child.type=='LABEL':
                  if before:
                     input_label = child
                  else:
                     output_label = child
               elif not isinstance(child,Token):
                  before = False
         elif item.data=='source':
            if isinstance(item.children[0],Token) and item.children[0].type=='LABEL':
               statement.source = item.children[0].value[1:]
            elif isinstance(item.children[0],Tree) and item.children[0].data.value=='parameter_literal':
               index += 1
               subject = LiteralSource(index,None)
               realize_step(subject)
            elif isinstance(item.children[0],Tree) and item.children[0].data.value=='resource':
               index += 1
               subject = ResourceSource(index)
               realize_step(subject)
            else:
               print(item)
               assert False, 'Unknown context for source'
         elif item.data=='parameter_literal':
            media_type = None
            value = ''
            line = 0
            column = 0
            for child in item.children:
               if isinstance(child,Token) and child.type=='PARAMETER_BODY':
                  value = child.value
                  line = child.line
                  column = child.column
            literal = ParameterLiteral(value)
            literal.line = line
            literal.column = column
            if subject is not None:
               subject.parameters = literal
            else:
               print(item)
               assert False, f'{line}:{column} Unknown context for parameter literal'

         elif item.data=='media_type_literal':
            media_type = item.children[0].value[1:-1]
            if isinstance(subject,ParameterLiteral):
               subject.media_type = media_type
            elif isinstance(subject,LiteralSource) or isinstance(subject,Task):
               subject.parameters.media_type = media_type
            else:
               assert False, 'Unknown subject for media_type_literal'
         elif item.data=='resource':
            subject.uri = item.children[0].value[1:-1]
         elif item.data=='task_list':
            assert len(item.children)==1, 'meet shorthand not supported'
         elif item.data=='task':
            index += 1
            step = Task(index,item.children[0].value)
            step.line = item.children[0].line
            step.column = item.children[0].column
            if iterate:
               step = Iterate(step)
               step.index = step.step.index
            realize_step(step)
            subject = step
         elif item.data=='destination':
            if isinstance(item.children[0],Token) and item.children[0].type=='LABEL':
               statement.destination = item.children[0].value[1:]
            elif isinstance(item.children[0],Tree) and item.children[0].data.value=='resource':
               index += 1
               subject = ResourceSink(index)
               realize_step(subject)
         else:
            line = 0
            column = 0
            if isinstance(item.children[0],Token):
               line = item.children[0].line
               column = item.children[0].column
            print(item.data)
            print(item)
            assert False, f'{line}:{column} Cannot handle item: {item.data}'

      index += 1
      end.index = index
      workflow.indexed.append(end)

      for index,item in enumerate(workflow.indexed):
         assert index==item.index, f'Index for item at {index} does not match: {item}'

      return workflow
