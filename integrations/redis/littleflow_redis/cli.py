import sys
import os
import threading
from time import sleep
from random import random
import signal
import json
import logging

import click
from rqse import EventClient, receipt_for, message, ReceiptListener
import redis

from littleflow_redis import run_workflow, TaskEndListener, TaskStartListener, LifecycleListener, WaitTaskListener, RequestTaskListener
from littleflow_redis import compute_vector, trace_vector
from littleflow_redis import create_jwt_credential_actor

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
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
@click.option('--input',help='The workflow input')
@click.argument('workflow')
def run(stream,workflow_id,wait,host,port,username,password,workflow,input):

   with open(workflow,'r') as data:
      workflow_spec = data.read()

   if input is not None:
      if input[0]=='@':
         with open(input[1:],'r') as data:
            input = json.load(data)
      else:
         input = json.loads(input)

   stopper = None
   if wait:
      # we need something to listen for the end of the workflow and shutdown the threads
      class StopAtEnd(LifecycleListener):

         def process(self,event_id, event):
            if event.get('kind')=='end-workflow' and event.get('workflow')==workflow_id:
               self.stop()
            return False

      stop_listener = StopAtEnd(stream,'stopping',workflows_key=default_workflows_key,inprogress_key=default_inprogress_key,host=host,port=port,username=username,password=password)

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
   client = EventClient(stream,host=host,port=port,username=username,password=password)
   workflow_id = run_workflow(workflow_spec,client,workflow_id=workflow_id,input=input)

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
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
@click.option('--issuer',help='The key configuration for JWT authentication',default=os.environ.get('ISSUER'))
@click.option('--log-level',help='Sets the log level',type=click.Choice(['debug','info','warning','error','critical']),default=os.environ.get('LOG_LEVEL'))
def worker(stream,group,lifecycle_group,workflows,inprogress,host,port,username,password,issuer,log_level):

   if log_level is not None:
      n_log_level = getattr(logging, log_level.upper(), None)
      if n_log_level is not None:
         logging.basicConfig(level=n_log_level)

   auth_actor = None

   if issuer is not None and os.path.exists(os.path.expanduser(issuer)):
      with open(os.path.expanduser(issuer),'r') as raw:
         issuer_info = json.load(raw)
         issuer = issuer_info.get('client_email')
         private_key = issuer_info.get('private_key')
         kid = issuer_info.get('private_key_id')

         if private_key is not None:
            auth_actor = create_jwt_credential_actor({},private_key=private_key,kid=kid,issuer=issuer)

   # we need something that will respond to end tasks and the algorithm forward
   end_listener = TaskEndListener(stream,group,host=host,port=port,username=username,password=password)

   ending = threading.Thread(target=lambda : end_listener.listen())
   ending.start()

   # we need something that will respond to end tasks and the algorithm forward
   wait_listener = WaitTaskListener(stream,host=host,port=port,username=username,password=password)

   wait = threading.Thread(target=lambda : wait_listener.listen())
   wait.start()

   # we need something that will respond to end tasks and the algorithm forward
   request_listener = RequestTaskListener(stream,credential_actor=auth_actor,host=host,port=port,username=username,password=password)

   request = threading.Thread(target=lambda : request_listener.listen())
   request.start()

   # jut wait till tings are established
   max_wait = 5
   while not end_listener.established and not wait_listener.established and not request_listener.established and max_wait>0:
      sleep(1)
      max_wait -= 1

   # make sure we're connected
   assert end_listener.established
   assert wait_listener.established
   assert request_listener.established

   recorder = LifecycleListener(stream,lifecycle_group,workflows_key=workflows,inprogress_key=inprogress,host=host,port=port,username=username,password=password)

   interrupt_count = 0
   def interrupt_handler(signum,frame):
      nonlocal interrupt_count
      interrupt_count += 1
      if interrupt_count>1:
         print('Okay then, attempting exit!')
         sys.exit(1)

      end_listener.stop()
      wait_listener.stop()
      request_listener.stop()
      recorder.stop()
      print(f'Received interrupt, shutting down',flush=True)

   signal.signal(signal.SIGINT, interrupt_handler)

   recorder.listen()

@cli.command('end')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
@click.argument('workflow')
@click.argument('name')
@click.argument('index')
def event(stream,host,port,username,password,workflow,name,index):
   index = int(index)
   client = EventClient(stream,host=host,port=port,username=username,password=password)
   event = {'name':name,'index':index,'workflow':workflow}
   client.append(message(event,kind='end-task'))

@cli.command('event')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
@click.option('--data',help='The event data')
@click.argument('event')
def event(stream,host,port,username,password,data,event):
   client = EventClient(stream,host=host,port=port,username=username,password=password)
   if data is None:
      data = {}
   else:
      if data[0]=='@':
         with open(data[1:],'r') as raw:
            data = json.load(raw)
      else:
         data = json.loads(data)
   client.append(message(data,kind=event))

@cli.command('simulate')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--group',help='The consume group',default='starting')
@click.option('--wait-period',help='The amount of time to wait',default=3,type=int)
@click.option('--failures',help='The percent of failures',default=0.0,type=float)
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
def simulate(stream,group,wait_period,failures,host,port,username,password):

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
   waiter = RandomWait(stream,group,host=host,port=port,username=username,password=password)
   waiter.listen()

@cli.command('receipts')
@click.option('--stream',help='The event stream to use',default=default_stream_key)
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
def receipts(stream,host,port,username,password):

   class ReceiptLog:
      def log(self,connection,id,receipt,target_id,target):
         print(f'{target} processed at {receipt["at"]}',flush=True)
         return True

   logger = ReceiptLog()
   receipts = ReceiptListener(stream,logger=logger,host=host,port=port,username=username,password=password)
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
@click.option('--host',help='The Redis server host',default=os.environ.get('REDIS_HOST','0.0.0.0'))
@click.option('--port',help='The Redis server port',default=int(os.environ.get('REDIS_PORT',6379)))
@click.option('--username',help='The Redis username',default=os.environ.get('REDIS_USERNAME'))
@click.option('--password',help='The Redis authentication',default=os.environ.get('REDIS_PASSWORD'))
@click.argument('workflow_id')
def adjust(all,host,port,username,password,workflow_id):
   client = redis.Redis(host=host,port=port,username=username,password=password)
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
