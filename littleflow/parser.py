import logging
from lark import Lark, Token, Tree

from .model import Workflow, Declaration, SubFlow, Statement, Start, End, Iterate, Task, LiteralSource, ResourceSource, ResourceSink, ParameterLiteral, LiteralType

grammar = r"""
flow: (declaration | flow_statement)+
declaration: DECLARE NAME (EQUAL NAME)? parameter_literal? doc_comment? ";"?
flow_statement: (source ARROW)? step (ARROW step)* (ARROW destination)? ";"?
step: LABEL? (STAR | MERGE)? (task_list | subflow | conditional) LABEL?
task_list : task (OR task)*
task: NAME parameter_literal?
subflow: "{" flow_statement+ "}"
conditional: "if" EXPR "then" step ("elif" EXPR "then" step)* ("else" step)?
source: LABEL | resource | resource_literal
destination: MERGE? (LABEL | resource)
resource: URI parameter_literal?
parameter_literal: empty_parameter | json_object_parameter | json_array_parameter | yaml_parameter
empty_parameter: "(" ")"
json_object_parameter: "({" JSON_OBJECT_PARAMETER_BODY? "})"
json_array_parameter: "([" JSON_ARRAY_PARAMETER_BODY? "])"
yaml_parameter: "(-" YAML_PARAMETER_BODY? "-)"
resource_literal : empty_resource | json_object_resource | json_array_resource | yaml_resource
empty_resource: "<" ">"
json_object_resource: "<{" JSON_OBJECT_RESOURCE_BODY? "}>"
json_array_resource: "<[" JSON_ARRAY_RESOURCE_BODY? "]>"
yaml_resource: "<-" YAML_RESOURCE_BODY? "->"
doc_comment: "'''" DOC_COMMENT_BODY_SINGLE? "'''" | "\"\"\"" DOC_COMMENT_BODY_DOUBLE? "\"\"\""
ARROW: "→" | "->"
STAR: "*"
OR: "|"
MERGE: ">"
EQUAL: "="
DECLARE: "@" NAME
LABEL: ":" NAME
NAME: /[a-zA-Z_][\w\-_:]*/
DEC_NUMBER: /0|[1-9][\d_]*/i
EXPR: /`[^`]*`/
STRING: /("(?!"").*?(?<!\\)(\\\\)*?"|'(?!'').*?(?<!\\)(\\\\)*?')/i
URI: /<[^>\-{[][^>]*>/
JSON_OBJECT_PARAMETER_BODY: /([^}]+|(}[^)]))+/
JSON_ARRAY_PARAMETER_BODY: /([^]]+|(][^)]))+/
YAML_PARAMETER_BODY: /([^-]+|(-[^)]))+/
JSON_OBJECT_RESOURCE_BODY: /([^}]+|(}[^>]))+/
JSON_ARRAY_RESOURCE_BODY: /([^]]+|(][^>]))+/
YAML_RESOURCE_BODY: /([^-]+|(-[^>]))+/
DOC_COMMENT_BODY_SINGLE: /([^']+|'[^']|''[^'])+/
DOC_COMMENT_BODY_DOUBLE: /([^"]+|"[^"]|""[^"])+/
COMMENT: /#[^\n]*/
%import common.WS
%ignore WS
%ignore COMMENT
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

def find_position(tree,target):
   for item in tree.iter_subtrees():
      for child in item.children:
         if isinstance(child,Token):
            target.line = child.line
            target.column = child.column
            return;
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
      subject = workflow
      source = None
      media_tyope = None
      input_label = None
      output_label = None
      source_labeled = False
      last_step = None
      ancestors = []

      def realize_step(step):
         nonlocal source_labeled, last_step
         last_step = step
         if statement is not None:
            statement.steps.append(step)
         workflow.indexed.append(step)
         if not source_labeled and statement.source is not None:
            flow.named_inputs[statement.source] = step
            source_labeled = True
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
               index += 1
               end.index = index
               workflow.indexed.append(end)
               subject = flow

               flow, statement = ancestors.pop()
               end = flow.named_inputs['end']
               start = flow.named_outputs['start']
            elif item.data=='parameter_literal':
               if subject is not None:
                  subject.parameters = literal
               else:
                  print(item)
                  assert False, f'{line}:{column} Unknown context for parameter literal'
            elif item.data=='flow_statement':
               if statement.destination is not None:
                  flow.named_outputs[statement.destination] = last_step

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
            flow = SubFlow(index,merge=merge)
            workflow.flows.append(flow)
            start = Start(index)
            if iterate:
               step = Iterate(flow)
               step.index = step.step.index
               realize_step(step)
            else:
               realize_step(flow)
            flow.named_outputs['start'] = start
            end = End(-1)
            flow.named_inputs['end'] = end
            flow.named_inputs['start'] = start
         elif item.data=='flow_statement':
            iterate = False
            step = None
            source = None
            source_labeled = False
            statement = Statement()
            find_position(item,statement)
            flow.statements.append(statement)
         elif item.data=='step':
            subject = None

            input_label = None
            output_label = None
            before = True
            iterate = False
            merge = False
            for child in item.children:
               if isinstance(child,Token) and child.type=='STAR':
                  iterate = True
               elif isinstance(child,Token) and child.type=='MERGE':
                  merge = True
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
         elif item.data=='resource':
            index += 1
            subject = ResourceSource(index,item.children[0].value[1:-1])
            realize_step(subject)
         elif item.data=='resource_literal':
            index += 1
            literal = LiteralSource(index,None)
            realize_step(literal)
         elif item.data=='empty_resource':
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='yaml_resource':
            literal.value = item.children[0].value if len(item.children)>0 else ''
            literal.type = LiteralType.YAML
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='json_object_resource':
            literal.value = item.children[0].value if len(item.children)>0 else ''
            literal.type = LiteralType.JSON_OBJECT
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='json_array_resource':
            literal.value = item.children[0].value if len(item.children)>0 else ''
            literal.type = LiteralType.JSON_ARRAY
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='parameter_literal':
            literal = None
         elif item.data=='empty_parameter':
            literal = ParameterLiteral(None)
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='yaml_parameter':
            literal = ParameterLiteral(item.children[0].value if len(item.children)>0 else '',LiteralType.YAML)
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='json_object_parameter':
            literal = ParameterLiteral(item.children[0].value if len(item.children)>0 else '',LiteralType.JSON_OBJECT)
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='json_array_parameter':
            literal = ParameterLiteral(item.children[0].value if len(item.children)>0 else '',LiteralType.JSON_ARRAY)
            literal.line = item.meta.line
            literal.column = item.meta.column
         elif item.data=='task_list':
            assert len(item.children)==1, 'meet shorthand not supported'
         elif item.data=='task':
            index += 1
            step = Task(index,item.children[0].value,merge=merge)
            step.line = item.children[0].line
            step.column = item.children[0].column
            if iterate:
               step = Iterate(step)
               step.index = step.step.index
            realize_step(step)
            subject = step
         elif item.data=='destination':
            if isinstance(item.children[-1],Token) and item.children[-1].type=='LABEL':
               statement.destination = item.children[-1].value[1:]
               statement.merge_destination = isinstance(item.children[0],Token) and item.children[0].type=='MERGE'
            elif isinstance(item.children[-1],Tree) and item.children[-1].data.value=='resource':
               index += 1
               subject = ResourceSink(index,merge=isinstance(item.children[0],Token) and item.children[0].type=='MERGE')
               realize_step(subject)
         elif item.data=='doc_comment':
            subject.doc = item.children[0].value
         elif item.data=='declaration':
            kind = item.children[0].value[1:]
            decl = Declaration(kind,item.children[1].value)
            if len(item.children)>2 and isinstance(item.children[2],Token) and item.children[2].type=='EQUAL':
               if kind=='flow':
                  assert False, f'{item.data.line}:{item.data.column} flows can not have base types'
               decl.base = item.children[3].value
            if kind=='flow':
               workflow.name = decl.name
            key = (kind,decl.name)
            if key in workflow.declarations:
               # warning needed, last one wins
               pass
            workflow.declarations[key] = decl
            subject = decl
         else:
            line = item.meta.line
            column = item.meta.column
            logging.error(item.data)
            logging.error(str(item))
            assert False, f'{line}:{column} Cannot handle item: {item.data}'

      index += 1
      end.index = index
      workflow.indexed.append(end)

      for index,item in enumerate(workflow.indexed):
         assert index==item.index, f'Index for item at {index} does not match: {item}'

      return workflow
