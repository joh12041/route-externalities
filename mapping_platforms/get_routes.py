#!/usr/bin/env python
"""Get routes from external APIs.

Currently implemented for Google and Mapquest APIs.
Requires API keys for either API as well as input origin-destination pairs.
Timezone where script is being run and where routes are being collected can be
set so that gathering time of routes is carefully controlled.
"""
from abc import ABCMeta, abstractmethod

import csv
import argparse
import time
import json
import ast
import traceback
import urllib.parse
import urllib.request
import argparse
import datetime

from random import random
from time import strftime

import googlemaps

class API(object, metaclass = ABCMeta):

    def __init__(self, api_key_fn, api_limit=2500, stop_at_api_limit=True, city="nyc", route_type="grid", output_num=1):
        with open(api_key_fn, 'r') as keyfile:
            self.api_key = next(keyfile).strip()
        self.api_limit = api_limit
        self.stop_at_api_limit = stop_at_api_limit
        if output_num > 1:
            self.get_alternatives = True
        else:
            self.get_alternatives = False
        self.output_num = output_num
        self.logfile_fn = "logs/{0}_{1}_PLATFORM_log.txt".format(city, route_type)
        self.queries_made = 0
        self.exceptions = 0

    @classmethod
    @abstractmethod
    def get_routes(self, origin, destination, route_id):
        self.queries_made += 1
        return [Route()]


    def write_to_log(self, mess_type="LOG", message=""):
        with open(self.logfile_fn, 'a') as fout:
            fout.write("{0}: At {1}: {2}. {3} queries made.\n".format(mess_type, strftime("%Y-%m-%d %H:%M:%S"), message, self.queries_made))

    def end(self):
        self.write_to_log("END", "Ending script")

    def reset(self):
        self.queries_made = 0
        self.exceptions = 0
        self.write_to_log("RESET", "Returned counts to zero")


class Route(dict):

    def __init__(self, route_id="", name="", route_points=[], time_sec=None, distance_meters=None, maneuvers=[]):
        self['ID'] = route_id
        self['name'] = name
        self['polyline_points'] = route_points
        self['total_time_in_sec'] = time_sec
        self['total_distance_in_meters'] = distance_meters
        self['maneuvers'] = maneuvers
        self['number_of_steps'] = len(maneuvers)
        

