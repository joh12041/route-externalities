import csv
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline_routes_fn', help="Filepath of CSV file containing baseline routes (e.g. fastest path)")
    parser.add_argument('comparison_routes_fn', help="Filepath of CSV file containing alternative routes (e.g. safety path)")
    args = parser.parse_args()

    baseline = {}
    with open(args.baseline_routes_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        time_idx = header.index("total_time_in_sec")
        rid_idx = header.index("ID")
        total_routes = 0
        valid_routes = 0
        for line in csvreader:
            total_routes += 1
            try:
                rid = line[rid_idx]
                t_sec = float(line[time_idx])
                if t_sec > 0:
                    baseline[rid] = t_sec
                    valid_routes += 1
            except ValueError:
                continue

    print("{0} routes in {1}, of which {2} had valid travel times.".format(total_routes,
                                                                           args.baseline_routes_fn,
                                                                           valid_routes))
    with open(args.comparison_routes_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        time_idx = header.index("total_time_in_sec")
        rid_idx = header.index("ID")
        total_routes = 0
        valid_routes = 0
        routes_skipped = 0
        routes_changed = 0
        for line in csvreader:
            total_routes += 1
            try:
                rid = line[rid_idx]
                t_sec = float(line[time_idx])
                if rid not in baseline:
                    routes_skipped += 1
                elif t_sec > 0:
                    valid_routes += 1
                    if baseline[rid] != t_sec:
                        routes_changed += 1
            except ValueError:
                continue

        print("{0} routes in {1}, of which {2} were skipped, "
                "{3} had valid travel times, and {4} changed.".format(total_routes,
                                                                      args.comparison_routes_fn,
                                                                      routes_skipped,
                                                                      valid_routes,
                                                                      routes_changed))


if __name__ == "__main__":
    main()
