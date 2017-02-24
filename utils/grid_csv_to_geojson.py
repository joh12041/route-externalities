"""Convert CSV containing grid row/column IDs and category values to GeoJSON."""

import csv
import argparse

from geojson import Polygon, Feature, FeatureCollection, dump

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_in")
    parser.add_argument("-columns", nargs="+", default=[])
    args = parser.parse_args()

    with open(args.csv_in, 'r') as fin:
        csvreader = csv.reader(fin)
        header = next(csvreader)
        rid_idx = header.index('rid')
        cid_idx = header.index('cid')
        empath_indices = {}
        if not args.columns:
            for i in range(0, len(header)):
                if header[i] == 'rid' or header[i] == 'cid':
                    continue
                empath_indices[header[i]] = i
        else:
            for cat in args.columns:
                empath_indices[cat] = header.index(cat)
        features = []
        for line in csvreader:
            cid = line[cid_idx]
            rid = line[rid_idx]
            properties = {'rid':rid, 'cid':cid}
            for cat in empath_indices:
                properties[cat] = float(line[empath_indices[cat]])
            bottomleftcorner = (float(cid) / 10**3, float(rid) / 10**3)
            coords = [bottomleftcorner]
            for i in [(0.001, 0), (0.001, 0.001), (0, 0.001), (0,0)]:
                coords.append((bottomleftcorner[0] + i[1], bottomleftcorner[1] + i[0]))
            features.append(Feature(geometry=Polygon([coords]), properties=properties))

    with open(args.csv_in.replace(".csv", ".geojson"), 'w') as fout:
        dump(FeatureCollection(features), fout)


if __name__ == "__main__":
    main()
            
