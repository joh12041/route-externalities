"""Generate grid cell scores from Empath analysis of user-generated content."""
import csv
import json
import argparse
import re
import traceback
from math import floor

from nltk.stem import WordNetLemmatizer
import numpy
from shapely.geometry import shape, box, point
from empath import Empath

SCALE = 3

def preprocess_ugc(ugc, repo, lemmatizer):
    """Perform text preprocessing steps on tweet or photo tags

    For maximum recall with Empath: lower-case + lemmatized

    Args:
        ugc: String containing photo tags or tweet text
        repo: flickr or twitter
        lemmatizer: lemmatizer object to be used

    Returns:
        A list of preprocessed text, either words for a tweet or tags for a photo.
        For example,
            "This was a tweet" >> ['this', 'wa', 'a', tweet']
            "{beautiful+city,i+love+sunsets}" >> ['beautiful city', 'i love sunset']
    """

    if repo == "flickr":
        # list of tags
        ugc = ugc.strip("{}").lower().split(',')
        num_tags = len(ugc)
        for i in range(0, num_tags):
            tag = ugc[i].split("+")
            for j in range(0, len(tag)):
                tag[j] = lemmatizer.lemmatize(tag[j])
            ugc[i] = " ".join(tag)
    elif repo == "twitter":
        # list of words
        ugc = re.split("\W+", ugc.lower())
        num_words = len(ugc)
        for i in range(0, num_words):
            ugc[i] = lemmatizer.lemmatize(ugc[i])
    elif repo == "crime":
        ugc = ugc.strip().lower()
    return ugc


