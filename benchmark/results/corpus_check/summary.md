# Whole-catalog run

121 datasets, run 2026-11-22 by `tools/corpus_check.py`, after steps were bounded by the catalog's
region when no study area is set (before that, every yellow-taxi year failed both steps).

**Note:** the preview stage here measured the old preview, every feature with every column (up to
856 MB). Previews now send geometry, the coloring column and at most 50,000 features: re-measured on
the largest datasets, 3.6–6.5 MB (forestry service requests 856 → 4.9 MB).

| Stage | OK | Failed | Slowest (s) |
|---|---|---|---|
| load | 121 | 0 | 24.14 |
| coverage | 121 | 0 | 2.18 |
| checks | 121 | 0 | 26.86 |
| step_zones | 118 | 3 | 23.58 |
| step_h3 | 119 | 2 | 21.47 |
| preview | 121 | 0 | 15.94 |
| export | 121 | 0 | 20.36 |

## Failures

- `2018_2019_school_locations` · step_zones: PlanInputError: The study area spans 115.2° of longitude, wider than one UTM zone can measure accurately (12° at most). Pass an explicit projected CRS (crs=), equal-area when areas are compared.
- `raised_crosswalk_locations` · step_zones: PlanInputError: Every source has coordinates outside longitude -180..180 and latitude -90..90 (x up to 1.05256e+06, y up to 267137), yet the CRS EPSG:4326 is geographic: the CRS is probably mislabelled. Set the right one with GeoDataFrame.set_crs(..., allow_override=True).
- `raised_crosswalk_locations` · step_h3: PlanInputError: Every source has coordinates outside longitude -180..180 and latitude -90..90 (x up to 1.05256e+06, y up to 267137), yet the CRS EPSG:4326 is geographic: the CRS is probably mislabelled. Set the right one with GeoDataFrame.set_crs(..., allow_override=True).
- `street_closures_due_to_construction_activities_by_intersection` · step_zones: PlanInputError: Every source has coordinates outside longitude -180..180 and latitude -90..90 (x up to 1.0526e+06, y up to 267762), yet the CRS EPSG:4326 is geographic: the CRS is probably mislabelled. Set the right one with GeoDataFrame.set_crs(..., allow_override=True).
- `street_closures_due_to_construction_activities_by_intersection` · step_h3: PlanInputError: Every source has coordinates outside longitude -180..180 and latitude -90..90 (x up to 1.0526e+06, y up to 267762), yet the CRS EPSG:4326 is geographic: the CRS is probably mislabelled. Set the right one with GeoDataFrame.set_crs(..., allow_override=True).

## Outside the catalog's region

- `2018_2019_school_locations`: bbox [40.4967, -74.2314, 40.904, -73.7081]
- `raised_crosswalk_locations`: bbox None
- `street_closures_due_to_construction_activities_by_intersection`: bbox None

## Checks with errors

- `2017_2018_schools_nypd_crime_data_report`: error:out_of_extent(919), error:missing_disguised(455)
- `2018_2019_school_locations`: error:coordinates_swapped(1940), error:coordinates_swapped(1940)
- `2020_doe_high_school_directory`: error:missing_disguised(110)
- `NYC_Bike_Routes`: error:missing_disguised(21978)
- `accessible_pedestrian_signal_locations`: error:missing_disguised(2077)
- `archived_nypd_shooting_incident_data_historic`: error:missing_disguised(3148), error:missing_disguised(1836)
- `canine_waste_dispensers`: error:missing_disguised(192)
- `childrens_play_areas_cpas`: error:missing_disguised(430), error:missing_disguised(374)
- `city_bench_locations_historical`: error:missing_disguised(2098), error:missing_disguised(1889), error:missing_disguised(1377)
- `exclusive_pedestrian_signal_barnes_dance_locations`: error:missing_disguised(639)
- `forestry_planting_spaces`: error:missing_disguised(54048)
- `holiday_construction_embargo_intersection`: error:missing_disguised(727)
- `leaf_drop_off_locations_in_nyc`: error:geometry_duplicate(8)
- `nyc_bridge_strike_data`: error:geometry_duplicate(744)
- `nyc_clean_soil_bank_generating_and_receiving_sites`: error:geometry_empty(23)
- `nyc_dot_pedestrian_plazas_point_feature`: error:missing_disguised(82)
- `nyc_parks_drinking_fountains`: error:missing_disguised(573)
- `nyc_parks_spray_showers`: error:missing_disguised(126)
- `nyc_veteran_owned_businesses`: error:geometry_empty(17)
- `nypd_complaint_data_current_year_to_date`: error:missing_disguised(160427), error:missing_disguised(129013), error:missing_disguised(119264), error:missing_disguised(110863)
- `nypd_criminal_court_summons_historic`: error:missing_disguised(204713), error:missing_disguised(91542)
- `nypd_criminal_court_summons_incident_level_data_year_to_date`: error:missing_disguised(12525)
- `open_storefronts_applications_historical`: error:out_of_extent(116), error:out_of_extent(116), error:geometry_duplicate(52)
- `overhead_electronic_signs`: error:missing_disguised(21)
- `parks_closure_status_due_to_covid_19_adult_exercise_equipment`: error:missing_disguised(49)
- `parks_closure_status_due_to_covid_19_athletic_facilities`: error:missing_disguised(929)
- `parks_closure_status_due_to_covid_19_comfort_stations`: error:missing_disguised(125)
- `parks_closure_status_due_to_covid_19_dog_runs`: error:missing_disguised(14)
- `parks_closure_status_due_to_covid_19_playgrounds`: error:missing_disguised(214), error:missing_disguised(206), error:missing_disguised(196)
- `parks_closure_status_due_to_covid_19_skate_parks`: error:missing_disguised(6)
- `parks_signs`: error:missing_disguised(2280)
- `pedestrian_ramp_locations`: error:missing_disguised(129055)
- `property_valuation_and_assessment_data`: error:geometry_empty(40314)
- `protected_streets_map_block_dataset`: error:missing_disguised(2974)
- `raised_crosswalk_locations`: error:crs_mislabelled(83)
- `real_time_passenger_information_sign_locations`: error:missing_disguised(494), error:missing_disguised(43)
- `scenic_landmarks`: error:geometry_invalid(2)
- `seating_locations`: error:missing_disguised(2160)
- `street_and_highway_capital_reconstruction_projects_block`: error:geometry_duplicate(1442)
- `street_closures_due_to_construction_activities_by_intersection`: error:crs_mislabelled(105), error:missing_disguised(50)
- `street_pavement_rating`: error:missing_disguised(19462)
- `street_pothole_work_orders_closed_dataset`: error:missing_disguised(48719)
- `taxicab_partition_manufacturers_and_installers`: error:geometry_empty(3)
- `tlc_approved_labcorp_patient_services_drug_test_locations`: error:out_of_extent(11), error:out_of_extent(11)

## Slowest datasets (total seconds)

- `forestry_work_orders`: 130.0 s
- `forestry_service_requests`: 116.2 s
- `property_valuation_and_assessment_data`: 75.0 s
- `forestry_planting_spaces`: 73.3 s
- `nypd_complaint_data_current_year_to_date`: 66.3 s
- `forestry_inspections`: 64.7 s
- `building_elevation_and_subgrade_bes`: 56.1 s
- `nypd_calls_for_service_historic`: 52.8 s
- `nypd_arrests_data_historic`: 50.2 s
- `forestry_tree_points`: 48.0 s
