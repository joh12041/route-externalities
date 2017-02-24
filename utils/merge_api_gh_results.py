import csv
import argparse
from os.path import isfile


EXPECTED_HEADER = ['ID','name','polyline_points', 'total_time_in_sec', 'total_distance_in_meters', 'number_of_steps',
                   'maneuvers', 'beauty', 'simplicity', 'pctNonHighwayTime', 'pctNonHighwayDist', 'pctNeiTime', 'pctNeiDist']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("api_csv",
                        help="Filename of CSV output from external API")
    parser.add_argument("gh_csv",
                        help="Filename of CSV output from GraphHopper Map Matching")
    parser.add_argument("output_csv",
                        help="Filename of output CSV with merged results.")
    parser.add_argument("-threshold", default=0.05, type=float,
                        help="Percent error that will be tolerated between distance results.")
    args = parser.parse_args()


    print("\nMerging {0} and {1} with {2} threshold and output to {3}".format(args.api_csv, args.gh_csv,
                                                                              args.threshold, args.output_csv))

    if not isfile(args.api_csv):
        print("{0} does not exist. Files will not be merged.".format(args.api_csv))
        return
    if not isfile(args.gh_csv):
        print("{0} does not exist. Files will not be merged.".format(args.gh_csv))
        return    

    gh_data = {}
    route_idx = EXPECTED_HEADER.index("ID")
    dist_idx = EXPECTED_HEADER.index("total_distance_in_meters")
    beauty_idx = EXPECTED_HEADER.index("beauty")
    simplicity_idx = EXPECTED_HEADER.index("simplicity")
    nhwdist_idx = EXPECTED_HEADER.index("pctNonHighwayDist")
    nhwtime_idx = EXPECTED_HEADER.index("pctNonHighwayTime")
    sntime_idx = EXPECTED_HEADER.index("pctNeiTime")
    sndist_idx = EXPECTED_HEADER.index("pctNeiDist")
    with open(args.gh_csv, 'r') as fin:
        csvreader = csv.reader(fin)
        gh_header = next(csvreader)
        assert gh_header == EXPECTED_HEADER[:len(gh_header)]
        for line in csvreader:
            try:
                route_id = line[route_idx]
                dist = float(line[dist_idx])
                beauty = float(line[beauty_idx])
                simplicity = float(line[simplicity_idx])
                non_hw_time = float(line[nhwtime_idx])
                non_hw_dist = float(line[nhwdist_idx])
                sn_time = float(line[sntime_idx])
                sn_dist = float(line[sndist_idx])
                gh_data[route_id] = {'dist':dist, 'beauty':beauty, 'simplicity':simplicity, 'non_hw_time':non_hw_time,
                                     'non_hw_dist':non_hw_dist, 'sn_time':sn_time, 'sn_dist':sn_dist}
            except ValueError:
                print("GH:", line)

    with open(args.api_csv, 'r') as fin:
        csvreader = csv.reader(fin)
        api_header = next(csvreader)
        assert api_header == EXPECTED_HEADER[:len(api_header)]
        processed = 0
        skipped = 0
        kept = 0
        with open(args.output_csv, 'w') as fout:
            csvwriter = csv.writer(fout)
            csvwriter.writerow(EXPECTED_HEADER)
            for line in csvreader:
                route_id = line[route_idx]
                try:
                    dist = float(line[dist_idx])
                    if route_id not in gh_data:
                        skipped += 1
                        continue
                    if route_id in gh_data and abs((dist - gh_data[route_id]['dist']) / dist) < args.threshold:
                        line.extend([gh_data[route_id]['beauty'], gh_data[route_id]['simplicity'],
                                     gh_data[route_id]['non_hw_time'], gh_data[route_id]['non_hw_dist'],
                                     gh_data[route_id]['sn_time'], gh_data[route_id]['sn_dist']])
                        csvwriter.writerow(line)
                        kept += 1
                    processed += 1
                except ValueError:
                    print("API:", line)

    print("{0} external API routes processed, {1} skipped, and {2} kept.".format(processed, skipped, kept))


if __name__ == "__main__":
    main()
