# Case 20 — Multi-burden neighborhood screening

**Status:** revised  
**Case ID:** 20  
**Theme:** composite prioritization  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> A city analyst wants to identify NYC neighborhoods for priority follow-up where multiple burdens overlap: poverty, unemployment, heat vulnerability, ambient air pollution, and traffic safety harm. Using the available data catalog, select the most defensible datasets for each burden, explain which indicators are directly available versus which require aggregation or temporal choices, choose a workable common geography or harmonization strategy, and describe how the resulting screen should be interpreted.

## Why this benchmark matters

This is not a one-table lookup task. It is a benchmark for **cross-domain burden screening under mixed geographies and mixed data shapes**.

It matches the current UrbanTrace architecture well:

- `backend/llm_agent.py` supplies dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports **dataset suggestion**, not automatic spatial overlays, joins, or index computation;
- so benchmark quality depends on whether the agent can:
  1. pick the correct burden layers,
  2. notice that they live on different geographies and data structures,
  3. propose a defensible harmonization workflow,
  4. frame the result as a **screening** product rather than a definitive causal ranking.

A weak answer will say something like “combine `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_HVI`, `NYC_air_pollution`, and `NYC_vehicle_collisions_crashes` and rank neighborhoods.” A stronger answer should notice that:

- poverty and unemployment are on **Sub-Borough Area** polygons,
- air pollution is on **community-district-style polygons** with repeated time slices,
- heat vulnerability is on **ZCTA** polygons,
- crash burden is a **point event table** that must be aggregated,
- `NTA_Neighborhood_Tabulation_Areas` is available, but is not the native geography of the core burden layers.

That is exactly the kind of judgment this benchmark should test.

## Recommended benchmark framing

A benchmark-credible answer should say, in substance:

- Use `NYC_poverty_rate` and `NYC_unemployment_rate` for socioeconomic burden.
- Use `NYC_HVI` for heat vulnerability.
- Use `NYC_air_pollution` for chronic pollution burden, especially PM2.5 and/or NO2.
- Use `NYC_vehicle_collisions_crashes` for traffic safety harm, aggregated to a polygon geography with an injury-focused metric.
- Explicitly acknowledge that these layers do **not** come pre-aligned to a single neighborhood unit in the repo.
- Recommend a harmonization step before any composite ranking.
- Interpret the output as a **priority screening index** for follow-up, not as proof that the listed neighborhoods are objectively the “worst” in every sense.

### Expected core datasets
- `NYC_poverty_rate`
- `NYC_unemployment_rate`
- `NYC_HVI`
- `NYC_air_pollution`
- `NYC_vehicle_collisions_crashes`

### Important support dataset
- `NTA_Neighborhood_Tabulation_Areas` only if the agent clearly explains it is being used as a reporting or harmonization target rather than as an already-native join key

### Likely distractors
- `NYC_population` — useful for rates or context, but not one of the requested burdens
- `MODZCTA` — tempting because HVI is ZIP-like, but it does not solve alignment with Sub-Borough Areas, community districts, and crash points by itself
- `City_Council_Districs` — useful for policy communication, not the natural starting geography for this case
- raw traffic volume datasets — not a substitute for traffic safety harm if the prompt asks about burden and priority intervention

## Source-grounded rationale

This case is supported by a combination of official NYC materials and peer-reviewed cumulative-vulnerability literature.

### 1) Interactive heat vulnerability index
- **Type:** official NYC Health data feature
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/
- **What it supports:** NYC explicitly frames heat vulnerability as a neighborhood inequity issue and links disproportionate heat harm to structural racism, poverty, air-conditioning access, green space, and neighborhood cooling resources.
- **Why it matters here:** It supports using `NYC_HVI` as a true vulnerability layer, not just a temperature proxy.

### 2) New York City Community Air Survey (NYCCAS) / Air quality reporting
- **Type:** official NYC Health program / data reporting
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page
- **What it supports:** NYC Health treats neighborhood air-pollution differences as an urban public-health burden and publishes neighborhood-scale PM2.5, NO2, and related measures.
- **Why it matters here:** It is the cleanest official grounding for the `NYC_air_pollution` layer in a cumulative-burden screen.

### 3) Economic conditions data for NYC
- **Type:** official NYC Health data explorer
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-explorer/economic-conditions/
- **What it supports:** NYC publicly reports neighborhood-level economic-condition indicators including poverty and unemployment.
- **Why it matters here:** It supports the inclusion of poverty and unemployment as official local burden indicators rather than generic ACS variables chosen ad hoc.

### 4) Vision Zero
- **Type:** official NYC city program page
- **Agency:** City of New York / NYC DOT and partners
- **URL:** https://www.nyc.gov/content/visionzero/pages/
- **What it supports:** NYC treats traffic deaths and serious injuries as a major policy priority and frames traffic harm as an intervention-worthy burden.
- **Why it matters here:** It supports using crash injury burden as the traffic-safety component of a priority screen rather than a generic mobility metric like traffic volume.

