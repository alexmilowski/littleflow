import json
import os

import redis

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
      if not isinstance(value,dict) and not isinstance(value,list):
         raise ValueError(f'Incompatible type {type(value)}')
      key = f'{self._prefix}:output:{index}'
      self._client.set(key,json.dumps(value))

class MetadataService:

   def getService(host=None,port=None,username=None,password=None,prefix=None,environ='global'):
      connection_host = host if host is not None else os.environ.get('REDIS_HOST','0.0.0.0')
      connection_port = int(port if port is not None else os.environ.get('REDIS_PORT',6379))
      connection_username = username if username is not None else os.environ.get('REDIS_USERNAME')
      connection_password = password if password is not None else os.environ.get('REDIS_PASSWORD')
      pool = redis.ConnectionPool(host=connection_host,port=connection_port,username=connection_username,password=connection_password)
      return MetadataService(pool,prefix=prefix,environ=environ)

   def __init__(self,pool,prefix=None,environ='global'):
      self._pool = pool
      self._prefix = prefix
      self._environ = environ
      if self._environ is None:
         self._environ = 'global'

   @property
   def environ(self):
      return self._environ

   @property
   def pool(self):
      return self._pool

   @property
   def prefix(self):
      prefix = self._prefix
      if prefix is None:
         prefix = self.connection.get('littleflow:config:env-prefix')
      return prefix if prefix is not None else ''

   @property
   def connection(self):
      return redis.Redis(connection_pool=self.pool)

   def get(self,name,environ=None,default=None):
      key = f'{self.prefix}env:{self._environ if environ is None else environ}:{name}'
      value = self.connection.get(key)
      if value is None:
         return default
      else:
         return value.decode('utf-8')

   def __getitem__(self,name):
      key = f'{self.prefix}env:{self._environ}:{name}'
      value = self.connection.get(key)
      return value.decode('utf-8') if value is not None else None
