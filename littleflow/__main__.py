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

   def end(self,tasks):
      print('E',str(self.S.flatten()),str(self.A.flatten()),str((1*tasks).flatten()),str(self.a.flatten()))

   def start(self,tasks):
      self._E = 1*tasks
      print('S',str(self.S.flatten()),str(self.A.flatten()),str(self._E.flatten()),str(self.a.flatten()))

   @property
   def E(self):
      return self._E

@cli.command()
@click.option('--limit',type=int,default=-1,help='Iteration limit')
@click.argument('workflow')
def run(limit,workflow):
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

   count = 0
   context.start(context.initial)
   while (limit<0 or count<limit) and runner.next(context,context.E):
      count += 1


if __name__=='__main__':
   cli()
