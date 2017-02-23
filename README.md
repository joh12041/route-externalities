# route-externalities
An examination of externalities associated with alternative routing criteria and third-party platforms.

## Analysis Steps
1. Choose geographic area and download OSM-based road network from Mapzen
2. Generate origin-destination pairs for the study area
3. Get routes
    * Get Google and Mapquest routes for od-pairs
    * Get GraphHopper routes for od-pairs
4. Match Google and Mapquest routes to GraphHopper network for final metrics
5. Analysis
    * Route-level analyses between all routes
    * Compute signiificant differences with GraphHopper fastest routes and run community-level analyses

## Scenic Routing Preprocessing
1. Generate grid covering city area
2. Gather Flickr and Twitter data for study region
3. Score each grid cell based on Empath analysis of Flickr/Twitter data

## Safety Routing Preprocessing
1. Generate grid covering city area
2. Generate mapping of grid cells to census tracts (or equivalent) for city
3. Gather crime data for city
4. Aggregate grid data to census tract equivalent and set threshold for unsafe areas
5. Propagate blocked areas back to grid cells for GraphHopper
