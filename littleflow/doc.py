from .flow import Source, Sink, InvokeTask, InvokeFlow

def graph_name(obj,end=-1):
   if isinstance(obj,InvokeTask):
      return obj.name
   elif isinstance(obj,Source):
      return '[*]'
   elif isinstance(obj,Sink):
      return '[*]' if obj.index==end else f'_end_{obj.index}_'
   elif isinstance(obj,InvokeFlow):
      return f'_start_{obj.index}_'
   else:
      return None

def graph(flow,output,format='mermaid',name='workflow'):
   assert format=='mermaid', 'Only mermaid is currently supported'
   print(f'stateDiagram-v2',file=output)
   size = len(flow)
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
