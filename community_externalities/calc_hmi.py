"""Compute Household Median Income (HMI) data for the routes provided by each routing algorithm.

Contains a function for computing the weighted household median income of all census tracts passed through as
well as a function for computing the weighted household median income of areas that saw increased or decreased traffic
when comparing two alternative routing algorithms."""

import csv
import argparse
import ast
from os.path import isfile, isdir, join
from os import listdir
import math
import json
import random
import copy

from shapely.geometry import LineString, shape
import numpy

EXPECTED_HEADER = ['ID', 'name', 'polyline_points', 'total_time_in_sec', 'total_distance_in_meters',
                   'number_of_steps', 'maneuvers', 'beauty', 'simplicity', 'pctNonHighwayTime',
                   'pctNonHighwayDist', 'pctNeiTime', 'pctNeiDist']

def convert_xy_to_cr(coord, precision=3):
    """Convert polyline coordinates to column-row IDs used by grid cells.

    For example:
    35.2358 degrees north -> 35236
    74.5233 degrees west -> -74523
    """
    return round(coord * 10**precision)


def get_city(fn):
    if 'sf_' in fn.lower():
        return 'sf'
    elif 'nyc_' in fn.lower():
        return 'nyc'
    else:
        return ''


def get_routetype(fn):
    if 'taxi' in fn.lower():
        return 'taxi'
    elif 'rand' in fn.lower():
        return 'rand'
    else:
        return ''


def get_baselines(city, routetype):
    """Times for GraphHopper fastest route to compare against."""
    baseline_times = {}
    fn = "data/routes/{0}_{1}_gh_routes_fast.csv".format(city, routetype)
    with open(fn, "r") as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        route_idx = header.index("ID")
        time_idx = header.index("total_time_in_sec")
        for line in csvreader:
            try:
                baseline_times[line[route_idx]] = float(line[time_idx])
            except ValueError:
                print("File {0}. Invalid time at index {1}: {2}".format(fn, time_idx, line))
                baseline_times[line[route_idx]] = -1
    return baseline_times


