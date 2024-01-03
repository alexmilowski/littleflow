import os
import io
import json
from uuid import uuid4
from enum import EnumMeta
from typing import Union, Type
from inspect import isclass
from copy import deepcopy
import builtins
import importlib
import logging

from flask import Flask, request, jsonify, current_app, g, render_template_string
import yaml
import redis
import boto3
from botocore.exceptions import ClientError

# only needed for restarting
from rqse import EventClient

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin

from pydantic import BaseModel

from littleflow_redis import load_workflow, compute_vector, trace_vector, workflow_state, delete_workflow, terminate_workflow, workflow_archive, restart_workflow, restore_workflow, run_workflow, get_failures, RedisOutputCache
from littleflow import graph

from .message import StatusResponse, StatusCode, ServiceJSONProvider, VersionInfo, WorkflowId, ArchiveLocation, Location, WorkflowStart

def version_info():
   from littleflow import __version__ as lf_version
   from littleflow_redis import __version__ as redis_version
   return 'v' + '.'.join(map(str,lf_version)),'v' + '.'.join(map(str,redis_version))

_old_prefix = '#/definitions'
def schema_fixup(item : dict):
   item = deepcopy(item)
   queue = [item]
   while len(queue)>0:
      current = queue.pop(0)
      for value in current.values():
         match type(value):
            case builtins.dict:
               queue.append(value)
            case builtins.list:
               for array_item in value:
                  if type(array_item)==dict:
                     queue.append(array_item)
      if '$ref' in current:
         value = current['$ref']
         if value.startswith(_old_prefix):
            current['$ref'] = '#/components/schemas'+value[len(_old_prefix):]
   return item

def enum_schema(e : EnumMeta):
   return {
      "type" : "string",
      "enum" : [item.value for item in list(e)]
   }

api_version = version_info()
spec = APISpec(
   title="littleflow",
   version=f'{api_version[1]} ({api_version[0]})',
   openapi_version='3.0.2',
   info={'descrition' : 'Littleflow service API'},
   plugins=[FlaskPlugin()]
)

def add_type(name : str,schema : Union[dict,EnumMeta,Type[BaseModel]]):
   if isclass(schema):
      if isinstance(schema,EnumMeta):
         schema = enum_schema(schema)
      elif issubclass(schema,BaseModel):
         schema = schema.schema()
   spec.components.schema(name,schema_fixup(schema))

for name, class_type in [(cls.__name__,cls) for cls in [
   StatusResponse,
   VersionInfo,
   WorkflowId,
   ArchiveLocation,
   Location,
   WorkflowStart
]]:
   add_type(name, class_type)

class Config:
   WORKFLOWS_STREAM = 'workflows:run'
   WORKFLOWS_KEY = 'workflows:all'
   INPROGRESS_KEY = 'workflows:inprogress'

service = Flask('api')
service.config.from_object(Config())
service.json = ServiceJSONProvider(service)


def get_pool():
   if 'pool' not in g:
      service_spec = current_app.config.get('REDIS_SERVICE')
      if service_spec is None:
         host = os.environ.get('REDIS_HOST','0.0.0.0')
         port = int(os.environ.get('REDIS_PORT',6379))
      else:
         host, _, port = service_spec.partition(':')
         if len(port)==0:
            port = 6379
         else:
            port = int(port)
      auth_spec = current_app.config.get('REDIS_AUTH')
      if auth_spec is None:
         username = os.environ.get('REDIS_USERNAME')
         password = os.environ.get('REDIS_PASSWORD')
      else:
         username, _, password = auth_spec.partition(':')
         if len(password)==0:
            password = username
            username = 'default'

      g.pool = redis.ConnectionPool(host=host,port=port,username=username,password=password)
   return g.pool

def get_redis():

   if 'redis' not in g:
      g.redis = redis.Redis(connection_pool=get_pool())

   return g.redis

def get_event_client():
   if 'event_client' not in g:
      g.event_client = EventClient(current_app.config['WORKFLOWS_STREAM'],pool=get_pool())
   return g.event_client

# def message_response(status,message=None,data=None):
#    return 
#    msg = data.copy() if data is not None else {}
#    msg['status'] = status
#    if message is not None:
#       msg['message'] = message
#    return msg

def success(message=None,workflow=None,uri=None):
   return StatusResponse(status=StatusCode.Success,message=message,workflow=workflow,uri=uri)

def error(message=None):
   return StatusResponse(status=StatusCode.Error,message=message)

def unavailable(message=None):
   return StatusResponse(status=StatusCode.Unavailable,message=message)

