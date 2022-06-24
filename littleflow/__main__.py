import sys
import os

from littleflow import FlowParser

for file in sys.argv[1:]:
   p = FlowParser()
   try:
      with open(file,'r') as input:
         t = p.parse(input)
         print(t)
   except FileNotFoundError as ex:
      print(f'Cannot open {file}',file=sys.stderr)
