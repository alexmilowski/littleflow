from .flow import Source, Sink, InvokeTask, InvokeFlow

def mangle(name):
   return name.replace(':','_COLON_').replace('-','_HYPHEN_')
def graph_name(obj,end=-1):
   if isinstance(obj,InvokeTask):
      return f'{mangle(obj.name)}.{obj.index}'
   elif isinstance(obj,Source):
      return '[*]'
   elif isinstance(obj,Sink):
      return '[*]' if obj.index==end else f'_end_{obj.index}_'
   elif isinstance(obj,InvokeFlow):
      return f'_start_{obj.index}_'
   else:
      return None

def shortdesc(doc):
   oneliner, _, rest = doc.strip().partition('\n')
   return oneliner

def graph(flow,output,format='mermaid',name='workflow',embed_docs=True,left_to_right=True):
   assert format=='mermaid', 'Only mermaid is currently supported'
   print(f'stateDiagram-v2',file=output)
   if left_to_right:
      print('  direction LR',file=output)
   size = len(flow)
   for index in range(size):
      invocation = flow[index]
      name = graph_name(invocation,end=size-1)
      if isinstance(invocation,InvokeFlow):
         print(f'  state {name} <<fork>>',file=output)
      elif isinstance(invocation,Sink) and index!=(size-1):
         print(f'  state {name} <<join>>',file=output)
      elif isinstance(invocation,InvokeTask):
         print(f'  state "{invocation.name}" as {name}',file=output)

   for index,row in enumerate(flow.F):
      source = flow[index]
      source_name = graph_name(source,end=size-1)
      for target_index, value in enumerate(row.flatten()):
         if value==0:
            continue
         target = flow[target_index]
         #print(source,target)
         target_name = graph_name(target,end=size-1)
         print(f'  {source_name}-->{target_name}',file=output)
         if  embed_docs and isinstance(target,InvokeTask) and target.doc is not None:
            print(f'  note left of {target.name}',file=output)
            print(f'    {shortdesc(target.doc)}',file=output)
            print(f'  end note',file=output)