class GoogleAPI(API):

    def __init__(self, api_key_fn, api_limit=2500, stop_at_api_limit=True, city="nyc", route_type="grid", output_num=1):
        super().__init__(api_key_fn, api_limit, stop_at_api_limit, city, route_type, output_num)
        self.logfile_fn = self.logfile_fn.replace("PLATFORM", "google")
        self.write_to_log("START", "Starting Google API")
        self.client = None

    def get_routes(self, origin, destination, route_id):
        if not self.client:
            self.connect_to_api()

        routes = []
        try:
            route_jsons = self.client.directions(origin = origin, destination = destination, units = "metric", mode = "driving", departure_time = "now", alternatives = self.get_alternatives)

        except Exception:
            traceback.print_exc()
            self.exceptions += 1
            self.write_to_log("EXCEPTION", "Connection failed")
            return [Route()]
                        
        try:
            idx = 0
            for route_json in route_jsons:
                # no waypoints - take first leg, which is entire trip
                route = route_json.get('legs')[0]

                # overview_polyline would provide smoothed overall line
                # overviewPolylinePoints = route_json.get('overview_polyline').get('points')
                # instead, we take the least-smoothed version at the step-level
                route_steps = route.get('steps')
                route_points = []
                for step in route_steps:
                    polyline_str = step.get("polyline", {"points":""}).get("points")
                    polyline_pts = self.decode(polyline_str)
                    # check if first point duplicates last point from previous step
                    if polyline_pts and route_points and polyline_pts[0] == route_points[-1]:
                        polyline_pts.pop(0)
                    route_points.extend(polyline_pts)

                total_time_sec = route.get('duration').get('value')
                total_distance_meters = route.get('distance').get('value')

                maneuvers = list()
                for i in range(0, len(route_steps)):
                    if 'maneuver' in route_steps[i]:
                        maneuvers.append(route_steps[i].get('maneuver'))

                name = "main"
                if idx > 0:
                    name = "alternative {0}".format(idx)
                routes.append(Route(route_id=route_id, name=name, route_points=route_points, time_sec=total_time_sec, distance_meters=total_distance_meters, maneuvers=maneuvers))
                idx += 1

        except Exception:
            traceback.print_exc()
            self.exceptions += 1
            try:
                self.write_to_log("EXCEPTION", str(route_json))
            except Exception:
                traceback.print_exc()
                self.write_to_log("EXCEPTION", "Route processing failed. JSON not valid")
            return [Route()]

        self.queries_made += 1
        return routes
        
    
    def connect_to_api(self):
        # ValueError if invalid API-Key
        self.client = googlemaps.Client(key=self.api_key)


    def decode(self, point_str):
        '''Decodes a polyline that has been encoded using Google's algorithm
        http://code.google.com/apis/maps/documentation/polylinealgorithm.html

        This is a generic method that returns a list of (latitude, longitude)
        tuples.

        Code taken from: https://gist.github.com/signed0/2031157

        :param point_str: Encoded polyline string.
        :type point_str: string
        :returns: List of 2-tuples where each tuple is (latitude, longitude)
        :rtype: list

        '''

        # sone coordinate offset is represented by 4 to 5 binary chunks
        coord_chunks = [[]]
        for char in point_str:

            # convert each character to decimal from ascii
            value = ord(char) - 63

            # values that have a chunk following have an extra 1 on the left
            split_after = not (value & 0x20)
            value &= 0x1F

            coord_chunks[-1].append(value)

            if split_after:
                coord_chunks.append([])

        del coord_chunks[-1]

        coords = []

        for coord_chunk in coord_chunks:
            coord = 0

            for i, chunk in enumerate(coord_chunk):
                coord |= chunk << (i * 5)

            #there is a 1 on the right if the coord is negative
            if coord & 0x1:
                coord = ~coord #invert
            coord >>= 1
            coord /= 100000.0

            coords.append(coord)

        # convert the 1 dimensional list to a 2 dimensional list and offsets to
        # actual values
        points = []
        prev_x = 0
        prev_y = 0
        for i in range(0, len(coords) - 1, 2):
            if coords[i] == 0 and coords[i + 1] == 0:
                continue

            prev_x += coords[i + 1]
            prev_y += coords[i]
            # a round to 6 digits ensures that the floats are the same as when
            # they were encoded
            points.append((round(prev_y, 6), round(prev_x, 6)))

        return points


