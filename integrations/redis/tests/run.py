import os
from time import sleep
from random import random
import threading

from littleflow_redis import run_workflow, TaskEndListener, TaskStartListener, LifecycleListener
from rqse import EventClient, message, receipt_for, ReceiptListener


workflow = """
A → {
  B → C
  D
} → E
"""

workflow_id = 'littleflow:test:workflow-1'

class RandomWait(TaskStartListener):

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      index = event.get('index')
      self.append(receipt_for(event_id))
      wait = round(random()*3,3)
      print(f'Workflow {workflow_id} start task {name} ({index}), waiting {wait}s')
      sleep(wait)
      event = {'name':name,'index':index,'workflow':workflow_id}
      self.append(message(event,kind='end-task'))


stream_key = 'littleflow:test:run'
client = EventClient(stream_key,server=os.environ.get('REDIS_SERVER','0.0.0.0'),port=int(os.environ.get('REDIS_PORT',6379)),username=os.environ.get('REDIS_USER'),password=os.environ.get('REDIS_PASSWORD'))

# cleanup
client.connection.delete(stream_key)
client.connection.delete(workflow_id)
client.connection.delete(workflow_id+':A')
client.connection.delete(workflow_id+':S')


# we need something that will respond to end tasks and the algorithm forward
end_listener = TaskEndListener(stream_key,'ending')

ending = threading.Thread(target=lambda : end_listener.listen())
ending.start()

# we need something to simular tasks. This will wait a random number of seconds.
start_listener = RandomWait(stream_key,'starting')

starting = threading.Thread(target=lambda : start_listener.listen())
starting.start()

# and we can listen for the processin receipt
receipt_listener = None
class ReceiptLog:

   def __init__(self):
      self.cache = []

   def log(self,connection,id,receipt,target_id,target):
      self.cache.append((target,receipt))
      if target.get('kind')=='end-workflow':
         receipt_listener.stop()
      return True

logger = ReceiptLog()
receipt_listener = ReceiptListener(stream_key,logger=logger)
receipts = threading.Thread(target=lambda : receipt_listener.listen())
receipts.start()

# we need something to listen for the end of the workflow and shutdown the threads
class StopAtEnd(LifecycleListener):

   def process(self,event_id, event):
      super().process(event_id,event)
      if event.get('kind')=='end-workflow':
         end_listener.stop()
         start_listener.stop()
         self.stop()
      return True


stop_listener = StopAtEnd(stream_key,'stopping')

stopper = threading.Thread(target=lambda : stop_listener.listen())
stopper.start()

# jut wait till tings are established
max_wait = 5
while (not end_listener.established or not start_listener.established or not receipt_listener.established or not stop_listener.established) and max_wait>0:
   sleep(1)
   max_wait -= 1

# make sure we're connected
assert end_listener.established
assert start_listener.established
assert receipt_listener.established
assert stop_listener.established

# run the workflow
run_workflow(workflow,workflow_id,client)

# we wait till the end of the workflow
receipts.join(timeout=120)

# Now let's drain all the receipts
for target, receipt in logger.cache:
   print(f'{target} processed at {receipt["at"]}')
