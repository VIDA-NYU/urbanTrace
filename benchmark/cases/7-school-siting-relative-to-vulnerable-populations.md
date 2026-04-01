# Case 7 — School siting relative to vulnerable populations

**Status:** revised  
**Case ID:** 7  
**Theme:** public services / equity  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> An education and planning team wants to screen for NYC neighborhoods where population pressure and social vulnerability are high while school presence appears comparatively sparse. Using the available data catalog, select the school, poverty, unemployment, and population datasets needed for a first-pass access screen, choose a defensible common geography, and explain how the results should inform later facilities or outreach review without being treated as a school-quality evaluation.

## Why this benchmark matters

This is a benchmark for **dataset selection under geography mismatch and proxy discipline**.

A weak agent will simply name `NYC_Schools`, `NYC_population`, and one hardship layer, then jump straight to a map. A stronger agent should recognize that:

1. the social-vulnerability layers in the repo are on **55 sub-borough-area polygons**, not on NTA geography;
2. `NYC_Schools` is a **point** dataset and already carries neighborhood identifiers like `nta2020` and tract fields, but that does **not** make NTA the automatic comparison unit;
3. the local schools dataset includes **public and non-public records**, so a benchmark-credible answer should at least acknowledge that the task is about public-school access and that filtering or careful interpretation may be needed;
4. the result is an **equity screening for follow-up**, not proof that any neighborhood definitively lacks school capacity; and
5. under the current UrbanTrace architecture, benchmark quality depends more on choosing the right layers and explaining the harmonization logic than on pretending the agent can already execute a full capital-planning workflow.

This fits the current repo well. `backend/llm_agent.py` assembles answers from dataset descriptions, metadata, and dashboard state, while `backend/tool.py` focuses on dataset suggestion behavior rather than GIS execution. So this case should reward agents that reason carefully about the catalog the way it actually exists.

## Source-grounded planning rationale

The Independent Budget Office report *Barriers to Learning: Age, Accessibility, Space Usage, and Air Conditioning in NYC School Buildings* frames school facilities as an equity issue, not just a building inventory issue. It is directly relevant because it ties school conditions and accessibility to how well facilities serve students across the city.

The NYC School Construction Authority’s capital-planning materials add a more direct siting rationale. The SCA’s capital-plan and demographic materials state that projected enrollment is combined with projected housing growth, note that **new housing development projects can stress local schools by introducing an influx of new students**, and publish identified seat-need tables by district. That is exactly the kind of official planning context that makes a benchmark about neighborhood pressure and relative facility presence credible: the benchmark is not claiming to replace formal siting analysis, but to identify where further facilities review may be warranted.

The Mayor’s 2025 school-opening announcement sharpens that rationale further by saying the City is **increasing seat capacity in neighborhoods with overcrowded schools**. That is a direct official statement that neighborhood differences in school-seat pressure are a real planning problem, not just an inference from the capital-plan machinery.

Those sources support a benchmark framed as:

- an **equity and facilities-access screening**;
- grounded in **population pressure plus socioeconomic vulnerability**;
- interpreted as a prompt for follow-up on school access or facilities planning;
- while avoiding unsupported claims about capacity, utilization, or final siting decisions.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_Schools` as the local school-facility layer.
- Use `NYC_population`, `NYC_poverty_rate`, and `NYC_unemployment_rate` as the population-pressure / vulnerability context layers already available in the repo.
- Treat the **55 sub-borough-area polygons** used by those socioeconomic datasets as the most defensible first-pass common geography.
- Treat `NTA_Neighborhood_Tabulation_Areas` as optional reference or reporting geography unless the agent explicitly explains an overlay or crosswalk step.
- Interpret the result as a **screen for neighborhoods where vulnerability and population are high relative to observed school presence**, not as a definitive statement about seat shortage, overcrowding, or capital-project priority.

### Expected core datasets
- `NYC_Schools`
- `NYC_population`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`

### Important support / reference datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains why it is being used for reporting, contextual labeling, or an additional overlay step

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when chosen as if it were already the native common geography for all layers
- `MODZCTA` when used as a generic substitute for neighborhood comparison without justification
- `City_Council_Districs` because it is an administrative reporting geography, not the natural unit implied by the vulnerability datasets