class MapquestAPI(API):

    _turn_types = ['straight', 'slight right', 'right', 'sharp right', 'reverse', 'sharp left', 'left', 'slight left', 'right u-turn', 'left u-turn', 'right merge', 'left merge', 'right on ramp', 'left on ramp', 'right off ramp', 'left off ramp', 'right fork', 'left fork', 'straight fork', 'take transit', 'transfer transit', 'port transit', 'enter transit', 'exit transit']

    def __init__(self, api_key_fn, api_limit=2500, stop_at_api_limit=True, city="nyc", route_type="grid", output_num=1):
        super().__init__(api_key_fn, api_limit, stop_at_api_limit, city, route_type, output_num)
        self.logfile_fn = self.logfile_fn.replace("PLATFORM", "mapquest")
        self.write_to_log("LOG", "Starting Mapquest API")
        if self.get_alternatives:
            self.base_url = "http://www.mapquestapi.com/directions/v2/alternateroutes?"
        else:
            self.base_url = "http://www.mapquestapi.com/directions/v2/route?"

    def get_routes(self, origin, destination, route_id):
        routes = []
        start = "{0},{1}".format(origin[0], origin[1])
        dest = "{0},{1}".format(destination[0], destination[1])
        if self.get_alternatives:
            url = self.base_url + urllib.parse.urlencode([('key', self.api_key), ("from", start), ("to", dest), ('narrativeType', 'text'), ('fullShape', 'true'), ('routeType', 'fastest'), ('unit', 'k'), ('doReverseGeocode','false'), ('maxRoutes', self.output_num)])
        else:
            url = self.base_url + urllib.parse.urlencode([('key', self.api_key), ("from", start), ("to", dest), ('narrativeType', 'text'), ('fullShape', 'true'), ('routeType', 'fastest'), ('unit', 'k'), ('doReverseGeocode','false')])      

        try:
            response = urllib.request.urlopen(url)
            response_str = response.read().decode('utf-8')
            route_json = ast.literal_eval(response_str.replace('false','False').replace('true','True'))['route']
        except Exception:
            traceback.print_exc()
            self.exceptions += 1
            self.write_to_log("EXCEPTION", "Connection failed")
            return [Route()]

        try:
            main_route = self.process_route(route_id, route_json, "main")
            routes.append(main_route)
            if self.get_alternatives:
                if 'alternateRoutes' in route_json:
                    for i in range(0, min(self.output_num - 1, len(route_json['alternateRoutes']))):
                        alt_route = self.process_route(route_id, route_json['alternateRoutes'][i]['route'], "alternative {0}".format(i + 1))
                        routes.append(alt_route)
        except Exception:
            traceback.print_exc()
            self.exceptions += 1
            try:
                self.write_to_log("EXCEPTION", str(route_json))
            except Exception:
                traceback.print_exc()
                self.write_to_log("EXCEPTION", "Processing routes failed. JSON not valid")
            return [Route()]

        self.queries_made += 1
        return routes

    def process_route(self, route_id, route_json, name):
        route_steps = route_json.get('legs')[0].get('maneuvers')
        route_points_raw = route_json.get('shape')['shapePoints']
        route_points = []
        for i in range(0, len(route_points_raw), 2):
            route_points.append((route_points_raw[i], route_points_raw[i+1]))

        total_time_sec = route_json.get('realTime')
        if total_time_sec > 10000000:  # used by mapquest to signify closed road
            total_time_sec = route_json.get('time')
        total_distance_meters = route_json.get('distance')*1000

        maneuvers = []
        for i in range(0, len(route_steps)):
            try:
                maneuvers.append(self._turn_types[route_steps[i].get('turnType')])
            except IndexError:
                self.write_to_log("EXCEPTION", "{0}: illegal maneuver {1}".format(row[id_idx], route_steps[i]))
                maneuvers.append(None)
        num_steps = len(maneuvers) - 1  # don't count first step
        return Route(route_id=route_id, name=name, route_points=route_points, time_sec=total_time_sec, distance_meters=total_distance_meters, maneuvers=maneuvers)
        



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("city", help="City to run grid analysis for: 'sf' or 'nyc'")
    parser.add_argument("start_time", type=int, help="## between 00 and 24")
    parser.add_argument("--current_utc_offset", type=int, default=-6, help="UTC zone for where script is being run (e.g. -6 is Chicago)")
    args = parser.parse_args()

    utczones = {'sf':-8, 'nyc':-5, 'lon':0, 'man':8, 'sin':8}

    # Time in Chicago during winter - must adjust after Daylight Savings Time
    current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=args.current_utc_offset)))
    try:
        utc_zone = utczones.get(args.city)
    except KeyError:
        print("Invalid city. Must be one of {0}.".format(utczones.keys()))
        return

    start_time = datetime.datetime(year = current_time.year, month = current_time.month, day = current_time.day, hour=args.start_time, tzinfo = datetime.timezone(datetime.timedelta(hours=utc_zone)))
    sleep_for = (start_time - current_time).seconds
    print("Will sleep for {0} seconds before starting.".format(sleep_for))

    input_odpairs_fn = "data/intermediate/{0}_grid_od_pairs.csv".format(args.city)
    output_routes_g_fn = "data/intermediate/{0}_grid_google_routes.csv".format(args.city)
    output_routes_m_fn = "data/intermediate/{0}_grid_mapquest_routes.csv".format(args.city)

    od_pairs = []
    with open(input_odpairs_fn, 'r') as fin:
        # open file with origin long, origin lat, dest long, dest lat
        csvreader = csv.reader(fin)
        input_header = ["ID", "origin_lon", "origin_lat", "destination_lon", "destination_lat", "straight_line_distance"]
        assert next(csvreader) == input_header
        id_idx = input_header.index("ID")
        oln_idx = input_header.index("origin_lon")
        olt_idx = input_header.index("origin_lat")
        dln_idx = input_header.index("destination_lon")
        dlt_idx = input_header.index("destination_lat")
        dist_idx = input_header.index("straight_line_distance")
        for row in csvreader:
            origin = float(row[olt_idx]), float(row[oln_idx])
            destination = float(row[dlt_idx]), float(row[dln_idx])
            route_id = row[id_idx]
            od_pairs.append({'id':route_id, 'origin':origin, 'destination':destination})
                            
    with open(output_routes_g_fn, 'w') as foutg:
        with open(output_routes_m_fn, 'w') as foutm:
            fieldnames = ['ID', 'name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
            csvwriter_g = csv.DictWriter(foutg, fieldnames=fieldnames)
            csvwriter_m = csv.DictWriter(foutm, fieldnames=fieldnames)
            csvwriter_g.writeheader()
            csvwriter_m.writeheader()
            g = GoogleAPI(api_key_fn="api_keys/google.txt", api_limit=2500, stop_at_api_limit=True, city=args.city, route_type="grid", output_num=2)
            m = MapquestAPI(api_key_fn="api_keys/mapquest.txt", api_limit=2500, stop_at_api_limit=True, city=args.city, route_type="grid", output_num=2)
            
            time.sleep(sleep_for)
            g.write_to_log("LOG: At {0}: Starting script.\n".format(strftime("%Y-%m-%d %H:%M:%S")))
            m.write_to_log("LOG: At {0}: Starting script.\n".format(strftime("%Y-%m-%d %H:%M:%S")))

            for od_pair in od_pairs:
                try:
                    routes_g = g.get_routes(od_pair['origin'], od_pair['destination'], od_pair['id'])
                    routes_m = m.get_routes(od_pair['origin'], od_pair['destination'], od_pair['id'])
                    for route in routes_g:
                        csvwriter_g.writerow(route)
                    for route in routes_m:
                        csvwriter_m.writerow(route)

                    if (g.exceptions + 1) % 40 == 0 or (m.exceptions + 1) % 40 == 0:
                        g.write_to_log("TOO MANY EXCEPTIONS", "{0} exceptions reached. Should be halting script".format((g.exceptions, m.exceptions)))
                        m.write_to_log("TOO MANY EXCEPTIONS", "{0} exceptions reached. Should be halting script".format((g.exceptions, m.exceptions)))
                        #break
                            
                    if g.queries_made % 500 == 0:
                        g.write_to_log("LOG", "Every 500 query check")
                        m.write_to_log("LOG", "Every 500 query check")
                        
                    # when almost hit API limit, shut-down
                    if g.stop_at_api_limit and g.queries_made == g.api_limit:
                        current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
                        sleep_for = (start_time - current_time).seconds
                        g.write_to_log("API LIMIT", "Script sleeping for {0} seconds. Current route ID is {1}".format(sleep_for, od_pair['id']))
                        m.write_to_log("API LIMIT", "Script sleeping for {0} seconds. Current route ID is {1}".format(sleep_for, od_pair['id']))
                            
                        time.sleep(sleep_for)
                        g.reset()
                        m.reset()
                    else:
                        # be nice to API
                        time.sleep(1 + (0.5 - random()))
                    

                except KeyboardInterrupt:
                    traceback.print_exc()
                    break

            g.end()
            m.end()

if __name__ == "__main__":
    main()
