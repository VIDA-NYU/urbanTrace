# Case 22 — Youth workforce-opportunity access under economic stress

**Status:** drafted  
**Case ID:** 22  
**Theme:** economic opportunity / service access  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> A city analyst wants to identify NYC neighborhoods where economic stress appears high but access to youth and workforce-development program sites may be comparatively thin. Using the available data catalog, select the most relevant program-site and socioeconomic datasets, explain which service-site fields are usable for identifying workforce-related programs, choose a defensible common geography, and describe how the results should guide later opportunity-access follow-up.

## Why this benchmark matters

This is a benchmark for **economic-opportunity reasoning with a large administrative point layer plus neighborhood hardship context**.

It fits the current UrbanTrace copilot architecture well:

- `backend/llm_agent.py` supplies dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports dataset suggestion and explanation, not a turnkey service-gap model;
- so benchmark quality depends on whether the agent can:
  1. identify the strongest local service-site layer for youth/workforce access,
  2. recognize that not every DYCD site is equally relevant to employment opportunity,
  3. choose a defensible geography for comparing program locations against poverty and unemployment, and
  4. interpret the result as a **follow-up screening** rather than proof that a neighborhood is truly underserved.

A weak answer will say “use `dycd_program_sites` and poverty.” A stronger answer should notice that:

- `dycd_program_sites` is broad and includes many program areas, so the agent should at least mention filtering or prioritizing workforce-oriented categories where possible;
- the DYCD point layer contains useful place fields like `program_area`, `program_type`, `service_category`, `age_range`, `nta`, and `communitydistrict`, but the repo’s poverty and unemployment layers natively live on **Sub-Borough Area** polygons;
- `NYC_population` is useful context because raw site counts can be misleading in high-population neighborhoods;
- a defensible answer should say whether it is using the shared sub-borough socioeconomic geography, or whether it is moving to NTA and accepting the extra harmonization burden.

That is exactly the kind of dataset-choice, filtering, and geography discipline this benchmark should test.

## Source-grounded planning rationale

This case is grounded in official NYC materials rather than invented scenario framing.

NYC DYCD’s **Jobs & Internships** page explicitly says DYCD is the City’s lead agency for **youth employment programs** and that its employment programs help young people ages 14 to 24 gain work experience and further their education. The page also lists concrete workforce-oriented program families such as **SYEP**, **Train & Earn**, **Learn & Earn**, **Advance & Earn**, and **Work, Learn & Grow**. That directly supports a benchmark about neighborhood access to youth and workforce-development opportunity sites.

The official **DYCD Program Sites** dataset documentation is also important because it shows that the repo contains a large administrative site inventory with fields such as `program_area`, `program_type`, `service_category`, `provider`, `borough`, `communitydistrict`, `nta`, `ntaname`, `totalslots`, `totalparticipants`, and `age_range`. That makes this a credible local service-access benchmark rather than a hypothetical planning exercise.

For neighborhood hardship context, NYC Health’s **Economic conditions** reporting provides official local evidence that poverty and unemployment are meaningful neighborhood-level indicators. Those align directly with the repo’s `NYC_poverty_rate` and `NYC_unemployment_rate` layers. Using them together with `NYC_population` produces a much more credible first-pass opportunity-access screen than mapping DYCD sites alone.

This yields a benchmark-credible question:

- use DYCD program sites as the service-access layer;
- use poverty, unemployment, and population as neighborhood stress and scale context;
- prefer the shared socioeconomic geography unless the agent explicitly justifies a more detailed but harder harmonization path; and
- interpret the result as a screen for places where workforce-oriented service presence may deserve closer review.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `dycd_program_sites` as the core youth/workforce service-site layer.
- Use `NYC_poverty_rate` and `NYC_unemployment_rate` as the main economic-stress layers.
- Use `NYC_population` so raw site counts are not interpreted without resident scale.
- Prefer the repo’s shared **Sub-Borough Area** geography from the poverty / unemployment / population layers for the first-pass comparison, with DYCD sites spatially summarized into those polygons.
- Mention that `program_area`, `program_type`, `service_category`, and `age_range` can help narrow the DYCD layer toward workforce-relevant opportunity programs rather than all youth services indiscriminately.
- Interpret the output as an **economic-opportunity access screen**: areas with high hardship and relatively limited workforce-oriented DYCD site presence may warrant follow-up.
- Avoid claiming that fewer sites automatically means lower opportunity, or that all DYCD sites have equivalent capacity, quality, or employment relevance.