## Expected UrbanTrace dataset mapping

### 1) `NYC_Schools`
- Geometry in local metadata: `Point`
- Rows: `3103`
- Confirmed key fields relevant to this benchmark:
  - `factype`
  - `facsubgrp`
  - `optype`
  - `student`
  - `nta2020`
  - `ct2020`
  - `schooldist`
  - `boro`
- Best benchmark interpretation: citywide school locations that can be counted or summarized spatially against neighborhood vulnerability surfaces
- Important limitation: the local file is not a pure public-school-only layer; it includes public and non-public records, so a strong answer should acknowledge the need to focus on the public-serving subset or at least interpret counts cautiously

### 2) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `2021`
  - `2022`
  - `2023`
  - `Official_SBA_name`
  - `bor_subb`
- Best benchmark interpretation: neighborhood-scale population-pressure anchor on sub-borough-area geography

### 3) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `2021`
  - `2022`
  - `2023`
  - `Official_SBA_name`
  - `bor_subb`
- Best benchmark interpretation: neighborhood socioeconomic vulnerability surface aligned with the population layer

### 4) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `2021`
  - `2022`
  - `2023`
  - `Official_SBA_name`
  - `bor_subb`
- Best benchmark interpretation: a second hardship / vulnerability signal on the same sub-borough-area geography

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed key fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
- Best benchmark interpretation: optional reporting or display geography, not the cleanest first-pass join unit for this case

## Common geography guidance

This is the key benchmark issue.

The current draft leaned toward NTA geography because `NYC_Schools` contains `nta2020`. But the actual repo evidence points to a better first-pass choice:

- `NYC_population`, `NYC_poverty_rate`, and `NYC_unemployment_rate` are all already aligned on **55 sub-borough-area polygons**.
- `NYC_Schools` is a **point** layer.
- The vulnerability layers do **not** come natively on NTA geography.

So the most benchmark-credible workflow is:

1. **Anchor the analysis on the sub-borough-area polygons** already shared by the population and vulnerability layers.
2. Spatially count or summarize school points within each sub-borough polygon.
3. Compare relative school presence against recent population and vulnerability values.
4. Flag high-population, high-poverty, and/or high-unemployment areas where school presence appears comparatively thin.
5. Only convert the result to NTAs if the agent explicitly describes an additional polygon overlay or crosswalk step.

A strong answer may also note that `NYC_Schools` contains `nta2020` and tract identifiers that could support finer-grained follow-up work later. But for the benchmark as currently represented in the catalog, the cleanest common geography is the one already shared by the vulnerability layers.

In other words, this benchmark succeeds when the agent says something like:

> “Because the population, poverty, and unemployment layers are already aligned on the same 55 sub-borough polygons, I would use that geography as the first-pass comparison unit and count school points into those polygons, rather than defaulting to NTA just because the school dataset happens to carry NTA attributes.”

That is materially more credible than assuming NTA is the natural join unit.

## Interpretation guidance

A strong answer should keep the claims calibrated.

The benchmark output is best interpreted as a screen for neighborhoods where:

- total population is relatively high,
- hardship indicators such as poverty and unemployment are elevated, and
- observed school locations in the local catalog appear relatively sparse.

That can support:

- follow-up facilities-access review,
- discussion of where public-school provision may deserve closer attention,
- comparison against formal SCA / DOE planning materials,
- or prioritization for deeper analysis using enrollment, seat-capacity, utilization, or school-level program data not fully represented in this benchmark.

It should **not** be interpreted as:

- proof of overcrowding,
- proof of inadequate seat capacity,
- a school-quality ranking,
- or a final recommendation for where to site a new school.

## Source-grounded rationale

### 1) Barriers to Learning: Age, Accessibility, Space Usage, and Air Conditioning in NYC School Buildings
- **Type:** policy report
- **Agency / publisher:** New York City Independent Budget Office
- **URL:** https://www.ibo.nyc.gov/content/publications/2025-march-barriers-to-learning-age-accessibility-space-usage-and-air-conditioning-in-nyc-school-buildings
- **What it supports:** It frames school building accessibility, conditions, and space usage as meaningful public-policy concerns rather than purely operational details.
- **Why it matters for this benchmark:** It justifies treating school facilities as part of an equity conversation, which makes a neighborhood screening benchmark credible.

