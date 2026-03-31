# Case 4 — Air pollution and neighborhood disadvantage

**Status:** revised  
**Case ID:** 4  
**Theme:** environment / equity  
**Language:** English  
**Reviewed on:** 2026-03-22

## Task

> You are assisting a public-health / environmental justice analyst who needs to identify NYC neighborhoods where **higher ambient air pollution and socioeconomic disadvantage overlap**. The analyst wants a screening view that is credible for NYC health-equity reporting: it should use a real local air-pollution layer, pair it with neighborhood poverty and unemployment, state the geography used for comparison, and explain what the output can and cannot support. Using UrbanTrace, determine which datasets should be selected, what common geography or harmonization step is most defensible, and how the resulting analysis would support an environmental-justice narrative grounded in NYC Community Air Survey findings.

## Why this benchmark matters

This is a strong benchmark for **dataset selection under geography mismatch**, not just for naming an air-quality file.

It fits the current UrbanTrace agent architecture because `backend/llm_agent.py` answers from dataset descriptions + metadata context, while `backend/tool.py` only supports dataset-suggestion behavior. So benchmark quality here depends on whether the agent can:

1. pick the right environmental and socioeconomic layers;
2. notice that their native geographies do **not** line up cleanly;
3. avoid a tempting but weak choice like forcing everything into NTAs without justification; and
4. explain a defensible screening workflow rather than overstating causality.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use the local `NYC_air_pollution` layer as the anchor environmental burden dataset.
- Pair it with `NYC_poverty_rate` and `NYC_unemployment_rate` as neighborhood disadvantage indicators.
- Explicitly acknowledge that the air-pollution layer and the socioeconomic layers use different polygon systems.
- Prefer the **coarsest directly policy-relevant common geography available from the source layers** or document an overlay / crosswalk step, instead of casually choosing NTAs.
- Frame the result as a **screening for compounded burden** consistent with NYCCAS and NYC health-equity reporting, not as proof that poverty causes pollution or that one pollutant alone fully defines environmental injustice.