def get_grid_ct_dict(fn):
    """Load in mapping of x,y coordinates to census tracts.

    Args:
        fn: path to CSV file containing mapping of grid cells to census tracts
    Returns:
        rc_to_ct: dictionary of grid cells mapped to ID of census tract ID that they intersect

    Note:
        x,y is equivalent to column,row is equivalent to lon,lat.
        Coordinates are stored as integers that are the true coordinates times 10**3 (e.g. 40.523 is stored as 40523)
    """
    rc_to_ct = {}
    with open(fn, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == ['x','y','ctidx']
        for line in csvreader:
            x = int(line[0])
            y = int(line[1])
            ct = int(line[2])
            rc_to_ct[(y,x)] = ct
    return rc_to_ct


def get_hmi_mapping(censusfn, geojsonfn):
    """Generate mapping of census tracts IDs to HMI data.

    Args:
        censusfn: path to CSV containing HMI data for census tracts.
        geojsonfn: path to GeoJSON containing census tract geography (determines census tracts indices used)
    Returns:
        ctidx_to_hmi: dictionary mapping census tract indices from GeoJSON file to HMI data from CSV
    """

    # Map Census Tract Name (some sort of unique identifier) to index at which it appears in GeoJSON
    with open(geojsonfn, 'r') as fin:
        gj = json.load(fin)
    ctid_to_idx = {}
    for i in range(0, len(gj['features'])):
        ct = gj['features'][i]
        if 'nyc' in geojsonfn:
            ctid_to_idx["{0}|{1}".format(ct['properties']['COUNTYFP'], ct['properties']['NAME'])] = i
        else:
            ctid_to_idx[ct['properties']['NAME']] = i

    # Gather HMI information for each census tract.
    ctidx_to_hmi = {}
    recalc = set()
    with open(censusfn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        if 'nyc' in geojsonfn:
            ctid_idx = header.index("County")
        else:
            ctid_idx = header.index("ID")
        hmi_idx = header.index("HMI")
        for line in csvreader:
            if 'nyc' in geojsonfn:
                ctid = "{0}|{1}".format(line[ctid_idx], line[ctid_idx + 1])  # County FIPS + additional census tract ID
            else:
                ctid = line[ctid_idx]
            try:
                idx = float(ctid_to_idx[ctid])
            except KeyError:
                ctid = '9' + ctid  # some census tracts IDs are sometimes recorded missing a 9 at the beginning
                try:
                    idx = float(ctid_to_idx[ctid])
                except KeyError:
                    print("\tMissing: ", ctid[1:])
                    continue
            try:
                hmi = float(line[hmi_idx])
                if hmi <= 0:
                    recalc.add(idx)
            except ValueError:
                recalc.add(idx)
                hmi = -1
            ctidx_to_hmi[idx] = hmi

    # Calculate HMI for census tracts without this data (e.g. parks) based on the average of their neighbors.
    if recalc:
        print("\tCalculating HMI for {0} based on neighbors".format(recalc))
        recalculated_hmis = {}
        for ft in gj['features']:
            ft['properties']['shape'] = shape(ft['geometry'])
        for idx in recalc:
            neighbors = []
            recalc_shape = gj['features'][round(idx)]['properties']['shape']
            for i in range(0, len(gj['features'])):
                if i != idx:
                    if gj['features'][i]['properties']['shape'].intersects(recalc_shape):
                        try:
                            if ctidx_to_hmi[i] > 0:
                                neighbors.append(ctidx_to_hmi[i])
                        except KeyError:
                            continue
            if neighbors:
                recalculated_hmis[idx] = numpy.average(neighbors)
        for idx in recalculated_hmis:
            ctidx_to_hmi[idx] = recalculated_hmis[idx]
    return ctidx_to_hmi


def cts_from_polyline(polyline, rc_to_ct, ct_entropy={}, weight=1):
    """Determine relative distance spent in each census tract by a route.

    Args:
        polyline: list of coordinates (e.g. [(lat1, lon1), (lat2, lon2), ...]
        rc_to_ct: Dictionary mapping gridcell row, column IDs to census tract indices
        ct_entropy: dictionary tracking the relative distance spent by all routes in each census tract
            (e.g. {<ct 3>: 7, <ct 4>: 15, ...})
        weight: weight to give a particular route.
    Returns:
        Void. Updates ct_entropy dictionary with values from the input polyline.
    """
    polyline = copy.deepcopy(polyline)
    num_coordinates = len(polyline)
    pts_processed = 0
    pts_not_found = 0
    if num_coordinates <= 2:
        for i in range(0, num_coordinates):
            y = convert_xy_to_cr(polyline[i][0])  # lat
            x = convert_xy_to_cr(polyline[i][1])  # lon
            pts_processed += 1
            try:
                ct = rc_to_ct[(y,x)]
                ct_entropy[ct] = ct_entropy.get(ct, 0) + (1 * weight)
            except KeyError:
                pts_not_found += 1
                continue
    else:
        # Coordinates flipped about for sampling line (input is GeoJSON format of lat,lon; Shapely expects x,y format)
        for i in range(0, num_coordinates):
            polyline[i] = (polyline[i][1], polyline[i][0])
        polyline = LineString(polyline)
        dist_along_line = 0
        poly_length = polyline.length
        while dist_along_line < poly_length:
            pt = polyline.interpolate(dist_along_line)
            dist_along_line += 0.0025  # this is actually in decimal degrees but provides a good level of sampling
            y = convert_xy_to_cr(pt.y)
            x = convert_xy_to_cr(pt.x)
            pts_processed += 1
            try:
                ct = rc_to_ct[(y,x)]
                ct_entropy[ct] = ct_entropy.get(ct, 0) + (1 * weight)
            except KeyError:
                pts_not_found += 1
                continue


def compute_entropy(occurence_dictionary):
    """Compute entropy of census tracts passed through.

    Args:
        occurence_dictionary: mapping of census tracts to relative distance spent - e.g. {0:18, 1:23, 2:45, ...}
    Returns:
        entropy: entropy of values in occurence_dictionary. Higher entropy reflect more uniform distribution of values.
            e.g. (2,2,2) has a higher entropy than (1,2,3)
    """
    entropy = 0
    total_count = sum(occurence_dictionary.values())
    for v in occurence_dictionary.values():
        entropy -= (v / total_count) * math.log(v / total_count, 2)
    return entropy


def compute_hmi(occurence_dictionary, ctidx_to_hmi, bootstrap=False, alpha=0.01, num_iter=1000):
    """Compute weighted HMI of census tracts passed through.

    Args:
        occurence_dictionary: mapping of census tracts to relative distance spent - e.g. {0:18, 1:23, 2:45, ...}
        ctidx_to_hmi: dictionary mapping census tract indices to household median income (HMI) data
        bootstrap: True if weighted HMI should be bootstrapped for confidence intervals
        alpha: confidence level if bootstrapping - alpha of 0.01 corresponds to 99% significance level
        num_iter: # of iterations to use for bootstrapping.
    Returns:
        hmi_stats: dictionary containing weighted mean HMI of census tracts passed through and upper and lower bounds
            if bootstrapping also used.
    """
    hmi_stats = {}
    ctindices = list(occurence_dictionary.keys())
    for ctidx in ctindices:
        try:
            if ctidx_to_hmi[ctidx] == -1:
                del(occurence_dictionary[ctidx])
                print("\tRemoved {0} from HMI calculations.".format(ctidx))
        except KeyError:
            print("\t{0} not in HMI calculations.".format(ctidx))

    num_ct_points = sum(occurence_dictionary.values())
    if bootstrap:
        hmi_w = []
        cts = []
        for k in occurence_dictionary:
            cts += [k] * occurence_dictionary[k]
        assert len(cts) == num_ct_points
        for i in range(0, num_iter):
            resampled_hmi = []
            for i in range(0, num_ct_points):
                resampled_hmi.append(ctidx_to_hmi[cts[random.randint(0, num_ct_points - 1)]])
            hmi_w.append(numpy.average(resampled_hmi))
        hmi_w = sorted(hmi_w)
        hmi_stats['LB_hmi_w'] = hmi_w[int(num_iter * (alpha / 2))]
        hmi_stats['UB_hmi_w'] = hmi_w[int(num_iter * (1 - (alpha / 2)))]
        hmi_stats['mean_hmi_w'] = hmi_w[int(num_iter*0.5)]
    else:
        hmi_w = []
        for ctidx in occurence_dictionary:
            hmi_w += [ctidx_to_hmi[ctidx]] * occurence_dictionary[ctidx]
        hmi_stats['LB_hmi_w'] = None
        hmi_stats['UB_hmi_w'] = None
        hmi_stats['mean_hmi_w'] = numpy.average(hmi_w)
    return hmi_stats


def ct_stats_geojson(geojson, rc_to_ct, ct_to_hmi):
    """Process HMI statistics for GeoJSON containing route segments and counts.

    This analysis depends on the difference in road segments taken by an alternative routing algorithm and baseline
    (e.g. fastest path) algorithm having already been computed. See utils/significant_diff_segments.py.

    Args:
        geojson: File path of GeoJSON with route segments and counts (and CIs) of routes that took each segment
        rc_to_ct: Dictionary mapping gridcell row, column IDs to census tract indices
        ct_to_hmi: Dictionary mapping census tract indices to the HMI of that census tract
    Returns:
        Void. Prints out HMI stats for both the roads favored and avoided by the routing algorithm
    """
    with open(geojson, 'r') as fin:
        segments = json.load(fin)

    ct_entropy_pos = {}
    ct_entropy_pos_LB = {}
    ct_entropy_pos_UB = {}
    ct_entropy_neg = {}
    ct_entropy_neg_LB = {}
    ct_entropy_neg_UB = {}
    segs_processed = 0
    pos_processed = 0
    neg_processed = 0
    segs_skipped = 0
    for seg in segments['features']:
        if seg['properties']['sig']:
            segs_processed += 1
            lineseg = seg['geometry']['coordinates']
            count = seg['properties']['med']
            # swap coordinates for GeoJSON specification
            for i in range(0, len(lineseg)):
                tmp = lineseg[i][0]
                lineseg[i][0] = lineseg[i][1]
                lineseg[i][1] = tmp
            # Increased traffic
            if count > 0:
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_pos, weight=count)
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_pos_LB, weight=seg['properties']['lb'])
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_pos_UB, weight=seg['properties']['ub'])
                pos_processed += 1
            # Decreased traffic
            elif count < 0:
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_neg, weight=abs(count))
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_neg_LB, weight=abs(seg['properties']['lb']))
                cts_from_polyline(lineseg, rc_to_ct, ct_entropy=ct_entropy_neg_UB, weight=abs(seg['properties']['ub']))
                neg_processed += 1
        else:
            segs_skipped += 1

    hmi_stats_pos = compute_hmi(ct_entropy_pos, ct_to_hmi, bootstrap=False)
    hmi_stats_pos_LB = compute_hmi(ct_entropy_pos_LB, ct_to_hmi, bootstrap=False)
    hmi_stats_pos_UB = compute_hmi(ct_entropy_pos_UB, ct_to_hmi, bootstrap=False)
    hmi_stats_neg = compute_hmi(ct_entropy_neg, ct_to_hmi, bootstrap=False)
    hmi_stats_neg_LB = compute_hmi(ct_entropy_neg_LB, ct_to_hmi, bootstrap=False)
    hmi_stats_neg_UB = compute_hmi(ct_entropy_neg_UB, ct_to_hmi, bootstrap=False)

    # Note: because LB and UB are computed based on change in route segments and not change in HMI, sometimes the LB
    # is higher than the UB and vice versa. This is not perfect but should not introduce any bias.
    print("\tMore Traffic: HMI: {0} [{1}-{2}]".format(round(hmi_stats_pos['mean_hmi_w'], 3),
                                                      round(min(hmi_stats_pos_LB['mean_hmi_w'],
                                                                hmi_stats_pos_UB['mean_hmi_w']), 3),
                                                      round(max(hmi_stats_pos_LB['mean_hmi_w'],
                                                                hmi_stats_pos_UB['mean_hmi_w']), 3)))
    print("\tLess Traffic: HMI: {0} [{1}-{2}]".format(round(hmi_stats_neg['mean_hmi_w'], 3),
                                                      round(min(hmi_stats_neg_LB['mean_hmi_w'],
                                                                hmi_stats_neg_UB['mean_hmi_w']), 3),
                                                      round(max(hmi_stats_neg_LB['mean_hmi_w'],
                                                                hmi_stats_neg_UB['mean_hmi_w']), 3)))

            
