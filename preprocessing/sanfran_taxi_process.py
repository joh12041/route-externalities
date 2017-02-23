"""Preprocess San Francisco taxi data to generate trip origins/destinations."""

# data: https://crawdad.cs.dartmouth.edu/epfl/mobility/20090224/

import csv
import datetime
import os
import sys

def process_taxi_data(taxi_data, od_pairs):
    # Assumptions:
    #  1. Taxi trip starts with the first GPS point where a taxi has a user
    #  2. Taxi trip ends with the last GPS point where the taxi has a user
    #  3. If the first GPS point for a taxi is occupied, then that trip is not included
    sorted_taxi_data = sorted(taxi_data.items())
    num_gps_points = len(sorted_taxi_data)
    prev_occupied = -1
    # loop through data until we find the first point where we know the cab to be unoccupied
    for i in range(0, num_gps_points):
        prev_occupied = sorted_taxi_data[i][1]['occ']
        if prev_occupied == 0:
            break
    # loop through rest of the data, tracking when people are picked up and dropped off
    for i in range(i, num_gps_points):
        gps_point = sorted_taxi_data[i]
        cur_occupied = gps_point[1]['occ']
        if cur_occupied != prev_occupied:
            if prev_occupied == 0:  # just picked up passenger
                global count_for_id
                count_for_id += 1
                time_string = gps_point[0]
                start_time = datetime.datetime.fromtimestamp(time_string)
                o_lat = gps_point[1]['lat']
                o_lon = gps_point[1]['lon']
            else:
                last_occupied_gps_point = sorted_taxi_data[i - 1]
                time_string = last_occupied_gps_point[0]
                end_time = datetime.datetime.fromtimestamp(time_string)
                d_lat = last_occupied_gps_point[1]['lat']
                d_lon = last_occupied_gps_point[1]['lon']
                duration_sec = (end_time - start_time).seconds
                od_id = ";".join([coord_to_id(o_lat), coord_to_id(o_lon), coord_to_id(d_lat), coord_to_id(d_lon)])
                od_pairs.append([od_id, o_lon, o_lat, d_lon, d_lat, duration_sec])
            prev_occupied = cur_occupied


def coord_to_id(coord, scale=3):
    return str(round(coord * (10**scale)))


def main():
    taxi_data_folder = "data/input/cabspottingdata/"
    output_fn = "data/output/sf_all_od_pairs.csv"
    output_header = ["ID", "origin_lon", "origin_lat", "destination_lon", "destination_lat", "duration_sec"]

    # not on actual file:
    #  file-name = unique taxi ID
    #  latitude = decimal degrees north
    #  longitude = decimal degrees west
    #  occupied = 1:yes, 0:no
    #  time = 24-hr timestamp (all from one day)
    taxi_data_header = ["latitude", "longitude", "occupied", "timestamp"]
    lat_idx = taxi_data_header.index("latitude")
    lon_idx = taxi_data_header.index("longitude")
    occ_idx = taxi_data_header.index("occupied")
    time_idx = taxi_data_header.index("timestamp")

    global count_for_id
    count_for_id = -1

    taxi_files = []
    for dirName, subdirList, fileList in os.walk(taxi_data_folder):
        for fname in fileList:
            if fname.find("new_") > -1:
                taxi_files.append(dirName + r'/' + fname)

    print("Found {0} taxi GPS traces.".format(len(taxi_files)))

    # all taxi data for a single taxi comes in a single file in reverse chronological order (most recent first)
    # procedure: gather a taxi's history and process it for origins/destinations before moving onto the next taxi_id
    #  to avoid storing all of the GPS data at once.
    with open(output_fn, 'w') as fout:
        csvwriter = csv.writer(fout)
        csvwriter.writerow(output_header)
        count = 0
        for file in taxi_files:
            od_pairs = []
            count += 1
            taxi_data = {}
            # taxi_id = file[file.find("new_") + 4 : file.find(".txt")]
            with open(file, "r") as fin:
                csvreader = csv.reader(fin, delimiter=" ")
                for line in csvreader:
                    time = int(line[time_idx])
                    lat = float(line[lat_idx])
                    lon = float(line[lon_idx])
                    occ = int(line[occ_idx])
                    assert(occ == 0 or occ == 1)  # make sure occupancy status always valid
                    taxi_data[time] = {'lat':lat, 'lon':lon, 'occ':occ}
                process_taxi_data(taxi_data, od_pairs)
                sys.stdout.write("\r{0} processed.".format(count))
                sys.stdout.flush()
            for origin_dest in od_pairs:
                csvwriter.writerow(origin_dest)


if __name__ == "__main__":
    main()
