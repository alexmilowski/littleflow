import sys
from datetime import datetime
import json

import numpy as np
from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext, Flow
from rqse import EventClient, EventListener, message, receipt_for

from .context import RedisInputCache

def tstamp():
   return datetime.utcnow().timestamp()


class RemoteTaskContext(FunctionTaskContext):

   def __init__(self,event_client,workflow_id,key,lookup={}):
      super().__init__(lookup)
      self._client = event_client
      self._workflow_id = workflow_id
      self._key = key
      self._key_S = self._key + ':S'

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

      self._client.connection.sadd(self._key_S,str(tstamp())+':'+str(starting.flatten())[1:-1])

class RedisContext(Context):
   def __init__(self,flow,client,key,workflow_id,state=None,activation=None,cache=None,task_context=None):
      super().__init__(flow,state=state,activation=activation,cache=cache,task_context=task_context,)
      self._client = client
      self._key_A = key + ':A'
      self._workflow_id = workflow_id

   def accumulate(self,A):
      if (1*A).sum()>0:
         self._client.connection.sadd(self._key_A,str(tstamp())+':'+str(A.flatten())[1:-1])

   def start(self,N):
      super().start(N)
      A = - 1*N * self.T
      self._client.connection.sadd(self._key_A,str(tstamp())+':'+str(A.flatten())[1:-1])

   def ended(self,value):
      self._client.append(message({'workflow':self._workflow_id },kind='end-workflow'))



def save_workflow(client,flow,key):
   client.set(key,str(flow))

def restore_workflow(client,key):
   value = client.get(key)
   if value is None:
      raise IOError(f'No workflow value at {key}')
   object = json.loads(value.decode('UTF-8'))
   f = Flow(serialized=object)
   return f

def compute_vector(client,key):
   result = None
   cursor = -1
   while cursor!=0:
      response = client.sscan(key,cursor=cursor if cursor>0 else 0,count=20)
      cursor = response[0]
      for value in response[1]:
         value = value.decode('UTF-8')
         tstamp, _, repl = value.partition(':')
         if result is None:
            result = np.fromstring(repl,dtype=int,sep=' ')
         else:
            result += np.fromstring(repl,dtype=int,sep=' ')
   result = result.reshape((result.shape[0],1))
   return result


def restore_workflow_state(event_client,key,workflow_id):
   remote_context = RemoteTaskContext(event_client,workflow_id,key)
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

   remote_context = RemoteTaskContext(event_client,workflow_id,key)
   context = RedisContext(flow,event_client,key,workflow_id,cache=RedisInputCache(event_client.connection,key),task_context=remote_context)

   save_workflow(event_client.connection,flow,key)

   event_client.append(message({'workflow':workflow_id},kind='start-workflow'))
   context.start(context.initial)

   runner = Runner()
   while not context.ending.empty():
      runner.next(context,context.ending.get())

class LifecycleListener(EventListener):

   def __init__(self,key,group,server='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-workflow','end-workflow'],server=server,port=port,username=username,password=password,pool=pool)

   def process(self,event_id, event):
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
      key = self._prefix + workflow_id
      context = restore_workflow_state(self, key, workflow_id)
      ended = context.new_transition()
      ended[index] = 1
      context.ending.put(ended)
      self.append(receipt_for(event_id))

      S = -ended
      self.connection.sadd(key + ':S',str(tstamp())+':'+str(S.flatten())[1:-1])

      runner = Runner()
      while not context.ending.empty():
         runner.next(context,context.ending.get())

      return True
