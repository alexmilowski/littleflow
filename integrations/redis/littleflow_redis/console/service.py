import sys
import importlib.resources

from flask import Flask, request, jsonify, current_app, g, render_template, send_from_directory
import requests

import littleflow_redis.console

assets_dir = str(importlib.resources.path(sys.modules['littleflow_redis.console'],'assets'))
templates_dir = str(importlib.resources.path(sys.modules['littleflow_redis.console'],'templates'))

class Config:
   API = 'http://localhost:5000/'

service = Flask('console',template_folder=templates_dir)
service.config.from_object(Config())

@service.route('/')
def index():
   return render_template('index.html')

@service.route('/assets/<path:path>')
def assets(path):
   return send_from_directory(assets_dir, path)

@service.route('/service/<path:path>',methods=['GET','DELETE','POST'])
def device_status_proxy(path):
   url = current_app.config['API']
   url += path
   if request.method=='GET':
      response = requests.get(url)
   elif request.method=='DELETE':
      response = requests.delete(url)
   elif request.method=='POST':
      response = requests.post(url,data=request.json,headers={'Content-Type':request.headers['Content-Type']})
   headers = {}
   if 'Content-Type' in response.headers:
      headers['Content-Type'] = response.headers['Content-Type']
   return response.text, response.status_code, headers
