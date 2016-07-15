#!/usr/bin/env python

import time
import sys
import numpy
import math

from mitmproxy.script import concurrent
from mitmproxy.models import decoded

from geojson import GeometryCollection, Point, Feature, FeatureCollection
import geojson

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


#We can often look up the right deserialization structure based on the method, but there are some deviations
mismatched_apis = {
  'RECYCLE_INVENTORY_ITEM': 'RECYCLE_ITEM',
  'USE_INCENSE': 'USE_INCENSE_ACTION',
  'GET_PLAYER_PROFILE': 'PLAYER_PROFILE',
  #'SFIDA_ACTION_LOG': This one is mismatches, but so bad that it had to be fixed in the protobuf
  'GET_ASSET_DIGEST': 'ASSET_DIGEST_REQUEST',
  'DOWNLOAD_REMOTE_CONFIG_VERSION': 'GET_REMOTE_CONFIG_VERSIONS',
}

request_api = {} #Match responses to their requests
pokeLocation = {}
request_location = {}

def triangulate((LatA, LonA, DistA), (LatB, LonB, DistB), (LatC, LonC, DistC)):
  #using authalic sphere
  #if using an ellipsoid this step is slightly different
  #Convert geodetic Lat/Long to ECEF xyz
  #   1. Convert Lat/Long to radians
  #   2. Convert Lat/Long(radians) to ECEF
  earthR = 6371
  xA = earthR *(math.cos(math.radians(LatA)) * math.cos(math.radians(LonA)))
  yA = earthR *(math.cos(math.radians(LatA)) * math.sin(math.radians(LonA)))
  zA = earthR *(math.sin(math.radians(LatA)))

  xB = earthR *(math.cos(math.radians(LatB)) * math.cos(math.radians(LonB)))
  yB = earthR *(math.cos(math.radians(LatB)) * math.sin(math.radians(LonB)))
  zB = earthR *(math.sin(math.radians(LatB)))

  xC = earthR *(math.cos(math.radians(LatC)) * math.cos(math.radians(LonC)))
  yC = earthR *(math.cos(math.radians(LatC)) * math.sin(math.radians(LonC)))
  zC = earthR *(math.sin(math.radians(LatC)))

  P1 = numpy.array([xA, yA, zA])
  P2 = numpy.array([xB, yB, zB])
  P3 = numpy.array([xC, yC, zC])

  #from wikipedia
  #transform to get circle 1 at origin
  #transform to get circle 2 on x axis
  ex = (P2 - P1)/(numpy.linalg.norm(P2 - P1))
  i = numpy.dot(ex, P3 - P1)
  ey = (P3 - P1 - i*ex)/(numpy.linalg.norm(P3 - P1 - i*ex))
  ez = numpy.cross(ex,ey)
  d = numpy.linalg.norm(P2 - P1)
  j = numpy.dot(ey, P3 - P1)

  #from wikipedia
  #plug and chug using above values
  x = (pow(DistA,2) - pow(DistB,2) + pow(d,2))/(2*d)
  y = ((pow(DistA,2) - pow(DistC,2) + pow(i,2) + pow(j,2))/(2*j)) - ((i/j)*x)

  # only one case shown here
  z = numpy.sqrt(pow(DistA,2) - pow(x,2) - pow(y,2))

  #triPt is an array with ECEF x,y,z of trilateration point
  triPt = P1 + x*ex + y*ey + z*ez

  #convert back to lat/long from ECEF
  #convert to degrees
  lat = math.degrees(math.asin(triPt[2] / earthR))
  lon = math.degrees(math.atan2(triPt[1],triPt[0]))

  return (lat, lon)

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

@concurrent
def request(context, flow):
  if flow.match("~d pgorelease.nianticlabs.com"):
    env = RpcRequestEnvelopeProto()
    env.ParseFromString(flow.request.content)
    if ( len(env.parameter) == 0 ):
      print 'Failed - empty request parameters'
      return
    key = env.parameter[0].key
    value = env.parameter[0].value

    request_api[env.request_id] = key
    request_location[env.request_id] = (env.lat,env.long)

    name = Method.Name(key)
    name = mismatched_apis.get(name, name) #return class name when not the same as method
    klass = underscore_to_camelcase(name) + "Proto"
    try:
      mor = deserialize(value, "." + klass)
      print("Deserialized Request %s" % name)
    except:
      print("Missing Request API: %s" % name)

