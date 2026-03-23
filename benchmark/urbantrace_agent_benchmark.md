# UrbanTrace Agent Benchmark Corpus (Reconciled)

This aggregate document summarizes the current benchmark corpus under `benchmark/cases/` and replaces the older partial aggregate write-up. It is intended as a source-grounded overview of the benchmark set the agent is expected to handle.

## Reconciliation notes

- Total case files currently summarized here: **25**
- Source of truth for case framing: the per-case markdown files in `benchmark/cases/`
- `benchmark/index.json` remains useful for seed metadata, but it currently omits Cases **14–17**; those cases are included here from the case corpus so this overview is not stale.
- Status, theme, query framing, expected datasets, distractors, and caveat summaries were refreshed to match the current per-case documents as closely as possible without inventing unsupported claims.

## Corpus overview

- Coverage spans mobility safety, environmental burden, climate resilience, public-service access, economic opportunity, accessibility, and multi-burden prioritization.
- Many revised cases now explicitly test geography harmonization: Sub-Borough Areas, NTAs, MODZCTAs, community districts, point events, and sampled counts are not interchangeable.
- Cases 21–25 expand the corpus into commercial-corridor support, DYCD workforce access, older-adult service coverage, heat-resilience cooling assets, and accessible crossing support.

## Case 1 — Pedestrian safety risk screening

- **Status:** revised
- **Theme:** mobility / safety
- **Benchmark query:** Which NYC neighborhoods appear to have especially high pedestrian safety risk, based on crash history and pedestrian activity?
- **Expected datasets:** `NYC_vehicle_collisions_crashes`, `NYC_pedestrian_counts`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_automated_traffic_volume_counts`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection + geography harmonization, not just for naming a safety dataset.
- **Source grounding:** Vision Zero: DOT Releases Update to Borough Pedestrian Safety Action Plans, With Targeted Analysis of Priority Corridors and Intersections; Bi-Annual Pedestrian Counts

## Case 2 — Bike safety and infrastructure mismatch

- **Status:** revised
- **Theme:** mobility / safety
- **Benchmark query:** Where does bike activity appear high but bike infrastructure seem limited or safety outcomes still look poor?
- **Expected datasets:** `NYC_bicycle_counts`, `NYC_Bike_Routes`, `NYC_vehicle_collisions_crashes`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_pedestrian_counts`, `NYC_automated_traffic_volume_counts`
- **Why it matters:** This case is credible because the local catalog contains a realistic three-part planning stack:
- **Source grounding:** NYC DOT — Bike Network and Ridership; Safe Streets for Cycling

## Case 3 — Traffic burden near vulnerable communities

- **Status:** revised draft
- **Theme:** mobility / equity / environmental justice
- **Benchmark query:** Which communities face heavy traffic exposure while also showing higher socioeconomic vulnerability?
- **Expected datasets:** `NYC_automated_traffic_volume_counts`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_population`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `MODZCTA`, `City_Council_Districs`
- **Why it matters:** This is a source-grounded transportation-equity / environmental-burden selection problem.
- **Source grounding:** New York City Community Air Survey; The public health impacts of PM2.5 from traffic air pollution

## Case 4 — Air pollution and neighborhood disadvantage

- **Status:** revised
- **Theme:** environment / equity
- **Benchmark query:** Which neighborhoods combine worse air pollution with higher poverty or unemployment?
- **Expected datasets:** `NYC_air_pollution`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_HVI`, `NYC_population`
- **Why it matters:** This is a strong benchmark for dataset selection under geography mismatch, not just for naming an air-quality file.
- **Key workflow / caveat:** A strong benchmark answer should not assume that NTAs are the right join target.
- **Source grounding:** New York City Community Air Survey; New York City’s Environmental Justice for All Report Scope of Work

## Case 5 — Heat vulnerability and public resource access

