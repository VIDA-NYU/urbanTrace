# Case 18 — Bike routes in environmentally burdened areas

**Status:** revised  
**Case ID:** 18  
**Theme:** mobility / environment  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> Which NYC areas with worse air-pollution burden appear to have weaker bike-route support? Using only the datasets already available in UrbanTrace, identify the strongest layers for a first-pass screen, choose the most defensible common geography, and explain the limits of what this analysis can and cannot say about environmental justice and active transportation.

## Why this benchmark matters

This is a benchmark for **dataset selection, geography discipline, and interpretation discipline** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. treat `NTA_Neighborhood_Tabulation_Areas` as the default neighborhood unit just because it is a familiar NYC geography, without noticing that the local air-pollution layer is not natively stored at NTA level;
2. reach for `NYC_bicycle_counts` as if it were a citywide neighborhood coverage layer, even though the local metadata shows it is a sparse point counter network with only about 40 distinct counter IDs;
3. turn the task into a generic bike-safety analysis by over-prioritizing `NYC_vehicle_collisions_crashes`, even though the prompt is about environmental burden and bike-route support rather than crash risk; or
4. imply that adding bike routes by itself will directly solve local air-pollution burden, which goes beyond what the repo can support.

A stronger agent should recognize that this case is really about **screening whether neighborhoods with documented pollution burden also appear less supported by current cycling infrastructure in the repo’s available layers**. That aligns well with the current evaluation target in `backend/llm_agent.py` and `backend/tool.py`: the benchmark rewards choosing the best local datasets, selecting a defensible common geography, and narrating caveats clearly. It does not reward pretending the repo already contains causal evidence about emissions reductions from individual bike-route projects.

## Source-grounded planning rationale

This case has a real NYC policy basis, but it must be framed carefully.

First, the NYC Health Department’s **New York City Community Air Survey (NYCCAS)** explicitly evaluates how air quality differs across neighborhoods and says the program studies how pollutants from traffic, buildings, and other sources affect air quality in different neighborhoods. The page also notes that additional monitoring sites were included to better understand emissions in **environmental justice sites**. That directly supports treating localized air-pollution burden as a legitimate neighborhood planning concern.

Second, New York City’s **Environmental Justice for All Report Scope of Work** provides official city grounding for screening place-based environmental burdens and inequities. Even without using every element of that report in the benchmark, it is strong official justification for asking which neighborhoods face heavier environmental burdens and may deserve targeted planning attention.

Third, NYC DOT’s cycling planning materials — especially **A Plan for Cycling in New York City** and **Safe Streets for Cycling** — establish that bike-network planning is a real city transportation priority, including expansion of safe cycling facilities and attention to network gaps. Those sources justify the mobility side of the benchmark.

The benchmark-credible synthesis is therefore not “bike routes will prove pollution reduction here.” It is narrower and more defensible:

- NYC officially tracks neighborhood-scale air-pollution burden;
- NYC officially plans and expands bicycle networks as part of city transportation policy;
- UrbanTrace can therefore support a **screening analysis** asking whether more polluted areas appear under-served by the current mapped bike network.

