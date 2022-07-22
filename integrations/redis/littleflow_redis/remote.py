import sys
from datetime import datetime, timezone
import json
from uuid import uuid4


import numpy as np
from littleflow import Parser, Compiler, Runner, Context, FunctionTaskContext, Flow
from rqse import EventClient, EventListener, message, receipt_for

from .context import RedisOutputCache

def tstamp():
   return datetime.now(timezone.utc).isoformat()

def workflow_state(client,key,default=None):
   value = client.get(key+':state')
   return value.decode('UTF-8') if value is not None else default

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

      if input is not None and len(input)>0:
         event['input'] = input

      self._client.append(message(event,kind='start-task'))

      starting = context.new_transition()
      starting[invocation.index] = 1


class RedisContext(Context):
   def __init__(self,flow,client,key,workflow_id,state=None,activation=None,cache=None,task_context=None):
      super().__init__(flow,state=state,activation=activation,cache=cache,task_context=task_context,)
      self._client = client
      self._key = key
      self._key_A = key + ':A'
      self._key_S = key + ':S'
      self._workflow_id = workflow_id

   def accumulate(self,A):
      if (1*A).sum()>0:
         self._client.connection.lpush(self._key_A,str(tstamp())+' '+str(A.flatten())[1:-1])

   def start(self,N):
      client = self._client.connection
      if not is_running(client,self._key):
         return
      starting = 1*N
      client.lpush(self._key_S,str(tstamp())+' '+str(starting.flatten())[1:-1])
      super().start(N)
      A = - starting * self.T
      client.lpush(self._key_A,str(tstamp())+' '+str(A.flatten())[1:-1])

   def end(self,N):
      ending = - 1*N
      self._client.connection.lpush(self._key_S,str(tstamp())+' '+str(ending.flatten())[1:-1])
      super().end(N)

   def ended(self,value):
      self._client.append(message({'workflow':self._workflow_id },kind='end-workflow'))

def workflow_archive(client,key):
   value = client.get(key)
   if value is None:
      raise IOError(f'No workflow value at {key}')
   object = json.loads(value.decode('UTF-8'))
   object['S'] = [ [tstamp.isoformat(),v.flatten().tolist()] for tstamp, v in trace_vector(client,key+':S')]
   object['A'] = [ [tstamp.isoformat(),v.flatten().tolist()] for tstamp, v in trace_vector(client,key+':A')]
   return object

def restart_workflow(event_client,key,workflow_id):
   client = event_client.connection
   s_key = key+':S'
   S = compute_vector(client,s_key)
   if S.sum()>0:
      # Make an adjusment to S to take it back to zero
      ending = - S
      client.lpush(s_key,str(tstamp())+' '+str(ending.flatten())[1:-1])

      # ensure S is a zero/one vector
      S = S>0
      S = 1*S

      client.delete(key+':FAILED')
      set_workflow_state(client,key,'RUNNING')

      # reload the context
      context = load_workflow_state(event_client, key, workflow_id)
      context.start(S)

      # run the algorithm forward
      runner = Runner()
      while not context.ending.empty():
         runner.next(context,context.ending.get())

      return True
   else:
      return False

def restore_workflow(client,key,archive,workflows_key=None):
   S = archive['S']
   del archive['S']
   A = archive['A']
   del archive['A']
   client.set(key,json.dumps(archive))
   skey = key + ':S'
   started = np.zeros(len(archive['T']),dtype=int)
   for tstamp, v in reversed(S):
      started += np.array(v)
      client.lpush(skey,tstamp+' '+' '.join(map(str,v)))
   akey = key + ':A'
   for tstamp, v in reversed(A):
      client.lpush(akey,tstamp+' '+' '.join(map(str,v)))
   set_workflow_state(client,key,'TERMINATED')
   if workflows_key is not None:
      client.lpush(workflows_key,key)



def save_workflow(client,flow,key):
   client.set(key,str(flow))

def load_workflow(client,key,return_json=False):
   value = client.get(key)
   if value is None:
      raise IOError(f'No workflow value at {key}')
   object = json.loads(value.decode('UTF-8'))
   f = Flow(serialized=object)
   return f if not return_json else (f,object)

def get_failures(client,key):
   f_key = key+':FAILED'
   value = client.get(f_key)
   return np.fromstring(value,dtype=int,sep=' ') if value is not None else None

def set_failures(client,key,failures):
   value = str(failures.flatten())[1:-1]
   f_key = key+':FAILED'
   client.set(f_key,value)

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
         tstamp, _, repl = value.partition(' ')
         result = np.fromstring(repl,dtype=int,sep=' ')
         yield datetime.fromisoformat(tstamp), result

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
         tstamp, _, repl = value.partition(' ')
         if result is None:
            result = np.fromstring(repl,dtype=int,sep=' ')
         else:
            result += np.fromstring(repl,dtype=int,sep=' ')
   result = result.reshape((result.shape[0],1)) if result is not None else None
   return result