- **Status:** revised
- **Theme:** climate / public services
- **Benchmark query:** Which areas with high heat vulnerability may need more nearby public resources such as libraries or schools that could support resilience planning?
- **Expected datasets:** `NYC_HVI`, `NYC_libraries`, `NYC_Schools`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_Wi-Fi_Hotspot_Locations`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection under proxy reasoning and geography mismatch, not just for naming the heat layer.
- **Key workflow / caveat:** The previous draft treated NTA as the obvious common geography.
- **Source grounding:** Interactive heat vulnerability index – Environment & Health Data Portal; 2025 Heat Mortality Report

## Case 6 — Digital divide and public access points

- **Status:** revised
- **Theme:** digital equity / public services
- **Benchmark query:** Where might residents have weaker digital access and therefore greater need for public Wi‑Fi and library support?
- **Expected datasets:** `NYC_Wi-Fi_Hotspot_Locations`, `NYC_libraries`, `NYC_poverty_rate`, `NYC_population`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_Schools`, `MODZCTA`
- **Why it matters:** This is a benchmark for dataset selection, proxy reasoning, and geography discipline under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The previous draft treated NTA_Neighborhood_Tabulation_Areas as an expected core layer.
- **Source grounding:** Digital Equity - NYC Office of Technology and Innovation; The New York City Digital Equity Roadmap

## Case 7 — School siting relative to vulnerable populations

- **Status:** revised
- **Theme:** public services / equity
- **Benchmark query:** Which neighborhoods have high population and social vulnerability but comparatively fewer school locations nearby?
- **Expected datasets:** `NYC_Schools`, `NYC_population`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `MODZCTA`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection under geography mismatch and proxy discipline.
- **Key workflow / caveat:** The current draft leaned toward NTA geography because NYC_Schools contains nta2020.
- **Source grounding:** Barriers to Learning: Age, Accessibility, Space Usage, and Air Conditioning in NYC School Buildings; Accessible NYC 2025: An Accessibility Guide for City Agencies

## Case 8 — Library access under poverty burden

- **Status:** revised
- **Theme:** public services / equity
- **Benchmark query:** Which neighborhoods with higher poverty rates appear underserved by libraries?
- **Expected datasets:** `NYC_libraries`, `NYC_poverty_rate`, `NYC_population`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_Wi-Fi_Hotspot_Locations`, `MODZCTA`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and proxy interpretation under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The previous draft listed NTA_Neighborhood_Tabulation_Areas as an expected core layer.
- **Source grounding:** Public Libraries | New York City Preliminary Mayor’s Management Report FY2026; Digital Equity - NYC Office of Technology and Innovation

## Case 9 — Housing stress and unemployment overlap

- **Status:** revised
- **Theme:** housing / inequality
- **Benchmark query:** Which neighborhoods combine housing pressure with higher unemployment and poverty?
- **Expected datasets:** `NYC_housing_units`, `NYC_unemployment_rate`, `NYC_poverty_rate`, `NYC_population`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_income_diversity_ratio`, `MODZCTA`
- **Why it matters:** This benchmark is really about proxy discipline, geography discipline, and explanation quality under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The prior draft listed NTA_Neighborhood_Tabulation_Areas as a core layer and implied NYC_housing_units was the primary housing-side dataset.
- **Source grounding:** New Yorkers in Need: The Housing Insecurity Crisis; Economic conditions data for NYC – Environment & Health Data Portal

## Case 10 — Income diversity and public amenity mismatch

- **Status:** revised
- **Theme:** inequality / public services
- **Benchmark query:** Are there neighborhoods with low income diversity that also seem underserved by public amenities like libraries or Wi‑Fi hotspots?
- **Expected datasets:** `NYC_income_diversity_ratio`, `NYC_libraries`, `NYC_Wi-Fi_Hotspot_Locations`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_population`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and proxy interpretation under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The earlier draft treated NTA_Neighborhood_Tabulation_Areas as an expected core layer.
- **Source grounding:** The New York City Digital Equity Roadmap; Public Libraries | New York City Preliminary Mayor’s Management Report FY2026

## Case 11 — Arrest patterns and social conditions

- **Status:** revised
- **Theme:** public safety / equity
- **Benchmark query:** Which neighborhoods show elevated arrest activity alongside high poverty or unemployment?
- **Expected datasets:** `NYPD_arrests_data`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_population`
- **Common distractors:** `NTA_Neighborhood_Tabulation_Areas`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and interpretation control under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The seed metadata lists NTA_Neighborhood_Tabulation_Areas as an expected relevant dataset, but the actual repo evidence says the cleaner first-pass comparison unit is the sub-borough-area geography already shared by the social-condition layers:
- **Source grounding:** Color Contrast: Racial and Ethnic Disparities in New York City Law Enforcement; Reports & Analysis – Crime & Enforcement

