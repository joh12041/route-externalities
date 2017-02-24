# route-externalities
An examination of externalities associated with alternative routing criteria and third-party platforms.

## Origin-Destination Pair Preprocessing
1. Choose geographic area and download OSM-based road network from Mapzen
    * (https://mapzen.com/data/metro-extracts/)
2. Generate grid covering city area
    * preprocessing/grid_creation.py
3. Generate od-pairs for a grid
    * preprocessing/generate_od_pairs.py

## Scenic Routing Preprocessing
1. Gather Flickr and Twitter data for study region
2. Score each grid cell based on Empath analysis of Flickr/Twitter data
    * preprocessing/generate_grid_scores.py

## Safety Routing Preprocessing
1. Generate mapping of grid cells to census tracts (or equivalent) for city
    * utils/gridcell_to_ct_mapping.py
2. Gather crime data for city
3. Aggregate grid data to census tract equivalent and set threshold for unsafe areas
    * utils/aggregate_grid_values_to_ct.py

## Analysis Steps
1. Get Google and Mapquest routes for od-pairs
    * mapping_platforms/get_routes.py
2. Get GraphHopper routes for od-pairs
    * see https://github.com/joh12041/graphhopper
3. Match Google and Mapquest routes to GraphHopper network for final metrics
    * see https://github.com/joh12041/graphhopper
4. Merge together GraphHopper metrics and original data
    * utils/merge_api_gh_results.py
5. Route-level analyses between all routes
    * routelevel-externalities/routelevel_externalities.ipynb
6. Compute signiificant differences with GraphHopper fastest routes
    * utils/significant_diff_segments.py
7. Run community-level analyses
    * community_externalities/calc_hmi.py
