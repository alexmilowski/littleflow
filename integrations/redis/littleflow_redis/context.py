import json

class RedisOutputCache:

   def __init__(self,client,prefix):
      self._client = client
      self._prefix = prefix

   def get(self,index,default=None):
      key = f'{self._prefix}:output:{index}'

      # retrieve current value
      value = self._client.get(key)

      if value is None:
         return default

      # if there is a current value, decode
      value = json.loads(value.decode('UTF-8'))

      return value

   def __getitem__(self,index):
      value = self.get(value)
      if value is None:
         raise KeyError(index)
      return value

   def __setitem__(self,index,value):
      if type(value)!=dict and type(value)!=list:
         raise ValueError(f'Incompatible type {type(value)}')
      key = f'{self._prefix}:output:{index}'
      self._client.set(key,json.dumps(value))