That is a credible planning question. What it cannot support, on its own, is a causal claim that a given neighborhood’s measured PM2.5 or NO2 level would materially change because of the bike routes visible in this repo.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_air_pollution` as the environmental-burden anchor layer.
- Use `NYC_Bike_Routes` as the main active-transportation support layer.
- Treat `NYC_bicycle_counts` as **optional supporting evidence only**, because the local dataset is a sparse set of count locations rather than comprehensive neighborhood coverage.
- Prefer the air-pollution layer’s own polygon geography as the first-pass comparison surface, then summarize bike-route presence into those polygons.
- Avoid defaulting to NTA unless the agent explicitly explains that an extra harmonization step is being introduced for reporting or display.
- Interpret the result as an exploratory **environmental-burden / bike-network support screen** for follow-up, not as proof of health benefit, demand, or emissions change.

### Expected core datasets
- `NYC_air_pollution`
- `NYC_Bike_Routes`

### Important optional support dataset
- `NYC_bicycle_counts` only if the agent explicitly explains that bike counters are sparse and corridor-specific, so they are useful as spot evidence of observed cycling activity rather than full neighborhood coverage

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when treated as the automatic common geography
- `NYC_vehicle_collisions_crashes`, which is relevant for bike safety but not the core environmental-burden question in this case
- `NYC_HVI`, which is another environmental-risk layer but is not the pollution measure named by the benchmark

## Expected UrbanTrace dataset mapping

### 1) `NYC_air_pollution`
- Geometry in local metadata: `MultiPolygon`
- Rows: `107`
- Confirmed useful fields in local metadata:
  - `BoroCd`
  - `Geo Place Name`
  - `Time Period`
  - `Start_Date`
  - `Fine particles (PM 2.5)`
  - `Nitrogen dioxide (NO2)`
  - `Ozone (O3)`
- Best benchmark interpretation: the primary neighborhood-scale environmental burden surface available in the repo
- Important caveat: this is not stored at NTA level; the metadata indicates a community-district style geography keyed by `BoroCd` / `Geo Place Name`, with multiple time periods

### 2) `NYC_Bike_Routes`
- Geometry in local metadata: `MultiLineString`
- Rows: `28983`
- Confirmed useful fields in local metadata:
  - `status`
  - `boro`
  - `street`
  - `facilitycl`
  - `allclasses`
  - `lanecount`
  - `ft_facilit`
  - `tf_facilit`
  - `instdate`
  - `ret_date`
- Best benchmark interpretation: the main mapped cycling-network support layer available in the repo
- Important caveat: route presence is not the same thing as route quality, continuity, comfort, or actual usage everywhere

### 3) `NYC_bicycle_counts` (optional support)
- Geometry in local metadata: `Point`
- Rows: `28459`
- Confirmed useful fields in local metadata:
  - `date`
  - `counts`
  - `name`
  - `lon`
  - `lat`
- Best benchmark interpretation: spot observations of bicycle activity at instrumented locations
- Important caveat: local metadata shows only about `40` distinct counter IDs, so this is a sparse monitoring network and should not be treated as complete neighborhood bike-demand coverage

### 4) `NTA_Neighborhood_Tabulation_Areas` (optional reporting geography only)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed useful fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
  - `cdtaname`
- Best benchmark interpretation: optional display/reporting geography if an agent explicitly documents the harmonization step
- Important caveat: not the clean default comparison surface for this case because `NYC_air_pollution` is not natively stored at NTA resolution

## Common geography guidance

This is the key benchmark correction for Case 18.

The seed listed `NTA_Neighborhood_Tabulation_Areas` as expected relevant, but the local repo evidence points to a stronger default workflow:

- `NYC_air_pollution` is already a polygon layer with community-district-style place names and `BoroCd` values;
- `NYC_Bike_Routes` is a line layer that can be spatially summarized into those polygons;
- `NYC_bicycle_counts` is a point layer that can also be attached to those polygons if used carefully;
- `NTA_Neighborhood_Tabulation_Areas` would introduce an extra geography conversion step without being the native burden layer.

So the most benchmark-credible first-pass workflow is:

1. Anchor the analysis on the existing `NYC_air_pollution` polygons.
2. Choose a defensible pollution variable and time slice, such as a recent `Fine particles (PM 2.5)` or `Nitrogen dioxide (NO2)` observation.
3. Summarize `NYC_Bike_Routes` into those polygons using measures such as route length, count of current segments, or presence of higher-class facilities.
4. Optionally use `NYC_bicycle_counts` as corridor-specific corroboration where counters exist, while stating clearly that counter coverage is sparse.
5. Flag places where pollution burden looks relatively high while bike-route support looks relatively limited.

A strong answer may say something like:

> “Because the air-pollution layer already provides the environmental-burden polygons and the bike network is a line layer, I would keep the first-pass analysis on the pollution polygons and summarize current bike routes into them. I would only bring in NTA later if I had to re-express results for reporting.”

That is materially stronger than defaulting to NTA from habit.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for places where measured pollution burden and weaker mapped bike-route support overlap;
- identification of neighborhoods that may warrant follow-up in environmental-justice and transportation-planning discussions;
- comparison of current route presence across burdened areas using the repo’s available mobility and environmental layers.

### What it cannot prove
- that adding bike routes would directly reduce local PM2.5 or NO2 levels by a specific amount;
- that neighborhoods with fewer mapped routes necessarily have low cycling demand;
- that observed pollution differences are caused by transportation infrastructure alone;
- that mapped route quantity is equivalent to safety, comfort, connectivity, or quality of the cycling experience.

### Important caveats a strong agent should mention
- **Geography caveat:** the pollution layer is not natively NTA-based.
- **Temporal caveat:** `NYC_air_pollution` contains multiple time periods, while `NYC_Bike_Routes` includes installation and retirement dates and `NYC_bicycle_counts` contains timestamped observations over many years.
- **Coverage caveat:** bicycle counts are sparse and should not be over-generalized.
- **Infrastructure caveat:** route length or segment count is only a proxy for support; facility class and continuity matter.
- **Causality caveat:** this is a screening benchmark, not a causal emissions or health-impact evaluation.

## Selected supporting references

### 1) New York City Community Air Survey (NYCCAS)
- **Type:** official NYC Health program page
- **URL:** https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page
- **Why relevant:** The page explicitly describes neighborhood air-quality differences, traffic-related pollutants, and inclusion of additional environmental-justice monitoring sites.
- **Confidence:** high

### 2) New York City’s Environmental Justice for All Report Scope of Work
- **Type:** official NYC environmental justice planning document
- **URL:** https://www.nyc.gov/assets/sustainability/downloads/pdf/EJ-Report-Scope.pdf
- **Why relevant:** Provides direct city grounding for environmental-justice screening and neighborhood burden assessment.
- **Confidence:** high

### 3) A Plan for Cycling in New York City
- **Type:** official NYC DOT report
- **URL:** https://www.nyc.gov/html/dot/downloads/pdf/bike-safety-plan.pdf
- **Why relevant:** Establishes bicycle-network planning and expansion as a real NYC policy domain rather than an invented benchmark theme.
- **Confidence:** high

### 4) Safe Streets for Cycling
- **Type:** official NYC DOT report
- **URL:** https://www.nyc.gov/html/dot/downloads/pdf/safe-streets-for-cycling.pdf
- **Why relevant:** Supports the use of bike-network conditions and network gaps as a defensible planning concern in NYC.
- **Confidence:** high

### 5) NYC DOT — Bike Network and Ridership
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/bicyclists/bikestats.shtml
- **Why relevant:** Provides programmatic context for bike-network extent and ridership tracking, supporting why bike-route and bike-count layers belong in the same analytic family even if they should not be interpreted identically.
- **Confidence:** medium-high

## Data access points for reproducibility

1. **Air-pollution burden layer**
   - Local dataset: `NYC_air_pollution`
   - Local repository evidence: `data/metadata/NYC_air_pollution.json`
   - Official context page: `https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page`

2. **Bike-route network layer**
   - Local dataset: `NYC_Bike_Routes`
   - Local repository evidence: `data/metadata/NYC_Bike_Routes.json`
   - Official source family: NYC DOT bike network materials

3. **Optional bike-activity spot observations**
   - Local dataset: `NYC_bicycle_counts`
   - Local repository evidence: `data/metadata/NYC_bicycle_counts.json`

4. **Optional reporting/display geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_air_pollution` and `NYC_Bike_Routes` as the core layers.
- Explain that the clean first-pass geography is the air-pollution polygon layer, not automatically NTA.
- Treat `NYC_bicycle_counts` as optional, sparse spot evidence rather than comprehensive neighborhood demand coverage.
- Keep the interpretation calibrated: this is an environmental-burden / bike-support screening exercise for follow-up.