def ct_stats_csv(fn, rc_to_ct, ct_to_hmi, diffonly=True):
    """Process HMI statistics for CSV containing route polylines.

    This analysis provides the HMI of the routes for a particular algorithm and is most useful when compared to
    the results for the routes from the same origin-destination pairs but other routing algorithms. It also provides
    the entropy of census tracts passed through (i.e. how concentrated or dispersed the routes are)

    Args:
        fn: File path of CSV with route polylines
        rc_to_ct: Dictionary mapping gridcell row, column IDs to census tract indices
        ct_to_hmi: Dictionary mapping census tract indices to the HMI of that census tract
        diffonly: True if only include routes that differ from the fastest path baseline.
    Returns:
        Void. Prints out HMI stats for the roads taken by the routing algorithm
    """
    if diffonly:
        if 'sf' in fn:
            baseline_times = get_baselines("sf", get_routetype(fn))
        elif 'nyc' in fn:
            baseline_times = get_baselines("nyc", get_routetype(fn))
    ct_entropy = {}
    with open(fn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        polyline_idx = header.index("polyline_points")
        time_idx = header.index("total_time_in_sec")
        route_idx = header.index("ID")
        lines_processed = 0
        lines_skipped = 0
        lines_failed = 0
        for line in csvreader:
            if not diffonly or (float(line[time_idx]) > 0 and
                                        float(line[time_idx]) != baseline_times.get(line[route_idx], -1)):
                lines_processed += 1
                try:
                    cts_from_polyline(ast.literal_eval(line[polyline_idx]), rc_to_ct, ct_entropy=ct_entropy)
                except Exception:
                    lines_failed += 1
            else:
                lines_skipped += 1

    print("\t{0} lines processed and {1} failed and {2} skipped.".format(lines_processed, lines_failed, lines_skipped))
    print("\tCensus Tract entropy: {0}".format(compute_entropy(ct_entropy)))
    hmi_stats = compute_hmi(ct_entropy, ct_to_hmi, bootstrap=True)
    print("\tWeighted Census Tract Mean HMI: {0} [{1}-{2}]".format(hmi_stats['mean_hmi_w'],
                                                                   hmi_stats['LB_hmi_w'],
                                                                   hmi_stats['UB_hmi_w']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_fns", nargs="+", default=[],
                        help="CSVs (all routes) or GeoJSONs (significantly different routes from baseline) to process")
    args = parser.parse_args()

    # If folder is given, include all of the files in that folder
    if isdir(args.input_fns[0]):
        files = [join(args.input_fns[0], f) for f in listdir(args.input_fns[0]) if isfile(join(args.input_fns[0], f))]
        args.input_fns.pop(0)
        args.input_fns.extend(files)
    print("Processing:", args.input_fns)

    prev_city = None
    for input_fn in args.input_fns:
        city = get_city(input_fn)
        if not city:
            continue
        if city != prev_city:
            prev_city = city
            if city == "nyc":
                rc_to_ct = get_grid_ct_dict(fn='geometries/nyc_ct_grid.csv')
                ct_to_hmi = get_hmi_mapping(censusfn='geometries/nyc_ct_census.csv', geojsonfn="geometries/nyc_ct.geojson")
            elif city == "sf":
                rc_to_ct = get_grid_ct_dict(fn='geometries/sf_ct_grid.csv')
                ct_to_hmi = get_hmi_mapping(censusfn='geometries/sf_ct_census.csv', geojsonfn="geometries/sf_ct.geojson")
        if 'geojson' in input_fn:
            print("Computing geojson-based HMI stats for {0}".format(input_fn))
            ct_stats_geojson(input_fn, rc_to_ct, ct_to_hmi)
        elif 'csv' in input_fn:
            print("Computing csv-based HMI stats for {0}".format(input_fn))
            ct_stats_csv(input_fn, rc_to_ct, ct_to_hmi, diffonly=True)


if __name__ == "__main__":
    main()
