import sys
import os
import threading
from time import sleep
from random import random
import signal

import click
from rqse import EventClient, receipt_for, message, ReceiptListener
import redis

from littleflow_redis import run_workflow, TaskEndListener, TaskStartListener, LifecycleListener, WaitTaskListener
from littleflow_redis import compute_vector, trace_vector

default_stream_key = 'workflows:run'
default_workflows_key = 'workflows:all'
default_inprogress_key = 'workflows:inprogress'

@click.group()
def cli():
   pass

@cli.command('run')
@click.option('--stream',help='The event stream to use',default='workflows:run')
@click.option('--workflow-id',help='The workflow identifier to use.')
@click.option('--wait',is_flag=True)
@click.argument('workflow')
def run(stream,workflow_id,wait,workflow):

   with open(workflow,'r') as data:
      workflow_spec = data.read()

   stopper = None
   if wait:
      # we need something to listen for the end of the workflow and shutdown the threads
      class StopAtEnd(LifecycleListener):

         def process(self,event_id, event):
            if event.get('kind')=='end-workflow' and event.get('workflow')==workflow_id:
               self.stop()
            return False

      stop_listener = StopAtEnd(stream,'stopping',workflows_key=default_workflows_key,inprogress_key=default_inprogress_key)

      stopper = threading.Thread(target=lambda : stop_listener.listen())
      stopper.start()

      # jut wait till tings are established
      max_wait = 5
      while not stop_listener.established and max_wait>0:
         sleep(1)
         max_wait -= 1

      # make sure we're connected
      assert stop_listener.established

   # run the workflow
   client = EventClient(stream,server=os.environ.get('REDIS_SERVER','0.0.0.0'),port=int(os.environ.get('REDIS_PORT',6379)),username=os.environ.get('REDIS_USER'),password=os.environ.get('REDIS_PASSWORD'))
   workflow_id = run_workflow(workflow_spec,client,workflow_id=workflow_id)

   print_id = workflow_id[9:] if workflow_id.startswith('workflow:') else workflow_id
   print(f'workflow {print_id} is running')

   if wait:
      stopper.join()

@cli.command('worker')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--group',help='The consumer group',default='ending')
@click.option('--lifecycle-group',help='The lifecycle consumer group',default='lifecycle')
@click.option('--workflows',help='The key for the workflows set',default=default_workflows_key)
@click.option('--inprogress',help='The key for the inprogress set',default=default_inprogress_key)
def worker(stream,group,lifecycle_group,workflows,inprogress):

   # we need something that will respond to end tasks and the algorithm forward
   end_listener = TaskEndListener(stream,group)

   ending = threading.Thread(target=lambda : end_listener.listen())
   ending.start()

   # we need something that will respond to end tasks and the algorithm forward
   wait_listener = WaitTaskListener(stream)

   wait = threading.Thread(target=lambda : wait_listener.listen())
   wait.start()

   # jut wait till tings are established
   max_wait = 5
   while not end_listener.established and not wait_listener.established and max_wait>0:
      sleep(1)
      max_wait -= 1

   # make sure we're connected
   assert end_listener.established
   assert wait_listener.established

   recorder = LifecycleListener(stream,lifecycle_group,workflows_key=workflows,inprogress_key=inprogress)

   interrupt_count = 0
   def interrupt_handler(signum,frame):
      nonlocal interrupt_count
      interrupt_count += 1
      if interrupt_count>1:
         print('Okay then, attempting exit!')
         sys.exit(1)

      end_listener.stop()
      wait_listener.stop()
      recorder.stop()
      print(f'Received interrupt, shutting down',flush=True)

   signal.signal(signal.SIGINT, interrupt_handler)

   recorder.listen()

@cli.command('event')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.argument('event')
def event(stream,event):
   client = EventClient(stream,server=os.environ.get('REDIS_SERVER','0.0.0.0'),port=int(os.environ.get('REDIS_PORT',6379)),username=os.environ.get('REDIS_USER'),password=os.environ.get('REDIS_PASSWORD'))
   # TODO: add option for data
   data = {}
   client.append(message(data,kind=event))

@cli.command('simulate')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--group',help='The consume group',default='starting')
@click.option('--wait-period',help='The amount of time to wait',default=3,type=int)
@click.option('--failures',help='The percent of failures',default=0.0,type=float)
def simulate(stream,group,wait_period,failures):

   failures = failures / 100.0

   class RandomWait(TaskStartListener):

      def process(self,event_id, event):
         workflow_id = event.get('workflow')
         name = event.get('name')
         category, _, task_name = name.partition(':')
         if category=='wait':
            return False
         index = event.get('index')
         self.append(receipt_for(event_id))
         event = {'name':name,'index':index,'workflow':workflow_id}
         failure_check = random()
         if failure_check<failures:
            print(f'Workflow {workflow_id} start task {name} ({index}), failure [{failure_check}<{failures}]')
            event['status'] = 'FAILURE'
            self.append(message(event,kind='end-task'))
            return True

         wait = round(random()*wait_period,3)
         print(f'Workflow {workflow_id} start task {name} ({index}), waiting {wait}s ({failure_check})')
         sleep(wait)
         event['status'] = 'SUCCESS'
         self.append(message(event,kind='end-task'))

         return True

   # we need something to simular tasks. This will wait a random number of seconds.
   waiter = RandomWait(stream,group)
   waiter.listen()

@cli.command('receipts')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
def receipts(stream):

   class ReceiptLog:
      def log(self,connection,id,receipt,target_id,target):
         print(f'{target} processed at {receipt["at"]}',flush=True)
         return True

   logger = ReceiptLog()
   receipts = ReceiptListener(stream,logger=logger)
   receipts.listen()

def format_vector(v):
   s = '['
   for index,c in enumerate(v):
      if index>0:
         s += ' '
      s += f'{c:2}'
   s += ']'
   return s

@cli.command('inspect')
@click.option('--all',is_flag=True)
@click.argument('workflow_id')
def adjust(all,workflow_id):
   client = redis.Redis(host=os.environ.get('REDIS_SERVER','0.0.0.0'),port=int(os.environ.get('REDIS_PORT',6379)),username=os.environ.get('REDIS_USER'),password=os.environ.get('REDIS_PASSWORD'))
   key = 'workflow:'+workflow_id
   for name in ['A','S']:
      if all:
         vectors = {}
         for tstamp, value in trace_vector(client,key+':'+name):
            vectors[tstamp] = value

         for tstamp in sorted(vectors.keys()):
            value = vectors[tstamp]
            print(name,format_vector(value.flatten()),tstamp.isoformat())
      V = compute_vector(client,key+':'+name)
      if V is not None:
         print(name,format_vector(V.flatten()))


# Not now ... adjusting is dangerous
# @cli.command('adjust')
# @click.argument('workflow_id')
# @click.argument('vector')
# @click.argument('adjustment',nargs=-1)
# def adjust(workflow_id,vector,adjustment):
#    pass
#

if __name__=='__main__':
   cli()