def response(context, flow):
  with decoded(flow.response):
    if flow.match("~d pgorelease.nianticlabs.com"):
      env = RpcResponseEnvelopeProto()
      env.ParseFromString(flow.response.content)
      key = request_api[env.response_id]
      value = env.returns[0]

      name = Method.Name(key)
      name = mismatched_apis.get(name, name) #return class name when not the same as method
      klass = underscore_to_camelcase(name) + "OutProto"
      try:
        mor = deserialize(value, "." + klass)
        print("Deserialized Response %s" % name)
      except:
        print("Missing Response API: %s" % name)


      if (key == GET_MAP_OBJECTS):
        features = []

        for cell in mor.MapCell:
          for fort in cell.Fort:

            props = {
                "id": fort.FortId,
                "LastModifiedMs": fort.LastModifiedMs,
                }

            if fort.FortType == CHECKPOINT:
              props["marker-symbol"] = "circle"
              props["title"] = "PokéStop"
              props["type"] = "pokestop"
            else:
              props["marker-symbol"] = "town-hall"
              props["marker-size"] = "large"
              props["type"] = "gym"

            if fort.Team == BLUE:
              props["marker-color"] = "0000FF"
              props["title"] = "Blue Gym"
            elif fort.Team == RED:
              props["marker-color"] = "FF0000"
              props["title"] = "Red Gym"
            elif fort.Team == YELLOW:
              props["marker-color"] = "FF0000"
              props["title"] = "Yellow Gym"
            else:
              props["marker-color"] = "808080"

            p = Point((fort.Longitude, fort.Latitude))
            f = Feature(geometry=p, id=fort.FortId, properties=props)
            features.append(f)

          for spawn in cell.SpawnPoint:
            p = Point((spawn.Longitude, spawn.Latitude))
            f = Feature(geometry=p, id=len(features), properties={
              "type": "spawn",
              "id": len(features),
              "title": "spawn",
              "marker-color": "00FF00",
              "marker-symbol": "garden",
              "marker-size": "small",
              })
            features.append(f)

          for spawn in cell.DecimatedSpawnPoint:
            p = Point((spawn.Longitude, spawn.Latitude))
            f = Feature(geometry=p, id=len(features), properties={
              "id": len(features),
              "type": "decimatedspawn",
              "title": "Decimated spawn",
              "marker-color": "000000",
              "marker-symbol": "monument"
              })
            features.append(f)

          for pokemon in cell.WildPokemon:
            p = Point((pokemon.Longitude, pokemon.Latitude))
            f = Feature(geometry=p, id="wild" + str(pokemon.EncounterId), properties={
              "id": "wild" + str(pokemon.EncounterId),
              "type": "wild",
              "TimeTillHiddenMs": pokemon.TimeTillHiddenMs,
              "title": "Wild %s" % Custom_PokemonName.Name(pokemon.Pokemon.PokemonId),
              "marker-color": "FF0000",
              "marker-symbol": "suitcase"
              })
            features.append(f)

          for pokemon in cell.CatchablePokemon:
            p = Point((pokemon.Longitude, pokemon.Latitude))
            f = Feature(geometry=p, id="catchable" + str(pokemon.EncounterId), properties={
              "id": "catchable" + str(pokemon.EncounterId),
              "type": "catchable",
              "ExpirationTimeMs": pokemon.ExpirationTimeMs,
              "title": "Catchable %s" % Custom_PokemonName.Name(pokemon.PokedexTypeId),
              "marker-color": "000000",
              "marker-symbol": "circle"
              })
            features.append(f)

          for poke in cell.NearbyPokemon:
            gps = request_location[env.response_id]
            if poke.EncounterId in pokeLocation:
              add=True
              for loc in pokeLocation[poke.EncounterId]:
                if gps[0] == loc[0] and gps[1] == loc[1]:
                  add=False
              if add:
                pokeLocation[poke.EncounterId].append((gps[0], gps[1], poke.DistanceMeters/1000))
            else:
              pokeLocation[poke.EncounterId] = [(gps[0], gps[1], poke.DistanceMeters/1000)]
            if len(pokeLocation[poke.EncounterId]) >= 3:
              lat, lon = triangulate(pokeLocation[poke.EncounterId][0],pokeLocation[poke.EncounterId][1],pokeLocation[poke.EncounterId][2])
              if not math.isnan(lat) and not math.isnan(lon) :
                p = Point((lon, lat))
                f = Feature(geometry=p, id="nearby" + str(poke.EncounterId), properties={
                  "id": "nearby" + str(poke.EncounterId),
                  "type": "nearby",
                  "title": "Nearby %s" % Custom_PokemonName.Name(poke.PokedexNumber),
                  "marker-color": "FFFFFF",
                  "marker-symbol": "dog-park"
                  })
                features.append(f)


        fc = FeatureCollection(features)
        dump = geojson.dumps(fc, sort_keys=True)
        f = open('ui/get_map_objects.json', 'w')
        f.write(dump)

# vim: set tabstop=2 shiftwidth=2 expandtab : #
