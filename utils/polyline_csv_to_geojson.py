"""Converts polyline string from CSV file to GeoJSON"""
import csv
import json
import argparse
import ast
import random
import copy

import geojson
from shapely.geometry import LineString

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_geojson", help="path to output GeoJSON containing polylines.")
    parser.add_argument("input_csvs", nargs="+", help="path to CSV file containing polyline directions")
    args = parser.parse_args()
    
    #individual_lines(args.input_csvs, args.output_geojson)
    #if True:
    #    return
    if len(args.input_csvs) == 2:
        bootstrap_weighted_line(args.input_csvs, args.output_geojson, onlydiff=True)
    else:
        weighted_line(args.input_csvs, args.output_geojson)


def individual_lines(input_csvs, output_geojson):

    features = []
    for input_csv in input_csvs:
        with open(input_csv, 'r') as fin:
            csvreader = csv.reader(fin)
            header = ['ID', 'name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
            id_idx = header.index("ID")
            polyline_idx = header.index("polyline_points")
            time_idx = header.index('total_time_in_sec')
            dist_idx = header.index('total_distance_in_meters')
            step_idx = header.index('number_of_steps')
            assert next(csvreader)[:len(header)] == header
            success = 0
            failure = 0
            for line in csvreader:
                try:
                    if line[0] != '178;516;107;492':
                        continue
                    polyline = ast.literal_eval(line[polyline_idx])
                    num_coordinates = len(polyline)
                    # flip lat-lon to lon-lat (per GeoJSON specification)
                    for i in range(0, num_coordinates):
                        polyline[i] = (polyline[i][1], polyline[i][0])
                    polyline = geojson.Feature(geometry=geojson.LineString(polyline), properties={'ID':line[id_idx], 'fn':input_csv, 'time_s':line[time_idx], 'dist_m':line[dist_idx], 'num_steps':line[step_idx]})
                    features.append(polyline)
                    success += 1
                except SyntaxError:
                    failure += 1
                    
        print("{0} successes and {1} failures.".format(success, failure))
    fc = geojson.FeatureCollection(features)

    with open(output_geojson, 'w') as fout:
        geojson.dump(fc, fout)


def sample_line(input_csv="data/output/sf_grid_google_routes.csv", output_csv="02degree_google_route.csv", sample_dist = 0.0025):

    with open(input_csv, 'r') as fin:
        csvreader = csv.reader(fin)
        header = ['ID','polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
        id_idx = header.index("ID")
        polyline_idx = header.index("polyline_points")
        dist_idx = header.index('total_distance_in_meters')
        assert next(csvreader)[:len(header)] == header
        with open(output_csv, 'w') as fout:
            csvwriter = csv.writer(fout)
            csvwriter.writerow(['id','lat','lon'])
            for line in csvreader:
                try:
                    polyline = ast.literal_eval(line[polyline_idx])
                    num_coordinates = len(polyline)
                    dist = line[dist_idx]
                    route = line[id_idx]
                    # flip lat-lon to lon-lat (per GeoJSON specification)
                    for i in range(0, num_coordinates):
                        polyline[i] = (polyline[i][1], polyline[i][0])
                    polylinegj = geojson.Feature(geometry=geojson.LineString(polyline), properties={'ID':line[id_idx]})
                    polyline = LineString(polyline)
                    dist_along_line = 0
                    print(polyline.length, 'degrees', dist, 'km')
                    while dist_along_line < polyline.length:
                        pt = polyline.interpolate(dist_along_line)
                        dist_along_line += sample_dist
                        csvwriter.writerow([route, round(pt.y, 3), round(pt.x, 3)])
                except SyntaxError:
                    print("Failed")
                break                

    fc = geojson.FeatureCollection([polylinegj])                    
    with open(output_csv.replace(".csv",".geojson"), 'w') as fout:
        geojson.dump(fc, fout)



def bootstrap_weighted_line(input_csvs, output_geojson, onlydiff=False):

    if len(input_csvs) != 2:
        print("Only implemented for 2 csv files.")
        return
    print("\nBootstrap route differences for {0}".format(input_csvs))

    # get first set of polylines - e.g. featuresone = {'route1':[(1,2), (2,3), ...], ...}
    with open(input_csvs[0], 'r') as fin:
        csvreader = csv.reader(fin)
        header = ['ID','name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
        id_idx = header.index("ID")
        time_idx = header.index("total_time_in_sec")
        polyline_idx = header.index("polyline_points")
        assert next(csvreader)[:len(header)] == header
        featuresone = {}
        timesone = {}
        success = 0
        failure = 0
        for line in csvreader:
            try:
                route_id = line[id_idx]
                t_sec = float(line[time_idx])
                polyline = ast.literal_eval(line[polyline_idx])
                num_coordinates = len(polyline)
                # flip lat-lon to lon-lat (per GeoJSON specification)
                for i in range(0, num_coordinates):
                    polyline[i] = (polyline[i][1], polyline[i][0])
                featuresone[route_id] = polyline
                timesone[route_id] = t_sec              
                success += 1
            except SyntaxError:
                failure += 1

    # get second set of polylines
    with open(input_csvs[1], 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader)[:len(header)] == header
        featurestwo = {}
        timestwo = {}
        for line in csvreader:
            try:
                route_id = line[id_idx]
                t_sec = float(line[time_idx])
                polyline = ast.literal_eval(line[polyline_idx])
                num_coordinates = len(polyline)
                for i in range(0, num_coordinates):
                    polyline[i] = (polyline[i][1], polyline[i][0])
                featurestwo[route_id] = polyline
                timestwo[route_id] = t_sec
                success += 1
            except SyntaxError:
                failure += 1

    # filter out routes that don't appear in both CSVs
    routeids = list(featuresone.keys())
    print("{0} and {1} route IDs to start. {2} successes and {3} failures.".format(len(routeids), len(featurestwo), success, failure))
    numids = len(routeids)
    for i in range(numids - 1, -1, -1):
        if routeids[i] not in featurestwo:
            featuresone.pop(routeids.pop(i))
    routestoremove = []
    for routeid in featurestwo:
        if routeid not in featuresone:
            routestoremove.append(routeid)
    for routeid in routestoremove:
        featurestwo.pop(routeid)
    if onlydiff:
        numids = len(routeids)
        routestoremove = []
        for i in range(numids - 1, -1, -1):
            if timesone.get(routeids[i]) == timestwo.get(routeids[i]):
                routestoremove.append(routeids.pop(i))
        print("{0} routes not different out of {1}.".format(len(routestoremove), numids))
        for rid in routestoremove:
            featuresone.pop(rid)
            featurestwo.pop(rid)
    print("{0} route IDs left over.".format(len(routeids)))
    
    # get dictionary of all possible line segments
    segments = get_segments([featuresone, featurestwo])
    num_segments = len(segments)
    print("{0} segments.".format(num_segments))
    # bootstrap resample
    numiters = 1000
    alpha = 0.01
    for i in range(0, numiters):
        sampled_ids = resample(routeids)
        segmentdiffs = get_diff(featuresone, featurestwo, sampled_ids)
        looped = 0
        for segment in segments:
            looped += 1
            segments[segment].append(segmentdiffs.get(segment, 0))
        if i % 50 == 0:
            print("Iteration {0} of {1}".format(i, numiters))
    processed = 0
    for segment in segments:
        sorted_segs = sorted(segments[segment])
        #print(sorted_segs)
        lb = sorted_segs[int(numiters * alpha)]
        ub = sorted_segs[int(numiters * (1- alpha))]
        med = sorted_segs[int(numiters / 2)]
        if (lb > 0 and ub > 0) or (lb < 0 and ub < 0):
            significant = True
        else:
            significant = False
        segments[segment] = {'lb':lb, 'ub':ub, 'med':med, 'sig':significant}
        processed += 1
        if processed % 1000 == 0:
            print("{0} processed out of {1}".format(processed, num_segments))
            
    output = []
    outputsig = []
    for feature in segments:
        polyline = geojson.Feature(geometry=geojson.LineString(feature), properties={'lb':segments[feature]['lb'], 'ub':segments[feature]['ub'], 'med':segments[feature]['med'], 'sig':segments[feature]['sig']})
        output.append(polyline)
        if segments[feature]['sig']:
            outputsig.append(polyline)

    fc = geojson.FeatureCollection(output)
    fcsign = geojson.FeatureCollection(outputsig)

    #with open(output_geojson, 'w') as fout:
    #    geojson.dump(fc, fout)
    with open(output_geojson.replace(".geojson", "_sigonly.geojson"), 'w') as fout:
        geojson.dump(fcsign, fout)


def resample(routeids):
    numids = len(routeids)
    resampledids = []
    for i in range(0, numids):
        resampledids.append(routeids[random.randint(0, numids - 1)])
    return resampledids


def get_segments(routedicts, default_value = []):
    segments = {}
    for routes in routedicts:
        for routeid in routes:
            pts = routes[routeid]
            numcoords = len(pts)
            for i in range(0, numcoords - 1):
                segments[(pts[i], pts[i+1])] = copy.deepcopy(default_value)
    return segments


def get_diff(routesone, routestwo, routeids):
    diffs = {}
    for routeid in routeids:
        numcoords = len(routesone[routeid])
        for i in range(0, numcoords - 1):
            segment = (routesone[routeid][i], routesone[routeid][i+1])
            diffs[segment] = diffs.get(segment, 0) + 1
        numcoords = len(routestwo[routeid])
        for i in range(0, numcoords - 1):
            segment = (routestwo[routeid][i], routestwo[routeid][i+1])
            diffs[segment] = diffs.get(segment, 0) - 1
    return diffs


def weighted_line(input_csvs, output_geojson):

    if not input_csvs or len(input_csvs) > 2:
        print("Only implemented for 1-2 csv files.")
        return

    with open(input_csvs[0], 'r') as fin:
        csvreader = csv.reader(fin)
        header = ['ID','name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
        id_idx = header.index("ID")
        polyline_idx = header.index("polyline_points")
        assert next(csvreader)[:len(header)] == header
        features = {}
        success = 0
        failure = 0
        for line in csvreader:
            try:
                polyline = ast.literal_eval(line[polyline_idx])
                num_coordinates = len(polyline)
                # flip lat-lon to lon-lat (per GeoJSON specification)
                for i in range(0, num_coordinates):
                    polyline[i] = (polyline[i][1], polyline[i][0])
                for i in range(0, num_coordinates - 1):
                    features[(polyline[i], polyline[i+1])] = features.get((polyline[i], polyline[i+1]), 0) + 1
                success += 1
            except SyntaxError:
                failure += 1

    if len(input_csvs) == 2:
        with open(input_csvs[1], 'r') as fin:
            csvreader = csv.reader(fin)
            assert next(csvreader)[:len(header)] == header
            for line in csvreader:
                try:
                    polyline = ast.literal_eval(line[polyline_idx])
                    num_coordinates = len(polyline)
                    for i in range(0, num_coordinates):
                        polyline[i] = (polyline[i][1], polyline[i][0])
                    for i in range(0, num_coordinates - 1):
                        features[(polyline[i], polyline[i+1])] = features.get((polyline[i], polyline[i+1]), 0) - 1
                    success += 1
                except SyntaxError:
                    failure += 1

            
    output = []
    for feature in features:
        polyline = geojson.Feature(geometry=geojson.LineString(feature), properties={'count':features[feature]})
        output.append(polyline)


    print("{0} successes and {1} failures.".format(success, failure))
    fc = geojson.FeatureCollection(output)

    with open(output_geojson, 'w') as fout:
        geojson.dump(fc, fout)



if __name__ == "__main__":
    main()
