"""Converts polyline string from CSV file to GeoJSON"""
import csv
import argparse
import ast

import geojson

def individual_lines(input_csvs, output_geojson):
    """Output GeoJSON with a line for every route."""
    features = []
    for input_csv in input_csvs:
        with open(input_csv, 'r') as fin:
            csvreader = csv.reader(fin)
            header = ['ID', 'name', 'polyline_points', 'total_time_in_sec','total_distance_in_meters',
                      'number_of_steps', 'maneuvers']
            id_idx = header.index("ID")
            polyline_idx = header.index("polyline_points")
            time_idx = header.index('total_time_in_sec')
            assert next(csvreader)[:len(header)] == header
            success = 0
            failure = 0
            for line in csvreader:
                try:
                    polyline = ast.literal_eval(line[polyline_idx])
                    num_coordinates = len(polyline)
                    # flip lat-lon to lon-lat (per GeoJSON specification)
                    for i in range(0, num_coordinates):
                        polyline[i] = (polyline[i][1], polyline[i][0])
                    polyline = geojson.Feature(geometry=geojson.LineString(polyline),
                                               properties={'ID':line[id_idx], 'fn':input_csv, 'time_s':line[time_idx]})
                    features.append(polyline)
                    success += 1
                except SyntaxError:
                    failure += 1
                    
        print("{0} successes and {1} failures.".format(success, failure))
    fc = geojson.FeatureCollection(features)

    with open(output_geojson, 'w') as fout:
        geojson.dump(fc, fout)


def weighted_line(input_csvs, output_geojson):
    """Output GeoJSON where each road segment has how many routes passed over it."""
    for input_csv in input_csvs:
        with open(input_csv, 'r') as fin:
            csvreader = csv.reader(fin)
            header = ['ID','name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps', 'maneuvers']
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

    output = []
    for feature in features:
        polyline = geojson.Feature(geometry=geojson.LineString(feature), properties={'count':features[feature]})
        output.append(polyline)

    print("{0} successes and {1} failures.".format(success, failure))
    fc = geojson.FeatureCollection(output)

    with open(output_geojson, 'w') as fout:
        geojson.dump(fc, fout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_geojson", help="path to output GeoJSON containing polylines.")
    parser.add_argument("input_csvs", nargs="+", help="path to CSV file containing polyline directions")
    args = parser.parse_args()
    weighted_line(args.input_csvs, args.output_geojson)


if __name__ == "__main__":
    main()