## Case 12 — Councils with greatest compounded need

- **Status:** revised
- **Theme:** governance / prioritization
- **Benchmark query:** Which City Council districts appear to face the greatest combined burden from poverty, unemployment, pollution, and crash risk?
- **Expected datasets:** `City_Council_Districs`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_air_pollution`, `NYC_vehicle_collisions_crashes`
- **Common distractors:** `NYC_population`, `NYC_HVI`
- **Why it matters:** This is a benchmark for cross-domain dataset selection, geography harmonization, and composite-prioritization discipline under the current UrbanTrace copilot design.
- **Key workflow / caveat:** The seed correctly points to City Council districts as the governance target, but the repo evidence shows that the burden layers do not share that geography natively.
- **Source grounding:** Poverty Measure – NYC Opportunity; New York City Community Air Survey

## Case 13 — ZIP-based screening for vulnerable service gaps

- **Status:** revised
- **Theme:** service planning / geography discipline
- **Benchmark query:** At the ZIP-code level, where do high vulnerability indicators coincide with weaker public service coverage?
- **Expected datasets:** `NYC_HVI`, `NYC_Wi-Fi_Hotspot_Locations`, `NYC_libraries`, `citywide_public_computer_centers`
- **Common distractors:** `MODZCTA`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_Schools`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and benchmark honesty under the current UrbanTrace copilot design.
- **Key workflow / caveat:** This is the core correction for the case.
- **Source grounding:** Interactive heat vulnerability index; Digital Equity - NYC Office of Technology and Innovation

## Case 14 — Climate vulnerability and air pollution overlap

- **Status:** drafted
- **Theme:** climate / environment
- **Benchmark query:** You are helping a public-health or climate-equity analyst identify NYC neighborhoods where higher heat vulnerability and worse ambient air pollution overlap.
- **Expected datasets:** `NYC_HVI`, `NYC_air_pollution`
- **Common distractors:** `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_population`, `NTA_Neighborhood_Tabulation_Areas`
- **Why it matters:** This is a benchmark for cross-domain environmental burden reasoning under geography mismatch, not just for naming two plausible datasets.
- **Key workflow / caveat:** Use NYC_HVI and NYC_air_pollution, but make the geography mismatch explicit before any overlap screen.
- **Index reconciliation note:** present in `benchmark/cases/` but currently missing from `benchmark/index.json`.

## Case 15 — Neighborhoods needing safer routes to schools

- **Status:** revised
- **Theme:** mobility / child safety
- **Benchmark query:** Which school-rich areas also show heavy traffic or collision concerns that might motivate safer-route interventions?
- **Expected datasets:** `NYC_Schools`, `NYC_vehicle_collisions_crashes`, `NYC_automated_traffic_volume_counts`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_pedestrian_counts`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for dataset selection + scale discipline + policy-grounded interpretation.
- **Key workflow / caveat:** Roll the three point layers up to NTAs and treat the result as school-safety screening, not a route audit.
- **Source grounding:** NYC DOT — School Safety; DDC Feature: Safe Routes to School
- **Index reconciliation note:** present in `benchmark/cases/` but currently missing from `benchmark/index.json`.

## Case 16 — Pedestrian demand versus civic support assets

- **Status:** revised
- **Theme:** mobility / public services
- **Benchmark query:** Which areas have heavy pedestrian activity but relatively limited nearby civic resources such as libraries or public Wi‑Fi?
- **Expected datasets:** `NYC_pedestrian_counts`, `NYC_libraries`, `NYC_Wi-Fi_Hotspot_Locations`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_population`, `NYC_Schools`, `City_Council_Districs`, `seating_locations`
- **Why it matters:** This is a benchmark for dataset selection + geography discipline + interpretation discipline.
- **Key workflow / caveat:** Aggregate pedestrian counts, libraries, and Wi-Fi hotspots to NTAs and interpret the output as a civic-support screening layer.
- **Source grounding:** NYC DOT — Pedestrian Mobility Plan; NYC DOT — NYC Streets Plan
- **Index reconciliation note:** present in `benchmark/cases/` but currently missing from `benchmark/index.json`.

