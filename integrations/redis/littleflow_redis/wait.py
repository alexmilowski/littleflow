import os
import collections
import threading
from dataclasses import dataclass
from uuid import uuid4
import logging
import json

from rqse import EventListener, message, receipt_for
import redis
from littleflow import merge

from .context import RedisOutputCache

def retry_output_cache_limit():
   return int(os.environ.get('LITTLEFLOW_OUTPUT_CACHE_RETRY_LIMIT',10))

def retry_output_cache(cache,index,value):
   retries = 0
   success = False
   limit = retry_output_cache_limit()
   while not success and retries < limit:
      try:
         cache[index] = value
         success = True
      except redis.exceptions.ConnectionError as ex:
         logging.exception(ex)
         logging.error(f'Connection reset while setting output of step {index}')
         retries += 1

def retry_output_cache_get(cache,index):
   retries = 0
   success = False
   limit = retry_output_cache_limit()
   value = None
   while not success and retries < limit:
      try:
         value = cache[index]
         success = True
      except redis.exceptions.ConnectionError as ex:
         logging.exception(ex)
         logging.error(f'Connection reset while setting output of step {index}')
         retries += 1
   return value

@dataclass
class TaskInfo:
   workflow_id : str
   index : int
   name : str
   input : 'typing.Any' = None

class WaitForEventListener(EventListener):
   def __init__(self,key,parent,info,event_name,send_receipt=True,match={},host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,f'wait-for-{uuid4()}',select=[event_name],host=host,port=port,username=username,password=password,pool=pool)
      self.parent = parent
      self._event_name = event_name
      self._info = info
      self._send_receipt = send_receipt
      self._match = match
      self._thread = None

   @property
   def target(self):
      f = lambda : self.listen()
      f.__name__ = f'wait_for {self._event_name} {self._match }'
      return f

   @property
   def thread(self):
      return self._thread

   @thread.setter
   def thread(self,value):
      self._thread = value

   def matches(self,event):
      for key,value in self._match.items():
         if event.get(key)!=value:
            return False
      return True

   def process(self,event_id, event):

      # check to make sure the event type matches
      if not self.matches(event):
         return False

      # send a receipt for the event
      if self._send_receipt:
         self.append(receipt_for(event_id))

      # cache the output of the wait
      output = event.get('output')
      if output is None:
         output = self._info.input
      else:
         output = merge([self._match,output])
      if output is not None:
         cache = RedisOutputCache(self.connection,self._info.workflow_id)
         retry_output_cache(cache,self._info.index,output)
      # Generate the end task
      event = {'name':self._info.name,'index':self._info.index,'workflow':self._info.workflow_id}
      self.append(message(event,kind='end-task'))

      # end the wait
      self.stop()
      if not self.parent.stop_work(self):
         print('Cannot remove wait_for thread.')
      return True

class Delay:
   def __init__(self,parent,info,delay):
      self.parent = parent
      self._info = info
      self._delay = delay
      self._wait = threading.Event()

   @property
   def target(self):
      f = lambda : self.run()
      f.__name__ = f'delay {self._delay}'
      return f

   @property
   def thread(self):
      return self._thread

   @thread.setter
   def thread(self,value):
      self._thread = value

   def stop(self):
      self._wait.set()

   def run(self):
      self._wait.wait(self._delay)
      if self._info.input is not None:
         cache = RedisOutputCache(self.parent.connection,self._info.workflow_id)
         retry_output_cache(cache,self._info.index,self._info.input)
      event = {'name':self._info.name,'index':self._info.index,'workflow':self._info.workflow_id}
      self.parent.append(message(event,kind='end-task'))
      self.stop()
      if not self.parent.stop_work(self):
         logging.error('Cannot remove delay thread.')
      return True

