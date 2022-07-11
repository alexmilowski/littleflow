import sys
import os

import click

from littleflow import __version__, Parser, Compiler, Runner, Context, graph

@click.group()
def cli():
   pass

@cli.command()
def version():
   print('.'.join(map(str,__version__)))

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
            if flow.name is not None:
               print(flow.name)
            print(flow.F)

      except FileNotFoundError as ex:
         print(f'Cannot open {file}',file=sys.stderr)

class LogContext(Context):

   def __init__(self,flow,state=None,activation=None,show_cache=False):
      super().__init__(flow,state=state,activation=activation)
      self.show_cache = show_cache

   def input_for(self,index):
      if self.show_cache:
         print(self.cache)
      return super().input_for(index)

   def ended(self,value):
      print(f'output → {value}')

   def output_for(self,index,value):
      print(f'{index} → {value}')
      super().output_for(index,value)
   def append_input_for(self,source,target,value):
      print(f'{source} → {target}')
      super().append_input_for(source,target,value)

   def end(self,tasks):
      print('E',str(self.S.flatten()),str(self.A.flatten()),str((1*tasks).flatten()),str(self.T.flatten()))
      super().end(tasks)

   def start(self,tasks):
      E = 1*tasks
      print('S',str(self.S.flatten()),str(self.A.flatten()),str(E.flatten()),str(self.T.flatten()))
      super().start(tasks)

   def start_task(self,invocation,input):
      print(f'{input} → {invocation.index} ({invocation.name})')
      self.output_for(invocation.index,input)
      super().start_task(invocation,input)

@cli.command()
@click.option('--limit',type=int,default=-1,help='Iteration limit')
@click.option('--show-cache',is_flag=True)
@click.argument('workflow')
def run(limit,show_cache,workflow):
   p = Parser()
   c = Compiler()
   try:
      with open(workflow,'r') as input:
         model = p.parse(input)
         flow = c.compile(model)
   except FileNotFoundError as ex:
      print(f'Cannot open {file}',file=sys.stderr)

   runner = Runner()
   context = LogContext(flow)
   context.start(context.initial)
   count = 0
   while (limit<0 or count<limit) and not context.ending.empty():
      count += 1
      runner.next(context,context.ending.get())

@cli.command()
@click.option('--no-docs',is_flag=True)
@click.option('--vertical',is_flag=True)
@click.argument('workflow')
def doc(no_docs,vertical,workflow):
   p = Parser()
   c = Compiler()
   try:
      with open(workflow,'r') as input:
         model = p.parse(input)
         flow = c.compile(model)
   except FileNotFoundError as ex:
      print(f'Cannot open {file}',file=sys.stderr)

   graph(flow,sys.stdout,embed_docs=not no_docs,left_to_right=not vertical)


if __name__=='__main__':
   cli()