### Expected core datasets
- `dycd_program_sites`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`
- `NYC_population`

### Important optional support dataset
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains that it is switching to a neighborhood reporting geography and accepting an extra harmonization step because the socioeconomic layers are not natively NTA-based

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when used as the default common geography without explaining the mismatch with the poverty / unemployment / population layers
- `NYC_Issued_Licenses`, which may be relevant to economic context but is not the strongest service-access layer for youth/workforce opportunity delivery
- `NYC_libraries` or `citywide_public_computer_centers`, which may support workforce access indirectly but are weaker than the repo’s direct DYCD site inventory for this prompt
- using all DYCD sites equally with no mention of workforce-oriented filtering

## Expected UrbanTrace dataset mapping

### 1) `dycd_program_sites`
- Geometry in local metadata: `Point`
- Rows: `9392`
- Confirmed useful fields in local metadata:
  - `date`
  - `program_area`
  - `program_type`
  - `service_category`
  - `provider`
  - `program_site_name`
  - `borough`
  - `communitydistrict`
  - `community_name`
  - `nta`
  - `ntaname`
  - `totalslots`
  - `totalparticipants`
  - `age_range`
- Best benchmark interpretation: administrative inventory of DYCD-funded or DYCD-listed program sites that can support workforce/youth-opportunity screening when filtered appropriately
- Important caveat: this is a broad site inventory, not a workforce-only dataset and not a direct measure of service quality or seat availability by neighborhood

### 2) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed useful fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - yearly values including `2021`, `2022`, `2023`
- Best benchmark interpretation: official neighborhood hardship context on the shared sub-borough geography

### 3) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed useful fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - yearly values including `2021`, `2022`, `2023`
- Best benchmark interpretation: neighborhood labor-market stress context aligned with the poverty layer

### 4) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed useful fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - yearly values including `2021`, `2022`, `2023`
- Best benchmark interpretation: resident scale / denominator context so neighborhoods are not compared using raw site counts alone

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed useful fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: optional reporting geography, not the cleanest first-pass comparison surface for the repo’s economic-stress layers

## Common geography guidance

The strongest first-pass answer should anchor on the shared socioeconomic geography.

Why:

- `dycd_program_sites` is a point layer.
- `NYC_poverty_rate`, `NYC_unemployment_rate`, and `NYC_population` already align on the same **55-area Sub-Borough Area** polygon system.
- the prompt is about screening neighborhoods under economic stress for possible opportunity-access gaps, not about comparing one exact site address against one census tract.

That makes the sub-borough geography the cleanest benchmark answer for an initial screen.

A strong answer may say something like:

> “Because poverty, unemployment, and population already share the same sub-borough geography, I would use those polygons as the first-pass comparison surface and spatially summarize DYCD program sites into them. I would also narrow the DYCD layer toward workforce-oriented program types where possible before comparing site presence against hardship indicators.”

That is more benchmark-credible than defaulting to NTA simply because the DYCD file contains an `nta` attribute.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for sub-borough areas where poverty and unemployment are relatively high while workforce-oriented DYCD site presence appears comparatively limited;
- a first-pass comparison of neighborhood economic stress and local youth/workforce service presence using only the repo’s available layers;
- follow-up questions about whether certain neighborhoods may merit closer review of service distribution, outreach, transportation access, or program capacity.

### What it cannot prove
- that a neighborhood truly lacks opportunity in practice;
- that all DYCD sites are equally relevant to employment or workforce advancement;
- that site counts reflect actual seat availability, take-up, quality, or outcomes;
- that lower site density causes unemployment or poverty;
- that resident demand is fully captured without more age-specific population and travel-access context.

### Important caveats a strong agent should mention
- **Program-mix caveat:** not every DYCD program site is employment-focused, so filtering by `program_area`, `program_type`, `service_category`, or `age_range` matters.
- **Capacity caveat:** site presence is not the same as program capacity, quality, or participant success.
- **Scale caveat:** raw counts alone are weak without population context.
- **Geography caveat:** the socioeconomic layers and DYCD site fields do not automatically share a single native neighborhood key.
- **Temporal caveat:** DYCD site records include a `date` field while the hardship layers are annual indicators; a strong answer may mention aligning to a recent period rather than mixing years carelessly.

## Selected supporting references

### 1) Jobs & Internships - DYCD
- **Type:** official NYC DYCD program page
- **URL:** https://www.nyc.gov/site/dycd/services/jobs-internships.page
- **Why relevant:** The page says DYCD is the City’s lead agency for youth employment programs and lists workforce-oriented offerings such as SYEP, Train & Earn, Learn & Earn, Advance & Earn, and Work, Learn & Grow.
- **Confidence:** high

### 2) Workforce Job Trainings - DYCD
- **Type:** official NYC DYCD services page
- **URL:** https://www.nyc.gov/site/dycd/services/jobs-internships/workforce_job_trainings.page
- **Why relevant:** Supports the benchmark’s emphasis on workforce-oriented DYCD programming rather than treating all youth-service sites as interchangeable.
- **Confidence:** medium-high

### 3) DYCD Program Sites - NYC Open Data
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/ebkm-iyma
- **Why relevant:** Official documentation for the site inventory represented locally as `dycd_program_sites`, including the program and geography fields that drive this benchmark.
- **Confidence:** high

### 4) Economic conditions data for NYC - Environment & Health Data Portal
- **Type:** official NYC portal page
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-explorer/economic-conditions/
- **Why relevant:** Official city framing for neighborhood poverty and unemployment as meaningful economic-condition indicators.
- **Confidence:** high

### 5) Poverty Data - NYC Opportunity
- **Type:** official NYC documentation page
- **URL:** https://www.nyc.gov/site/opportunity/poverty-in-nyc/poverty-data.page
- **Why relevant:** Supports the use of poverty as an official local hardship metric in a benchmark about access to opportunity.
- **Confidence:** medium-high

## Data access points for reproducibility

1. **Youth/workforce service-site layer**
   - Local dataset: `dycd_program_sites`
   - Local repository evidence: `data/metadata/dycd_program_sites.json`
   - Official source: `https://data.cityofnewyork.us/api/views/ebkm-iyma`

