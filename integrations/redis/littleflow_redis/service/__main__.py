import sys

from .service import service

def main():
   if len(sys.argv)>1:
      host, sep, port = sys.argv[1].partition(':')
      if len(sep)==0:
         port = 5000
      else:
         port = int(port)
   else:
      host = '0.0.0.0'
      port = 5000
   service.run(host=host,port=port)

if __name__=='__main__':
   main()
