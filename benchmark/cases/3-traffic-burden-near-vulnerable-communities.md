# Case 3 — Traffic burden near vulnerable communities

**Status:** revised draft  
**Case ID:** 3  
**Theme:** mobility / equity / environmental justice  
**Language:** English  
**Reviewed on:** 2026-03-22

## Task

> You are assisting a city environmental-justice or public-health analyst who needs to identify NYC communities where **high traffic activity coincides with social vulnerability**. The analyst is not asking for a generic traffic hotspot map. They want a screening workflow that uses UrbanTrace to combine traffic activity with neighborhood poverty, unemployment, and population burden, then summarizes the results at a defensible community geography for prioritization. The answer should explicitly acknowledge that traffic counts are a **proxy for burden/exposure**, not a direct health outcome, and should stay consistent with NYC environmental-health framing around unequal impacts from traffic-related pollution.

## Why this benchmark matters

This is a source-grounded transportation-equity / environmental-burden selection problem.

It fits the current UrbanTrace agent architecture because `backend/llm_agent.py` answers from dataset descriptions + metadata context, while `backend/tool.py` supports dataset suggestion behavior rather than deep automatic modeling. So benchmark quality depends on whether the agent:

1. picks the right traffic and vulnerability layers;
2. notices the real geography mismatch in the repo; and
3. explains a credible roll-up strategy instead of bluffing a perfect direct join.

## Source grounding

The case is supported by official NYC health / environmental-justice materials rather than invented scenario framing:

- NYC Health’s **New York City Community Air Survey** states that the program studies how pollutants from **traffic** and other sources affect air quality in different neighborhoods, and that extra monitoring sites were added to better understand emissions in **low-income neighborhoods**.
- NYC Health’s **The public health impacts of PM2.5 from traffic air pollution** states that traffic is a major PM2.5 source in NYC and that the impacts are felt more acutely in less wealthy neighborhoods; it further notes that PM2.5 from all traffic sources is about **50% higher in high-poverty neighborhoods than in low-poverty neighborhoods**.
- NYC’s **Environmental Justice for All Report Scope of Work** provides city-level policy grounding for neighborhood burden screening tied to environmental justice.

That makes this case benchmark-credible as a screening question about where heavy traffic activity and social vulnerability overlap, even though the local repo dataset is traffic volume counts rather than direct exposure modeling.

## Recommended benchmark framing

A strong answer should:

1. identify the traffic counts layer plus the socioeconomic vulnerability layers;
2. choose **Sub-Borough Areas** as the cleanest common geography available in the repo for this case;
3. explain that traffic points must be spatially aggregated into those polygons;
4. describe traffic counts as a proxy for burden/exposure, not as direct pollution or health-risk measurement; and
5. avoid drifting into nearby but less appropriate boundary layers just because their names sound “community-like.”

## Expected dataset strategy

