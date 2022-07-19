import sys
import os

from .service import Config, service

__configured__ = None
if 'SERVICE_CONFIG' in os.environ and __configured__ is None:
   config_value = os.environ['SERVICE_CONFIG']
   print(f'Loading configuration from: {config_value}')
   modulename, _, classname = os.environ['SERVICE_CONFIG'].rpartition('.')
   print(f'\tmodule: {modulename}')
   print(f'\t class: {classname}')


   try:
      m = __import__(modulename)
      if not hasattr(m,classname):
         print(f'Module {modulename} does not have a class named {classname}',file=sys.stderr)
         sys.exit(1)
      config = getattr(m,classname)()
      service.config.from_object(config)
      __configured__ = {
         'module' : modulename,
         'class' : classname,
         'instance' : config
      }
   except ModuleNotFoundError as ex:
      print(f'Cannot load module {modulename}',file=sys.stderr)
      sys.exit(1)
