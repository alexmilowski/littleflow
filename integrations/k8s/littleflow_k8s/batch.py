from rqse import EventListener, message, receipt_for
from time import sleep

# TODO: should we have this dependency?
from littleflow_redis import RedisOutputCache

class BatchStart(EventListener):

   def __init__(self,key,group,host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],host=host,port=port,username=username,password=password,pool=pool)

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      ns, _, job_name = name.partition(':')
      if ns!='batch':
         return False
      index = event.get('index')
      input = event.get('input')
      parameters = event.get('parameters')

      print(f'Workflow {workflow_id} start task {name} ({index})')
      self.append(receipt_for(event_id))

      # hack for now
      sleep(2)

      output = input
      if output is not None:
         cache = RedisOutputCache(self.connection,workflow_id)
         cache[index] = output

      event = {'name':name,'index':index,'workflow':workflow_id}
      event['status'] = 'SUCCESS'
      self.append(message(event,kind='end-task'))

      return True
