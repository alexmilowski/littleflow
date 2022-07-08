import sys

from .service import service

if __name__=='__main__':

   if len(sys.argv)>1:
      host, sep, port = sys.argv[1].partition(':')
      if len(sep)==0:
         port = 8000
      else:
         port = int(port)
   else:
      host = '0.0.0.0'
      port = 8000
   service.run(host=host,port=port)
