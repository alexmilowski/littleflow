import threading
import signal

import click

from littleflow_k8s import BatchStart

@click.group()
def cli():
   pass

def start_trackers(stream,count):
   def do_stop():
      pass
   return do_stop, None

@cli.command('track')
@click.option('--stream',help='The event stream to use',default='workflows:run')
@click.option('--trackers',help='The number of trackers',default=1,type=int)
def track(stream,trackers):
   stop, waiter = start_trackers(stream,trackers)

   running = True
   interrupt_count = 0
   def interrupt_handler(signum,frame):
      nonlocal interrupt_count
      nonlocal running
      running = False
      interrupt_count += 1
      if interrupt_count>1:
         print('Okay then, attempting exit!')
         sys.exit(1)

      stop()

      print(f'Received interrupt, shutting down',flush=True)

   signal.signal(signal.SIGINT, interrupt_handler)

   while running:
      waiter.join(10)

@cli.command('worker')
@click.option('--stream',help='The event stream to use',default='workflows:run')
@click.option('--group',help='The consume group',default='starting-batch')
@click.option('--listeners',help='The number of listeners',default=1,type=int)
@click.option('--trackers',help='The number of trackers',default=1,type=int)
def worker(stream,group,listeners,trackers):

   if listeners<1 and trackers<1:
      return

   workers = []
   worker_threads = []

   tracker_stop = None
   if trackers>0:
      tracker_stop, waiter = start_trackers(stream,trackers)
      if waiter is not None:
         worker_thread.append(waiter)

   if listeners>0:

      for _ in range(listeners):
         worker = BatchStart(stream,group)
         workers.append(worker)
         worker_threads.append(threading.Thread(target=lambda : worker.listen()))
         worker_threads[-1].start()

   interrupt_count = 0
   running = True
   def interrupt_handler(signum,frame):
      nonlocal interrupt_count
      nonlocal running
      running = False
      interrupt_count += 1
      if interrupt_count>1:
         print('Okay then, attempting exit!')
         sys.exit(1)

      for worker in workers:
         worker.stop()

      if tracker_stop is not None:
         tracker_stop()

      print(f'Received interrupt, shutting down.',flush=True)

   signal.signal(signal.SIGINT, interrupt_handler)

   while running:
      worker_threads[0].join(10)

   for thread in threading.enumerate():
      if thread!=threading.main_thread():
         print(thread.ident,thread.name)

if __name__=='__main__':
   cli()
