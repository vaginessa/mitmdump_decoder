import numpy
import math
# Make pokedex requests async
from requests_futures.sessions import FuturesSession
from geojson import GeometryCollection, Point, Feature, FeatureCollection
import geojson

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


##Make a secrets.py with bearer= and endpoint=
try:
  from secrets import bearer, endpoint
except:
  bearer = ""
  endpoint = ""
requests = FuturesSession()

class GetMapObjectsHandler:
  def __init__(self):
    self.pokeLocation = {}
    self.request_location = {}
    self._player = geojson.dumps(FeatureCollection([]))
    self._gmo = geojson.dumps(FeatureCollection([]))

  def player(self):
    return self._player

  def get_map_objects(self):
    return self._gmo

  def request(self, mor, env):
    self.request_location[env.request_id] = (env.lat, env.long)

    features = []
    props = {
        "id": "player",
        "marker-symbol": "pitch",
        "title": "You",
        "marker-size": "large",
        "marker-color": "663399",
        "type": "player"
    }
    p = Point((mor.PlayerLng, mor.PlayerLat))
    f = Feature(geometry=p, id="player", properties=props)
    features.append(f)
    fc = FeatureCollection(features)
    dump = geojson.dumps(fc, sort_keys=True)
    self._player = dump
    f = open('ui/player.json', 'w')
    f.write(dump)

  def response(self, mor, env):
    gps = self.request_location.pop(env.response_id)
    features = []
    bulk = []

    for cell in mor.MapCell:
      for fort in cell.Fort:
        props = {
            "id": fort.FortId,
            "LastModifiedMs": fort.LastModifiedMs,
            }

        if fort.FortType == CHECKPOINT:
          props["marker-symbol"] = "circle"
          props["title"] = "PokeStop"
          props["type"] = "pokestop"
          props["lure"] = fort.HasField('FortLureInfo')
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
        bulk.append(self.createItem("gym", fort.FortId, p, f.properties))

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
        bulk.append(self.createItem("spawnpoint", 0, p, f.properties))

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
        f = Feature(geometry=p, id="wild%s" % pokemon.EncounterId, properties={
          "id": "wild%s" % pokemon.EncounterId,
          "type": "wild",
          "TimeTillHiddenMs": pokemon.TimeTillHiddenMs,
          "WillDisappear": pokemon.TimeTillHiddenMs + pokemon.LastModifiedMs,
          "title": "Wild %s" % Custom_PokemonName.Name(pokemon.Pokemon.PokemonId),
          "marker-color": "FF0000",
          "marker-symbol": "suitcase"
          })
        features.append(f)
        bulk.append(self.createItem("pokemon", pokemon.EncounterId, p, f.properties))

      for pokemon in cell.CatchablePokemon:
        p = Point((pokemon.Longitude, pokemon.Latitude))
        f = Feature(geometry=p, id="catchable%s" % pokemon.EncounterId, properties={
          "id": "catchable%s"  % pokemon.EncounterId,
          "type": "catchable",
          "ExpirationTimeMs": pokemon.ExpirationTimeMs,
          "title": "Catchable %s" % Custom_PokemonName.Name(pokemon.PokedexTypeId),
          "marker-color": "000000",
          "marker-symbol": "circle"
          })
        features.append(f)

      for poke in cell.NearbyPokemon:
        if poke.EncounterId not in self.pokeLocation.keys():
          self.pokeLocation[poke.EncounterId] = []

        new_loc = (gps[0], gps[1], poke.DistanceMeters/1000)
        if new_loc not in self.pokeLocation[poke.EncounterId]:
          self.pokeLocation[poke.EncounterId].append(new_loc)

        if len(self.pokeLocation[poke.EncounterId]) >= 3:
          locations = self.pokeLocation.pop(poke.EncounterId)
          try:
            lat, lon = self.triangulate(locations[0], locations[1], locations[2])
            p = Point((lon, lat))
            f = Feature(geometry=p, id="nearby%s" % poke.EncounterId, properties={
              "id": "nearby%s" % poke.EncounterId,
              "type": "nearby",
              "title": "Nearby %s" % Custom_PokemonName.Name(poke.PokedexNumber),
              "marker-color": "FFFFFF",
              "marker-symbol": "dog-park"
              })
            data = self.createItem("pokemon", poke.EncounterId, p, f.properties)
            bulk.append(data)
            features.append(f)
          except Exception, e:
            print("Error with nearby: %s" % e)

    self.dumpToMap(bulk)
    fc = FeatureCollection(features)
    dump = geojson.dumps(fc, sort_keys=True)
    f = open('ui/get_map_objects.json', 'w')
    f.write(dump)

  def dumpToMap(self, data):
    if bearer == "":
      return
    headers = {"Authorization" : "Bearer %s" % bearer}
    r = requests.post("%s/api/push/mapobject/bulk" % endpoint, json = data, headers = headers)

  def createItem(self, t, uid, point, meta):
    data = {"type" : t,
            "uid" : uid,
            "location" : point,
            "properties" : meta
    }
    return data

  def triangulate(self, (LatA, LonA, DistA), (LatB, LonB, DistB), (LatC, LonC, DistC)):
    #grabbed from http://gis.stackexchange.com/questions/66/trilateration-using-3-latitude-and-longitude-points-and-3-distances
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


# vim: set tabstop=2 shiftwidth=2 expandtab : #
