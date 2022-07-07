import json
from littleflow import InputCache

class RedisInputCache(InputCache):
   def __init__(self,client,prefix):
      self._client = client
      self._prefix = prefix

   def append_input_for(self,source,target,value):
      if value is None or (type(value)==dict and len(value)==0):
         return
      key = f'{self._prefix}:input:{target}'

      # retrieve current value
      current = self._client.get(key)

      # if there is no current value, set to the value
      if current is None:
         assert type(value)==dict, "Non-dictionary value set as input"
         self._client.set(key,json.dumps(value))
      else:
         # if there is a current value, decode
         current = json.loads(current.decode('UTF-8'))

         # if a dictionary, convert to a list
         if type(current)==dict:
            current = [current,value]
         else:
            # otherwise, we should have a list
            assert type(current)==list, 'Non-array value retrieved from Redis'
            current.append(value)

         # commit new value
         self._client.set(key,json.dumps(current))

   def input_for(self,index):
      key = f'{self._prefix}:input:{index}'
      current = self._client.get(key)

      # No value means empty
      if current is None:
         return {}

      # decode valeu
      value = json.loads(current.decode('UTF-8'))

      # delete key for consumption of value
      self._client.delete(key)

      return value
