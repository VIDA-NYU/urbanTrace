# Case 12 — Councils with greatest compounded need

**Status:** revised  
**Case ID:** 12  
**Theme:** governance / prioritization  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are helping an urban policy team identify which NYC City Council districts appear to face the greatest combined burden from poverty, unemployment, air-pollution burden, and crash risk. The benchmark is not asking for a generic district profile. It is testing whether the agent can connect multiple burden layers that live on different geographies, recognize that City Council districts are a governance-facing reporting unit rather than the native analysis unit for most source layers, and explain what kind of composite prioritization would be credible under the current UrbanTrace workflow.

## Why this benchmark matters

This is a benchmark for **cross-domain dataset selection, geography harmonization, and composite-prioritization discipline** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. select `City_Council_Districs` plus only one burden layer and pretend that is a composite need screen;
2. choose the right burden layers but fail to explain that they live on **different underlying geographies**;
3. treat the council polygons as if poverty, unemployment, and air-pollution values are already measured there;
4. summarize crashes as raw counts only, without acknowledging exposure / scale issues; or
5. produce a dramatic “worst districts” ranking without clarifying that this is an exploratory prioritization screen rather than a validated causal index.

A stronger agent should recognize that this case is really about **reconciling multiple burdens into a governance-facing district lens**. That fits the current UrbanTrace architecture well because `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` only supports suggestion-oriented dataset selection rather than automatic GIS overlay pipelines. So benchmark quality depends on choosing the right 1–5 datasets, resisting plausible distractors, and clearly narrating how the layers would have to be harmonized before any district ranking is credible.

## Source-grounded planning rationale

This case is supported by real NYC public-policy materials rather than invented scenario framing.

The NYC Opportunity poverty-measure materials explicitly frame poverty as part of broader citywide economic hardship and note that many New Yorkers faced mounting financial pressure as temporary relief receded and the cost of basic necessities rose. That is a strong official basis for using poverty-related burden as one component of a district-prioritization screen.

The repo also contains a direct unemployment layer (`NYC_unemployment_rate`) on the same sub-borough geography as poverty. Together, those two local datasets provide a credible **socioeconomic-need component**.

On the environmental side, the NYC Community Air Survey page and related city health materials make neighborhood-scale air burden a legitimate policy concern, while the local `NYC_air_pollution` layer contains measured pollutant indicators such as **Fine particles (PM 2.5)** and **Nitrogen dioxide (NO2)** on community-district-style polygons across multiple time periods.

On the safety side, Vision Zero materials justify the use of crash history as a city planning and prioritization signal. The local `NYC_vehicle_collisions_crashes` dataset provides geocoded collision events with injury and fatality fields, which can be summarized spatially into a policy reporting geography.

The key benchmark challenge is that none of those burden layers are natively stored as City Council districts:

- `City_Council_Districs` is a **51-row MultiPolygon** governance geography.
- `NYC_poverty_rate` is a **55-row MultiPolygon** sub-borough-area dataset.
- `NYC_unemployment_rate` is a **55-row MultiPolygon** sub-borough-area dataset.
- `NYC_air_pollution` is a **107-row MultiPolygon** dataset with repeated observations across time periods on community-district-style geography.
- `NYC_vehicle_collisions_crashes` is a **point** dataset.

So the benchmark is not simply “find bad council districts.” It is: **Can the agent recognize that council districts are the reporting target, while the need layers must first be chosen carefully, time-aligned, and spatially translated into that governance geography?**

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `City_Council_Districs` as the final governance / reporting geography because the prompt explicitly asks for City Council districts.
- Use `NYC_poverty_rate` and `NYC_unemployment_rate` as the socioeconomic burden layers.
- Use `NYC_air_pollution` for the environmental burden component, preferably with a clearly named annual pollutant metric such as **PM2.5** or **NO2** from a recent annual-average slice.
- Use `NYC_vehicle_collisions_crashes` for the traffic-safety burden component, ideally emphasizing injuries (and optionally fatalities) rather than raw collision presence alone.
- Explain that poverty, unemployment, and air-pollution polygons would need overlay / crosswalk logic to be translated into council districts, while crashes would need to be spatially summarized into those districts.
- Treat the output as a **screen for council-level follow-up and resource prioritization**, not as a definitive formula for budget allocation or proof of causal relationships.

