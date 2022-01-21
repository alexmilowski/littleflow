from lark import Lark

grammar = r"""
workflow: flow_statement+
flow_statement: (source ARROW)? LABEL? step LABEL? (ARROW LABEL? step LABEL? )* (ARROW destination)? ";"?
step: STAR? (task | subflow | conditional)
task: NAME parameter_list?
subflow: "{" flow_statement+ "}"
conditional: "if" EXPR "then" step ("elif" EXPR "then" step)* ("else" step)?
source: LABEL | resource
destination: LABEL | resource
resource: URI parameter_list?
parameter_list: "(" name_value ("," name_value)* ")"
name_value: NAME "=" (STRING | DEC_NUMBER)
ARROW: "→" | "->"
STAR: "*"
LABEL: ":" NAME
NAME: /[a-zA-Z_]\w*/
DEC_NUMBER: /0|[1-9][\d_]*/i
EXPR: /`[^`]*`/
STRING: /("(?!"").*?(?<!\\)(\\\\)*?"|'(?!'').*?(?<!\\)(\\\\)*?')/i
URI: /<[^>]*>/
%import common.WS
%ignore WS
"""

class FlowParser:

   def __init__(self):
      self._parser = Lark(grammar,parser='lalr',start='workflow')

   def parse(self,source):
      if type(source)!=str:
         source = source.read()
      tree = self._parser.parse(source)

      return tree