## Case 17 — Small business activity and neighborhood context

- **Status:** revised
- **Theme:** economic development
- **Benchmark query:** How do business license locations align with neighborhood population, unemployment, and poverty patterns?
- **Expected datasets:** `NYC_Issued_Licenses`, `NYC_population`, `NYC_unemployment_rate`, `NYC_poverty_rate`
- **Common distractors:** `NTA_Neighborhood_Tabulation_Areas`, `City_Council_Districs`, `MODZCTA`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and interpretation discipline under the current UrbanTrace copilot design.
- **Key workflow / caveat:** Anchor the first pass on the shared sub-borough socioeconomic polygons, not on NTA fields embedded in the license file.
- **Source grounding:** Neighborhood 360° - SBS; Commercial District Needs Assessments - SBS
- **Index reconciliation note:** present in `benchmark/cases/` but currently missing from `benchmark/index.json`.

## Case 18 — Bike routes in environmentally burdened areas

- **Status:** revised
- **Theme:** mobility / environment
- **Benchmark query:** Which NYC areas with worse air-pollution burden appear to have weaker bike-route support?
- **Expected datasets:** `NYC_air_pollution`, `NYC_Bike_Routes`, `NYC_bicycle_counts`
- **Common distractors:** `NTA_Neighborhood_Tabulation_Areas`, `NYC_HVI`, `NYC_vehicle_collisions_crashes`
- **Why it matters:** This is a benchmark for dataset selection, geography discipline, and interpretation discipline under the current UrbanTrace copilot design.
- **Key workflow / caveat:** Use air-pollution burden plus bike-route supply and optional bicycle-count context, but avoid assuming NTA is the natural shared geography.
- **Source grounding:** New York City Community Air Survey (NYCCAS); New York City’s Environmental Justice for All Report Scope of Work

## Case 19 — Population concentration and service density

- **Status:** revised
- **Theme:** public services / capacity
- **Benchmark query:** Which high-population neighborhoods may have relatively sparse coverage of libraries, schools, or Wi-Fi hotspots?
- **Expected datasets:** `NYC_population`, `NYC_libraries`, `NYC_Wi-Fi_Hotspot_Locations`, `NYC_Schools`
- **Common distractors:** `NTA_Neighborhood_Tabulation_Areas`, `MODZCTA`, `City_Council_Districs`
- **Why it matters:** This is a benchmark for population-pressure reasoning, service-proxy discipline, and geography harmonization under the current UrbanTrace copilot design.
- **Key workflow / caveat:** Use the shared population geography first, then compare counts of libraries, schools, and Wi-Fi assets as service-density proxies.
- **Source grounding:** Population Reports — NYC Planning; Population Changes in NYC Neighborhoods — NYC Planning

## Case 20 — Multi-burden neighborhood screening

- **Status:** revised
- **Theme:** composite prioritization
- **Benchmark query:** You are helping a city analyst identify NYC neighborhoods for priority intervention where multiple burdens overlap: poverty, unemployment, heat vulnerability, ambient air pollution, and traffic safety harm.
- **Expected datasets:** `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_HVI`, `NYC_air_pollution`, `NYC_vehicle_collisions_crashes`
- **Common distractors:** `NYC_population`, `MODZCTA`, `City_Council_Districs`, `raw traffic volume datasets`
- **Why it matters:** This is not a one-table lookup task.
- **Key workflow / caveat:** Choose a reporting geography, aggregate crashes, select a time slice for air pollution, crosswalk HVI, then normalize the burden measures before combining them.

## Case 21 — Commercial corridors needing public-realm support

