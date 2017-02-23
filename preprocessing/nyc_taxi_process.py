"""Preprocess NYC taxi data to generate trip origins/destinations."""

# data: http://www.nyc.gov/html/tlc/html/about/trip_record_data.shtml

import csv
import datetime
import os
import sys

def main():
    taxi_data_folder = "data/input/nyc_taxi_data/"
    output_fn = "data/output/nyc_all_od_pairs.csv"
    output_header = ["ID", "origin_lon", "origin_lat", "destination_lon", "destination_lat", "duration_sec"]

    # along with many other columns:
    #  no unique taxi ID
    #  Pickup_latitude = decimal degrees north
    #  Pickup_longitude = decimal degrees west
    #  Dropoff_latitude = decimal degrees north
    #  Dropoff_longitude = decimal degrees west
    #  lpep_pickup_datetime = YYYY-MM-DD HH:MM:SS (e.g., 2015-01-01 00:34:42)
    #  Lpep_dropoff_datetime = YYYY-MM-DD HH:MM:SS (e.g., 2015-01-01 00:34:42)
    #  Payment_type = 6 when trip was voided

    green_taxi_data_header = ['VendorID','lpep_pickup_datetime','Lpep_dropoff_datetime','Store_and_fwd_flag',
                              'RateCodeID','Pickup_longitude','Pickup_latitude','Dropoff_longitude','Dropoff_latitude',
                              'Passenger_count','Trip_distance','Fare_amount','Extra','MTA_tax','Tip_amount','Tolls_amount',
                              'Ehail_fee','improvement_surcharge','Total_amount','Payment_type','Trip_type']
    yellow_taxi_data_header = ['VendorID','tpep_pickup_datetime','tpep_dropoff_datetime','passenger_count','trip_distance',
                               'pickup_longitude','pickup_latitude','RateCodeID','store_and_fwd_flag','dropoff_longitude',
                               'dropoff_latitude','payment_type','fare_amount','extra','mta_tax','tip_amount',
                               'tolls_amount','improvement_surcharge','total_amount']
    for header in [green_taxi_data_header, yellow_taxi_data_header]:
        for i in range(0, len(header)):
            header[i] = header[i].lower()

    g_o_lat_idx = green_taxi_data_header.index("pickup_latitude")
    g_o_lon_idx = green_taxi_data_header.index("pickup_longitude")
    g_o_time_idx = green_taxi_data_header.index("lpep_pickup_datetime")
    g_d_lat_idx = green_taxi_data_header.index("dropoff_latitude")
    g_d_lon_idx = green_taxi_data_header.index("dropoff_longitude")
    g_d_time_idx = green_taxi_data_header.index("lpep_dropoff_datetime")
    y_o_lat_idx = yellow_taxi_data_header.index("pickup_latitude")
    y_o_lon_idx = yellow_taxi_data_header.index("pickup_longitude")
    y_o_time_idx = yellow_taxi_data_header.index("tpep_pickup_datetime")
    y_d_lat_idx = yellow_taxi_data_header.index("dropoff_latitude")
    y_d_lon_idx = yellow_taxi_data_header.index("dropoff_longitude")
    y_d_time_idx = yellow_taxi_data_header.index("tpep_dropoff_datetime")
    time_format = "%Y-%m-%d %H:%M:%S"

    count_for_id = -1

    taxi_files = []
    for dirName, subdirList, fileList in os.walk(taxi_data_folder):
        for fname in fileList:
            if fname.find("tripdata") > -1:
                taxi_files.append(dirName + r'/' + fname)

    print("Found {0} taxi GPS files.".format(len(taxi_files)))

    # all taxi data for a single taxi comes in a single file in reverse chronological order (most recent first)
    # procedure: gather a taxi's history and process it for origins/destinations before moving onto the next taxi_id
    #  to avoid storing all of the GPS data at once.
    with open(output_fn, 'w') as fout:
        csvwriter = csv.writer(fout)
        csvwriter.writerow(output_header)
        total_lines = 0
        for file in taxi_files:
            print("Processing {0}.".format(file))
            if 'green' in file:
                o_lat_idx = g_o_lat_idx
                o_lon_idx = g_o_lon_idx
                o_time_idx = g_o_time_idx
                d_lat_idx = g_d_lat_idx
                d_lon_idx = g_d_lon_idx
                d_time_idx = g_d_time_idx
                header = green_taxi_data_header
            elif 'yellow' in file:
                o_lat_idx = y_o_lat_idx
                o_lon_idx = y_o_lon_idx
                o_time_idx = y_o_time_idx
                d_lat_idx = y_d_lat_idx
                d_lon_idx = y_d_lon_idx
                d_time_idx = y_d_time_idx
                header = yellow_taxi_data_header
            else:
                print("{0} is an invalid taxi data file.".format(file))
                continue

            # round lat/lons to six digits to match other GPS files and more realistic precision.
            # procedure: pull necessary data from each row of NYC trip data and standardize format for further analysis
            with open(file, "r") as fin:
                csvreader = csv.reader(fin)
                file_header = next(csvreader)
                for i in range(0, len(file_header)):
                    file_header[i] = file_header[i].lower().strip()
                assert file_header == header
                for line in csvreader:
                    total_lines += 1
                    count_for_id += 1
                    o_time = datetime.datetime.strptime(line[o_time_idx], time_format)
                    o_lat = round(float(line[o_lat_idx]), 6)
                    o_lon = round(float(line[o_lon_idx]), 6)
                    d_time = datetime.datetime.strptime(line[d_time_idx], time_format)
                    d_lat = round(float(line[d_lat_idx]), 6)
                    d_lon = round(float(line[d_lon_idx]), 6)
                    duration_secs = (d_time - o_time).seconds
                    ny_id = "NY_ID" + str(count_for_id)
                    csvwriter.writerow([ny_id, o_lon, o_lat, d_lon, d_lat, duration_secs])
                    if total_lines % 100000 == 0:
                        sys.stdout.write("\r{0} processed.".format(total_lines))
                        sys.stdout.flush()


if __name__ == "__main__":
    main()