@service.route('/apispec.json')
def apispec():
   openapi = spec.to_dict()
   return jsonify(openapi)

@service.route('/apidocs/')
def apidocs():
   import littleflow_redis as source_module
   with importlib.resources.as_file(importlib.resources.files(source_module).joinpath(f'service/elements.html')) as path:
      with open(path,'r') as raw:
         template = raw.read()
   return render_template_string(template,url='../apispec.json')

@service.route('/',methods=['GET'])
def index():
   """
   ---
   get:
      description: |-
         Returns the service version information
      responses:
         200:
            description: The version information
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/VersionInfo'
   """
   return jsonify(VersionInfo(littleflow=api_version[0],littleflow_redis=api_version[1]))

@service.route('/workflows',methods=['GET'])
def workflows():
   """
   ---
   get:
      description: |-
         Returns a list all the cached workflows
      responses:
         200:
            description: A list of workflow
            content:
               'application/json':
                  schema:
                     type: array
                     items:
                        type: string
   """
   client = get_redis()
   start = int(request.args.get('next',0))
   size = int(request.args.get('size',50))
   items = client.lrange(current_app.config['WORKFLOWS_KEY'],start,start+size-1)
   convert = lambda x : {'id':x[9:],'state':workflow_state(client,x,default='UNKNOWN')}
   workflows = [convert(value.decode('UTF-8')) for value in items]
   response =jsonify(workflows)
   if len(items)==size:
      response.headers['Link'] = f'<{request.base_url}?next={start+size}>; rel="next"'
   return response

@service.route('/inprogress',methods=['GET'])
def inprogress():
   """
   ---
   get:
      description: |-
         Returns a list of currently cached workflows that are in progress
      responses:
         200:
            description: A list of workflow ids
            content:
               'application/json':
                  schema:
                     type: array
                     items:
                        type: string
   """
   client = get_redis()
   items = client.smembers(current_app.config['INPROGRESS_KEY'])
   workflows = [value.decode('UTF-8')[9:] for value in items]
   return jsonify(workflows)

@service.route('/workflows/<workflow_id>',methods=['GET','DELETE'])
def get_workflow(workflow_id):
   """Returns a workflow
   ---
   get:
      description: |-
         Returns a specific workflow
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: A list of workflow ids
            content:
               'application/json':
                  schema:
                     type: object
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   delete:
      description: |-
         Deletes a workflow
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: A status response
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   if request.method=='DELETE':
      if client.sismember(current_app.config['INPROGRESS_KEY'],key)>0:
         return jsonify(error(f'Workflow {workflow_id} is running and cannot be deleted.')), 400
      delete_workflow(client,key,workflows_key=current_app.config['WORKFLOWS_KEY'])
      return jsonify(success(f'Workflow {workflow_id} has been deleted'))

   flow, repl = load_workflow(client,key,return_json=True)
   return jsonify(repl)

@service.route('/workflows/<workflow_id>/terminate',methods=['POST'])
def terminate(workflow_id):
   """
   ---
   post:
      description: |-
         Terminates a running workflow
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: The workflow is terminating or terminated.
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   event_client = get_event_client()
   key = 'workflow:'+workflow_id
   if event_client.connection.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   terminated = terminate_workflow(event_client,key,workflow_id,inprogress_key=current_app.config['INPROGRESS_KEY'])
   return jsonify(success(f'Workflow {workflow_id} is {"terminated" if terminated else "terminating"}'))

@service.route('/workflows/terminate',methods=['POST'])
def terminate_request():
   """
   ---
   post:
      description: |-
         Terminates a running workflow
      requestBody:
         content:
            "application/json":
               schema:
                  $ref: '#/components/schemas/WorkflowId'
      responses:
         200:
            description: The workflow is terminating or terminated.
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   workflow_id = request.json.get('workflow')
   return terminate(workflow_id)

@service.route('/workflows/<workflow_id>/state',methods=['GET'])
def get_workflow_state(workflow_id):
   """Returns a workflow state
   ---
   get:
      description: |-
         Returns the workflow state
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: The workflow state
            content:
               'application/json':
                  schema:
                     type: object
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404

   state = workflow_state(client,key)
   if state is None:
      state = 'UKNOWN'
   S = compute_vector(client,key+':S')
   A = compute_vector(client,key+':A')
   failures = get_failures(client,key)
   data = {'state':state, 'S':S.flatten().tolist() if S is not None else [], 'A': A.flatten().tolist() if A is not None else []}
   if failures is not None:
      data['failures'] = failures.flatten().tolist()
   cache = RedisOutputCache(client,key)
   data['output'] = [cache.get(index,{}) for index in range(len(S))]

   return jsonify(data)

