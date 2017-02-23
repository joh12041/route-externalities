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
    parser.add_argument("output_geojson",
                        help="path to output GeoJSON containing polylines")
    parser.add_argument("input_csvs",
                        nargs="+",
                        help="path to CSV file containing polyline directions")
    parser.add_argument("--num_iters",
                        type=int,
                        default=1000,
                        help="Number of iterations to use in bootstrap resampling")
    parser.add_argument("--alpha",
                        type=float,
                        default=0.01,
                        help="Threshold for determining significance (e.g. 0.01 is 99% significance)")
    args = parser.parse_args()

    if len(args.input_csvs) == 2:
        bootstrap_weighted_line(args.input_csvs[0],
                                args.input_csvs[1],
                                args.output_geojson,
                                args.num_iters,
                                args.alpha,
                                onlydiff=True)
    else:
        raise NotImplementedError, "Significant difference only implemented for two input files"


def bootstrap_weighted_line(input_csv_one, input_csv_two, output_geojson, numiters, alpha, onlydiff=True):
    """Use bootstrap resampling to determine significant differences in where routes go.

    Args:
        input_csv_one: File path of first CSV file with routes.
        input_csv_two: File path of second CSV file with routes.
        output_geojson: File path of GeoJSON file to which the results will be written.
        onlydiff: True if only use routes that are actually different between the two files.
    Returns:
        Void. Writes output to GeoJSON.

    """
    print("\nBootstrap route differences for {0} and {1}".format(input_csv_one, input_csv_two))

    # get first set of polylines - e.g. featuresone = {'route1':[(1,2), (2,3), ...], ...}
    with open(input_csv_one, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        id_idx = header.index("ID")
        time_idx = header.index("total_time_in_sec")
        polyline_idx = header.index("polyline_points")
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
    with open(input_csv_two, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == header
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
    print("{0} and {1} route IDs to start. {2} successes and {3} failures.".format(len(routeids),
                                                                                   len(featurestwo),
                                                                                   success,
                                                                                   failure))
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
    for i in range(0, numiters):
        sampled_ids = resample(routeids)
        segmentdiffs = get_diff(featuresone, featurestwo, sampled_ids)
        for segment in segments:
            segments[segment].append(segmentdiffs.get(segment, 0))
        if i % 50 == 0:
            print("Iteration {0} of {1}".format(i, numiters))

    # Determine significance
    processed = 0
    for segment in segments:
        sorted_seg_diffs = sorted(segments[segment])
        lb = sorted_seg_diffs[int(numiters * (alpha / 2))]
        ub = sorted_seg_diffs[int(numiters * (1 - (alpha / 2)))]
        med = sorted_seg_diffs[int(numiters / 2)]
        if (lb > 0 and ub > 0) or (lb < 0 and ub < 0):
            significant = True
        else:
            significant = False
        segments[segment] = {'lb':lb, 'ub':ub, 'med':med, 'sig':significant}
        processed += 1
        if processed % 1000 == 0:
            print("{0} processed out of {1}".format(processed, num_segments))
            
    output = []
    for feature in segments:
        polyline = geojson.Feature(geometry=geojson.LineString(feature),
                                   properties={'lb':segments[feature]['lb'],
                                               'ub':segments[feature]['ub'],
                                               'med':segments[feature]['med'],
                                               'sig':segments[feature]['sig']})
        output.append(polyline)

    fc = geojson.FeatureCollection(output)

    with open(output_geojson, 'w') as fout:
        geojson.dump(fc, fout)

def resample(routeids):
    """Resample a list with replacement."""
    numids = len(routeids)
    resampledids = []
    for i in range(0, numids):
        resampledids.append(routeids[random.randint(0, numids - 1)])
    return resampledids


def get_segments(routedicts, default_value = []):
    """Get dictionary of all possible route segments."""
    segments = {}
    for routes in routedicts:
        for routeid in routes:
            pts = routes[routeid]
            numcoords = len(pts)
            for i in range(0, numcoords - 1):
                segments[(pts[i], pts[i+1])] = copy.deepcopy(default_value)
    return segments


def get_diff(routesone, routestwo, routeids):
    """Get difference in number of routes using each segment."""
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


if __name__ == "__main__":
    main()
