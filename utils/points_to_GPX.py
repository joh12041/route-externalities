"""Convert polyline to GPX representation for use by GraphHopper"""
import csv
import argparse
import ast

from geopy.distance import great_circle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csvs", nargs="+", help="Input CSVs with Point List")
    args = parser.parse_args()

    startTime = 0
    default_speed = 0.00555556 # 20 km/hr in m/ms
    line_no = 0
    points_skipped = 0
    
    for csvin in args.input_csvs:
        print("Processing {0}".format(csvin))
        with open(csvin, 'r') as fin:
            csvreader = csv.reader(fin)
            header = next(csvreader)
            id_idx = header.index("ID")
            name_idx = header.index("name")
            points_idx = header.index("polyline_points")
            csvout = csvin.replace(".csv", "_gpx.csv")
            with open(csvout, 'w') as fout:
                csvwriter = csv.writer(fout)
                csvwriter.writerow(['ID','name','lat','lon','millis'])
                for line in csvreader:
                    line_no += 1
                    try:
                        route_id = line[id_idx]
                        name = line[name_idx]
                        pointList = ast.literal_eval(line[points_idx])
                        prevLat = pointList[0][0]
                        prevLon = pointList[0][1]
                        time = startTime
                        csvwriter.writerow([route_id, name, prevLat, prevLon, time])
                        for pt in pointList[1:]:
                            lat = pt[0]
                            lon = pt[1]
                            if (lat, lon) == (prevLat, prevLon):
                                points_skipped += 1
                                continue
                            timeDeltaMs = int(great_circle((prevLat, prevLon), (lat, lon)).kilometers * 1000 / default_speed)
                            assert timeDeltaMs > 0
                            time += timeDeltaMs
                            csvwriter.writerow([route_id, name, lat, lon, time])
                            prevLat = lat
                            prevLon = lon
                    except SyntaxError:
                        print(line_no, line)


if __name__ == "__main__":
    main()