2. **Poverty context layer**
   - Local dataset: `NYC_poverty_rate`
   - Local repository evidence: `data/metadata/NYC_poverty_rate.json`

3. **Unemployment context layer**
   - Local dataset: `NYC_unemployment_rate`
   - Local repository evidence: `data/metadata/NYC_unemployment_rate.json`

4. **Population context layer**
   - Local dataset: `NYC_population`
   - Local repository evidence: `data/metadata/NYC_population.json`

5. **Optional neighborhood reporting geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `dycd_program_sites`, `NYC_poverty_rate`, `NYC_unemployment_rate`, and `NYC_population`.
- Explain that `dycd_program_sites` is broad and should be narrowed toward workforce-relevant program categories where possible.
- Prefer the shared sub-borough poverty / unemployment / population geography for the first-pass rollup.
- Use population context so raw site counts are not over-read.
- Frame the output as an opportunity-access screening exercise for follow-up, not a definitive ranking of underserved neighborhoods.

### What a very strong agent may also mention
- `totalslots` and `totalparticipants` may improve downstream interpretation, but only if the agent notes data-quality and comparability issues.
- `date` should be used to align the DYCD site layer to a recent period rather than mixing stale and current records indiscriminately.
- NTA may be useful for later neighborhood communication, but only after acknowledging that it is not the shared native geography of the hardship layers.
- A fuller opportunity-access model would ideally add age-specific population, transit travel time, school/work status, or outcome data that are not directly available in the current repo.

### Common failure modes
- Treating all DYCD sites as equivalent workforce opportunity sites.
- Ignoring poverty or unemployment and returning only a site map.
- Ignoring population scale.
- Defaulting to NTA with no explanation of the geography mismatch.
- Claiming that fewer sites automatically means lower opportunity or worse outcomes.

## Retrieval / provenance notes

- This case was drafted against the actual repo inventory in:
  - `data/metadata/dycd_program_sites.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark framing was checked against the current agent/tool constraints in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The key benchmark value is that it tests whether the agent can combine a large administrative program-site inventory with neighborhood economic-stress context while staying honest about filtering, capacity, and geography limits.
- No backend changes were required for this case.