### 2) NYCSCA Capital Plan Reports & Data
- **Type:** official NYC facilities-planning page
- **Agency:** New York City School Construction Authority
- **URL:** https://nycsca.org/Community/Capital-Plan-Reports-Data
- **What it supports:** The SCA states that projected enrollment is combined with projected housing growth, that new housing development can stress local schools, and that the agency tracks identified seat need by district.
- **Why it matters for this benchmark:** It is the clearest direct official support for screening neighborhoods where population pressure may be rising faster than visible school presence.

### 3) NYC School Construction Authority — Enrollment, Capacity & Utilization Report page
- **Type:** official NYC facilities-planning page
- **Agency:** New York City School Construction Authority
- **URL:** https://www.nycsca.org/Community/Overview/Capital-Plan-Reports-and-Data/Enrollment-Capacity-Utilization-Report
- **What it supports:** The SCA treats enrollment, capacity, and utilization as formal dimensions of facilities review.
- **Why it matters for this benchmark:** It is the reason a strong benchmark answer should avoid overclaiming from raw school-point counts alone; point density is a screening signal, not a substitute for seat-capacity analysis.

### 4) Mayor Adams, Chancellor Aviles-Ramos Announce Seven New Schools Opening in 2025-2026 Academic Year
- **Type:** official NYC Mayor's Office press release
- **Agency:** Mayor's Office of the City of New York
- **URL:** https://www.nyc.gov/mayors-office/news/2025/05/mayor-adams-chancellor-aviles-ramos-seven-new-schools-opening-2025-2026-academic-year
- **What it supports:** The City says new schools are being opened while continuing to increase seat capacity in neighborhoods with overcrowded schools.
- **Why it matters for this benchmark:** It is a direct official problem statement tying neighborhood-level school access pressure to seat-capacity expansion.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_Schools`, `NYC_population`, `NYC_poverty_rate`, and `NYC_unemployment_rate`.
- Use the shared sub-borough-area geography from the socioeconomic layers as the preferred first-pass comparison unit.
- Explain why NTA is optional rather than automatic.
- Acknowledge that the school dataset includes mixed school types and that public-school interpretation may require filtering or caution.
- Frame the result as a facilities-access and equity screen for follow-up.

### What a very strong agent may also mention
- The `student` field may be useful as a secondary signal, but should not be treated as a clean measure of available seat capacity.
- Public-school-only filtering may be more appropriate than using all records if the question is interpreted strictly.
- A per-capita school count or school-count-per-child-population measure would be stronger in a later analytic pass, but is not required for the benchmark to be useful.
- If finer neighborhood reporting is desired, NTA or tract-level follow-up could be layered in after the first-pass sub-borough screening.

### Common failure modes
- Selecting only `NYC_Schools` and one demographic layer.
- Treating `NTA_Neighborhood_Tabulation_Areas` as the default common geography without explanation.
- Ignoring that `NYC_Schools` includes non-public records.
- Making unsupported claims about overcrowding, utilization, or seat shortages from point counts alone.
- Recommending a new school site directly from this screening setup.

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYC_Schools` is the correct facility layer in the local catalog;
- `NYC_population`, `NYC_poverty_rate`, and `NYC_unemployment_rate` provide the pressure and vulnerability context;
- the cleanest first-pass geography is the shared sub-borough-area polygon system used by those vulnerability datasets;
- school points should be counted or summarized into those polygons;
- neighborhoods with high population and elevated hardship but thinner school presence should be flagged for follow-up against more formal enrollment / capacity planning materials;
- and the result is an exploratory equity screen, not a final siting recommendation.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/descriptions.csv` and `data/metadata/`, especially:
  - `data/metadata/NYC_Schools.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrade in this revision is replacing a generic NTA-centric framing with a metadata-grounded statement that the socioeconomic layers already share a 55-area polygon geography and should usually anchor the first-pass comparison.
- No backend changes were required for this case; the revision is benchmark-only.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding a source that more directly links seat need to student travel or school-access barriers at neighborhood scale. The case now already has direct official support for projected housing growth and identified seat need, so the remaining gap is about travel/access consequences rather than facilities planning itself.
