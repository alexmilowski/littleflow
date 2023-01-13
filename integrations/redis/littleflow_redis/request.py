import logging
from urllib.parse import urljoin
import json

import requests 

from rqse import EventListener, message, receipt_for
from littleflow import merge

from .context import RedisOutputCache, MetadataService

def value_for(input,parameters,name,default=None):
   return input.get(name,parameters.get(name,default)) if input is not None else parameters.get(name,default) if parameters is not None else default

class jsondict(dict):
   def __str__(self):
      return json.dumps(self)
   def copy_of(other):
      copy = jsondict()
      for key, value in other.items():
         if type(value)==dict:
            value = jsondict.copy_of(value)
         copy[key] = value
      return copy

class RequestTaskListener(EventListener):

   def __init__(self,key,credential_actor=None,group='request',host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],host=host,port=port,username=username,password=password,pool=pool)
      self._credential_actor = credential_actor

   def fail(self,workflow_id,index,name,reason=None):
      event = {'name':name,'index':index,'workflow':workflow_id,'status':'FAILURE'}
      if reason is not None:
         event['reason'] = reason
      self.append(message(event,kind='end-task'))
      return True

   def output_for(self,workflow_id,index,output):
      if output is not None:
         cache = RedisOutputCache(self.connection,workflow_id)
         cache[index] = output

   def process(self,event_id, event):

      is_debug = logging.DEBUG >= logging.getLogger().getEffectiveLevel()

      workflow_id = event.get('workflow')
      base = event.get('base')
      name = event.get('name')
      index = event.get('index')
      ns, _, task_name = base.partition(':') if base is not None else name.partition(':')
      if ns!='request':
         return False

      input = jsondict.copy_of(event.get('input'))
      parameters = jsondict.copy_of(event.get('parameters'))

      self.append(receipt_for(event_id))

      sync = bool(value_for(input,parameters,'sync',True))

      environ = value_for(input,parameters,'environ')
      metadata = MetadataService.getService(environ=environ)

      category = value_for({},parameters,'category',default='')

      base_url = metadata[f'{category}_url' if category is not None else 'base_url']

      url = value_for(input,parameters,'url')
      if is_debug:
         logging.debug(f'environ={environ}')
         logging.debug(f'category={category}')
         logging.debug(f'base_url={base_url}')
         logging.debug(f'url={url}')

      if base_url is not None:
         url = urljoin(base_url,url)

      if is_debug:
         logging.debug(f'final_url={url}')
         
      template = value_for(input,parameters,'template')
      content_type = value_for(input,parameters,'content_type','application/json')
      use_context_parameters = bool(value_for(input,parameters,'use_context_parameters',True))
      output_modes = value_for(input,parameters,'output_mode',[])
      if type(output_modes)==str:
         output_modes = [output_modes]
      error_on_status = bool(value_for(input,parameters,'error_on_status',True))

      if task_name not in ['get','post','put','delete']:
         return self.fail(workflow_id,index,name,f'Unrecognized wait task name {task_name}')

      if url is None:
         return self.fail(workflow_id,index,name,f'Unrecognized wait task name {task_name}')

      if not sync and use_context_parameters:
         if url.rfind('?')<0:
            url += '?'
         else:
            url += '&'
         url += f'littleflow-name={name}'
         url += f'&littleflow-base={base}'
         url += f'&littleflow-index={index}'
         url += f'&littleflow-workflow={workflow_id}'

      if is_debug:
         logging.debug(f'HTTP {task_name.upper()} request on {url}')

      try:
         headers = {}
         if self._credential_actor is not None:
            headers['Authorization'] = f'Bearer {self._credential_actor(input,parameters)}'
            if is_debug:
               logging.debug(f'Authorization: {headers["Authorization"]}')
         data = template.format(input=input,parameters=parameters) if template is not None else json.dumps(input)
         if is_debug and data is not None:
            logging.debug("Request data:")
            logging.debug(data)
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

         if is_debug:
            logging.debug(f'{response.status_code} response for {url}')
            logging.debug(response.text)

         if error_on_status and (response.status_code<200 or response.status_code>=300):
            return self.fail(workflow_id,index,name,f'Request failed ({response.status_code}): {response.text}')


         try:
            output = input
            for mode in output_modes:
               if output is None:
                  output = {}
               if mode=='status':
                  output['request_status'] = response.status_code
               elif mode=='response_text':
                  if is_debug:
                     logging.debug(response.text)
                  output['response'] = response.text
               elif mode=='response_json':
                  if is_debug:
                     logging.debug(response.text)
                  output['response'] = response.json()
         except Exception as ex:
            logging.exception(f'Unabled to process output of {name} due to exception.')
            return self.fail(workflow_id,index,name,f'Unabled to process response output due to exception: {ex}')

         self.output_for(workflow_id,index,output)

         if sync:
            event = {'name':name,'index':index,'workflow':workflow_id}
            self.append(message(event,kind='end-task'))

         return True

      except Exception as ex:
         logging.exception(f'Unabled to send {name} due to exception.')
         return self.fail(workflow_id,index,name,f'Unabled to send request due to exception: {ex}')
