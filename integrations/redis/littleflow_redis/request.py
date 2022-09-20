import requests 

from rqse import EventListener, message, receipt_for
from littleflow import merge

from .context import RedisOutputCache

def value_for(input,parameters,name,default=None):
   return input.get(name,parameters.get(name,default))

class RequestTaskListener(EventListener):

   def __init__(self,key,credential_actor=None,group='starting',host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],host=host,port=port,username=username,password=password,pool=pool)
      self._credential_actor = credential_actor

   def fail(self,workflow_id,index,name,reason=None):
      event = {'name':name,'index':index,'workflow':workflow_id,'status':'FAILURE'}
      if reason is not None:
         event['reason'] = reason
      self.append(message(event,kind='end-task'))
      return True

   def process(self,event_id, event):
      workflow_id = event.get('workflow')
      name = event.get('name')
      index = event.get('index')
      ns, _, task_name = name.partition(':')
      if ns!='request':
         return False

      input = event.get('input')
      parameters = event.get('parameters')

      self.append(receipt_for(event_id))

      sync = bool(value_for(input,parameters,'sync',True))
      url = value_for(input,parameters,'url')
      template = value_for(input,parameters,'template')
      content_type = value_for(input,parameters,'content-type','application/json')
      use_context_parameters = bool(value_for(input,parameters,'use-context-parameters',True))

      if task_name not in ['get','post','put','delete']:
         return self.fail(workflow_id,index,name,f'Unrecognized wait task name {task_name}')

      if url is None:
         return self.fail(workflow_id,index,name,f'Unrecognized wait task name {task_name}')

      if not sync and use_context_parameters:
         if url.rfind('?')<0:
            url += '?'
         else:
            url += '&'
         url += f'task-name={name}'
         url += f'&index={index}'
         url += f'&workflow={workflow_id}'

      headers = {}
      if self._credential_actor is not None:
         headers['Authorization'] = self._credential_actor(input,parameters)
      data = template.format(input=input,parameters=parameters) if template is not None else None
      if task_name=='get':
         response = requests.get(url,headers=headers)
      elif task_name=='post':
         headers['Content-Type'] = content_type
         response = requests.post(url,headers=headers,data=data if data is not None else '')
      elif task_name=='put':
         headers['Content-Type'] = content_type
         response = requests.put(url,headers=headers,data=data if data is not None else '')
      elif task_name=='delete':
         response = requests.delete(url)

      if response.status_code<200 or response.status_code>=300:
         return self.fail(workflow_id,index,name,f'Request failed ({response.status_code}): {response.text}')

      if sync:
         event = {'name':name,'index':index,'workflow':workflow_id}
         self.append(message(event,kind='end-task'))

      return True