### 5) New York City’s Environmental Justice for All Report Scope of Work
- **Type:** official NYC environmental justice planning document
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/sustainability/downloads/pdf/EJ-Report-Scope.pdf
- **What it supports:** The city’s environmental-justice planning explicitly centers cumulative burdens, inequitable exposures, and vulnerable communities.
- **Why it matters here:** It provides official NYC policy justification for a benchmark built around overlapping environmental and socioeconomic burdens rather than a single hazard.

### 6) Morello-Frosch, Pastor, Porras, & Sadd (2012). *Cumulative Environmental Vulnerability and Environmental Justice in California’s San Joaquin Valley*.
- **Type:** peer-reviewed article
- **Venue:** International Journal of Environmental Research and Public Health
- **DOI:** 10.3390/ijerph9051593
- **URL:** https://doi.org/10.3390/ijerph9051593
- **What it supports:** A concrete methodological precedent for combining social vulnerability and environmental burden into a cumulative screening framework.
- **Why it matters here:** It is a strong conceptual match for this case’s composite-prioritization logic.

### 7) Rappold et al. (2025). *Does socioeconomic and environmental burden affect vulnerability to extreme air pollution and heat? A case-crossover study of mortality in California*.
- **Type:** peer-reviewed article
- **Venue:** Journal of Exposure Science & Environmental Epidemiology
- **DOI:** 10.1038/s41370-024-00676-9
- **URL:** https://doi.org/10.1038/s41370-024-00676-9
- **What it supports:** Socioeconomic and environmental burdens can interact in ways that worsen vulnerability to heat and air pollution.
- **Why it matters here:** It strengthens the case for looking at **overlap** rather than treating each burden independently.

### 8) New York City Neighborhood Health Atlas
- **Type:** official NYC Health platform
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://www.nyc.gov/site/doh/health/neighborhood-health/nyc-neighborhood-health-atlas.page
- **What it supports:** NYC Health describes the Atlas as a neighborhood tool covering social and economic conditions, housing, and neighborhood conditions including **air quality** and **crime complaints**.
- **Why it matters here:** It adds NYC-specific evidence that cross-domain neighborhood screening is an established city public-health planning approach, even if this benchmark uses a different set of local layers and geographies.

## Local dataset evidence from the repo

This case should be judged against the repo’s actual inventory, not an idealized GIS stack.

### 1) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Native geography evidence:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
- Time structure:
  - yearly columns from `2000` through `2023` (with `2020` missing)
- Best interpretation:
  - a neighborhood socioeconomic burden layer on **Sub-Borough Area** polygons

### 2) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Native geography evidence:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
- Time structure:
  - yearly columns from `2000` through `2023` (with `2020` missing)
- Best interpretation:
  - a second socioeconomic burden layer aligned with the poverty geography

### 3) `NYC_HVI`
- Geometry in local metadata: `MultiPolygon`
- Rows: `184`
- Native geography evidence:
  - `ZIP Code Tabulation Area (ZCTA) 2020`
  - `Heat Vulnerability Index (HVI)`
- Best interpretation:
  - a ZIP/ZCTA-style heat-vulnerability layer with a 1–5 burden scale

### 4) `NYC_air_pollution`
- Geometry in local metadata: `MultiPolygon`
- Rows: `107`
- Native geography evidence:
  - `BoroCd`
  - `Geo Place Name`
  - repeated seasonal / annual `Time Period` and `Start_Date`
- Relevant burden fields:
  - `Fine particles (PM 2.5)`
  - `Nitrogen dioxide (NO2)`
  - `Ozone (O3)`
- Best interpretation:
  - a community-district-style air-burden layer with repeated time slices rather than a single static map

### 5) `NYC_vehicle_collisions_crashes`
- Geometry in local metadata: `Point`
- Rows: `8605`
- Native data-shape evidence:
  - point events with `CRASH DATE`, `LATITUDE`, `LONGITUDE`
- Relevant burden fields:
  - `NUMBER OF PERSONS INJURED`
  - `NUMBER OF PERSONS KILLED`
  - `NUMBER OF PEDESTRIANS INJURED`
  - `NUMBER OF PEDESTRIANS KILLED`
- Best interpretation:
  - an event table that must be spatially aggregated before it can be part of a neighborhood composite

### 6) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Key fields:
  - `nta2020`
  - `ntaname`
  - `cdta2020`
- Best interpretation:
  - a plausible reporting surface, but **not** the native geography of the five requested burden layers

## Geography and harmonization guidance

This is the central benchmark issue.

The repo does **not** offer a frictionless single-neighborhood join:

- poverty and unemployment are on **Sub-Borough Areas**;
- HVI is on **ZCTAs**;
- air pollution is on **community-district-style polygons**;
- traffic safety is in **points**;
- NTA is a fifth geography, useful but not native.

