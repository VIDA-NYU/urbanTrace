# Case 16 — Pedestrian demand versus civic support assets

**Status:** revised  
**Case ID:** 16  
**Theme:** mobility / public services  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> A public-realm analyst wants to identify NYC areas with heavy pedestrian activity but relatively limited nearby civic resources such as libraries or public Wi-Fi. Using the available data catalog, select the pedestrian-activity and civic-support datasets needed for a first-pass neighborhood screen, choose a defensible common geography, and explain how the results should be interpreted for pedestrian-support and public-access planning rather than as a generic amenity map.

## Why this benchmark matters

This is a benchmark for **dataset selection + geography discipline + interpretation discipline**.

A weak agent may do one or more of the following:

1. treat `NYC_pedestrian_counts` as if it were a complete citywide pedestrian surface rather than a sampled count program;
2. name libraries and Wi‑Fi without explaining why those are legitimate **support assets** for places with high pedestrian demand;
3. ignore the need to roll point layers into a common comparison geography; or
4. imply that a high-foot-traffic / low-asset area is automatically underserved in an operational sense.

A stronger agent should recognize that the local repo supports a **neighborhood screening for places where pedestrian activity and civic-support access may be misaligned**, not a definitive pedestrian-level service adequacy audit. That is the right fit for UrbanTrace’s current evaluation target: `backend/llm_agent.py` and `backend/tool.py` reward agents that choose the strongest local datasets and explain a credible workflow over the catalog. They do not execute a full pedestrian-shed model, sidewalk-capacity study, or facility-operations analysis.

## Source-grounded planning rationale

Two official NYC planning strands support this case.

First, NYC DOT’s **Pedestrian Mobility Plan** explicitly frames the city as a place of pedestrians and says DOT uses a **data-driven framework** and **anticipated pedestrian volumes** based on pedestrian generators to identify different street and corridor types. The plan also states that pedestrian space must account not only for safe movement but also for the mix of sidewalk uses and amenities that shape pedestrian comfort and convenience. That matters because it gives this benchmark a real planning basis for using pedestrian-demand evidence as more than a transportation curiosity.

Second, NYC’s digital-equity and civic-access materials support the idea that public resources such as libraries and connectivity access points are meaningful neighborhood support assets. The official announcement for **Neighborhood Tech Help** says the program provides in-person support with internet, mobile devices, and computers, was developed with the three public library systems, and is meant to connect residents to essential services. That is a strong local justification for treating libraries and public connectivity infrastructure as practical civic-support assets rather than decorative amenities.

A related NYC DOT public-space source also helps calibrate the case. The official **Pedestrian Plazas** page describes plazas as reclaimed street space that enhances safety, walkability, and access to public transit, while the program prioritizes neighborhoods lacking open space. That reinforces the broader planning idea that heavy pedestrian places can legitimately be evaluated alongside public-support infrastructure and public-space resources. Even so, the local seed for this case is best matched by libraries and public Wi‑Fi because those layers exist directly in the repo and fit the current benchmark query.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Pedestrian-demand layer:** `NYC_pedestrian_counts`
2. **Civic-support asset layer:** `NYC_libraries`
3. **Connectivity / public-access asset layer:** `NYC_Wi-Fi_Hotspot_Locations`
4. **Neighborhood rollup geography:** `NTA_Neighborhood_Tabulation_Areas`
5. **Interpretation rule:** flag NTAs where observed pedestrian counts are relatively high at sampled locations while counts of civic/public-access assets are comparatively low, then treat those NTAs as candidates for follow-up public-realm or service-access review.

