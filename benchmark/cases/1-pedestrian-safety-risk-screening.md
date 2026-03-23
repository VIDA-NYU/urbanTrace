# Case 1 — Pedestrian safety risk screening

**Status:** revised  
**Case ID:** 1  
**Theme:** mobility / safety  
**Language:** English  
**Reviewed on:** 2026-03-22

## Task

> Which NYC neighborhoods should be screened as higher-priority candidates for pedestrian safety follow-up when crash harm is interpreted together with pedestrian activity rather than from crash totals alone? Use the available UrbanTrace datalake to identify the datasets needed for a neighborhood-level screen, choose a neighborhood geography that planners would plausibly use, and explain how the resulting screen should guide later corridor- or intersection-level review.

## Why this benchmark matters

This is a benchmark for **dataset selection + geography harmonization**, not just for naming a safety dataset.

A weak agent will stop at collision points or borough totals. A stronger agent should recognize that:

1. pedestrian crash burden is the main outcome signal;
2. pedestrian counts are needed as an exposure proxy so busy walking areas are not interpreted the same way as low-foot-traffic areas;
3. both point datasets need to be rolled up to a planning geography; and
4. the resulting neighborhood screen is only a first-pass prioritization before corridor/intersection engineering review.

That behavior is well aligned with the current backend design in `backend/llm_agent.py` and `backend/tool.py`, where the copilot is evaluated on selecting the right UrbanTrace datasets and proposing a coherent workflow over the local catalog rather than executing a full external analysis pipeline.

## Source-grounded planning rationale

NYC DOT's 2023 update to the Borough Pedestrian Safety Action Plans explicitly describes pedestrian safety prioritization as a **data-driven process** focused on **priority corridors and intersections** and reports that DOT ranked corridors using pedestrian **fatalities and severe injuries (KSI) per mile** while prioritizing intersections with the highest KSI burden. That is exactly the kind of policy context this benchmark should reflect: raw incidents alone are not the full decision rule, and screening is used to decide where deeper follow-up should happen.

Within the UrbanTrace repository, the closest locally available denominator / exposure proxy is `NYC_pedestrian_counts`. It is not a complete citywide pedestrian exposure surface, but it is still the most defensible local dataset for distinguishing places with heavy pedestrian activity from places with little foot traffic. That makes it benchmark-credible as the expected companion to collision data.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Outcome / harm signal:** `NYC_vehicle_collisions_crashes`
2. **Exposure proxy:** `NYC_pedestrian_counts`
3. **Neighborhood rollup layer:** `NTA_Neighborhood_Tabulation_Areas`
4. **Interpretation rule:** flag NTAs where pedestrian harm is elevated relative to pedestrian activity, then use those NTAs to motivate later corridor/intersection review.

A good gold-standard answer does **not** need to compute a perfect formal risk model. It does need to show the right analytical logic:

- filter or emphasize pedestrian-involved harm from the collisions table;
- spatially aggregate crash events and pedestrian count locations to NTAs;
- compare burden across neighborhoods using both signals together;
- explain that the neighborhood screen is for triage, while engineering treatments still belong at corridor/intersection scale.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_vehicle_collisions_crashes`**
   - Geometry in local metadata: `Point`
   - Why it matters: primary street-safety harm signal
   - Relevant local columns confirmed in metadata:
     - `NUMBER OF PEDESTRIANS INJURED`
     - `NUMBER OF PEDESTRIANS KILLED`
     - `CRASH DATE`
     - `ON STREET NAME`
     - `CROSS STREET NAME`
   - Best benchmark interpretation: use as the pedestrian injury / fatality event source, not just as undifferentiated vehicle crashes

2. **`NYC_pedestrian_counts`**
   - Geometry in local metadata: `Point`
   - Why it matters: closest local pedestrian exposure proxy in the repo
   - Relevant local columns confirmed in metadata:
     - `count`
     - `start_date`
     - `end_date`
     - `Street_Nam`
   - Important caveat for evaluation: this is a sample-based count program, so a strong agent may describe it as an exposure indicator or proxy rather than a complete denominator for every NYC block

3. **`NTA_Neighborhood_Tabulation_Areas`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: plausible neighborhood planning geography for first-pass screening
   - Relevant local columns confirmed in metadata:
     - `nta2020`
     - `ntaname`
     - `boroname`
   - Best benchmark interpretation: use as the common geography to harmonize both point datasets

### Acceptable secondary context, but not substitutes

- `NYC_automated_traffic_volume_counts`
  - May add general traffic context, but it is **not** a substitute for pedestrian exposure.
- `City_Council_Districs`
  - A possible aggregation geography, but less appropriate than NTAs for this neighborhood-screening task.

## Selected supporting references

### 1) Vision Zero: DOT Releases Update to Borough Pedestrian Safety Action Plans, With Targeted Analysis of Priority Corridors and Intersections
- **Type:** official NYC DOT press release / policy update
- **Agency:** NYC Department of Transportation
- **URL:** https://www.nyc.gov/html/dot/html/pr2023/vision-zero-borough-pedestrian-safety-action-plan.shtml
- **Why relevant:** Directly grounds the benchmark in a real NYC pedestrian-safety planning workflow. The release explicitly describes data-driven prioritization of corridors and intersections and references KSI-based ranking logic.
- **Confidence:** high

### 2) Bi-Annual Pedestrian Counts
- **Type:** official NYC Open Data dataset
- **Agency:** NYC Department of Transportation
- **URL:** https://data.cityofnewyork.us/d/cqsj-cfgu
- **Why relevant:** Official source corresponding to the local `NYC_pedestrian_counts` table. Supports using pedestrian counts as the best available local exposure proxy instead of relying on crash totals alone.
- **Confidence:** high

### 3) Motor Vehicle Collisions - Crashes
- **Type:** official NYC Open Data dataset
- **Agency:** NYPD
- **URL:** https://data.cityofnewyork.us/d/h9gi-nx95
- **Why relevant:** Canonical city crash-event dataset and the clearest upstream source for the local `NYC_vehicle_collisions_crashes` table.
- **Confidence:** high

## Data access points for reproducibility

1. **Pedestrian crash harm**
   - Local dataset: `NYC_vehicle_collisions_crashes`
   - Local repository evidence: `data/metadata/NYC_vehicle_collisions_crashes.json`
   - Upstream public access point: https://data.cityofnewyork.us/d/h9gi-nx95

2. **Pedestrian exposure proxy**
   - Local dataset: `NYC_pedestrian_counts`
   - Local repository evidence: `data/metadata/NYC_pedestrian_counts.json`
   - Upstream public access point: https://data.cityofnewyork.us/d/cqsj-cfgu

3. **Neighborhood geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
   - Benchmark role: common polygon geography for point-in-polygon rollup

## Suggested evaluation notes

### What a strong agent should do
- Select exactly the three core datasets above, or at minimum make them central.
- Explain why collisions alone are insufficient for neighborhood screening.
- Treat `NYC_pedestrian_counts` as a pedestrian-activity proxy.
- Use NTAs as the common neighborhood geography.
- Keep the interpretation calibrated: neighborhood screening first, then corridor/intersection follow-up.

### What a very strong agent may also mention
- The collisions table contains pedestrian-specific injury and fatality columns and should be filtered toward pedestrian harm rather than all crash events equally.
- The pedestrian counts dataset is sparse/sample-based, so the result is a screening layer rather than a full causal risk estimate.
- A time-window alignment check between crash records and pedestrian counts would improve rigor if the benchmark runner executes the analysis rather than only selecting datasets.

### Common failure modes
- Returning only `NYC_vehicle_collisions_crashes`.
- Replacing pedestrian counts with generic traffic volume.
- Choosing a geography only after analysis, or not naming one at all.
- Treating the task as hotspot mapping instead of neighborhood screening.
- Claiming exact risk rankings without acknowledging exposure-proxy limitations.

## Retrieval / provenance notes

- Core policy grounding confirmed from the NYC DOT Borough Pedestrian Safety Action Plan update page.
- Local dataset viability confirmed from repository metadata for:
  - `NYC_vehicle_collisions_crashes`
  - `NYC_pedestrian_counts`
  - `NTA_Neighborhood_Tabulation_Areas`
- This revised case is intentionally scoped to current UrbanTrace agent behavior: selecting source tables and articulating a credible neighborhood-screening workflow over the local datalake.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the most useful upgrade would be to add one peer-reviewed transportation-safety citation showing why pedestrian injury burden should be interpreted against pedestrian exposure. The case is already benchmark-usable without that addition because the NYC DOT source and official Open Data sources are sufficient to justify the workflow.