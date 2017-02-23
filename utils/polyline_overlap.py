import csv
import argparse
import ast
import os

import numpy
from shapely.geometry import LineString

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csvs", nargs="+", help="csvs to compare")
    args = parser.parse_args()

    print("Computing overlap for each pair of:")
    num_files = len(args.input_csvs)
    for i in range(num_files - 1, -1, -1):
        fn = args.input_csvs[i]
        if not os.path.isfile(fn):
            print("\tSkipping {0}: not a file.".format(fn))
            args.input_csvs.pop(i)
        else:
            print("\t{0}".format(fn))

    assert len(args.input_csvs) >= 2, "Must be at least two files to compare."

    for i in range(0, len(args.input_csvs)):
        for j in range(i+1, len(args.input_csvs)):
            print("\n{0} x {1}".format(args.input_csvs[i], args.input_csvs[j]))
            print("\tProportion Distance Overlap: {0}".format(round(get_overlap([args.input_csvs[i],
                                                                                 args.input_csvs[j]]), 3)))

def get_overlap(csvs):
    """Get proportion of routes that overlap.

    For example, if there were two routes of 1 km each and a half kilometer overlapped, this would actually be an
    overlap of 0.25 (0.5 km shared / 1.5 km total unique segments)

    Args:
        csvs: Two input CSV files
    Returns:
        Proportion between 0 and 1 of overlap, calculated as described above.
    """
    routeids = {}
    for fn in csvs:
        with open(fn, "r") as fin:
            csvreader = csv.reader(fin)
            header = next(csvreader)
            id_idx = header.index("ID")
            pts_idx = header.index("polyline_points")
            for line in csvreader:
                routeid = line[id_idx]
                # keep only routes with points (i.e. actual data)
                try:
                    if ast.literal_eval(line[pts_idx]):
                        routeids[routeid] = routeids.get(routeid, 0) + 1
                except ValueError:
                    continue

    ris = list(routeids.keys())
    num_files = len(csvs)
    for ri in ris:
        if routeids[ri] != num_files:
            del(routeids[ri])
    print("\t{0} route IDs that are all in {1}.".format(len(routeids), csvs))

    features = {}
    failure = 0
    success = 0
    for fn in csvs:
        with open(fn, "r") as fin:
            csvreader = csv.reader(fin)
            header = next(csvreader)
            id_idx = header.index("ID")
            polyline_idx = header.index("polyline_points")
            for line in csvreader:
                routeid = line[id_idx]
                if routeid in routeids:
                    try:
                        if routeid not in features:
                            features[routeid] = {}
                        polyline = ast.literal_eval(line[polyline_idx])
                        num_coordinates = len(polyline)
                        # flip lat-lon to lon-lat (per GeoJSON specification) - only necessary for outputting GeoJSONs
                        for i in range(0, num_coordinates):
                            polyline[i] = (polyline[i][1], polyline[i][0])
                        for i in range(0, num_coordinates - 1):
                            features[routeid][(polyline[i], polyline[i+1])] = features[routeid].get((polyline[i], polyline[i+1]), 0) + 1
                        success += 1
                    except SyntaxError:
                        failure += 1
    print("\t{0} failures and {1} successes.".format(failure, success))

    dist_overlaps = []
    for routeid in features:
        distance_overlapped = 0
        total_distance = 0
        for segment in features[routeid]:
            segdist = LineString(segment).length
            if features[routeid][segment] == num_files:
                distance_overlapped += segdist
            total_distance += segdist
        try:
            dist_overlaps.append(distance_overlapped / total_distance)
        except ZeroDivisionError:
            print("\t\tNo segments: {0}".format(routeid))
    return numpy.mean(dist_overlaps)


if __name__ == "__main__":
    main()