@service.route('/workflows/<workflow_id>/trace/<kind>',methods=['GET'])
def get_workflow_trace(workflow_id,kind):
   """Returns a workflow trace
   ---
   get:
      description: |-
         Returns the workflow trace
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
       - name: kind
         in: path
         schema:
            type: string
            enum:
            - S
            - A
         description: The kind must be 'S' (state) or 'A' (activation)
      responses:
         200:
            description: A trace array
            content:
               'application/json':
                  schema:
                     type: array
                     items:
                        type: array
                        items: string
         400:
            description: A bad trace kind was specified
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if kind not in ['A','S']:
      return jsonify(error(f'Unrecognized trace {kind}')), 400
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   response = []
   for tstamp, value in trace_vector(client,key+':'+kind):
      response.append([tstamp.isoformat(),value.flatten().tolist()])
   return jsonify(response)

@service.route('/workflows/<workflow_id>/graph',methods=['GET'])
def get_workflow_graph(workflow_id):
   """
   ---
   get:
      description: |-
         Returns the workflow graphs as a mermaid diagram
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
       - name: orientation
         in: query
         schema:
            type: string
            enum:
            - horizontal
            - vertical
         description: The graph orientation
      responses:
         200:
            description: A trace array
            content:
               'text/plain':
                  schema:
                     type: string
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   left_to_right = True
   if request.args.get('orientation','horizontal')=='vertical':
      left_to_right = False
   flow = load_workflow(client,key)
   output = io.StringIO()
   graph(flow,output,embed_docs=False,left_to_right=left_to_right)
   return output.getvalue(), 200, {'Content-Type':'text/plain; charset=UTF-8'}

@service.route('/workflows/<workflow_id>/archive',methods=['GET','POST'])
def archive_workflow(workflow_id):
   """
   get:
      description: |-
         Returns the workflow archive representation of the current state
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: A workflow archive
            content:
               'application/json':
                  schema:
                     type: object
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   post:
      description: |-
         Stores the workflow archive representation of the current state into object storage
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      requestBody:
         content:
            "application/json":
               schema:
                  $ref: '#/components/schemas/ArchiveLocation'
      responses:
         200:
            description: Indicates the achive was stored
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   object = workflow_archive(client,key)

   if request.method=='GET':
      return jsonify(object), {'Content-Disposition': f'attachment; filename={workflow_id}.json;'}

   data =  request.json
   bucket = data.get('bucket')
   uri = data.get('uri')
   if uri is not None:
      if not uri.startswith('s3://'):
         return jsonify(error('Malformed s3 uri: '+uri)), 400
      uri = uri[5:]
      bucket, _, path = uri.partition('/')
      if len(path)==0:
         path = workflow_id + '.json'
   elif bucket is None:
      return jsonify(error('The uri or bucket must be specified.')), 400
   else:
      path = workflow_id + '.json'

   repl = json.dumps(object)
   try:
      s3 = boto3.client('s3')
      s3.put_object(Bucket=bucket,Key=path,Body=repl.encode('UTF-8'))

      result_uri = f's3://{bucket}/{path}'

      response = jsonify(success('Archive created',uri=result_uri))
      response.headers['Location'] = result_uri
      return response
   except ClientError as ex:
      return jsonify(error('Error accessing bucket: '+str(ex))), 400

@service.route('/workflows/<workflow_id>/restart',methods=['GET'])
def service_restart_workflow(workflow_id):
   """
   get:
      description: |-
         Restarts a workflow
      parameters:
       - name: workflow_id
         in: path
         schema:
            type: string
         description: The workflow identifier assigned when the workflow instance was created
      responses:
         200:
            description: Indicates success
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         400:
            description: The workflow failed to restart
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         404:
            description: The workflow does not exist
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return jsonify(error(f'Workflow {workflow_id} does not exist')), 404
   state = workflow_state(client,key)
   if state!='TERMINATED' and state!='FAILED':
      return jsonify(error(f'Workflow {workflow_id} cannot be restarted from current state {state}')), 400

   started = restart_workflow(get_event_client(),key,key)

   if started:
      return jsonify(success(f'Restarted workflow {workflow_id}',workflow=workflow_id))
   else:
      return jsonify(error(f'Restarting workflow {workflow_id} had no tasks to resume')), 400