def analyze_ugc(gridcells, key, ugc, user, lexicon, repo, categories, first_ugc_only=False):
    """Analyze UGC and update gridcells.

    Only first UGC from a user retained for a grid cell

    Args:
        gridcells: dictionary of gridcells with appropriate statistics
        key: gridcell to be updated
        ugc: list of tags or words depending on repository
        user: userID string to prevent multiple UGC from a user in a cell
        lexicon: Empath lexicon
        repo: UGC repository - either flickr, twitter, or placepulse
        categories: Empath categories to include in analysis
        first_ugc_only: if True, only include first post from any user for a cell

    Returns:
        Void, updates gridcell dictionary appropriately
    """

    if first_ugc_only:
        if user in gridcells[key]['users']:
            return
        else:
            gridcells[key]['users'].add(user)

    if repo == 'twitter' or repo == 'flickr':
        emotions = lexicon.analyze(ugc, categories=categories)
        gridcells[key]['count_ugc'] += 1
        gridcells[key]['count_words'] += len(ugc)
        for category in emotions:
            gridcells[key][category] += emotions[category]
    elif repo == "crime":
        gridcells[key]['count_ugc'] += 1
        if ugc in gridcells[key]:
            gridcells[key]['count_words'] += 1
            gridcells[key][ugc] += 1
    else:
        print("Do not recognize repo {0}.".format(repo))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ugc_fn",
                        help="File path of the CSV file containing UGC for the city.")
    parser.add_argument("grid_geojson_fn",
                        help="File path of the GeoJSON file containing the grid cells for the city.")
    parser.add_argument("--first_ugc_only", action="store_true",
                        help="Store only the first piece of UGC from a user for each grid cell.")
    args = parser.parse_args()

    lexicon = Empath()

    fraction = True
    if 'flickr' in args.ugc_fn.lower():
        expected_header = ['id', 'uid', 'user_tags', 'lat', 'lon']
        ugc_idx = expected_header.index('user_tags')  # tags applied to photo by user
        uid_idx = expected_header.index('uid')  # flickr user who uploaded photo
        repo = "flickr"
        categories = lexicon.analyze("").keys()
    elif 'twitter' in args.ugc_fn.lower() or 'tweets' in args.ugc_fn.lower():
        expected_header = ['id', 'uid', 'text', 'lat', 'lon']
        ugc_idx = expected_header.index('text')  # tweet text
        uid_idx = expected_header.index('uid')  # twitter user who posted tweet
        repo = "twitter"
        categories = lexicon.analyze("").keys()
    elif 'crime' in args.ugc_fn.lower() or 'complaint' in args.ugc_fn.lower():
        repo = "crime"
        if 'sf' in args.ugc_fn.lower():
            expected_header = ['IncidntNum', 'Category', 'Descript', 'DayOfWeek', 'Date',
                               'Time', 'PdDistrict', 'Resolution', 'Address', 'X', 'Y', 'Location']
            date_idx = expected_header.index("Date")
            ugc_idx = expected_header.index("Category")
            uid_idx = expected_header.index("IncidntNum")
            categories = ['assault', 'vehicle theft', 'kidnapping', 'drug/narcotic', 'weapon laws',
                          'sex offenses, forcible']
        elif 'nyc' in args.ugc_fn.lower():
            expected_header = ['CMPLNT_NUM', 'CMPLNT_FR_DT', 'CMPLNT_FR_TM', 'CMPLNT_TO_DT', 'CMPLNT_TO_TM', 'RPT_DT',
                               'KY_CD', 'OFNS_DESC', 'PD_CD', 'PD_DESC', 'CRM_ATPT_CPTD_CD', 'LAW_CAT_CD', 'JURIS_DESC',
                               'BORO_NM', 'ADDR_PCT_CD', 'LOC_OF_OCCUR_DESC', 'PREM_TYP_DESC', 'PARKS_NM', 'HADEVELOPT',
                               'X_COORD_CD', 'Y_COORD_CD', 'lat', 'lon', 'Lat_Lon']
            date_idx = expected_header.index("CMPLNT_TO_DT")
            ugc_idx = expected_header.index("OFNS_DESC")
            uid_idx = expected_header.index("CMPLNT_NUM")
            categories = ['assault 3 & related offenses', 'grand larceny', 'dangerous drugs', 'felony assault',
                          'grand larceny of motor vehicle', 'dangerous weapons', 'kidnapping & related offenses']
        fraction = False
    else:
        raise Exception("source not recognized - must have 'flickr', 'twitter', 'crime' or 'complaint' in filename")
    try:
        lat_idx = expected_header.index('lat')
        lon_idx = expected_header.index('lon')
    except ValueError:
        lat_idx = expected_header.index('Y')
        lon_idx = expected_header.index('X')
    print("Analyzing {0} and {1}.".format(args.ugc_fn, args.grid_geojson_fn))

    # Load in grid cells
    with open(args.grid_geojson_fn, 'r') as fin:
        grid = json.load(fin)

    # Load in grid cells and compute bounding box that contains all of them
    bb_south = float("Inf")
    bb_north = float("-Inf")
    bb_east = float("-Inf")
    bb_west = float("Inf")
    gridcells = {}
    for gridcell in grid['features']:
        rid = gridcell['properties']['rid']
        cid = gridcell['properties']['cid']
        grid_shape = shape(gridcell['geometry'])
        grid_bb = grid_shape.bounds
        bb_south = min(bb_south, grid_bb[1])  # miny
        bb_north = max(bb_north, grid_bb[3])  # maxy
        bb_east = max(bb_east, grid_bb[0])  # maxx
        bb_west = min(bb_west, grid_bb[2])  # minx
        gridcells[(rid, cid)] = {'rid': rid, 'cid': cid, 'shape': grid_shape, 'count_ugc': 0, 'count_words': 0,
                                 'users': set()}
        for cat in categories:
            gridcells[(rid, cid)][cat] = 0

    keyset = list(gridcells[(rid, cid)].keys())
    for cat_to_not_output in ['users', 'shape']:
        keyset.remove(cat_to_not_output)

    # if UGC or crime data outside of this, then it can be skipped
    county_bb = box(bb_west, bb_south, bb_east, bb_north)

    # Process UGC
    points_analyzed = 0
    found_first_try = 0
    points_skipped = 0
    no_lat_lon = 0
    not_found = 0
    lemmatizer = WordNetLemmatizer()
    adj_idx = [0, 1, -1, 2, -2, 3, -3]
    with open(args.ugc_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == expected_header
        for line in csvreader:
            try:
                # crime must have been committed in past year
                if repo == 'crime' and "2016" not in line[date_idx]:
                    continue
                y = float(line[lat_idx])
                x = float(line[lon_idx])
                pt = point.Point(x, y)
                if not county_bb.contains(pt):
                    points_skipped += 1
                    continue
                ugc = preprocess_ugc(line[ugc_idx], repo, lemmatizer)
            except ValueError:
                no_lat_lon += 1
                if repo != 'crime':  # some crimes have no lat-lon for anonymity or lack of data
                    traceback.print_exc()
                    print(line)

            found = False
            user = line[uid_idx]
            best_guess = (floor(y * 10 ** SCALE), floor(x * 10 ** SCALE))  # likely grid cell containing data
            for i in adj_idx:  # try best guess and then three grid cells to either side
                for j in adj_idx:
                    try:
                        if gridcells[(best_guess[0] + i, best_guess[1] + j)]['shape'].contains(pt):
                            analyze_ugc(gridcells, (best_guess[0] + i, best_guess[1] + j), ugc, user, lexicon, repo,
                                        categories, args.first_ugc_only)
                            found = True
                            break
                    except KeyError:
                        continue
                if found:
                    break
            if not found:
                not_found += 1
            else:
                if i == 0 and j == 0:
                    found_first_try += 1
            points_analyzed += 1
            if points_analyzed % 10000 == 0:
                print("{0} points analyzed: {1} found first try, {2} not found, {3} skipped "
                      "and {4} missing x-y coords.".format(points_analyzed, found_first_try,
                                                           not_found, points_skipped, no_lat_lon))

    # All UGC processed, convert counts to logged fractions of words that were in that category
    if fraction:
        for gc in gridcells:
            if gridcells[gc]['count_ugc'] > 0:
                if gridcells[gc]['count_words'] > 0:
                    for cat in categories:
                        fraction_cat = gridcells[gc][cat] / gridcells[gc]['count_words']
                        gridcells[gc][cat] = numpy.log(fraction_cat + 1)

    # Dump output to CSV
    csv_out_fn = args.grid_geojson_fn.replace(".geojson", "_{0}_empath.csv".format(repo))
    with open(csv_out_fn, 'w') as fout:
        csvwriter = csv.DictWriter(fout, fieldnames=keyset, extrasaction="ignore")
        csvwriter.writeheader()
        for gc in grid['features']:
            rid = gc['properties']['rid']
            cid = gc['properties']['cid']
            gc['properties']['count_ugc'] = gridcells[(rid, cid)]['count_ugc']
            gc['properties']['count_words'] = gridcells[(rid, cid)]['count_words']
            for cat in categories:
                gc['properties'][cat] = gridcells[(rid, cid)][cat]
            csvwriter.writerow(gc['properties'])


if __name__ == "__main__":
    main()
