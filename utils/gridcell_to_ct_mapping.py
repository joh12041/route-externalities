"""Output CSV with mapping of x,y coordinates to census tracts indices."""
import json
import argparse
from math import floor, ceil
import csv

from shapely.geometry import shape, box

MUST_HALF_OVERLAP = True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('geojson_fn', help="File path to the GeoJSON of census tracts.")
    parser.add_argument('output_csv', help="File path for output CSV of points and associated census tracts.")
    parser.add_argument('--precision', type=int, default=3, help="number of decimal places to round lat/lons")
    args = parser.parse_args()

    with open(args.geojson_fn, 'r') as fin:
        ct_gj = json.load(fin)

    # multiply by to quickly switch between coordinates and integer representation
    transform = 10**(args.precision)
    untransform = 1 / transform

    pts = {}
    num_cts = len(ct_gj['features'])
    for i in range(0, num_cts):
        shp = shape(ct_gj['features'][i]['geometry'])
        bounds = shp.bounds
        # Change bounding box from coordinates to integers for easier looping
        west = floor(bounds[0] * transform)
        north = ceil(bounds[3] * transform)
        east = ceil(bounds[2] * transform)
        south = floor(bounds[1] * transform)
        for dy in range(0, north - south):
            for dx in range(0, east - west):
                y = south + dy
                x = west + dx
                if MUST_HALF_OVERLAP:
                    bx = box(x*untransform, y*untransform, (x+1)*untransform, (y+1)*untransform)
                    overlap = bx.intersection(shp).area
                    if overlap > 0.5 * untransform * untransform:
                        pts[(x, y)] = i
                else:
                    if shp.contains((y*untransform, x*untransform)):
                        pts[(x, y)] = i
        print("Processed {0} of {1}. {2} points.".format(i, num_cts, len(pts)))

    with open(args.output_csv, 'w') as fout:
        csvwriter = csv.writer(fout)
        csvwriter.writerow(['x','y','ctidx'])
        for pt in pts:
            csvwriter.writerow([pt[0], pt[1], pts[pt]])

if __name__ == "__main__":
    main()
