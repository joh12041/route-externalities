import csv
import sys
import json
from random import random, randint
from math import floor

from geopy.distance import vincenty
from geopy.distance import great_circle
from shapely.geometry import shape, Point

ODPAIRS_PER_CITY = 5000
OUTPUT_HEADER = ["ID", "origin_lon", "origin_lat", "destination_lon", "destination_lat", "straight_line_distance"]

def random_selection_routes(od_fn, output_fn, min_dist, max_dist):
    """Randomly downsample origin-destination pairs from a list of potential origin-destination pairs.

    Args:
        od_fn: CSV file with all origin-destination pairs
        output_fn: CSV file to which filtered origin-destination pairs will be written
        min_dist: only include od-pairs with a Euclidean distance greater than this threshold (km)
        max_dist: only include od-pairs with a Euclidean distance under this threshold (km)
    Returns:
        Void. Writes output origin-destination pairs along with straight-line distance to CSV file
    """

    potential_lines = []
    with open(od_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        found_header = next(csvreader)
        assert found_header == OUTPUT_HEADER[:len(found_header)]
        o_lat_idx = found_header.index("origin_lat")
        o_lon_idx = found_header.index("origin_lon")
        d_lat_idx = found_header.index("destination_lat")
        d_lon_idx = found_header.index("destination_lon")
        line_no = 0
        for line in csvreader:
            orig_pt = (float(line[o_lat_idx]), float(line[o_lon_idx]))
            dest_pt = (float(line[d_lat_idx]), float(line[d_lon_idx]))
            dist_km = get_distance(orig_pt, dest_pt)
            if dist_km >= min_dist and dist_km <= max_dist:
                potential_lines.append(line_no)
            line_no += 1

    sampled_lines = {}
    num_potential_lines = min(ODPAIRS_PER_CITY, len(potential_lines))
    while len(sampled_lines) < num_potential_lines:
        sampled_lines[potential_lines[random.randint(0, len(potential_lines) - 1)]] = True

    with open(od_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == OUTPUT_HEADER
        line_no = 0
        lines_kept = 0
        with open(output_fn, 'w') as fout:
            csvwriter = csv.writer(fout)
            csvwriter.writerow(OUTPUT_HEADER)
            for line in csvreader:
                if line_no in sampled_lines:
                    lines_kept += 1
                    orig_pt = (float(line[o_lat_idx]), float(line[o_lon_idx]))
                    dest_pt = (float(line[d_lat_idx]), float(line[d_lon_idx]))
                    dist_km = get_distance(orig_pt, dest_pt)
                    line.append(dist_km)
                    csvwriter.writerow(line)
                    if lines_kept % 200 == 0:
                        sys.stdout.write("\r{0} lines processed and {1} o-d pairs kept.".format(line_no, lines_kept))
                        sys.stdout.flush()
                line_no += 1
    sys.stdout.write("\rFinal: {0} lines processed and {1} o-d pairs kept.".format(line_no, lines_kept))
    sys.stdout.flush()


def odpairs_from_grid_centroids(input_geojson_fns, output_csv_fn, min_dist=0, max_dist=30, secondary_geojson=None):
    """Randomly select origin-destination pairs from combinations of grid cells.

    Args:
        input_geojsons_fns: list of geojson files containing gridcells
        output_csv_fn: path to output CSV file for od-pairs
        min_dist: only include od-pairs with a Euclidean distance greater than this threshold (km)
        max_dist: only include od-pairs with a Euclidean distance under this threshold (km)
        secondary_geojson: an optiona second geojson file to use as an extent to further constrain the od pairs.
    Returns:
        Void. Writes output origin-destination pairs along with straight-line distance to CSV file
    """

    #open/load grid geojson
    gridcells = []
    for geojson_fn in input_geojson_fns:
        with open(geojson_fn, 'r') as fin:
          gridcells.extend(json.load(fin)['features'])

    for feature in gridcells:
        feature['centroid'] = (shape(feature['geometry']).centroid.y, shape(feature['geometry']).centroid.x)
        feature['properties']['rid'] = str(feature['properties']['rid'])
        feature['properties']['cid'] = str(feature['properties']['cid'])

    if secondary_geojson:
        with open(secondary_geojson, 'r') as fin:
            specific_boundary = json.load(fin)
        for ft in specific_boundary['features']:
            ft['properties']['shape'] = shape(ft['geometry'])
        print("{0} regions in secondary geojson".format(len(specific_boundary['features'])))

    print("{0} grid cells".format(len(gridcells)))
    routes_added = 0

    with open(output_csv_fn, 'w') as fout:
        csvwriter = csv.writer(fout)
        csvwriter.writerow(OUTPUT_HEADER)
        num_features = len(gridcells)
        dist_bins = [0] * max_dist
        while routes_added < ODPAIRS_PER_CITY:
            i = randint(0, num_features - 1)
            j = randint(0, num_features - 1)
            if i != j:
                # randomly determine which point will be origin and which destination
                feature1 = gridcells[i]
                feature2 = gridcells[j]
                # Vincenty = most accurate distance calculation
                try:
                    dist_km = vincenty(feature1['centroid'], feature2['centroid']).kilometers
                # if Vincenty fails to converge, fall back on Great Circle - less accurate but guaranteed
                except ValueError:
                    dist_km = great_circle(feature1['centroid'], feature2['centroid']).kilometers
                # aim to have about the same number of routes as I can query the APIs for
                if dist_km >= min_dist and dist_km <= max_dist:
                    if secondary_geojson:
                        ptone = Point((feature1['centroid'][1], feature1['centroid'][0]))
                        pttwo = Point((feature2['centroid'][1], feature2['centroid'][0]))
                        if not is_contained(ptone, specific_boundary) or not is_contained(pttwo, specific_boundary):
                            continue
                    dist_bins[floor(dist_km)] += 1
                    routes_added += 1
                    if routes_added % 500 == 0:
                        print("{0} routes added of {1}".format(routes_added, ODPAIRS_PER_CITY))
                    rowcolID = ";".join([feature1['properties']['rid'], feature1['properties']['cid'], feature2['properties']['rid'], feature2['properties']['cid']])
                    csvwriter.writerow([rowcolID, round(feature1['centroid'][1], 6), round(feature1['centroid'][0], 6), round(feature2['centroid'][1], 6), round(feature2['centroid'][0], 6), round(dist_km, 6)])
        for i in range(0, len(dist_bins)):
            print("{0} between {1} and {2} km in length.".format(dist_bins[i], i, i+1))


def get_distance(orig_pt, dest_pt):
    """Get distance in kilometers between two points."""
    # Vincenty = most accurate distance calculation
    try:
        return vincenty(orig_pt, dest_pt).kilometers
    # if Vincenty fails to converge, fall back on Great Circle - less accurate but guaranteed
    except ValueError:
        return great_circle(orig_pt, dest_pt).kilometers


def is_contained(pt, containing_features):
    """Check if a point is contained by at least one or more polygons."""
    for ft in containing_features:
        if ft['properties']['shape'].contains(pt):
            return True
    return False


def main():
    min_dist = 0
    max_dist = 30
    data_folder = "data/input"
    cities = {'lon' : ["{0}/lon_grid.geojson".format(data_folder)],
              'man' : ["{0}/man_grid.geojson".format(data_folder)],
              'sf'  : ["{0}/sf_grid.geojson".format(data_folder)],
              'nyc' : ["{0}/36005_grid.geojson".format(data_folder),
                       "{0}/36047_grid.geojson".format(data_folder),
                       "{0}/36061_grid.geojson".format(data_folder),
                       "{0}/36081_grid.geojson".format(data_folder),
                       "{0}/36085_grid.geojson".format(data_folder)]}
    for city in cities:
        odpairs_from_grid_centroids(input_geojson_fns = cities[city],
                                    output_csv_fn = "data/output/{0}_grid_od_pairs.csv".format(city),
                                    min_dist = min_dist,
                                    max_dist = max_dist,
                                    secondary_geojson="geometries/{0}_outline.geojson".format(city))
    random_selection_routes(od_fn = "data/output/sf_all_taxi_od_pairs.csv",
                            output_fn = "data/output/sf_samp_taxi_od_pairs.csv",
                            min_dist = min_dist,
                            max_dist = max_dist)
    random_selection_routes(od_fn = "data/output/nyc_all_taxi_od_pairs.csv",
                            output_fn = "data/output/nyc_samp_taxi_od_pairs.csv",
                            min_dist = min_dist,
                            max_dist = max_dist)


if __name__ == "__main__":
    main()