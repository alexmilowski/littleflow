import sys
from datetime import datetime
import json

import numpy as np
from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext, Flow
from rqse import EventClient, EventListener, message, receipt_for

from .context import RedisInputCache

def tstamp():
   return datetime.utcnow().timestamp()

def workflow_state(client,key):
   value = client.get(key+':state')
   return value.decode('UTF-8') if value is not None else None

def set_workflow_state(client,key,value):
   return client.set(key+':state',value)

def is_running(client,key):
   return workflow_state(client,key)=='RUNNING'

class RemoteTaskContext(FunctionTaskContext):

   def __init__(self,event_client,workflow_id,lookup={}):
      super().__init__(lookup)
      self._client = event_client
      self._workflow_id = workflow_id

   def invoke(self,context,invocation,input):
      if invocation.name in self._lookup:
         return super().invoke(context,invocation,input)

      event = {'name':invocation.name,'index':invocation.index,'workflow':self._workflow_id}
      if invocation.parameters is not None:
         event['parameters'] = invocation.parameters

      if len(input)>0:
         event['input'] = input

      self._client.append(message(event,kind='start-task'))

      starting = context.new_transition()
      starting[invocation.index] = 1


class RedisContext(Context):
   def __init__(self,flow,client,key,workflow_id,state=None,activation=None,cache=None,task_context=None):
      super().__init__(flow,state=state,activation=activation,cache=cache,task_context=task_context,)
      self._client = client
      self._key_A = key + ':A'
      self._key_S = key + ':S'
      self._workflow_id = workflow_id

   def accumulate(self,A):
      if (1*A).sum()>0:
         self._client.connection.lpush(self._key_A,str(tstamp())+':'+str(A.flatten())[1:-1])

   def start(self,N):
      starting = 1*N
      self._client.connection.lpush(self._key_S,str(tstamp())+':'+str(starting.flatten())[1:-1])
      super().start(N)
      A = - starting * self.T
      self._client.connection.lpush(self._key_A,str(tstamp())+':'+str(A.flatten())[1:-1])

   def end(self,N):
      ending = - 1*N
      self._client.connection.lpush(self._key_S,str(tstamp())+':'+str(ending.flatten())[1:-1])
      super().end(N)

   def ended(self,value):
      self._client.append(message({'workflow':self._workflow_id },kind='end-workflow'))



def save_workflow(client,flow,key):
   client.set(key,str(flow))

def restore_workflow(client,key,return_json=False):
   value = client.get(key)
   if value is None:
      raise IOError(f'No workflow value at {key}')
   object = json.loads(value.decode('UTF-8'))
   f = Flow(serialized=object)
   return f if not return_json else (f,object)

def trace_vector(client,key):
   current = 0
   page_size = 20
   size = -1
   while size!=0:
      response = client.lrange(key,current,current+page_size-1)
      size = len(response)
      current += page_size
      for value in response:
         value = value.decode('UTF-8')
         tstamp, _, repl = value.partition(':')
         result = np.fromstring(repl,dtype=int,sep=' ')
         yield float(tstamp), result

def compute_vector(client,key):
   result = None
   current = 0
   page_size = 20
   size = -1
   while size!=0:
      response = client.lrange(key,current,current+page_size-1)
      size = len(response)
      current += page_size
      for value in response:
         value = value.decode('UTF-8')
         tstamp, _, repl = value.partition(':')
         if result is None:
            result = np.fromstring(repl,dtype=int,sep=' ')
         else:
            result += np.fromstring(repl,dtype=int,sep=' ')
   result = result.reshape((result.shape[0],1))
   return result


def restore_workflow_state(event_client,key,workflow_id):
   remote_context = RemoteTaskContext(event_client,workflow_id)
   client = event_client.connection
   flow = restore_workflow(client,key)
   S = compute_vector(client,key+':S')
   A = compute_vector(client,key+':A')
   context = RedisContext(flow,event_client,key,workflow_id,state=S,activation=A,cache=RedisInputCache(client,key),task_context=remote_context)
   return context

def run_workflow(workflow,workflow_id,event_client,prefix=''):
   p = Parser()
   c = Compiler()
   model = p.parse(workflow)
   flow = c.compile(model)

   key = prefix + workflow_id

   redis_client = event_client.connection

   redis_client.delete(key)
   redis_client.delete(key+':A')
   redis_client.delete(key+':S')

   remote_context = RemoteTaskContext(event_client,workflow_id)
   context = RedisContext(flow,event_client,key,workflow_id,cache=RedisInputCache(redis_client,key),task_context=remote_context)

   save_workflow(redis_client,flow,key)
   set_workflow_state(redis_client,key,'RUNNING')

   event_client.append(message({'workflow':workflow_id},kind='start-workflow'))

   runner = Runner()
   runner.start(context)

   while not context.ending.empty():
      runner.next(context,context.ending.get())

class LifecycleListener(EventListener):

   def __init__(self,key,group,workflows_key=None,inprogress_key=None,server='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-workflow','end-workflow'],server=server,port=port,username=username,password=password,pool=pool)
      self._workflows_key = workflows_key
      self._inprogress_key = inprogress_key

   def process(self,event_id, event):
      kind = event.get('kind')
      workflow_id = event.get('workflow')
      if workflow_id is not None:
         if kind=='start-workflow':
            if self._workflows_key is not None:
               self.connection.lpush(self._workflows_key,workflow_id)
            if self._inprogress_key is not None:
               self.connection.sadd(self._inprogress_key,workflow_id)
         elif kind=='end-workflow':
            if self._inprogress_key is not None:
               self.connection.srem(self._inprogress_key,workflow_id)
            set_workflow_state(self.connection,workflow_id,'FINISHED')
      self.append(receipt_for(event_id))
      return True

class TaskStartListener(EventListener):

   def __init__(self,key,group,server='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],server=server,port=port,username=username,password=password,pool=pool)


class TaskEndListener(EventListener):

   def __init__(self,key,group,prefix='',server='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['end-task'],server=server,port=port,username=username,password=password,pool=pool)
      self._prefix = prefix

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      index = event.get('index')
      if workflow_id is None:
         print('The workflow attribute is missing.',file=sys.stderr)
         return False
      if name is None:
         print('The task name attribute is missing.',file=sys.stderr)
         name = '(UNKNOWN)'
      if index is None:
         print('The task index attribute is missing.',file=sys.stderr)
         return False
      print(f'Workflow {workflow_id} end for task {name} ({index})')
      if not is_running(self.connection,workflow_id):
         print(f'Workflow {workflow_id} has been terminated')
         return True
      key = self._prefix + workflow_id
      context = restore_workflow_state(self, key, workflow_id)
      ended = context.new_transition()
      ended[index] = 1
      context.ending.put(ended)
      self.append(receipt_for(event_id))

      runner = Runner()
      while not context.ending.empty():
         runner.next(context,context.ending.get())

      return True