### Expected core datasets
- `NYC_automated_traffic_volume_counts`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`
- `NYC_population`

### Best common geography for this repo
Use the **55 Sub-Borough Area polygons already embedded in the socioeconomic layers** (`NYC_poverty_rate`, `NYC_unemployment_rate`, and `NYC_population`).

Why this is the strongest benchmark choice:
- all three vulnerability layers share the same 55-row Sub-Borough Area structure;
- each includes named neighborhood-scale areas such as `Sub-Borough Area` / `Official_SBA_name` plus polygon geometry;
- the traffic dataset is point-based, so it can plausibly be aggregated into those polygons; and
- this avoids forcing an unnecessary remap to a different boundary system.

### Optional contextual boundary layer
- `NTA_Neighborhood_Tabulation_Areas`

This can be useful as a reference boundary for display or later refinement, but it is **not** the cleanest first-pass harmonization target for this repo because the vulnerability layers are not natively stored at NTA resolution.

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when treated as the default join target without explaining a crosswalk or remap
- `MODZCTA`
- `City_Council_Districs`

## Repo-specific evidence for this framing

The local metadata supports this benchmark design directly:

- `NYC_automated_traffic_volume_counts` is a **Point** dataset with 24,600 rows and a numeric `Vol` field, along with `Yr`, `Boro`, `street`, `fromSt`, `toSt`, and `Direction`.
- `NYC_poverty_rate`, `NYC_unemployment_rate`, and `NYC_population` are all **55-row MultiPolygon** datasets keyed by **Sub-Borough Area** with yearly columns through 2023 (with 2020 missing).
- `NTA_Neighborhood_Tabulation_Areas` is a separate **262-row MultiPolygon** boundary layer and therefore should not be assumed to match the socioeconomic layers directly.

## What a strong agent should say or imply

A strong UrbanTrace answer should recommend a workflow like:

1. add `NYC_automated_traffic_volume_counts`;
2. add `NYC_poverty_rate`, `NYC_unemployment_rate`, and `NYC_population`;
3. aggregate traffic-count points into the Sub-Borough Area polygons already present in the vulnerability layers;
4. compare high aggregated traffic activity against high poverty / unemployment and optionally normalize or interpret with population burden; and
5. present the result as a neighborhood screening for transportation or environmental-justice follow-up.

It is also good if the agent mentions one or more limitations:
- traffic volume is not the same as emissions, PM2.5, or health outcomes;
- year alignment may need care because these layers are multi-year;
- different choices of aggregation statistic (sum, mean, density, high-percentile) can change rankings.

## Selected supporting references

### 1) New York City Community Air Survey
- **Type:** official NYC Health program page
- **URL:** https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page
- **Why relevant:** Official NYC source stating that neighborhood air quality differs across the city, that traffic is one of the studied sources, and that additional environmental-justice monitoring sites were included to understand emissions in low-income neighborhoods.
- **Confidence:** high

### 2) The public health impacts of PM2.5 from traffic air pollution
- **Type:** official NYC Health data story
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-stories/traffic-and-air-pollution/
- **Why relevant:** Directly supports the unequal-burden framing: traffic is a major PM2.5 source in NYC, impacts are more acute in less wealthy neighborhoods, and traffic-related PM2.5 is reported as higher in high-poverty neighborhoods.
- **Confidence:** high

### 3) New York City’s Environmental Justice for All Report Scope of Work
- **Type:** official NYC scope/report
- **URL:** https://www.nyc.gov/assets/sustainability/downloads/pdf/EJ-Report-Scope.pdf
- **Why relevant:** Provides city policy grounding for environmental-justice screening and prioritization across neighborhoods.
- **Confidence:** medium-high

## Data access points for reproducibility

- Local benchmark-relevant datasets are documented in `data/descriptions.csv` and corresponding files under `data/metadata/`.
- Relevant repo files for agent behavior: `backend/llm_agent.py`, `backend/tool.py`.
- This case is primarily about **dataset choice + geography reasoning** under the current copilot architecture, not about a fully automated validated exposure model.

## Suggested evaluation notes

### What a strong agent should do
- Select the four core datasets above.
- Prefer Sub-Borough Areas as the comparison geography because that is where the socioeconomic layers already align.
- Explain that traffic points must be spatially aggregated into those polygons.
- Frame the result as a screening of co-located traffic burden and vulnerability, not as a causal health estimate.
- Mention at least one limitation or proxy caveat.

### Common failure modes
- Treating `NTA_Neighborhood_Tabulation_Areas` as an obviously correct core dataset without discussing mismatch.
- Selecting only traffic counts and one vulnerability layer.
- Claiming traffic counts directly measure pollution or health burden.
- Ignoring the need for a shared geography.
- Recommending a boundary distractor because it sounds administrative or neighborhood-like.

## Retrieval / provenance notes

- This case was revised against the repo’s actual metadata inventory, not just the earlier seed summary.
- The key benchmark correction is that the socioeconomic layers are already aligned at **Sub-Borough Area** resolution, making that the most defensible first-pass geography for this case.
- `NTA_Neighborhood_Tabulation_Areas` remains useful context, but should be treated as optional unless the agent clearly explains how it would harmonize the mismatch.