def load_workflow_state(event_client,key,workflow_id):
   remote_context = RemoteTaskContext(event_client,workflow_id)
   client = event_client.connection
   flow = load_workflow(client,key)
   S = compute_vector(client,key+':S')
   A = compute_vector(client,key+':A')
   context = RedisContext(flow,event_client,key,workflow_id,state=S,activation=A,cache=RedisOutputCache(client,key),task_context=remote_context)
   return context

def run_workflow(workflow,event_client,input=None,workflow_id=None,prefix=''):
   p = Parser()
   c = Compiler()
   model = p.parse(workflow)
   flow = c.compile(model)

   if workflow_id is None:
      workflow_id = f'workflow:{flow.name+"-" if flow.name is not None else ""}{str(uuid4())}'

   key = prefix + workflow_id

   redis_client = event_client.connection

   redis_client.delete(key)
   redis_client.delete(key+':A')
   redis_client.delete(key+':S')

   remote_context = RemoteTaskContext(event_client,workflow_id)
   context = RedisContext(flow,event_client,key,workflow_id,cache=RedisOutputCache(redis_client,key),task_context=remote_context)

   save_workflow(redis_client,flow,key)
   set_workflow_state(redis_client,key,'RUNNING')

   event_client.append(message({'workflow':workflow_id},kind='start-workflow'))

   runner = Runner()
   runner.start(context,input=input)

   while not context.ending.empty():
      runner.next(context,context.ending.get())

   return workflow_id

class LifecycleListener(EventListener):

   def __init__(self,key,group,workflows_key=None,inprogress_key=None,host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-workflow','end-workflow','terminated-workflow','failed-workflow'],host=host,port=port,username=username,password=password,pool=pool)
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
         elif kind=='terminated-workflow' or kind=='failed-workflow':
            if self._inprogress_key is not None:
               self.connection.srem(self._inprogress_key,workflow_id)
      self.append(receipt_for(event_id))
      return True

class TaskStartListener(EventListener):

   def __init__(self,key,group,host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],host=host,port=port,username=username,password=password,pool=pool)


class TaskEndListener(EventListener):

   def __init__(self,key,group,prefix='',host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['end-task'],host=host,port=port,username=username,password=password,pool=pool)
      self._prefix = prefix

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      index = event.get('index')
      outcome = event.get('status','SUCCESS')
      ok = outcome=='SUCCESS'
      if workflow_id is None:
         print('The workflow attribute is missing.',file=sys.stderr)
         return False
      if name is None:
         print('The task name attribute is missing.',file=sys.stderr)
         name = '(UNKNOWN)'
      if index is None:
         print('The task index attribute is missing.',file=sys.stderr)
         return False
      if ok:
         print(f'Workflow {workflow_id} end for task {name} ({index})')
      else:
         print(f'Workflow {workflow_id} failure for task {name} ({index})')
      key = self._prefix + workflow_id

      state = workflow_state(self.connection,key)

      if state!='RUNNING':
         if state=='TERMINATING':
            print(f'Workflow {workflow_id} has been terminated')
            state = 'TERMINATED'
            set_workflow_state(self.connection,key,state)
            self.append(message({'workflow':workflow_id },kind='terminated-workflow'))
         elif state=='FAILED':
            pass
         elif state=='TERMINATED':
            pass
         else:
            print(f'Workflow {workflow_id}: unable to handle end outcome for state {state}')
      elif not ok:
         print(f'Workflow {workflow_id} has failed')
         state = 'FAILED'
         set_workflow_state(self.connection,key,state)
         self.append(message({'workflow':workflow_id },kind='failed-workflow'))


      self.append(receipt_for(event_id))

      if ok:

         context = load_workflow_state(self, key, workflow_id)

         ended = context.new_transition()
         ended[index] = 1

         context.ending.put(ended)

         runner = Runner()
         while not context.ending.empty():
            runner.next(context,context.ending.get())
      else:

         failures = get_failures(self.connection,key)
         if failures is None:
            flow = load_workflow(self.connection,key)
            failures = np.zeros(flow.F.shape[0],dtype=int)
         failures[index] = 1
         set_failures(self.connection,key,failures)

      return True

def terminate_workflow(event_client,key,workflow_id,inprogress_key=None):
   client = event_client.connection
   if client.exists(key)==0:
      return
   state = workflow_state(client,key)
   terminated = False
   if state=='TERMINATING':
      set_workflow_state(client,key,'TERMINATED')
      event_client.append(message({'workflow':workflow_id},kind='terminated-workflow'))
      terminated = True
   else:
      set_workflow_state(client,key,'TERMINATING')
   if inprogress_key is not None:
      client.srem(inprogress_key,key)
   return terminated

def delete_workflow(client,key,workflows_key=None):
   size = -1
   try:
      flow = load_workflow(client,key)
      size = flow.F.shape[0]
   except IOError as ex:
      pass
   client.delete(key)
   client.delete(key+':A')
   client.delete(key+':S')
   client.delete(key+':state')
   client.delete(key+':FAILED')
   if workflows_key is not None:
      client.lrem(workflows_key,0,key)
   client.delete(f'{key}:output:-1')
   if size<0:
      found = True
      index = 0
      while found:
         found = client.delete(f'{key}:output:{index}')>0
         index += 1
   else:
      for index in range(size):
         client.delete(f'{key}:output:{index}')