### Expected core datasets
- `City_Council_Districs`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`
- `NYC_air_pollution`
- `NYC_vehicle_collisions_crashes`

### Important optional support datasets
- `NYC_population` as a scale / denominator safeguard when comparing crash burden or interpreting district-wide need
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly says it is for secondary display or local drill-down rather than the core council-district scoring surface

### Likely distractors
- `NYC_HVI`, which is meaningful in heat-focused cases but is not one of the requested burden components here
- `MODZCTA`, which may look attractive because of ZIP familiarity but is not the prompt’s reporting unit and does not solve the core harmonization problem
- using `NYC_population` as the only social variable rather than as context for interpretation
- ranking districts from one metric alone while calling the result “compounded need"

## Expected UrbanTrace dataset mapping

### 1) `City_Council_Districs`
- Geometry in local metadata: `MultiPolygon`
- Rows: `51`
- Confirmed key fields:
  - `CounDist`
- Best benchmark interpretation: the governance-facing district geometry used for final reporting and prioritization, not the native source geography for most burden layers

### 2) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: one of the two core socioeconomic burden layers, already aligned with unemployment on shared sub-borough polygons

### 3) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: the second core socioeconomic burden layer, suitable for pairing with poverty in a combined hardship screen

### 4) `NYC_air_pollution`
- Geometry in local metadata: `MultiPolygon`
- Rows: `107`
- Confirmed key fields:
  - `BoroCd`
  - `Geo Place Name`
  - `Time Period`
  - `Start_Date`
  - `Fine particles (PM 2.5)`
  - `Nitrogen dioxide (NO2)`
- Best benchmark interpretation: neighborhood air-burden layer on community-district-style polygons, with time-specific observations that require a deliberate metric and period choice

### 5) `NYC_vehicle_collisions_crashes`
- Geometry in local metadata: `Point`
- Rows: `8605`
- Confirmed key fields:
  - `CRASH DATE`
  - `LATITUDE`
  - `LONGITUDE`
  - `NUMBER OF PERSONS INJURED`
  - `NUMBER OF PERSONS KILLED`
  - `NUMBER OF PEDESTRIANS INJURED`
  - `NUMBER OF CYCLIST INJURED`
- Best benchmark interpretation: point-level traffic-safety burden that should be summarized into the reporting districts, ideally with injury severity considered

### 6) `NYC_population` (important support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: an interpretation safeguard so highly populated districts are not automatically treated as highest-need purely from raw counts or total burden mass

## Common geography guidance

This is the key benchmark correction.

The seed correctly points to City Council districts as the governance target, but the repo evidence shows that the burden layers do **not** share that geography natively.

The local catalog shows:

- `City_Council_Districs` = **51 council polygons**
- `NYC_poverty_rate` + `NYC_unemployment_rate` + `NYC_population` = **55 shared sub-borough polygons**
- `NYC_air_pollution` = **community-district-style polygons with repeated time slices**
- `NYC_vehicle_collisions_crashes` = **points**

So the most benchmark-credible workflow is not “join everything directly because it is all NYC data.” Instead it is:

1. **Choose the council districts as the final reporting target.**
2. **Choose recent, clearly named source metrics** for poverty, unemployment, and air pollution rather than mixing arbitrary years or time periods.
3. **Translate polygon burdens into council districts** using an explicit overlay / crosswalk concept, not by assuming the boundaries already match.
4. **Summarize crash events into council districts** using point-in-polygon logic, and preferably emphasize injuries or severe crashes rather than raw event presence alone.
5. **Optionally use population as context** so the resulting ranking is not a simple reward for large resident counts or large land area.
6. Report the result as a **council-district screening index / shortlist for follow-up**, not a mechanically definitive burden score.

A strong answer may phrase this as:

> “Because the prompt asks for City Council districts, I would use `City_Council_Districs` as the final reporting surface. But poverty, unemployment, and air pollution are not natively measured on that same geography, so I would first pick recent comparable source metrics, overlay the polygon layers into council districts, summarize crash injuries into those districts, and only then create a composite need ranking.”

That is much more benchmark-credible than pretending the council layer is already the common geography for every burden.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Composite need is a policy screen, not a law of nature.** Different weighting choices can change rankings.
- **Time alignment matters.** Poverty and unemployment are annual neighborhood indicators, air pollution has repeated time slices, and crashes are event-level over many years.
- **Air-pollution metric choice matters.** PM2.5 and NO2 are both defensible, but they are not interchangeable and should not be blended casually without explanation.
- **Crash burden should not default to raw counts alone.** Injuries or severity-aware summaries are more credible than simple event totals.
- **Population context matters.** Large or highly active districts can accumulate more crashes or total burden partly because more people live in or travel through them.
- **Boundary translation introduces approximation.** Council districts, sub-borough areas, and community-district-style air polygons do not line up perfectly.
- **This is a prioritization screen.** It can help identify districts for council-level follow-up, advocacy, or budgeting discussion, but it does not prove causation or dictate funding formulas by itself.

## Source-grounded rationale

### 1) Poverty Measure – NYC Opportunity
- **Type:** official NYC policy / documentation page
- **Agency:** NYC Opportunity
- **URL:** https://www.nyc.gov/site/opportunity/poverty-in-nyc/poverty-measure.page
- **What it supports:** NYC describes the NYCgov Poverty Measure as accounting for the city’s higher housing costs and emphasizes that many New Yorkers faced mounting financial pressure as costs rose and temporary supports expired.
- **Why it matters for this benchmark:** It grounds the use of poverty-related hardship as a real city-policy burden relevant to district prioritization.

### 2) Poverty Data – NYC Opportunity
- **Type:** official NYC data/documentation page
- **Agency:** NYC Opportunity
- **URL:** https://www.nyc.gov/site/opportunity/poverty-in-nyc/poverty-data.page
- **What it supports:** NYC publishes underlying poverty-related datasets for researchers who want to replicate or expand poverty research.
- **Why it matters for this benchmark:** It supports treating poverty as a documented, operational city indicator rather than an invented benchmark variable.

### 3) New York City Community Air Survey
- **Type:** official NYC data portal page
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://www.nyc.gov/site/doh/data/data-sets/air-quality-nyc-community-air-survey.page
- **What it supports:** NYC maintains neighborhood air-pollution measures suitable for local burden analysis.
- **Why it matters for this benchmark:** It grounds the air-pollution component of the compounded-need screen in a real NYC monitoring and reporting program.

### 4) Vision Zero – NYC.gov
- **Type:** official city program page
- **Agency:** New York City
- **URL:** https://www.nyc.gov/content/visionzero/pages/
- **What it supports:** NYC treats crash and traffic-injury prevention as an active city policy priority.
- **Why it matters for this benchmark:** It makes crash risk a legitimate component of a district-level prioritization screen rather than an arbitrary add-on.

### 5) Economic conditions data for NYC – Environment & Health Data Portal
- **Type:** official NYC portal page
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-explorer/economic-conditions/
- **What it supports:** NYC maintains neighborhood economic-condition indicators, including unemployment-oriented context, in a city health/equity reporting environment.
- **Why it matters for this benchmark:** It supports using unemployment as part of a broader burden screen rather than as an unrelated labor-market side variable.

## Suggested evaluation notes

### What a strong agent should do
- Select all five core datasets named above, or four plus a clearly justified optional omission with explanation.
- Recognize that `City_Council_Districs` is the **reporting target**, not the native geometry of poverty, unemployment, or air pollution.
- Explain that polygon overlay / translation is required before ranking council districts.
- Treat crash risk as a point-summary problem and prefer injury-aware interpretation.
- Keep the output calibrated as a prioritization screen for council-level follow-up.

### What a very strong agent may also mention
- `NYC_population` is worth adding to guard against over-reading raw crash totals or total burden mass.
- A recent annual air-pollution slice such as `Annual Average 2022` is more defensible than mixing seasonal and annual rows.
- PM2.5 and NO2 should usually be evaluated separately or carefully standardized before any combined score is discussed.
- The best first pass may be a shortlist of likely high-need districts rather than a false-precision ranked index.

### Common failure modes
- Returning only `City_Council_Districs` plus one burden dataset.
- Ignoring the mismatch between council, sub-borough, community-district, and point geographies.
- Treating `NYC_HVI` as a core burden layer when the prompt is specifically about poverty, unemployment, pollution, and crash risk.
- Ranking districts from raw crash counts alone.
- Claiming a precise composite score without explaining source-metric selection, time alignment, or geometry translation.

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `City_Council_Districs` should be used because the question is explicitly governance-facing;
- `NYC_poverty_rate` and `NYC_unemployment_rate` provide the socioeconomic burden component on a shared local polygon geography;
- `NYC_air_pollution` provides the environmental burden component, ideally using a recent annual PM2.5 or NO2 measure;
- `NYC_vehicle_collisions_crashes` provides the traffic-safety burden component and should be spatially summarized into council districts;
- the burden layers do not share a native geography, so a credible workflow must translate them into council districts before creating any combined ranking;
- `NYC_population` is useful context if the agent wants to avoid misleading raw-count comparisons; and
- the result is best framed as a council-level prioritization shortlist for follow-up, not a definitive burden formula.

## Retrieval / provenance notes

- This case was reconstructed from the seed entry in `benchmark/urbantrace_agent_benchmark_seeds.json` for Case 12 and revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/City_Council_Districs.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_air_pollution.json`
  - `data/metadata/NYC_vehicle_collisions_crashes.json`
  - `data/metadata/NYC_population.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - restoring the missing seed case as a concrete per-case markdown file;
  - making explicit that City Council districts are the final governance target rather than the native common geometry;
  - tightening the case around the repo’s actual polygon and point layers instead of an implied ready-made district score; and
  - grounding the prompt in real NYC poverty, air-quality, economic-conditions, and Vision Zero materials.
- No backend changes were required for this case; the benchmark remains focused on evaluating dataset choice and harmonization reasoning under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one stronger official source specifically on council-district or district-level budgeting / prioritization practice in NYC, plus one explicit note about a preferred composite-construction strategy (for example, standardized z-scores versus tiered burden flags). The case is benchmark-usable now because the seed prompt is restored, the local metadata clearly supports the geometry warnings, and the official NYC poverty / air-quality / Vision Zero materials are sufficient to justify the compounded-burden framing.