- **Status:** drafted
- **Theme:** economic development / public realm
- **Benchmark query:** Which pedestrian-rich business areas appear to have relatively little visible public-realm support such as Open Streets or pedestrian plazas?
- **Expected datasets:** `NYC_pedestrian_counts`, `NYC_Issued_Licenses`, `open_streets_locations`, `nyc_dot_pedestrian_plazas_point_feature`, `NTA_Neighborhood_Tabulation_Areas`
- **Common distractors:** `NYC_population`, `open_storefronts_applications_historical`, `street_seats_2014_2019`
- **Why it matters:** This is a benchmark for economic-vitality reasoning under mixed data types and imperfect business proxies.
- **Key workflow / caveat:** For this benchmark, NTA is the cleanest first-pass answer.
- **Source grounding:** Neighborhood 360° - SBS; Commercial District Needs Assessments - SBS

## Case 22 — Youth workforce-opportunity access under economic stress

- **Status:** drafted
- **Theme:** economic opportunity / service access
- **Benchmark query:** Which neighborhoods with higher poverty and unemployment may have relatively sparse youth or workforce-development program-site coverage?
- **Expected datasets:** `dycd_program_sites`, `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_population`
- **Common distractors:** `NTA_Neighborhood_Tabulation_Areas`, `NYC_Issued_Licenses`, `NYC_libraries`, `citywide_public_computer_centers`
- **Why it matters:** This is a benchmark for economic-opportunity reasoning with a large administrative point layer plus neighborhood hardship context.
- **Key workflow / caveat:** The strongest first-pass answer should anchor on the shared socioeconomic geography.
- **Source grounding:** Jobs & Internships - DYCD; Workforce Job Trainings - DYCD

## Case 23 — Older-adult service access in heat-vulnerable ZIP areas

- **Status:** drafted
- **Theme:** aging / climate resilience / service access
- **Benchmark query:** Which ZIP-like areas with high heat vulnerability may have relatively sparse NYC Aging contracted-provider coverage?
- **Expected datasets:** `department_for_the_aging_nyc_aging_all_contracted_providers`, `NYC_HVI`, `MODZCTA`
- **Common distractors:** `NYC_poverty_rate`, `NYC_unemployment_rate`, `NTA_Neighborhood_Tabulation_Areas`, `NYC_population`
- **Why it matters:** This is a benchmark for service-access reasoning under vulnerable-population targeting and imperfect ZIP geography.
- **Key workflow / caveat:** The cleanest first-pass answer should stay ZIP-like.
- **Source grounding:** Older Adult Center - NYC Aging; Find Help - NYC Aging

## Case 24 — Cooling-water access in heat-vulnerable ZIP areas

- **Status:** drafted
- **Theme:** climate resilience / parks access / public health
- **Benchmark query:** Which ZIP-like areas with high heat vulnerability may have relatively sparse access to NYC Parks drinking fountains and spray showers?
- **Expected datasets:** `NYC_HVI`, `nyc_parks_drinking_fountains`, `nyc_parks_spray_showers`, `MODZCTA`
- **Common distractors:** `NYC_poverty_rate`, `NYC_unemployment_rate`, `NTA_Neighborhood_Tabulation_Areas`, `NYC_libraries`
- **Why it matters:** This is a benchmark for heat-resilience reasoning with underused parks datasets and imperfect ZIP geography.
- **Key workflow / caveat:** The cleanest first-pass answer should stay ZIP-like.
- **Source grounding:** Extreme Heat: Beat the Heat! — NYC Emergency Management; Interactive heat vulnerability index

## Case 25 — Accessible crossing support near older-adult services

- **Status:** drafted
- **Theme:** accessibility / aging / pedestrian infrastructure
- **Benchmark query:** Which NYC community districts seem to have many older-adult service destinations but comparatively sparse accessible pedestrian-crossing support?
- **Expected datasets:** `department_for_the_aging_nyc_aging_all_contracted_providers`, `accessible_pedestrian_signal_locations`, `pedestrian_ramp_locations`, `Community_Districs`
- **Common distractors:** `exclusive_pedestrian_signal_barnes_dance_locations`, `MODZCTA`, `NTA_Neighborhood_Tabulation_Areas`, `NYC_vehicle_collisions_crashes`
- **Why it matters:** This is a benchmark for pedestrian-accessibility reasoning with underused DOT accessibility layers plus a real public-service destination inventory.
- **Key workflow / caveat:** The cleanest first-pass answer should use community districts.
- **Source grounding:** Older Adult Center - NYC Aging; Accessible NYC 2025: An Accessibility Guide for City Agencies
