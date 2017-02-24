"""Combine two empath-grid files (e.g. Twitter and Flickr) into one."""
import csv
import argparse
import json
from math import exp, log
import os

from empath import Empath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fn_one")
    parser.add_argument("fn_two")
    parser.add_argument("fn_out")
    args = parser.parse_args()

    empath_categories = Empath().analyze("").keys()

    vals = {}
    with open(args.fn_one, 'r') as fin:
        csvreader = csv.DictReader(fin)
        for line in csvreader:
            grid_id = line['rid'] + "," + line['cid']
            vals[grid_id] = line

    with open(args.fn_two, 'r') as fin:
        csvreader = csv.DictReader(fin)
        for line in csvreader:
            grid_id = line.pop('rid') + "," + line.pop('cid')
            f1_count_words = float(vals[grid_id]['count_words'])
            f2_count_words = float(line['count_words'])
            f1_count_ugc = float(vals[grid_id]['count_ugc'])
            f2_count_ugc = float(line['count_ugc'])
            new_count_words = f1_count_words + f2_count_words
            new_count_ugc = f1_count_ugc + f2_count_ugc
            for cat in line:
                if cat in empath_categories:
                    f1_val = (exp(float(vals[grid_id][cat])) - 1) * f1_count_words
                    f2_val = (exp(float(line[cat])) - 1) * f2_count_words
                    try:
                        new_val = log(1 + ((f1_val + f2_val) / (new_count_words)))
                    except ZeroDivisionError:
                        new_val = log(1)
                    vals[grid_id][cat] = new_val
            vals[grid_id]['count_ugc'] = new_count_ugc
            vals[grid_id]['count_words'] = new_count_words

    # Shift rid, cid to first columns in file
    keys = sorted(vals[grid_id].keys())
    keys.remove('rid')
    keys.remove('cid')
    keys = ['rid','cid'] + keys 

    with open(args.fn_out, 'w') as fout:
        csvwriter = csv.DictWriter(fout, fieldnames = keys)
        csvwriter.writeheader()
        for photo in vals:
            csvwriter.writerow(vals[photo])

if __name__ == "__main__":
    main()