A very strong answer may also mention `citywide_public_computer_centers` as an optional enhancement because it is an especially direct digital-access service layer already present in the repo. But for seed-faithful evaluation, `NYC_libraries` and `NYC_Wi-Fi_Hotspot_Locations` should remain the core civic-support assets.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_pedestrian_counts`**
   - Geometry in local metadata: `Point`
   - Rows: `11970`
   - Why it matters: this is the repo’s direct local evidence of observed pedestrian activity
   - Relevant local fields confirmed in metadata:
     - `Street_Nam`
     - `From_Stree`
     - `To_Street`
     - `Borough`
     - `start_date`
     - `end_date`
     - `count`
   - Important caveat: the dataset is a sampled count program at selected locations and times across multiple years; it is **not** a full continuous map of all pedestrian activity citywide

2. **`NYC_libraries`**
   - Geometry in local metadata: `Point`
   - Rows: `253`
   - Why it matters: durable civic-service anchors that support access to information, public space, programming, and digital services
   - Relevant local fields confirmed in metadata:
     - `facname`
     - `zipcode`
     - `factype`
     - `facsubgrp`
     - `optype`
     - `boro`
     - `nta2020`
     - `count`
   - Best benchmark interpretation: treat as civic-support locations; a stronger answer may note that the file includes some non-public/special library records, so interpretation or filtering may matter

3. **`NYC_Wi-Fi_Hotspot_Locations`**
   - Geometry in local metadata: `Point`
   - Rows: `3319`
   - Why it matters: practical public-access / connectivity layer for walk-heavy places where digital access and wayfinding support may matter
   - Relevant local fields confirmed in metadata:
     - `Type`
     - `Provider`
     - `Location_T`
     - `Borough Name`
     - `Neighborhood Tabulation Area Code (NTACODE)`
     - `Neighborhood Tabulation Area (NTA)`
     - `Postcode`
     - `count`
   - Important caveat: hotspot types vary (for example kiosk, library, subway station, outdoor site), so simple counts are only a first-pass availability proxy

4. **`NTA_Neighborhood_Tabulation_Areas`**
   - Geometry in local metadata: `MultiPolygon`
   - Rows: `262`
   - Why it matters: most defensible neighborhood-scale rollup geography in the repo for comparing the three point layers
   - Relevant local fields confirmed in metadata:
     - `nta2020`
     - `ntaname`
     - `boroname`
   - Best benchmark interpretation: use as the common geography for a first-pass neighborhood screen, then reserve corridor or site-level follow-up for later work

### Useful optional enhancement

- **`citywide_public_computer_centers`**
  - Geometry in local metadata: `Point`
  - Rows: `508`
  - Why it may matter: stronger direct public-access support layer than Wi‑Fi alone because it includes fields such as `wi_fi_available`, `workstation`, `staffed`, `open_lab_hrs_per_wk`, `training_hours_per_wk`, and `wheelchair_accessible`
  - Why it is optional here: it improves the case materially, but the original seed specifically names libraries and public Wi‑Fi, so those should remain the core benchmark set

### Likely distractors

- `NYC_population`
  - Tempting as a need proxy, but the prompt is specifically about **pedestrian demand** rather than resident totals.
- `NYC_Schools`
  - Plausible as a civic facility layer, but it is weaker than libraries or public connectivity assets for the benchmark’s stated framing.
- `City_Council_Districs`
  - Useful for reporting or governance, but weaker than NTAs for neighborhood screening.
- `seating_locations`
  - Interesting public-realm context, but not a substitute for the core library / Wi‑Fi civic-support framing in the seed.

## Common geography guidance

For this benchmark, NTA is the cleanest answer.

Why:

- `NYC_pedestrian_counts` is a point layer.
- `NYC_libraries` is a point layer.
- `NYC_Wi-Fi_Hotspot_Locations` is a point layer.
- the question asks about **areas**, not one block, one library catchment, or one kiosk corner.

`NYC_Wi-Fi_Hotspot_Locations` and `NYC_libraries` already carry neighborhood-related attributes, but `NYC_pedestrian_counts` is still a point dataset tied to count locations. So the strongest common workflow is to spatially aggregate all three point layers to `NTA_Neighborhood_Tabulation_Areas` and compare the resulting neighborhood patterns there.

A strong answer may say something like:

> “Because the operational datasets are point layers and the prompt asks for area-level screening, I would roll pedestrian count locations, library sites, and Wi‑Fi hotspot sites up to NTAs first. Then I would look for NTAs where sampled pedestrian activity appears relatively high while civic-support asset counts remain comparatively thin.”

That is more credible than pretending the repo already contains a complete sidewalk-demand surface, actual pedestrian catchments, or user-level library / hotspot utilization.

## Interpretation guidance

A strong answer should keep the claims calibrated.

The benchmark output is best interpreted as a screen for neighborhoods where:

- sampled pedestrian activity appears comparatively high,
- the nearby stock of civic-support assets such as libraries and public Wi‑Fi looks comparatively limited, and
- additional public-realm or service-access review may be warranted.

That can support:

- public-realm planning,
- civic amenity siting discussions,
- digital-access outreach,
- or follow-up analysis of whether busy pedestrian corridors have adequate public-support infrastructure.

It should **not** be interpreted as:

- proof that pedestrians in those areas lack access to services,
- proof that a library or hotspot should be installed at a specific corner,
- proof that all foot traffic reflects local resident need rather than commuting or tourism,
- or a final capital/program investment list.

## Selected supporting references

### 1) NYC DOT — Pedestrian Mobility Plan
- **Type:** official NYC DOT planning page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/pedestrian-mobility.shtml
- **Why relevant:** The page explicitly describes NYC as a city of pedestrians, says DOT developed a holistic data-driven framework, and explains that anticipated pedestrian volumes and pedestrian generators are used to classify streets. That directly supports using pedestrian-demand evidence in a benchmark.
- **Confidence:** high

### 2) NYC DOT — NYC Streets Plan
- **Type:** official NYC DOT planning page / plan
- **URL:** https://www.nyc.gov/html/dot/html/about/nyc-streets-plan.shtml
- **Why relevant:** The page says the city needs safe and welcoming streets and public spaces and describes the Streets Plan as a five-year plan to improve the safety, accessibility, and quality of city streets. That supports a benchmark framed as public-realm and accessibility screening rather than only traffic measurement.
- **Confidence:** high

### 3) City Launches ‘Neighborhood Tech Help’ to Bridge Digital Divide Across the Boroughs
- **Type:** official NYC announcement
- **URL:** https://www.nyc.gov/site/hpd/news/015-25/city-launches-neighborhood-tech-help-bridge-digital-divide-across-boroughs
- **Why relevant:** The city explicitly ties in-person digital support, libraries, and internet/device access to essential services and neighborhood need. That strongly supports treating libraries and public connectivity assets as meaningful civic-support infrastructure.
- **Confidence:** high

### 4) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **Why relevant:** The roadmap provides the citywide policy context for evaluating public digital-access infrastructure, of which Wi‑Fi and library-linked support are practical local proxies.
- **Confidence:** high

### 5) NYC DOT — Pedestrian Plazas
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/nyc-plaza-program.shtml
- **Why relevant:** The page frames pedestrian-oriented public space as a safety, walkability, transit-access, and equity issue, which helps ground the broader public-realm interpretation of this case.
- **Confidence:** medium-high

### 6) Public Libraries | New York City Preliminary Mayor’s Management Report FY2026
- **Type:** official NYC service report
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **Why relevant:** This report supports treating libraries as active service infrastructure rather than passive amenities.
- **Confidence:** medium-high

## Data access points for reproducibility

1. **Pedestrian-demand evidence**
   - Local dataset: `NYC_pedestrian_counts`
   - Local repository evidence: `data/metadata/NYC_pedestrian_counts.json`

2. **Library civic-support assets**
   - Local dataset: `NYC_libraries`
   - Local repository evidence: `data/metadata/NYC_libraries.json`

3. **Public connectivity assets**
   - Local dataset: `NYC_Wi-Fi_Hotspot_Locations`
   - Local repository evidence: `data/metadata/NYC_Wi-Fi_Hotspot_Locations.json`

4. **Neighborhood comparison geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

5. **Optional stronger digital-access support layer**
   - Local dataset: `citywide_public_computer_centers`
   - Local repository evidence: `data/metadata/citywide_public_computer_centers.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_pedestrian_counts`, `NYC_libraries`, `NYC_Wi-Fi_Hotspot_Locations`, and `NTA_Neighborhood_Tabulation_Areas`.
- Explain that the result is a **neighborhood screening** for places where pedestrian demand and civic-support assets may be misaligned.
- Acknowledge that pedestrian counts are sampled observations across selected locations/times, not a complete citywide pedestrian-demand layer.
- Use NTA as the common geography.
- Keep the conclusion cautious: this is a shortlist for follow-up, not proof of unmet service need.

### What a very strong agent may also mention
- `citywide_public_computer_centers` is a stronger direct public-access service layer and could improve the screening.
- Wi‑Fi hotspot types are heterogeneous, so not every hotspot provides the same kind of civic support.
- Libraries may include special/non-public records, so filtering may matter depending on how strictly the user means public civic assets.
- Foot traffic in some places may reflect tourism, commuting, or transit transfer activity rather than residential need.

### Common failure modes
- Treating `NYC_pedestrian_counts` as a full map of pedestrian demand everywhere in NYC.
- Naming only libraries and Wi‑Fi with no pedestrian layer.
- Using population instead of pedestrian demand and silently changing the question.
- Ignoring the need for a polygon rollup geography.
- Claiming that a high-foot-traffic / low-asset NTA is definitively underserved.

## Retrieval / provenance notes

- Local dataset viability was checked directly in repository metadata for:
  - `NYC_pedestrian_counts`
  - `NYC_libraries`
  - `NYC_Wi-Fi_Hotspot_Locations`
  - `NTA_Neighborhood_Tabulation_Areas`
  - `citywide_public_computer_centers`
- Repo alignment was checked against:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - turning an undrafted seed into a source-grounded case file;
  - clarifying that pedestrian counts are sampled observations rather than a citywide pedestrian surface;
  - grounding libraries and public connectivity as real civic-support assets using official NYC digital-equity and service materials; and
  - making NTA the explicit common geography for a benchmark-credible first pass.
- No backend changes were required.

## Single-case next step if more rigor is wanted

The most useful next upgrade would be one additional official source or local layer that speaks more directly to public-space amenities along heavily walked corridors—for example plazas, benches, or related public-realm infrastructure—so the case could distinguish digital/civic support from broader pedestrian-comfort assets more explicitly. Even without that, this case is now benchmark-usable because the official DOT pedestrian-planning materials and NYC digital-equity/library-support materials are sufficient to justify the current pedestrian-demand-plus-civic-support framing.
