import os

from flask import Flask, request, jsonify, current_app, g
from flasgger import Swagger, swag_from, validate
import yaml
import redis

from littleflow_redis import restore_workflow, compute_vector, trace_vector, workflow_state

class Config:
   REDIS_SERVICE = '0.0.0.0:6379'
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

def get_redis():
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

   if 'redis' not in g:
      g.redis = redis.Redis(connection_pool=g.pool)

   return g.redis

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
   workflows = [value.decode('UTF-8')[9:] for value in items]
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

@service.route('/workflows/<workflow_id>',methods=['GET'])
def get_workflow(workflow_id):
   """Returns a workflow
   ---
   """
   client = get_redis()
   key = 'workflow:'+workflow_id
   flow, repl = restore_workflow(client,key,return_json=True)
   return jsonify(repl)

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
   return jsonify({'state':state, 'S':S.flatten().tolist(), 'A': A.flatten().tolist()})

@service.route('/workflows/<workflow_id>/trace/<kind>',methods=['GET'])
def get_workflow_trace(workflow_id,kind):
   """Returns a workflow trace
   ---
   """
   client = get_redis()
   if kind not in ['A','S']:
      return error(f'Unrecognized trace {kind}'), 400
   key = 'workflow:'+workflow_id
   response = []
   for tstamp, value in trace_vector(client,key+':'+kind):
      response.append([tstamp,value.flatten().tolist()])
   return jsonify(response)
