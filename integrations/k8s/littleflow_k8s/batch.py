from rqse import EventListener, message, receipt_for
from time import sleep

class BatchStart(EventListener):

   def __init__(self,key,group,server='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],server=server,port=port,username=username,password=password,pool=pool)

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      ns, _, job_name = name.partition(':')
      print(ns,job_name)
      if ns!='batch':
         return False
      index = event.get('index')
      input = event.get('input')
      parameters = event.get('parameters')

      print(f'Workflow {workflow_id} start task {name} ({index})')
      self.append(receipt_for(event_id))

      # hack for now
      sleep(2)
      event = {'name':name,'index':index,'workflow':workflow_id}
      event['status'] = 'SUCCESS'
      self.append(message(event,kind='end-task'))

      return True
