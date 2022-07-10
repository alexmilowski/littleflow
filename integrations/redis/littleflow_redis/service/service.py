import os
import io
import json
from uuid import uuid4

from flask import Flask, request, jsonify, current_app, g
from flasgger import Swagger, swag_from, validate
import yaml
import redis
import boto3
from botocore.exceptions import ClientError

# only needed for restarting
from rqse import EventClient

from littleflow_redis import load_workflow, compute_vector, trace_vector, workflow_state, delete_workflow, terminate_workflow, workflow_archive, restart_workflow, restore_workflow, run_workflow, get_failures
from littleflow import graph

class Config:
   REDIS_SERVICE = '0.0.0.0:6379'
   WORKFLOWS_STREAM = 'workflows:run'
   WORKFLOWS_KEY = 'workflows:all'
   INPROGRESS_KEY = 'workflows:inprogress'

service = Flask('api')
service.config.from_object(Config())

swag = Swagger(service)

swag_def = """
definitions:
  WorkflowList:
    type: array
    items:
       type: string
  StatusResponse:
    type: object
    properties:
       message:
          type: string
       data:
          type: object
       status:
          $ref: '#/definitions/StatusCode'
  StatusCode:
    type: string
    enum: ['Error','Success','Unavailable']
"""
defs = yaml.load(swag_def,Loader=yaml.Loader)

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

def message_response(status,message=None,data=None):
   msg = data.copy() if data is not None else {}
   msg['status'] = status
   if message is not None:
      msg['message'] = message
   return msg

def success(message=None,data=None):
   return message_response('Success',message=message,data=data)

def error(message=None,data=None):
   return message_response('Error',message=message,data=data)

def unavailable(message=None,data=None):
   return message_response('Unavailable',message=message,data=data)

@service.route('/',methods=['GET'])
@swag_from(defs)
def index():
   """Returns the service status
   ---
     consumes: []
     produces:
     - application/json
     responses:
        200:
           description: The service status.
           schema:
              $ref: '#/definitions/StatusResponse'
        default:
           description: An error
           schema:
              $ref: '#/definitions/StatusResponse'
   """
   return jsonify(success())

@service.route('/workflows',methods=['GET'])
@swag_from(defs)
def workflows():
   """Returns a list of currently cached workflows
   ---
     consumes: []
     produces:
     - application/json
     responses:
        200:
           description: The service status.
           schema:
              $ref: '#/definitions/WorkflowList'
        default:
           description: An error
           schema:
              $ref: '#/definitions/StatusResponse'
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
@swag_from(defs)
def inprogress():
   """Returns a list of currently cached workflows
   ---
     consumes: []
     produces:
     - application/json
     responses:
        200:
           description: The service status.
           schema:
              $ref: '#/definitions/WorkflowList'
        default:
           description: An error
           schema:
              $ref: '#/definitions/StatusResponse'
   """
   client = get_redis()
   items = client.smembers(current_app.config['INPROGRESS_KEY'])
   workflows = [value.decode('UTF-8')[9:] for value in items]
   return jsonify(workflows)

@service.route('/workflows/<workflow_id>',methods=['GET','DELETE'])
def get_workflow(workflow_id):
   """Returns a workflow
   ---
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   if request.method=='DELETE':
      if client.sismember(current_app.config['INPROGRESS_KEY'],key)>0:
         return jsonify(error(f'Workflow {workflow_id} is running and cannot be deleted.')), 400
      delete_workflow(client,key,workflows_key=current_app.config['WORKFLOWS_KEY'])
      return jsonify(success(f'Workflow {workflow_id} has been deleted'))

   flow, repl = load_workflow(client,key,return_json=True)
   return jsonify(repl)

@service.route('/workflows/<workflow_id>/terminate',methods=['POST'])
def terminate(workflow_id):
   event_client = get_event_client()
   key = 'workflow:'+workflow_id
   if event_client.connection.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   terminated = terminate_workflow(event_client,key,workflow_id,inprogress_key=current_app.config['INPROGRESS_KEY'])
   return jsonify(success(f'Workflow {workflow_id} is {"terminated" if terminated else "terminating"}'))

@service.route('/workflows/terminate',methods=['POST'])
def terminate_request():
   workflow_id = request.json.get('workflow')
   return terminate(workflow_id)

@service.route('/workflows/<workflow_id>/state',methods=['GET'])
def get_workflow_state(workflow_id):
   """Returns a workflow state
   ---
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404

   state = workflow_state(client,key)
   if state is None:
      state = 'UKNOWN'
   S = compute_vector(client,key+':S')
   A = compute_vector(client,key+':A')
   failures = get_failures(client,key)
   data = {'state':state, 'S':S.flatten().tolist() if S is not None else [], 'A': A.flatten().tolist() if A is not None else []}
   if failures is not None:
      data['failures'] = failures.flatten().tolist()
   return jsonify(data)

@service.route('/workflows/<workflow_id>/trace/<kind>',methods=['GET'])
def get_workflow_trace(workflow_id,kind):
   """Returns a workflow trace
   ---
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   if kind not in ['A','S']:
      return error(f'Unrecognized trace {kind}'), 400
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   response = []
   for tstamp, value in trace_vector(client,key+':'+kind):
      response.append([tstamp.isoformat(),value.flatten().tolist()])
   return jsonify(response)

