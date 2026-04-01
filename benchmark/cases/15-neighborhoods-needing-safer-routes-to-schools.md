# Case 15 — Neighborhoods needing safer routes to schools

**Status:** revised  
**Case ID:** 15  
**Theme:** mobility / child safety  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> An education or street-safety planner wants to identify school-rich NYC areas that also show heavy traffic or collision concerns and may warrant safer-routes interventions. Using the available data catalog, select the school, traffic, and safety datasets needed for a first-pass neighborhood screen, choose a defensible common geography, and explain how the results should guide later school-area or corridor-level review.

## Why this benchmark matters

This is a benchmark for **dataset selection + scale discipline + policy-grounded interpretation**.

A weak agent will simply name schools and crashes, then imply it has found dangerous school routes. A stronger agent should recognize that:

1. the local repo can support a **neighborhood screening near concentrations of schools**, not a literal route-level audit of each child’s walk to school;
2. `NYC_Schools`, `NYC_vehicle_collisions_crashes`, and `NYC_automated_traffic_volume_counts` form a plausible local evidence stack for school-access safety pressure;
3. all three operational layers are **point datasets**, so they need a polygon geography for comparison;
4. `NTA_Neighborhood_Tabulation_Areas` is the most defensible common neighborhood unit in the local catalog for this case;
5. the result should be framed as a **Safe Routes / school-area prioritization screen for follow-up**, not proof that a given school route is unsafe or that a capital project is automatically warranted.

That framing matches the current UrbanTrace evaluation target. `backend/llm_agent.py` and `backend/tool.py` reward agents that choose the right local datasets and articulate a coherent workflow over the repo’s catalog; they do not execute a full child pedestrian exposure model or network-based route analysis.

## Source-grounded planning rationale

NYC’s own school-safety materials strongly support a benchmark of this kind.

NYC DOT’s School Safety program says it implements Vision Zero by developing street-improvement projects near schools, focusing on **high-crash corridors and intersections near schools**, while using tools such as school slow zones, signals, signage, and traffic-calming redesigns. That is exactly the planning logic this benchmark should reflect: school safety is not just about school presence, and it is not just about citywide crash totals — it is about prioritizing school-adjacent places where conflict risk appears elevated.

The NYC DDC Safe Routes to School feature is even more specific. It explains that DOT examined accident histories around elementary and middle schools, evaluated schools using school information plus crash data, and used a prioritization method that geocoded school and crash information within a **700-foot radius** to identify priority schools for safety improvements. That matters for benchmark design because it shows that a strong answer should center school locations and nearby crash / traffic conditions together, while also acknowledging that the current local UrbanTrace catalog does **not** fully reproduce DOT’s original school-by-school prioritization pipeline.

Recent NYC DOT student-safety materials reinforce the same framing: the city describes student safety as a matter of safer walking, bicycling, and micromobility access to school, with new street-improvement projects and operational measures near schools and other places where injuries frequently occur.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **School concentration / destination layer:** `NYC_Schools`
2. **Safety outcome layer:** `NYC_vehicle_collisions_crashes`
3. **Traffic-pressure context layer:** `NYC_automated_traffic_volume_counts`
4. **Neighborhood rollup geography:** `NTA_Neighborhood_Tabulation_Areas`
5. **Interpretation rule:** flag NTAs where school presence is substantial and either collision burden or observed traffic pressure is also elevated, then treat those NTAs as candidates for later school-area or corridor-level safety review.

A benchmark-credible answer does **not** need to claim it can infer exact student walking routes. It does need to show the right analytical logic:

- identify neighborhoods with many schools or notable school concentration;
- spatially aggregate school points, crash points, and traffic-count locations into NTAs;
- interpret collision burden and traffic counts as complementary signals of street-safety concern around school-serving areas;
- explain that actual engineering review would still need school-frontage, intersection, corridor, crossing, or network-level follow-up.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_Schools`**
   - Geometry in local metadata: `Point`
   - Rows: `3103`
   - Why it matters: local anchor for where school destinations are located
   - Relevant local fields confirmed in metadata:
     - `factype`
     - `facsubgrp`
     - `optype`
     - `student`
     - `boro`
     - `nta2020`
     - `schooldist`
   - Best benchmark interpretation: use as the school-destination layer; a strong answer may note that the file includes mixed school/facility records, so public-school-focused interpretation may require caution or filtering

2. **`NYC_vehicle_collisions_crashes`**
   - Geometry in local metadata: `Point`
   - Rows: `8605`
   - Why it matters: primary safety-outcome signal
   - Relevant local fields confirmed in metadata:
     - `CRASH DATE`
     - `ON STREET NAME`
     - `CROSS STREET NAME`
     - `NUMBER OF PEDESTRIANS INJURED`
     - `NUMBER OF PEDESTRIANS KILLED`
     - `NUMBER OF PERSONS INJURED`
     - `NUMBER OF PERSONS KILLED`
   - Best benchmark interpretation: use pedestrian-involved harm when possible, because the case is about safer school access rather than generic motor-vehicle activity

3. **`NYC_automated_traffic_volume_counts`**
   - Geometry in local metadata: `Point`
   - Rows: `24600`
   - Why it matters: nearest local proxy for traffic pressure around school-rich areas
   - Relevant local fields confirmed in metadata:
     - `Vol`
     - `Yr`
     - `street`
     - `fromSt`
     - `toSt`
     - `Direction`
     - `Boro`
   - Important caveat: this is a count-program sampling layer, not a complete continuous traffic surface for every school frontage

4. **`NTA_Neighborhood_Tabulation_Areas`**
   - Geometry in local metadata: `MultiPolygon`
   - Rows: `262`
   - Why it matters: most defensible neighborhood-scale comparison geography for harmonizing the point layers in this case
   - Relevant local fields confirmed in metadata:
     - `nta2020`
     - `ntaname`
     - `boroname`
   - Best benchmark interpretation: use as the common geography for first-pass screening, then reserve school-frontage or corridor review for later work

### Acceptable secondary context, but not substitutes

- `raised_crosswalk_locations`
  - Useful as evidence of existing traffic-calming interventions, but not a substitute for school, crash, or traffic-pressure selection.
- `accessible_pedestrian_signal_locations`
  - Potentially relevant for later treatment or accessibility follow-up, but not the core layer for this screening question.
- `outdoor_learning_streets_locations_historical`
  - May provide context about school-adjacent street reallocation, but it is not the core signal for safer-route need.

### Likely distractors

- `NYC_pedestrian_counts`
  - Tempting because it is about walking, but it is not specifically tied to schools and does not directly replace school-destination or traffic-pressure evidence for this case.
- `City_Council_Districs`
  - Possible reporting geography, but weaker than NTAs for neighborhood screening.

## Common geography guidance

For this benchmark, NTA is the cleanest answer.

Why:

- `NYC_Schools` is a point layer.
- `NYC_vehicle_collisions_crashes` is a point layer.
- `NYC_automated_traffic_volume_counts` is a point layer.
- the question asks about **neighborhoods** needing safer-route attention, not a single corridor, school frontage, or districtwide budget memo.

That makes `NTA_Neighborhood_Tabulation_Areas` the most defensible first-pass common geography in the current repo.

A strong answer may say something like:

> “Because the three operational datasets are all point layers and the prompt asks for neighborhood-level prioritization, I would roll schools, collisions, and traffic counts up to NTAs first, then use the resulting school-rich / traffic-burdened / crash-burdened NTAs as a shortlist for school-frontage or corridor review.”

That is better aligned to the local catalog than pretending the benchmark already has a walk-network dataset, school catchment boundaries, or child-specific route traces.

## Interpretation guidance

A strong answer should keep the claims calibrated.

The benchmark output is best interpreted as a screen for neighborhoods where:

- school destinations are numerous or concentrated,
- nearby observed traffic pressure appears material, and/or
- pedestrian or overall crash harm is elevated enough to warrant follow-up.

That can support:

- Safe Routes to School-style prioritization,
- school-area traffic-calming review,
- school-frontage and crossing audits,
- or later corridor/intersection analysis near schools.

It should **not** be interpreted as:

- proof of the exact routes children use,
- proof that a specific school entrance is dangerous,
- proof that all collisions involved students,
- or a final project list for capital construction.

## Selected supporting references

### 1) NYC DOT — School Safety
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/schoolsafety.shtml
- **Why relevant:** The page explicitly says DOT School Safety focuses on street redesigns near schools and on high-crash corridors and intersections near schools, using school slow zones, signage, signals, and traffic-calming measures.
- **Confidence:** high

### 2) DDC Feature: Safe Routes to School
- **Type:** official NYC DDC feature page
- **URL:** https://www.nyc.gov/site/ddc/resources/features/september-2016-safe-routes-to-school.page
- **Why relevant:** This page gives unusually concrete program logic: DOT examined accident histories around schools, combined school information with crash data, and prioritized schools using geocoded school/crash information within a 700-foot radius. That directly supports a benchmark built around schools plus nearby crash/traffic signals.
- **Confidence:** high

### 3) NYC DOT Unveils New Student Safety Measures to Commemorate International Walk-And-Roll-To-School Day
- **Type:** official NYC DOT press release
- **URL:** https://www.nyc.gov/html/dot/html/pr2024/new-student-safety-measures.shtml
- **Why relevant:** This official release updates the policy context by explicitly linking student safety to safer walking, bicycling, and micromobility access near schools and by referencing the report *Safe Streets, Safe Schools, Safe Kids*.
- **Confidence:** high

### 4) Motor Vehicle Collisions - Crashes
- **Type:** official NYC Open Data dataset
- **URL:** https://data.cityofnewyork.us/d/h9gi-nx95
- **Why relevant:** Canonical city crash-event source corresponding to the local collision dataset used in the benchmark.
- **Confidence:** high

### 5) Automated Traffic Volume Counts
- **Type:** official NYC Open Data dataset
- **URL:** https://data.cityofnewyork.us/d/7ym2-wayt
- **Why relevant:** Upstream source for the local traffic-count layer used here as a practical traffic-pressure proxy.
- **Confidence:** medium-high

## Data access points for reproducibility

1. **School destinations**
   - Local dataset: `NYC_Schools`
   - Local repository evidence: `data/metadata/NYC_Schools.json`

2. **Crash harm / safety outcomes**
   - Local dataset: `NYC_vehicle_collisions_crashes`
   - Local repository evidence: `data/metadata/NYC_vehicle_collisions_crashes.json`
   - Upstream public access point: https://data.cityofnewyork.us/d/h9gi-nx95

3. **Traffic-pressure proxy**
   - Local dataset: `NYC_automated_traffic_volume_counts`
   - Local repository evidence: `data/metadata/NYC_automated_traffic_volume_counts.json`
   - Upstream public access point: https://data.cityofnewyork.us/d/7ym2-wayt

4. **Neighborhood geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_Schools`, `NYC_vehicle_collisions_crashes`, `NYC_automated_traffic_volume_counts`, and `NTA_Neighborhood_Tabulation_Areas`.
- Explain why the case is a **neighborhood screening** for school-route safety follow-up rather than a route-engineering audit.
- Use pedestrian-specific crash fields when discussing safety burden.
- Treat traffic counts as a sampled proxy for traffic pressure, not a complete road-network measure.
- Use NTAs as the common geography.
- Return a cautious shortlist for follow-up near schools rather than false-precision rankings.

