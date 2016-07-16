#!/usr/bin/env python

import time
import sys
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

getMapObjects = GetMapObjectsHandler()

methods_for_request = {}

@concurrent
def request(context, flow):
  if flow.match("~d pgorelease.nianticlabs.com"):
    env = RpcRequestEnvelopeProto()
    env.ParseFromString(flow.request.content)

    methods_for_request[env.request_id] = deque([])
    for parameter in env.parameter:
      key = parameter.key
      value = parameter.value
      methods_for_request[env.request_id].append(key)

      name = Method.Name(key)
      name = mismatched_apis.get(name, name) #return class name when not the same as method
      klass = underscore_to_camelcase(name) + "Proto"
      try:
        mor = deserialize(value, "." + klass)
        print("Deserialized Request %s" % name)
      except:
        print("Missing Request API: %s" % name)

      if (key == GET_MAP_OBJECTS):
        getMapObjects.request(mor, env)

def response(context, flow):
  with decoded(flow.response):
    if flow.match("~d pgorelease.nianticlabs.com"):
      env = RpcResponseEnvelopeProto()
      env.ParseFromString(flow.response.content)

      keys = methods_for_request[env.response_id]
      for value in env.returns:
        key = keys.popleft()

        name = Method.Name(key)
        name = mismatched_apis.get(name, name) #return class name when not the same as method
        klass = underscore_to_camelcase(name) + "OutProto"

        try:
          mor = deserialize(value, "." + klass)
          print("Deserialized Response %s" % name)
        except:
          print("Missing Response API: %s" % name)

        if (key == GET_MAP_OBJECTS):
          getMapObjects.response(mor, env)

# vim: set tabstop=2 shiftwidth=2 expandtab : #