@service.route('/workflows/<workflow_id>/graph',methods=['GET'])
def get_workflow_graph(workflow_id):
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   flow = load_workflow(client,key)
   output = io.StringIO()
   graph(flow,output,embed_docs=False)
   return output.getvalue(), 200, {'Content-Type':'text/plain; charset=UTF-8'}

@service.route('/workflows/<workflow_id>/archive',methods=['GET','POST'])
def archive_workflow(workflow_id):
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   object = workflow_archive(client,key)

   if request.method=='GET':
      return jsonify(object), {'Content-Disposition': f'attachment; filename={workflow_id}.json;'}

   data =  request.json
   bucket = data.get('bucket')
   uri = data.get('uri')
   if uri is not None:
      if not uri.startswith('s3://'):
         return error('Malformed s3 uri: '+uri), 400
      uri = uri[5:]
      bucket, _, path = uri.partition('/')
      if len(path)==0:
         path = workflow_id + '.json'
   elif bucket is None:
      return error('The uri or bucket must be specified.'), 400
   else:
      path = workflow_id + '.json'

   repl = json.dumps(object)
   try:
      s3 = boto3.client('s3')
      s3.put_object(Bucket=bucket,Key=path,Body=repl.encode('UTF-8'))

      result_uri = f's3://{bucket}/{path}'

      response = jsonify(success('Archive created',{'uri':result_uri}))
      response.headers['Location'] = result_uri
      return response
   except ClientError as ex:
      return error('Error accessing bucket: '+str(ex)), 400

@service.route('/workflows/<workflow_id>/restart',methods=['GET'])
def service_restart_workflow(workflow_id):
   client = get_redis()
   key = 'workflow:'+workflow_id
   if client.exists(key)==0:
      return error(f'Workflow {workflow_id} does not exist'), 404
   state = workflow_state(client,key)
   if state!='TERMINATED' and state!='FAILED':
      return error(f'Workflow {workflow_id} cannot be restarted from current state {state}'), 400

   started = restart_workflow(get_event_client(),key,key)

   if started:
      return success(f'Restarted workflow {workflow_id}')
   else:
      return error(f'Restarting workflow {workflow_id} had no tasks to resume'), 400

@service.route('/workflows/restore',methods=['GET','POST'])
def restore_workflow_from_archive():
   if request.method=='GET':
      workflow_id = request.args.get('workflow')
      uri = request.args.get('uri')
      archive = None
      if uri is None:
         return error(f'The uri parameter is missing'), 400
   elif request.method=='POST':
      workflow_id = request.args.get('workflow')
      uri = request.json.get('uri')
      archive = request.json if uri is None else None

   if workflow_id is not None:
      if client.exists('workflow:'+key)==1:
         return error(f'Workflow {workflow_id} already exists'), 400
   else:
      workflow_id = str(uuid4())

   if uri is not None and not uri.startswith('s3://'):
      return error(f'Only S3 URIs are currently supported'), 400

   if uri is not None:
      try:
         bucket, _, path = uri[5:].partition('/')
         s3 = boto3.client('s3')
         obj = s3.get_object(Bucket=bucket, Key=path)
         try:
            archive = json.loads(obj['Body'].read())
         except IOError as ex:
            return error(f'Error reading archive: {ex}'), 400
      except ClientError as ex:
         return error(f'Error accessing bucket: {ex}'), 400

   # quick check of archive:
   if type(archive)!=dict:
      return error(f'Archive type is not an object: {type(dict)}'), 400

   for key in ['F','T','A','S']:
      if key not in archive:
         return error(f'Archive is missing key {key}'), 400

   key = 'workflow:'+workflow_id

   event_client = get_event_client()

   restore_workflow(event_client.connection,key,archive,workflows_key=current_app.config['WORKFLOWS_KEY'])

   return success(f'Workflow restored as {workflow_id}',{'workflow':workflow_id})

@service.route('/workflows/start',methods=['POST'])
def start_workflow_post():
   workflow = request.data
   event_client = get_event_client()
   workflow_id = run_workflow(workflow,event_client)
   return success(f'Workflow restored as {workflow_id}',{'workflow':workflow_id})

@service.route('/workflows/start/upload',methods=['POST'])
def start_workflow_upload():
   print(request.files);
   if 'workflow' not in request.files:
      return error('The workflow was not attached.'), 400
   file = request.files['workflow']
   workflow = file.read().decode('UTF-8')
   event_client = get_event_client()
   workflow_id = run_workflow(workflow,event_client)
   _, _, workflow_id = workflow_id.partition(':')
   return success(f'Workflow restored as {workflow_id}',{'workflow':workflow_id})