class WaitTaskListener(EventListener):

   def __init__(self,key,group='wait',host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task','countdown-latch-zero'],host=host,port=port,username=username,password=password,pool=pool)
      self._work = collections.deque()
      self._lock = threading.RLock()

   def fail(self,workflow_id,index,name,reason=None):
      event = {'name':name,'index':index,'workflow':workflow_id,'status':'FAILURE'}
      if reason is not None:
         event['reason'] = reason
      self.append(message(event,kind='end-task'))
      return True

   def start_work(self,work):
      try:
         if not self._lock.acquire(timeout=30):
            return False
         work.thread = threading.Thread(target=work.target)
         self._work.append(work)
         work.thread.start()
         return True
      finally:
         self._lock.release()

   def stop_work(self,work):
      try:
         if not self._lock.acquire(timeout=30):
            return False
         self._work.remove(work)
         return True
      finally:
         self._lock.release()

   def wait_for(self,info,event_name,send_receipt=True,match={}):
      logging.info(f'Workflow {info.workflow_id} is waiting for event {event_name}')
      listener = WaitForEventListener(self._stream_key,self,info,event_name,send_receipt,match,pool=self.pool)
      if not self.start_work(listener):
         return False
      return True

   def delay(self,info,duration):
      logging.info(f'Workflow {info.workflow_id} delay for {duration}')
      do_delay = Delay(self,info,duration)
      if not self.start_work(do_delay):
         return False
      return True
   
   def latch_keys(self,info,name):
      latch_name = f'workflow:latch:{name}'
      latch_consumers = latch_name + ':consumers'
      return latch_name, latch_consumers
   
   def acquire(self,info,name):
      latch_name, _ = self.latch_keys(info,name)
      logging.info(f'Workflow {info.workflow_id} is acquiring {latch_name}')
      # We need to guarantee the count is positive
      value = self.connection.incr(latch_name)
      while value < 1:
         logging.warning(f'Workflow {info.workflow_id} acquiring returned negative count {value} on {latch_name}')
         value = self.connection.incr(latch_name)
      return True

   def release(self,info,name):
      latch_name, latch_consumers = self.latch_keys(info,name)
      logging.info(f'Workflow {info.workflow_id} is releasing {latch_name}')
      value = self.connection.decr(latch_name)
      if value < 0:
         logging.warning(f'Workflow {info.workflow_id} release returned negative count {value} on {latch_name}')
      if value <= 0:
         event = {'latch':latch_name,'consumers':latch_consumers}
         self.append(message(event,kind='countdown-latch-zero'))
      return True

   def countdown(self,info,name):
      latch_name, latch_consumers = self.latch_keys(info,name)
      event = {'name':info.name,'index':info.index,'workflow':info.workflow_id}
      value = self.connection.get(latch_name)
      if value is None or int(value)<=0:
         cache = RedisOutputCache(self.connection,info.workflow_id)
         retry_output_cache(cache,info.index,info.input)
         logging.warning(f' {latch_name} is already zero or less for workflow {info.workflow_id}, ending immediately')
         self.append(message(event,kind='end-task'))
         return True

      logging.info(f'Workflow {info.workflow_id} is waiting for countdown on {latch_name}')
      count = self.connection.incr(latch_consumers)
      consumer_info_key = f'{latch_name}:{count}'
      consumer_info = json.dumps(event)
      self.connection.set(consumer_info_key,consumer_info)
      return True

   def onStop(self):
      for work in self._work:
         work.stop()

   def process(self,event_id, event):

      # Process any countdown-latch-zero events first
      kind = event.get('kind')
      if kind=='countdown-latch-zero':
         latch_name = event.get('latch')
         if latch_name is None:
            logging.error(f'{kind} event did not have latch name.')
            return False
         latch_consumers = event.get('latch_consumers')
         if latch_consumers is None:
            latch_consumers = latch_name + ':consumers'

         consumers = self.connection.decr(latch_consumers)
         while consumers >= 0 :
            # Get the consumer information
            consumer_info_key = f'{latch_name}:{consumers+1}'
            raw_json = self.connection.get(consumer_info_key)

            # make sure we have something to process
            if raw_json is None:
               logging.error(f'The consumer {consumers+1} does not have information at {consumer_info_key}')
            else:
               # send the end event
               try:
                  event = json.loads(raw_json.decode('UTF-8'))
                  cache = RedisOutputCache(self.connection,event.get('workflow'))
                  index = event.get('index')
                  # The output is the input of the step so we get this from the cache
                  step_input = retry_output_cache_get(cache,index-1)
                  retry_output_cache(cache,index,step_input)
                  self.append(message(event,kind='end-task'))
               except ValueError as ex:
                  logging.error(f'Cannot parse consumer info at {consumer_info_key}: {ex}')

            # get the next consumer
            consumers = self.connection.decr(latch_consumers)

         # clean as the latch is now done
         self.connection.delete(latch_name)
         self.connection.delete(latch_consumers)
         return True
      
      # otherwise, we have a start-event for wait tasks 
      
      workflow_id = event.get('workflow')
      base = event.get('base')
      name = event.get('name')
      index = event.get('index')
      ns, _, task_name = base.partition(':') if base is not None else name.partition(':')
      if ns!='wait':
         return False

      step_input = event.get('input')
      parameters = event.get('parameters')

      info = TaskInfo(workflow_id,index,name,step_input)

      self.append(receipt_for(event_id))

      if task_name=='delay':
         # TODO: parse units
         duration = parameters.get('duration')
         if duration is None:
            return self.fail(workflow_id,index,name,f'{task_name} does not have an duration parameter')
         duration = int(duration)
         if not self.delay(info,duration):
            return self.fail(workflow_id,index,name,f'Cannot acquire lock for {task_name} task')

      elif task_name=='event':
         event_name = parameters.get('event')
         if event_name is None:
            return self.fail(workflow_id,index,name,f'{task_name} does not have an event parameter')

         receipt = bool(parameters.get('receipt',True))

         match_kind = parameters.get('match',None)
         if match_kind=='input':
            if step_input is None:
               match = {}
            else:
               match = step_input if type(step_input)==dict else step_input[0]
         else:
            match = {}

         if not self.wait_for(info,event_name,receipt,match):
            return self.fail(workflow_id,index,name,f'Cannot acquire lock for {task_name} task')
      elif task_name=='acquire':
         name_template = parameters.get('name')
         logging.info(f'name template: {name_template}')
         if step_input is None:
            step_input = {}
         try:
            latch_name = name_template.format(input=step_input,parameters=parameters)
         except KeyError as ex:
            return self.fail(workflow_id,index,name,f'Undefined variable {ex} referenced in name template.')
         except ValueError as ex:
            return self.fail(workflow_id,index,name,f'Bad name value template ({ex}): {name_template}')
         if self.acquire(info,latch_name):
            cache = RedisOutputCache(self.connection,workflow_id)
            retry_output_cache(cache,index,step_input)
            event = {'name':name,'index':index,'workflow':workflow_id}
            self.append(message(event,kind='end-task'))
         else:
            return self.fail(workflow_id,index,name,f'Cannot perform acquire task.')
         
      elif task_name=='release':
         name_template = parameters.get('name')
         if step_input is None:
            step_input = {}
         try:
            latch_name = name_template.format(input=step_input,parameters=parameters)
         except KeyError as ex:
            return self.fail(workflow_id,index,name,f'Undefined variable {ex} referenced in name template.')
         except ValueError as ex:
            return self.fail(workflow_id,index,name,f'Bad name value template ({ex}): {name_template}')
         if self.release(info,latch_name):
            cache = RedisOutputCache(self.connection,workflow_id)
            retry_output_cache(cache,index,step_input)
            event = {'name':name,'index':index,'workflow':workflow_id}
            self.append(message(event,kind='end-task'))
         else:
            return self.fail(workflow_id,index,name,f'Cannot perform acquire task.')
      elif task_name=='countdown':
         name_template = parameters.get('name')
         if step_input is None:
            step_input = {}
         try:
            latch_name = name_template.format(input=step_input,parameters=parameters)
         except KeyError as ex:
            return self.fail(workflow_id,index,name,f'Undefined variable {ex} referenced in name template.')
         except ValueError as ex:
            return self.fail(workflow_id,index,name,f'Bad name value template ({ex}): {name_template}')
         if not self.countdown(info,latch_name):
            return self.fail(workflow_id,index,name,f'Cannot perform latch count down wait task.')
      else:
         return self.fail(workflow_id,index,name,f'Unrecognized wait task name {task_name}')

      return True
