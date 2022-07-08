import os
from uuid import uuid4
import threading
from time import sleep
from random import random

import click
from rqse import EventClient, receipt_for, message, ReceiptListener

from littleflow_redis import run_workflow, TaskEndListener, TaskStartListener, LifecycleListener

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

   if workflow_id is None:
      workflow_id = 'workflow:'+str(uuid4())

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
   run_workflow(workflow_spec,workflow_id,client)

   if wait:
      stopper.join()

@cli.command('worker')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--workflows',help='The key for the workflows set',default=default_workflows_key)
@click.option('--inprogress',help='The key for the inprogress set',default=default_inprogress_key)
def worker(stream,workflows,inprogress):

   # we need something that will respond to end tasks and the algorithm forward
   end_listener = TaskEndListener(stream,'ending')

   ending = threading.Thread(target=lambda : end_listener.listen())
   ending.start()

   # jut wait till tings are established
   max_wait = 5
   while not end_listener.established and max_wait>0:
      sleep(1)
      max_wait -= 1

   # make sure we're connected
   assert end_listener.established

   recorder = LifecycleListener(stream,'lifecycle',workflows_key=workflows,inprogress_key=inprogress)
   recorder.listen()

@cli.command('simulate')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--wait-period',help='The amount of time to wait',default=3,type=int)
def simulate(stream,wait_period):

   class RandomWait(TaskStartListener):

      def process(self,event_id, event):
         workflow_id = event.get('workflow')
         name = event.get('name')
         index = event.get('index')
         self.append(receipt_for(event_id))
         wait = round(random()*wait_period,3)
         print(f'Workflow {workflow_id} start task {name} ({index}), waiting {wait}s')
         sleep(wait)
         event = {'name':name,'index':index,'workflow':workflow_id}
         self.append(message(event,kind='end-task'))

         return True

   # we need something to simular tasks. This will wait a random number of seconds.
   waiter = RandomWait(stream,'starting')
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

if __name__=='__main__':
   cli()
