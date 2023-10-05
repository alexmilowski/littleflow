import sys
import importlib.resources

from flask import Flask, request, jsonify, current_app, g, render_template, send_from_directory
import requests

import littleflow
import littleflow_redis.console

with importlib.resources.as_file(importlib.resources.files(sys.modules['littleflow_redis.console']).joinpath('templates')) as path:
   templates_dir = str(path)
with importlib.resources.as_file(importlib.resources.files(sys.modules['littleflow_redis.console']).joinpath('assets')) as path:
   assets_dir = str(path)

class Config:
   API = 'http://localhost:5000/'

service = Flask('console',template_folder=templates_dir)
service.config.from_object(Config())

def version_info():
   info = {
      'littleflow' : 'v' + '.'.join(map(str,littleflow.__version__)),
      'littleflow_redis' : 'v' + '.'.join(map(str,littleflow_redis.__version__)),
   }
   return info

@service.route('/')
def index():
   return render_template('index.html',version=version_info())

@service.route('/version')
def version():
   return jsonify(version_info())

@service.route('/workflow')
def workflow():
   return render_template('workflow.html',version=version_info())

@service.route('/assets/<path:path>')
def assets(path):
   return send_from_directory(assets_dir, path)

@service.route('/service/<path:path>',methods=['GET','DELETE','POST'])
def device_status_proxy(path):
   url = current_app.config['API']
   url += path
   first_arg = True
   for name, value in request.args.items():
      if first_arg:
         url += '?'
      else:
         url += '&'
      first_arg = False
      url += name
      url += '='
      # TODOL: encode value
      url += value
   if request.method=='GET':
      response = requests.get(url)
   elif request.method=='DELETE':
      response = requests.delete(url)
   elif request.method=='POST':
      headers = {'Content-Type':request.headers['Content-Type']}
      if 'Content-Length' in request.headers:
         headers['Content-Legth'] = request.headers['Content-Length']
      if len(request.files)>0:
         files = {}
         for key in request.files:
            files[key] = request.files[key].read()
         for key, value in request.form:
            files[key] = value
         response = requests.post(url,files=files)
      else:
         response = requests.post(url,data=request.data,headers=headers)
   headers = {}
   if 'Content-Type' in response.headers:
      headers['Content-Type'] = response.headers['Content-Type']
   if 'Content-Disposition' in response.headers:
      headers['Content-Disposition'] = response.headers['Content-Disposition']
   return response.text, response.status_code, headers