### What a very strong agent may also mention
- A recent time slice should be chosen explicitly from the air-pollution layer rather than mixing time periods.
- Current versus retired bike-route segments should be separated using `status` and, if needed, `ret_date`.
- Facility class matters: a simple count of segments may be weaker than a route-length or protected-facility summary.
- If the goal later shifts toward bike safety rather than bike support, then `NYC_vehicle_collisions_crashes` would become more central — but that is a different benchmark.

### Common failure modes
- Defaulting to NTA with no explanation.
- Treating `NYC_bicycle_counts` as citywide neighborhood bike-demand coverage.
- Substituting crash analysis for the pollution-support question.
- Claiming that route presence alone demonstrates emissions or health improvement.
- Ignoring time-slice consistency in the pollution data.

## Retrieval / provenance notes

- Local dataset viability was checked directly in repository metadata for:
  - `NYC_air_pollution`
  - `NYC_Bike_Routes`
  - `NYC_bicycle_counts`
  - `NTA_Neighborhood_Tabulation_Areas`
- Repo alignment was checked against:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this case are:
  - turning the seed into a source-grounded NYC environmental-justice / active-transportation screening task;
  - correcting the default geography away from NTA and toward the repo’s native air-pollution polygons;
  - downgrading `NYC_bicycle_counts` from assumed core layer to optional sparse support evidence;
  - adding explicit guardrails against causal overclaiming.
- No backend changes were required for this case; this remains a reasoning-quality benchmark under the current copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one directly quotable NYC source that more explicitly links active transportation investments to broader sustainability or environmental-justice planning. The case is benchmark-usable now because the local metadata clearly supports the geometry choice, and the official NYCCAS, environmental-justice, and DOT cycling materials are sufficient to justify a cautious screening benchmark.