### Expected core datasets
- `NYC_air_pollution`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`

### Important geography / support datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent clearly explains why it is being used for reference, display, or an additional harmonization step
- `NYC_population` as an optional contextual denominator / prioritization aid, not a substitute for disadvantage

### Likely distractors
- `NYC_HVI` — equity-adjacent, but this is heat vulnerability rather than air pollution
- `NTA_Neighborhood_Tabulation_Areas` when selected as if it were automatically the native join geography for all three core layers

## Source-grounded rationale

### 1) NYC Community Air Survey (NYCCAS)
- **Type:** official NYC Health report / data feature
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/nyccas/
- **What it supports:** NYCCAS is NYC’s long-running neighborhood air-monitoring program. The report explicitly says it presents **maps of neighborhood air pollution levels by year** and identifies local sources driving differences across neighborhoods. It also notes that PM2.5, NO2, NO, and black carbon are highest in areas with greater traffic density, building density, warehouses, and commercial cooking.
- **Why it matters for this benchmark:** This directly grounds a neighborhood-level burden-screening task rather than a citywide summary.

### 2) NYC Health: *The public health impacts of PM2.5 from traffic air pollution*
- **Type:** official NYC Health data story
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-stories/traffic-and-air-pollution/
- **What it supports:** The page states that traffic-related PM2.5 impacts are not evenly distributed across the city and that **PM2.5 levels from all traffic sources are about 50% higher in high-poverty neighborhoods than in low-poverty neighborhoods**.
- **Why it matters for this benchmark:** This is the clearest official justification for combining an air-pollution burden layer with poverty-related neighborhood disadvantage in an environmental-justice framing.

### 3) NYC Community Air Survey landing page
- **Type:** official NYC Health program page
- **URL:** https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page
- **What it supports:** The page explains that NYCCAS was created to evaluate how air quality differs across NYC neighborhoods and notes the addition of **environmental justice sites** to better understand emissions in low-income neighborhoods.
- **Why it matters for this benchmark:** It reinforces that NYCCAS is intended for neighborhood-scale inequality analysis, not just for generic pollution mapping.

## Local dataset evidence from the repo

The benchmark should be driven by what is actually in the repo, not by an imagined data model:

1. `NYC_air_pollution`
   - Geometry: `MultiPolygon`
   - Rows: `107`
   - Key fields visible in metadata / sample data: `BoroCd`, `Geo Place Name`, `Time Period`, `Start_Date`, `Fine particles (PM 2.5)`, `Nitrogen dioxide (NO2)`, `Ozone (O3)`, vehicle-miles-traveled fields
   - Best benchmark interpretation: neighborhood air-burden layer tied to `BoroCd` / named community-district-style polygons over multiple seasonal / annual time periods

2. `NYC_poverty_rate`
   - Geometry: `MultiPolygon`
   - Rows: `55`
   - Key fields: `Sub-Borough Area`, `Official_SBA_name`, yearly values from `2000` to `2023`
   - Best benchmark interpretation: neighborhood socioeconomic disadvantage layer at Sub-Borough Area geography

3. `NYC_unemployment_rate`
   - Geometry: `MultiPolygon`
   - Rows: `55`
   - Key fields: `Sub-Borough Area`, `Official_SBA_name`, yearly values from `2000` to `2023`
   - Best benchmark interpretation: second disadvantage layer that complements poverty rather than duplicating it

4. `NTA_Neighborhood_Tabulation_Areas`
   - Geometry: `MultiPolygon`
   - Rows: `262`
   - Best benchmark interpretation: useful reference geography, but **not** the obvious native common geography for the three core datasets

## Common geography guidance

This is the most important correction to the prior draft.

A strong benchmark answer should **not** assume that NTAs are the right join target. The local data show:

- `NYC_air_pollution` uses about **47 unique `BoroCd` areas** in the sample inventory.
- `NYC_poverty_rate` and `NYC_unemployment_rate` use **55 Sub-Borough Areas**.
- `NTA_Neighborhood_Tabulation_Areas` is much finer (**262 areas**) and is not the native unit of the socioeconomic tables.

So the benchmark-credible answer is:

1. **Acknowledge the mismatch first.**
2. Use the `NYC_air_pollution` geography as the anchor burden layer **or** use an explicit overlay / crosswalk step to reconcile it with Sub-Borough Areas.
3. Treat NTA as optional display or secondary reference geography unless the agent can justify a real harmonization workflow.

In other words, this benchmark is successful when the agent says something like:

> “The air-pollution layer and the poverty/unemployment layers are not already aligned, so I would either aggregate to the coarser comparable neighborhood geography or document an areal-interpolation / crosswalk step before comparing burdens.”

That is much more credible than claiming a frictionless neighborhood join.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_air_pollution`, `NYC_poverty_rate`, and `NYC_unemployment_rate`.
- Explain that the task is a **compounded burden screening**.
- Recognize the geography mismatch between air-pollution polygons and Sub-Borough Area polygons.
- Avoid treating `NTA_Neighborhood_Tabulation_Areas` as the automatic common geography.
- Mention a plausible comparison variable from the air layer, especially `Fine particles (PM 2.5)` and/or `Nitrogen dioxide (NO2)`.
- Keep the conclusion policy-oriented: identify neighborhoods for closer environmental-justice follow-up.

### Common failure modes
- Selecting only `NYC_air_pollution` and stopping there.
- Replacing disadvantage with `NYC_population` alone.
- Choosing `NYC_HVI` because it sounds like a general vulnerability layer.
- Declaring NTAs as the obvious join target without addressing the underlying geography mismatch.
- Making unsupported causal claims such as “poverty causes pollution” from these layers alone.

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYC_air_pollution` is the environmental burden source;
- `NYC_poverty_rate` and `NYC_unemployment_rate` provide the social disadvantage dimensions;
- the analysis should compare PM2.5 and/or NO2 burden against those disadvantage measures after harmonizing geographies;
- the result would identify neighborhoods where pollution burden and socioeconomic stress co-occur, matching NYC Health’s framing that traffic-related PM2.5 impacts are higher in poorer neighborhoods;
- the output is a screening product for prioritization, not a full causal exposure model.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/descriptions.csv` and `data/metadata/` plus the current agent/tool constraints in `backend/llm_agent.py` and `backend/tool.py`.
- The main benchmark upgrade in this revision is replacing a generic “use NTA” framing with a source- and metadata-grounded statement that the relevant local layers are on **different neighborhood geographies** and must be reconciled explicitly.
- No additional backend changes were required for this case; the benchmark remains focused on evaluating agent dataset choice and reasoning quality within the current suggestion-only tool design.