@service.route('/workflows/restore',methods=['GET','POST'])
def restore_workflow_from_archive():
   """
   get:
      description: |-
         Restores a workflow from a URI
      parameters:
       - name: uri
         in: query
         schema:
            type: string
         description: The object storage URI
      responses:
         200:
            description: The workflow was restored
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         400:
            description: The workflow could not be restored
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   post:
      description: |-
         Restores a workflow from a URI
      requestBody:
         content:
            "application/json":
               schema:
                  $ref: '#/components/schemas/Location'
      responses:
         200:
            description: The workflow was restored
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         400:
            description: The workflow could not be restored
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """   
   if request.method=='GET':
      workflow_id = request.args.get('workflow')
      uri = request.args.get('uri')
      archive = None
      if uri is None:
         return jsonify(error(f'The uri parameter is missing')), 400
   elif request.method=='POST':
      workflow_id = request.args.get('workflow')
      uri = request.json.get('uri')
      archive = request.json if uri is None else None

   if workflow_id is not None:
      if client.exists('workflow:'+key)==1:
         return jsonify(error(f'Workflow {workflow_id} already exists')), 400
   else:
      workflow_id = str(uuid4())

   if uri is not None and not uri.startswith('s3://'):
      return jsonify(error(f'Only S3 URIs are currently supported')), 400

   if uri is not None:
      try:
         bucket, _, path = uri[5:].partition('/')
         s3 = boto3.client('s3')
         obj = s3.get_object(Bucket=bucket, Key=path)
         try:
            archive = json.loads(obj['Body'].read())
         except IOError as ex:
            return jsonify(error(f'Error reading archive: {ex}')), 400
      except ClientError as ex:
         return jsonify(error(f'Error accessing bucket: {ex}')), 400

   # quick check of archive:
   if type(archive)!=dict:
      return jsonify(error(f'Archive type is not an object: {type(dict)}')), 400

   for key in ['F','T','A','S']:
      if key not in archive:
         return jsonify(error(f'Archive is missing key {key}')), 400

   key = 'workflow:'+workflow_id

   event_client = get_event_client()

   restore_workflow(event_client.connection,key,archive,workflows_key=current_app.config['WORKFLOWS_KEY'])

   return jsonify(success(f'Workflow restored as {workflow_id}',workflow=workflow_id))

@service.route('/workflows/start',methods=['POST'])
def start_workflow_post():
   """
   post:
      description: |-
         Starts a new workflow
      requestBody:
         content:
            "application/json":
               description: A littleflow workflow and input
               schema:
                  $ref: '#/components/schemas/WorkflowStart'
            "text/plain":
               description: A littleflow workflow
               schema:
                  type: string
      responses:
         200:
            description: The workflow was started
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         400:
            description: The workflow could not be started
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   if request.mimetype=='application/json':
      data = request.json
      workflow = data.get('workflow')
      input = data.get('input')
   else:
      workflow = request.data
      input = None

   if workflow is None or len(workflow)==0:
      return jsonify(error(f'No workflow was provided')), 400

   event_client = get_event_client()
   try:
      workflow_id = run_workflow(workflow,event_client,input=input)
      return jsonify(success(f'Workflow restored as {workflow_id}',workflow=workflow_id))
   except Exception as ex:
      return jsonify(error(f'Cannot compile workflow due to: {ex}')), 400

@service.route('/workflows/start/upload',methods=['POST'])
def start_workflow_upload():
   """
   post:
      description: |-
         Starts a new workflow from a form post where `input` is a text field
         that is expected to be a JSON object and `workflow` is a file
         attachment or form text field.
      requestBody:
         content:
            "application/json":
               description: A littleflow workflow and input
               schema:
                  $ref: '#/components/schemas/WorkflowStart'
            "text/plain":
               description: A littleflow workflow
               schema:
                  type: string
      responses:
         200:
            description: The workflow was started
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
         400:
            description: The workflow could not be started
            content:
               'application/json':
                  schema:
                     $ref: '#/components/schemas/StatusResponse'
   """
   if 'workflow' in request.files:
      file = request.files['workflow']
      workflow = file.read().decode('UTF-8')
   elif 'workflow' in request.form:
      workflow = request.form.get('workflow')
   else:
      return jsonify(error('The workflow was not attached.')), 400
   input = request.form.get('input')
   if input is not None:
      input = json.loads(input)
   event_client = get_event_client()
   try:
      workflow_id = run_workflow(workflow,event_client,input=input)
      _, _, workflow_id = workflow_id.partition(':')
      return jsonify(success(f'Workflow restored as {workflow_id}',workflow=workflow_id))
   except Exception as ex:
      return jsonify(error(f'Cannot compile workflow due to: {ex}')), 400


with service.test_request_context():
   for name, view in service.view_functions.items():
      try:
         spec.path(view=view)
      except Exception as ex:
         logging.exception(ex)
         logging.error(f'Cannot load view function {name}')