So a benchmark-credible answer should not imply that the composite score can be calculated with a trivial join.

The defensible first-pass workflow is:

1. **Choose a target reporting geography and say why.**
   - A strong answer may choose NTA for communication, or a coarser source geography to avoid false precision.
2. **Align poverty and unemployment together first** since they already share Sub-Borough Areas.
3. **Select a clear temporal slice for air pollution** (for example, a recent annual-average PM2.5 and/or NO2 field) rather than mixing arbitrary years and seasons.
4. **Aggregate crash points** to the chosen polygon layer using an injury-centered burden measure.
5. **Crosswalk / overlay** HVI ZCTAs into the same target geography.
6. **Normalize each burden** (rank, percentile, or z-score) before combining.
7. **Describe the output as screening**, not definitive truth.

A strong answer might say something like:

> “I would use `NYC_poverty_rate`, `NYC_unemployment_rate`, `NYC_HVI`, `NYC_air_pollution`, and `NYC_vehicle_collisions_crashes`, but I would not pretend they already share a neighborhood key. Poverty and unemployment are Sub-Borough Areas, HVI is ZCTA-based, air pollution is reported on community-district-style polygons with time slices, and crashes are point events. So I would first pick a reporting geography, aggregate crashes to it, crosswalk the polygon layers, normalize the resulting burden measures, and only then compute a composite screening score.”

That is much more credible than directly naming five datasets and jumping to a ranked list.

## Composite construction guidance

A strong agent does **not** need to invent a sophisticated weighting scheme. Equal-weight screening is acceptable if documented.

A good benchmark answer should accept one of these as reasonable:

- **Equal-weight percentile rank** across the five burdens
- **Equal-weight z-score composite**
- A lightly justified variant that gives crash injuries and chronic pollution slightly more emphasis only if the rationale is explicit

What matters is that the agent:

- uses all five burdens named in the prompt,
- preserves burden direction correctly,
- keeps the geography logic honest,
- avoids false precision.

## Suggested evaluation notes

### What a strong agent should do
- Select all five requested burden dimensions using the correct local datasets.
- Recognize that `NYC_poverty_rate` and `NYC_unemployment_rate` are already aligned.
- Recognize that `NYC_vehicle_collisions_crashes` must be aggregated from points.
- Recognize that `NYC_air_pollution` has a temporal dimension and requires a time-slice choice.
- Recognize that `NYC_HVI` is on ZCTA polygons and cannot be directly joined to the other layers without harmonization.
- Frame the product as a **priority screening index**.

### What a very strong agent may also mention
- PM2.5 and NO2 are the most straightforward chronic pollution fields for this composite.
- Injury counts may need denominator/context if the workflow later evolves into a rate-based safety benchmark, but for an intervention screen raw or normalized injury burden can still be acceptable.
- NTA can be a communication-friendly target geography, but choosing it increases interpolation complexity.
- A coarser target geography may be more defensible if the goal is policy screening rather than neighborhood branding.

### Common failure modes
- Ignoring one or more of the five burdens named in the prompt.
- Pretending all layers can be joined directly on “neighborhood.”
- Treating `NTA_Neighborhood_Tabulation_Areas` as the obvious native key for everything.
- Using raw traffic volume instead of crash or injury burden.
- Mixing air-pollution seasons/years without explanation.
- Returning a ranked list with no harmonization logic.
- Making claims of causal certainty or precise neighborhood diagnosis from what is really a screening workflow.

## Example of a benchmark-credible answer shape

A high-quality answer would likely say:

- Use `NYC_poverty_rate` and `NYC_unemployment_rate` for socioeconomic burden.
- Use `NYC_HVI` for heat vulnerability.
- Use `NYC_air_pollution`, preferably PM2.5 and/or NO2 from a recent consistent time slice, for chronic pollution burden.
- Use `NYC_vehicle_collisions_crashes` aggregated to the chosen polygon geography for traffic safety harm.
- Pick and justify a common reporting geography before computing any composite.
- Normalize the five burden measures and combine them into a screening score.
- Interpret the result as a cumulative-burden prioritization tool for follow-up analysis, not as a final causal ranking.

## Retrieval / provenance notes

- This case was revised against the repo’s actual local inventory in:
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_HVI.json`
  - `data/metadata/NYC_air_pollution.json`
  - `data/metadata/NYC_vehicle_collisions_crashes.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark framing was checked against current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark improvement is making the mixed-geography and mixed-data-shape problem explicit, so the case evaluates realistic agent judgment rather than an imaginary pre-joined dataset.
- No backend changes were required for this case.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding a **single official NYC methodology** that combines environmental, socioeconomic, and injury indicators into one operational score. The case now has direct city support for multi-domain neighborhood screening, but the benchmark still requires the agent to design the composite logic itself.
