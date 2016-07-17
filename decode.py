#!/usr/bin/env python

import time
import sys
import os
from collections import deque
from mitmproxy.script import concurrent
from mitmproxy.models import decoded

import site
site.addsitedir("/usr/local/Cellar/protobuf/3.0.0-beta-3/libexec/lib/python2.7/site-packages")
sys.path.append("/usr/local/lib/python2.7/site-packages")
sys.path.append("/usr/local/Cellar/protobuf/3.0.0-beta-3/libexec/lib/python2.7/site-packages")

from protocol.bridge_pb2 import *
from protocol.clientrpc_pb2 import *
from protocol.gymbattlev2_pb2 import *
from protocol.holoholo_shared_pb2 import *
from protocol.platform_actions_pb2 import *
from protocol.remaining_pb2 import *
from protocol.rpc_pb2 import *
from protocol.settings_pb2 import *
from protocol.sfida_pb2 import *
from protocol.signals_pb2 import *
from get_map_objects_handler import GetMapObjectsHandler

import flask
from flask import Flask, request

#We can often look up the right deserialization structure based on the method, but there are some deviations
mismatched_apis = {
  'RECYCLE_INVENTORY_ITEM': 'RECYCLE_ITEM',
  'USE_INCENSE': 'USE_INCENSE_ACTION',
  'GET_PLAYER_PROFILE': 'PLAYER_PROFILE',
  #'SFIDA_ACTION_LOG': This one is mismatches, but so bad that it had to be fixed in the protobuf
  'GET_ASSET_DIGEST': 'ASSET_DIGEST_REQUEST',
  'DOWNLOAD_REMOTE_CONFIG_VERSION': 'GET_REMOTE_CONFIG_VERSIONS',
}

#http://stackoverflow.com/questions/28867596/deserialize-protobuf-in-python-from-class-name
def deserialize(message, typ):
  import importlib
  module_name, class_name = typ.rsplit(".", 1)
  #module = importlib.import_module(module_name)
  MyClass = globals()[class_name]
  instance = MyClass()
  instance.ParseFromString(message)
  return instance

def underscore_to_camelcase(value):
  def camelcase():
    while True:
      yield str.capitalize

  c = camelcase()
  return "".join(c.next()(x) if x else '_' for x in value.split("_"))


app = Flask("events", static_folder='ui')
app.config['SECRET_KEY'] = 'amanaplanacanalplama'
app.debug = True

@app.route('/')
def index():
  return app.send_static_file('index.html')

@app.route('/pgo.pac')
def pac():
  return app.send_static_file('pgo.pac')

#Its possible I didn't need to make these explicit, but its late and I'm tired
@app.route('/css/<path:filename>')
def css(filename):
  return flask.send_from_directory(os.path.join('ui', 'css'), filename)

@app.route('/js/<path:filename>')
def js(filename):
  return flask.send_from_directory(os.path.join('ui', 'js'), filename)

@app.route('/player.json')
def player():
  return getMapObjects.player()

@app.route('/get_map_objects.json')
def get_map_objects():
  return getMapObjects.get_map_objects()

def start(context, argv):
  context.app_registry.add(app, "events", 80)
  context.methods_for_request = {}
  context.filter_methods = argv[1:]
  print("Filter methods: %s; Empty is no filtering" % context.filter_methods)

getMapObjects = GetMapObjectsHandler()

@concurrent
def request(context, flow):
  if not flow.match("~u plfe"):
    return
  try:
    env = RpcRequestEnvelopeProto()
    env.ParseFromString(flow.request.content)
  except Exception, e:
    print("Deserializating Envelop exception: %s" % e)
    return

  context.methods_for_request[env.request_id] = deque([])
  for parameter in env.parameter:
    key = parameter.key
    value = parameter.value
    context.methods_for_request[env.request_id].append(key)
    name = Method.Name(key)
    if (len(context.filter_methods) > 0 and name not in context.filter_methods):
      continue

    name = mismatched_apis.get(name, name) #return class name when not the same as method
    klass = underscore_to_camelcase(name) + "Proto"
    try:
      mor = deserialize(value, "." + klass)
      print("Deserialized Request %i: %s" % (env.request_id, name))
    except:
      print("Missing Request API: %s" % name)

    if (key == GET_MAP_OBJECTS):
      getMapObjects.request(mor, env)

def response(context, flow):
  if not flow.match("~u plfe"):
    return
  with decoded(flow.response):
    try:
      env = RpcResponseEnvelopeProto()
      env.ParseFromString(flow.response.content)
    except Exception, e:
      print("Deserializating Envelop exception: %s" % e)
      return

    keys = context.methods_for_request.pop(env.response_id)
    for value in env.returns:
      key = keys.popleft()
      name = Method.Name(key)
      if (len(context.filter_methods) > 0 and name not in context.filter_methods):
        continue

      name = mismatched_apis.get(name, name) #return class name when not the same as method
      klass = underscore_to_camelcase(name) + "OutProto"

      try:
        mor = deserialize(value, "." + klass)
        print("Deserialized Response %i: %s" % (env.response_id, name))
      except:
        print("Missing Response API: %s" % name)

      if (key == GET_MAP_OBJECTS):
        getMapObjects.response(mor, env)

# vim: set tabstop=2 shiftwidth=2 expandtab : #
