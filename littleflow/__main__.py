import sys
import os

import click

from littleflow import Parser, Compiler, Context, Runner

@click.group()
def cli():
   pass

@cli.command()
@click.argument('files',nargs=-1)
def compile(files):
   for file in files:
      p = Parser()
      c = Compiler()
      try:
         with open(file,'r') as input:
            model = p.parse(input)
            print(model)
            flow = c.compile(model)
            print(flow.F)

      except FileNotFoundError as ex:
         print(f'Cannot open {file}',file=sys.stderr)

class LogContext(Context):

   def __init__(self,flow):
      super().__init__(flow)
      self._E = None

   def start(self,tasks):
      self._E = 1*tasks
      print(str(self._A.flatten()),str(self._E.flatten()))

   @property
   def E(self):
      return self._E



@cli.command()
@click.argument('workflow')
def run(workflow):
   p = Parser()
   c = Compiler()
   try:
      with open(workflow,'r') as input:
         model = p.parse(input)
         flow = c.compile(model)
   except FileNotFoundError as ex:
      print(f'Cannot open {file}',file=sys.stderr)

   context = LogContext(flow)
   runner = Runner()

   current = context.initial
   while runner.next(context,current):
      current = context.E


if __name__=='__main__':
   cli()
