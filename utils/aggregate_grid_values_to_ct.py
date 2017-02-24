"""Aggregate grid values to census tracts and classify as above/below a given threshold. Used for safety routing."""
import csv
import json
import argparse

import numpy

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("empath_grid_csv")
    parser.add_argument("ct_grid_csv")
    parser.add_argument("ct_geojson")
    args = parser.parse_args()

    # NOTE:
    # count_ugc = total # of all crimes committed in a grid cell
    # count_words = total # of select crimes committed in a grid cell (i.e. the other crime categories in the header)

    # San Francisco
    if '06075' in args.ct_geojson:
        crime_cutoffs = [4, 5.5, 7.4, 15, 50]  # 25%, 15%, 10%, 5%, 1%
        expected_header = ['drug/narcotic', 'count_ugc', 'kidnapping', 'vehicle theft', 'assault', 'rid', 'weapon laws',
                           'cid', 'count_words', 'sex offenses, forcible']
    # New York City
    elif 'nyc' in args.ct_geojson:
        crime_cutoffs = [2.7, 3.95, 4.95, 6.5, 10.5] # 25%, 15%, 10%, 5%, 1%
        expected_header = ['dangerous drugs', 'kidnapping & related offenses', 'cid',
                           'grand larceny of motor vehicle', 'felony assault', 'count_words', 'count_ugc',
                           'dangerous weapons', 'rid', 'assault 3 & related offenses', 'grand larceny']
    data = {}
    print("loading empath grid scores")
    with open(args.empath_grid_csv, "r") as fin:
        csvreader = csv.reader(fin)
        found_header = next(csvreader)
        num_crime_idx = found_header.index("count_words")
        cid_idx = found_header.index("cid")
        rid_idx = found_header.index("rid")
        for col in expected_header:
            assert col in found_header, "{0} not in header.".format(col)
        for line in csvreader:
            gid = "{0},{1}".format(line[cid_idx], line[rid_idx])
            num_crimes = int(line[num_crime_idx])
            data[gid] = num_crimes

    gid_to_ct = {}
    ct_to_gid = {}
    print("loading ct to grid dict")
    with open(args.ct_grid_csv, "r") as fin:
        csvreader = csv.reader(fin)
        expected_header = ["x", "y", "ctidx"]
        cid_idx = expected_header.index("x")
        rid_idx = expected_header.index("y")
        ct_idx = expected_header.index("ctidx")
        assert next(csvreader) == expected_header
        for line in csvreader:
            gid = "{0},{1}".format(line[cid_idx], line[rid_idx])
            ct = int(line[ct_idx])
            gid_to_ct[gid] = ct
            ct_to_gid[ct] = ct_to_gid.get(ct, []) + [gid]

    with open(args.ct_geojson, "r") as fin:
        cts_gj = json.load(fin)

    for crime_cutoff in crime_cutoffs:
        print("averaging crime data across census tracts")
        num_features = len(cts_gj["features"])
        ct_to_block = set()
        crime_histogram = []  # useful for determining cutoff thresholds
        for i in range(0, num_features):
            avg_crimes = []
            for gid in ct_to_gid[i]:
                if gid in data:
                    avg_crimes.append(data[gid])
            if avg_crimes:
                avg_crimes = numpy.average(avg_crimes)
                crime_histogram.append(avg_crimes)
                if avg_crimes > crime_cutoff:            
                    ct_to_block.add(i)

        num_cells_blocked = 0
        for ct in ct_to_block:
            num_cells_blocked += len(ct_to_gid[ct])
        print("Number of grid cells blocked: {0}".format(num_cells_blocked))
        print("Number of census tracts blocked: {0}".format(len(ct_to_block)))

        with open(args.empath_grid_csv.replace(".csv", "_ctaggregated_{0}.csv".format(crime_cutoff)), "w") as fout:
            csvwriter = csv.writer(fout)
            csvwriter.writerow(['rid', 'cid', 'block'])
            for gid in data:
                rid = gid.split(',')[1]
                cid = gid.split(',')[0]
                block = 0
                if gid_to_ct.get(gid, -1) in ct_to_block:
                    block = 1
                csvwriter.writerow([rid, cid, block])


if __name__ == "__main__":
    main()
