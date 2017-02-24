import os
import json
import argparse
from math import ceil, floor

from geojson import Polygon, Feature, FeatureCollection, dump
from shapely.geometry import shape, Point

"""
Code adapted from answer to question here:
http://gis.stackexchange.com/questions/54119/creating-square-grid-polygon-shapefile-with-python
"""

# Output directory for the county geojson grids
GRIDS_DIR = "data/grids/"
SCALE = 3

def grid(outputGridfn, xmin, xmax, ymin, ymax, gridHeight, gridWidth, boundary):

    # check all floats
    xmin = float(xmin)
    xmax = float(xmax)
    ymin = float(ymin)
    ymax = float(ymax)
    gridWidth = float(gridWidth)
    gridHeight = float(gridHeight)

    # get rows
    rows = ceil((ymax - ymin) / gridHeight)
    # get columns
    cols = ceil((xmax - xmin) / gridWidth)

    # create grid cells
    countcols = 0
    features = []
    while countcols < cols:
        # set x coordinate for this column
        grid_x_left = xmin + (countcols * gridWidth)
        countcols += 1
        # reset count for rows
        countrows = 0
        while countrows < rows:
            # update y coordinate for this row
            grid_y_bottom = ymin + (countrows * gridHeight)
            countrows += 1
            # check if grid centroid contained in county boundary
            bottomleftcorner = (grid_x_left, grid_y_bottom)
            coords = [bottomleftcorner]
            # add other three corners of gridcell before closing grid with starting point again
            for i in [(0.001, 0), (0.001, 0.001), (0, 0.001), (0, 0)]:
                coords.append((bottomleftcorner[0] + i[1], bottomleftcorner[1] + i[0]))
            intersects = False
            for corner in coords[1:]:
                if boundary.contains(Point(corner)):
                    intersects = True
                    break
            if intersects:
                properties = {'rid': round(grid_y_bottom * 10**SCALE), 'cid': round(grid_x_left * 10**SCALE)}
                features.append(Feature(geometry=Polygon([coords]), properties=properties))

    with open(outputGridfn, 'w') as fout:
        dump(FeatureCollection(features), fout)

def main():
    """Generate grids for a list of counties."""

    parser = argparse.ArgumentParser()
    parser.add_argument("features_geojson", help="Path to GeoJSON with features to be gridded.")
    parser.add_argument("output_folder", help="Folder to contain output grid GeoJSONs.")
    args = parser.parse_args()

    with open(args.features_geojson, 'r') as fin:
        features_gj = json.load(fin)

    if not os.path.isdir(GRIDS_DIR):
        os.mkdir(GRIDS_DIR)

    count = 0
    for feature in features_gj['features']:
        try:
            feature['properties']['FIPS'] = "{0}{1}".format(feature['properties']['STATE'], feature['properties']['COUNTY'])
        except:
            pass
        count += 1
        boundary = shape(feature['geometry'])
        bb = boundary.bounds

        xmin = bb[0]  # most western point
        xmax = bb[2]  # most eastern point
        ymin = bb[1]  # most southern point
        ymax = bb[3]  # most northern point

        gridHeight = 0.001
        gridWidth = 0.001
        xmin = floor(xmin * 10**SCALE) / 10**SCALE
        ymax = ceil(ymax * 10**SCALE) / 10**SCALE

        grid("{0}.geojson".format(os.path.join(args.output_folder, feature['properties']['FIPS'])),
             xmin, xmax, ymin, ymax, gridHeight, gridWidth, boundary)
        if count % 150 == 0:
            print("{0} counties complete.".format(count))


if __name__ == "__main__":
    main()