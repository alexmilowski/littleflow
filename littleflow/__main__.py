import sys
import os

from littleflow import FlowParser, FlowCompiler

for file in sys.argv[1:]:
   p = FlowParser()
   c = FlowCompiler()
   try:
      with open(file,'r') as input:
         model = p.parse(input)
         print(model)
         flow = c.compile(model)
         print(flow.F)

   except FileNotFoundError as ex:
      print(f'Cannot open {file}',file=sys.stderr)