### What a very strong agent may also mention
- The local school file includes mixed facility/school records, so school-type filtering may matter.
- The `student` field may help as a rough indication of school size, but should not be overinterpreted as exposure or curbside demand.
- A later analytic pass could bring in intervention layers such as raised crosswalks or pedestrian signals to distinguish already-treated school areas from untreated ones.
- A true Safe Routes to School engineering workflow would ideally add school-frontage, crossing, sidewalk, speed, and route-network evidence not fully present in this benchmark.

### Common failure modes
- Selecting only `NYC_vehicle_collisions_crashes` and calling the result “safe routes to school.”
- Ignoring `NYC_Schools` and treating the problem as a generic crash hotspot case.
- Replacing traffic counts with unrelated pedestrian or political-boundary datasets.
- Claiming to identify actual student walking routes from the available catalog.
- Treating neighborhood screening as a final intervention recommendation.

## Retrieval / provenance notes

- Local dataset viability was checked directly in repository metadata for:
  - `NYC_Schools`
  - `NYC_vehicle_collisions_crashes`
  - `NYC_automated_traffic_volume_counts`
  - `NTA_Neighborhood_Tabulation_Areas`
- Repo alignment was checked against:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- This case is intentionally written to evaluate current UrbanTrace agent behavior: choosing credible local datasets, naming a defensible geography, and explaining the correct planning interpretation.
- No backend changes were required.

## Single-case next step if more rigor is wanted

The most useful next upgrade would be adding one child-pedestrian or school-area safety reference that speaks more directly to exposure or route auditing, plus one local intervention dataset comparison for “high need but limited treatment” logic. Even without that, this case is now benchmark-usable because the NYC DOT / DDC materials clearly justify school-centered safety prioritization and the local catalog supports the expected school + crash + traffic + neighborhood workflow.
