import logging
from urllib.parse import urljoin
import json

from rqse import EventListener, message, receipt_for
from littleflow import merge

from .context import RedisOutputCache, MetadataService
from .request import value_for

class RedisTaskListener(EventListener):

   def __init__(self,key,group='redis',host='0.0.0.0',port=6379,username=None,password=None,pool=None):
      super().__init__(key,group,select=['start-task'],host=host,port=port,username=username,password=password,pool=pool)

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

   def decode_response(self,response,conversion_type=str):
      def decode_item(item):
         if type(response)==list or type(response)==tuple:
            # TODO: recursive is not amazing here but these responses are small
            return self.decode_response(item)
         elif type(response)==bytes:
            return item.decode('UTF-8')
         elif type(response)==dict:
            return self.decode_response(item)
         else:
            return item
      if type(response)==list or type(response)==tuple:
         return list(map(decode_item,response))
      elif type(response)==dict:
         o = {}
         for name, value in response.items():
            o[name.decode('UTF-8')] = value.decode('UTF-8') if type(value)==bytes else value
         return o
      elif type(response)==bytes:
         response = response.decode('UTF-8') 
         return conversion_type(response)
      else:
         return response

   def process(self,event_id, event):

      is_debug = logging.DEBUG >= logging.getLogger().getEffectiveLevel()

      workflow_id = event.get('workflow')
      base = event.get('base')
      name = event.get('name')
      index = event.get('index')
      ns, _, task_name = base.partition(':') if base is not None else name.partition(':')
      if ns!='redis':
         return False

      input_data = event.get('input')
      parameters = event.get('parameters')
      args = parameters.get('args',[])
      if type(args)!=list:
         return self.fail(workflow_id,index,name,f'Type of args parameter is not a list: {type(args)}')

      try:
         format_args = parameters.get('format',True)
         if format_args:
            try:
               args = [str(item).format(input=input_data,parameters=parameters) for item in args]
            except Exception as ex:
               logging.exception(f'Template formatting of args caused exception: {ex}')
               return self.fail(workflow_id,index,name,f'Template formatting of args caused exception: {ex}')

         target_key = parameters.get('key',args[0] if len(args)>0 else None)
         target_type = parameters.get('type','string')
         if target_type=='string':
            target_type = str
         elif target_type=='int':
            target_type = int


         response = self.connection.execute_command(task_name,*args)

         self.append(receipt_for(event_id))

         logging.debug(f'{workflow_id} Redis target key {target_key} to type {target_type}')
         if response is not None and type(response)!=bool and target_key is not None:
            logging.debug(f'{workflow_id} decoding response and setting {target_key} on output')
            response = self.decode_response(response,target_type)
            if input_data is None:
               input_data = {}
            input_data[target_key] = response

         self.output_for(workflow_id,index,input_data)

         event = {'name':name,'index':index,'workflow':workflow_id}
         self.append(message(event,kind='end-task'))

         return True

      except Exception as ex:
         logging.exception(f'Unabled to handle {name} due to exception.')
         return self.fail(workflow_id,index,name,f'Unabled to handle {name} due to exception: {ex}')
