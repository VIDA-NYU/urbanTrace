# Case 11 — Arrest patterns and social conditions

**Status:** revised  
**Case ID:** 11  
**Theme:** public safety / equity  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> An urban-policy analyst wants to explore whether some NYC neighborhoods show comparatively elevated arrest activity while also facing higher poverty or unemployment. Using the available data catalog, identify the enforcement and social-condition datasets needed for a neighborhood screen, choose a defensible common geography, and explain how to interpret the result as an exploratory burden screen rather than a causal claim about policing or community behavior.

## Why this benchmark matters

This is a benchmark for **dataset selection, geography discipline, and interpretation control** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. select only `NYPD_arrests_data` and summarize arrests without bringing in any social-condition layer;
2. select poverty or unemployment polygons but fail to explain how point arrests would need to be summarized into them;
3. default to `NTA_Neighborhood_Tabulation_Areas` simply because it is a familiar neighborhood boundary, even though the repo’s poverty and unemployment layers are not natively on NTA geography; or
4. treat higher arrest counts as direct evidence of higher criminality, rather than as a blend of enforcement, reporting, offense mix, land use, and population exposure.

A stronger agent should recognize that this case is really about **screening for overlap between enforcement activity and neighborhood disadvantage** using the repo’s actual geometry inventory. That fits the current architecture well because `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` is designed to suggest relevant datasets rather than execute a full spatial ETL pipeline. So benchmark quality depends on picking the right 1–5 datasets, resisting plausible distractors, and clearly narrating the geography and interpretation limits.

## Source-grounded planning rationale

A strong external grounding source is the John Jay Research and Evaluation Center’s 2024 report **Color Contrast: Racial and Ethnic Disparities in New York City Law Enforcement**, which explicitly states that **arrest rates vary across New York City neighborhoods** and examines whether disparities persist after accounting for neighborhood demographics and crime rates. That makes neighborhood-pattern analysis of arrests an evidence-backed NYC public-policy task rather than an invented scenario.

An official NYPD source also supports this benchmark. The NYPD **Crime and Enforcement Activity Reports** page states that its enforcement reports present statistics on race and ethnicity from NYPD records, including **arrests** recorded through the booking process. That confirms that arrest activity is a recognized, reportable enforcement signal in NYC’s own institutional reporting.

The NYC Comptroller’s report **Addressing the Harms of Prohibition** makes the arrest-plus-disadvantage overlap even more explicit. Its neighborhood analysis found that places with the highest marijuana-arrest rates tended to have **lower incomes, higher unemployment, and higher poverty** than neighborhoods with lower arrest rates. While that report is offense-specific rather than a full arrest-system study, it is direct local evidence that enforcement concentration and socioeconomic disadvantage can overlap at neighborhood scale in NYC.

On the social-conditions side, the local repo already contains neighborhood poverty and unemployment layers:

- `NYC_poverty_rate`
- `NYC_unemployment_rate`

Both are **55-row MultiPolygon** datasets on the repo’s **Sub-Borough Area** geography, with shared keys such as `Sub-Borough Area`, `Official_SBA_name`, and `bor_subb`.

That matters because the local arrest dataset is not already aggregated to those same polygons:

- `NYPD_arrests_data` is a **point** dataset with coordinates, arrest date, offense descriptors, law category, borough, precinct, age group, sex, and race.

So the benchmark is not just “find arrest + poverty data.” It is really: **Can the agent notice that the cleanest first-pass geography is the repo’s sub-borough social-condition polygons, then summarize arrests into them instead of defaulting to a different boundary system without explanation?**

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYPD_arrests_data` as the enforcement-event layer.
- Use `NYC_poverty_rate` and/or `NYC_unemployment_rate` as the neighborhood disadvantage layers directly named by the prompt.
- Use `NYC_population` as an important denominator / context layer so arrest intensity is not interpreted from raw counts alone.
- Prefer the **poverty / unemployment / population polygon geography** as the first-pass comparison unit, because those local layers already share the same 55-area sub-borough structure.
- Treat `NTA_Neighborhood_Tabulation_Areas` as optional reporting geography only if the agent explicitly explains an additional overlay step.
- Interpret the output as an **exploratory overlap screen** for policy follow-up, not proof that disadvantage causes arrests or that arrests are an unbiased proxy for harm.

### Expected core datasets
- `NYPD_arrests_data`
- `NYC_poverty_rate`
- `NYC_unemployment_rate`

### Important optional support datasets
- `NYC_population`
- `NTA_Neighborhood_Tabulation_Areas` only if the agent clearly says it is being used for reporting/display rather than as the default harmonization surface

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when treated as the automatic common geography
- `City_Council_Districs` / council-district layers, which are useful for political reporting but are not the cleanest repo-native comparison surface here
- `NYC_population` when omitted entirely; it is not the main social-burden variable, but a strong agent should realize raw arrest counts are hard to interpret without scale
- race-only interpretation of `PERP_RACE` without first establishing the neighborhood overlap task requested in the prompt

## Expected UrbanTrace dataset mapping

### 1) `NYPD_arrests_data`
- Geometry in local metadata: `Point`
- Rows: `14649`
- Confirmed key fields:
  - `ARREST_DATE`
  - `OFNS_DESC`
  - `LAW_CAT_CD`
  - `ARREST_BORO`
  - `ARREST_PRECINCT`
  - `AGE_GROUP`
  - `PERP_SEX`
  - `PERP_RACE`
  - `Latitude`
  - `Longitude`
- Best benchmark interpretation: point-level enforcement events that can be filtered by time or offense type and spatially summarized into neighborhood polygons

### 2) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: one of the two main neighborhood disadvantage layers directly requested by the prompt

### 3) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: the second main neighborhood disadvantage layer directly requested by the prompt

### 4) `NYC_population` (important support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: a scale / denominator layer that helps distinguish high raw arrest counts from high arrest intensity relative to residents

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed key fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: optional reporting geography, not the cleanest first-pass harmonization layer for this case

## Common geography guidance

This is the key benchmark correction.

The seed metadata lists `NTA_Neighborhood_Tabulation_Areas` as an expected relevant dataset, but the actual repo evidence says the cleaner first-pass comparison unit is the **sub-borough-area** geography already shared by the social-condition layers:

- `NYPD_arrests_data` is a **point** layer.
- `NYC_poverty_rate` is a **55-row MultiPolygon** layer.
- `NYC_unemployment_rate` is a **55-row MultiPolygon** layer.
- `NYC_population` is a **55-row MultiPolygon** layer.
- `NTA_Neighborhood_Tabulation_Areas` is a different **262-row MultiPolygon** layer.

So the most benchmark-credible first-pass workflow is:

1. **Anchor the analysis on the poverty / unemployment polygons.**
2. Add `NYC_population` if the agent wants a more interpretable burden screen.
3. Spatially summarize arrests into those same polygons.
4. Compare arrest counts or simple arrest intensity proxies against poverty and unemployment patterns.
5. Flag polygons where arrest activity and social disadvantage overlap.
6. Only convert to NTAs later if the agent explicitly describes a second overlay / reporting step.

A strong answer may phrase this as:

> “Because the social-condition layers already share a sub-borough polygon geography and arrests are point events, I would anchor the comparison on those sub-borough polygons and summarize arrests into them. I would treat NTA boundaries as optional display geography rather than the default join surface.”

That is materially more credible than defaulting to NTAs without explanation.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Arrests are not the same thing as victimization or underlying offending.** They reflect enforcement, reporting, offense mix, and policing practice as well as community conditions.
- **Raw counts are not enough.** A large, dense, or highly active neighborhood may have more arrests partly because more people live in or move through it.
- **Population context matters.** `NYC_population` is not the main outcome of interest, but it materially improves interpretation.
- **Time choice matters.** The poverty and unemployment layers are annual neighborhood indicators, while arrests are daily events across a longer time range. A careful answer should align periods when possible.
- **Offense mix matters.** `LAW_CAT_CD`, `OFNS_DESC`, and related fields mean the arrest layer can represent very different kinds of enforcement activity.
- **This is a screening exercise.** The result should identify neighborhoods for follow-up, not prove that poverty or unemployment causes arrest patterns.

## Source-grounded rationale

### 1) Color Contrast: Racial and Ethnic Disparities in New York City Law Enforcement
- **Type:** policy / research report
- **Organization:** John Jay Research and Evaluation Center
- **Date:** March 2024
- **URL:** https://johnjayrec.nyc/2024/03/18/prrc79_colorcontrast/
- **What it supports:** The report explicitly states that arrest rates vary across NYC neighborhoods and examines disparity after accounting for neighborhood demographics and crime rates.
- **Why it matters for this benchmark:** It makes neighborhood-level arrest-pattern analysis a credible NYC policy task rather than an invented benchmark scenario.

### 2) Reports & Analysis – Crime & Enforcement
- **Type:** official NYPD reporting page
- **Agency:** New York City Police Department
- **URL:** https://www.nyc.gov/site/nypd/stats/reports-analysis/crime-enf.page
- **What it supports:** NYPD’s own enforcement reports include statistics on arrests and race/ethnicity drawn from NYPD records management and booking data.
- **Why it matters for this benchmark:** It confirms that arrest activity is a recognized official enforcement signal suitable for neighborhood-pattern analysis.

### 3) Poverty Data – NYC Opportunity
- **Type:** official NYC data/documentation page
- **Agency:** NYC Opportunity
- **URL:** https://www.nyc.gov/site/opportunity/poverty-in-nyc/poverty-data.page
- **What it supports:** NYC publishes data resources to replicate or extend its poverty research.
- **Why it matters for this benchmark:** It supports using neighborhood poverty as a legitimate city-policy context layer in an overlap screen with enforcement activity.

### 4) Addressing the Harms of Prohibition: What NYC Can do to Support an Equitable Cannabis Industry
- **Type:** official NYC Comptroller report
- **Agency / publisher:** Office of the New York City Comptroller
- **URL:** https://comptroller.nyc.gov/reports/addressing-the-harms-of-prohibition-what-nyc-can-do-to-support-an-equitable-cannabis-industry/
- **What it supports:** The report finds that neighborhoods with the highest marijuana-arrest rates tended to have lower incomes and higher unemployment and poverty than lower-arrest neighborhoods.
- **Why it matters for this benchmark:** It is unusually direct NYC evidence that arrest concentration and socioeconomic disadvantage can overlap geographically, which is exactly the logic this screening benchmark is testing.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYPD_arrests_data` plus at least one of `NYC_poverty_rate` or `NYC_unemployment_rate`, ideally both.
- Recognize that the social-condition layers share a cleaner common polygon geography than NTAs for this specific case.
- Explain that arrests must be spatially summarized into those polygons.
- Mention `NYC_population` as an important support layer for interpretation, even if it is not the main benchmark target.
- Keep the conclusion calibrated: this is an overlap screen for follow-up, not a causal statement about policing or neighborhood behavior.

### What a very strong agent may also mention
- `ARREST_DATE` enables period alignment with the annual social-condition indicators.
- `LAW_CAT_CD` and `OFNS_DESC` could be used to avoid mixing very different enforcement categories if the analytic goal becomes more specific.
- Borough or precinct fields may help contextualize results, but they are not the cleanest first-pass comparison geography against the repo’s poverty/unemployment layers.
- Population-adjusted or rate-style summaries would improve downstream interpretation, though they are not strictly required for a valid benchmark answer.

### Common failure modes
- Returning only `NYPD_arrests_data`.
- Treating arrests as equivalent to crime burden without caveats.
- Choosing `NTA_Neighborhood_Tabulation_Areas` as the default join geography without explaining the mismatch.
- Ignoring `NYC_population` and over-interpreting raw arrest counts.
- Jumping straight to race-demographic analysis when the benchmark prompt is primarily about arrest overlap with poverty or unemployment.

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYPD_arrests_data` is the correct enforcement-event layer because it contains geocoded arrest points plus time and offense fields;
- `NYC_poverty_rate` and `NYC_unemployment_rate` are the correct neighborhood social-condition anchors because they directly match the prompt and already share a common sub-borough geography;
- `NYC_population` is worth adding so the result is not interpreted from raw counts alone;
- the cleanest first pass is to summarize arrests into the sub-borough social-condition polygons rather than forcing the comparison into NTAs;
- polygons where arrest activity overlaps with higher poverty or unemployment should be flagged for follow-up;
- the output is an exploratory justice-and-disadvantage screen, not proof of causation or unbiased enforcement intensity.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYPD_arrests_data.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - replacing the seed’s implicit NTA-first framing with the repo-supported sub-borough social-condition geography;
  - making explicit that arrests are point events that must be summarized into the neighborhood layers;
  - adding `NYC_population` as an interpretation safeguard rather than pretending counts alone are enough; and
  - grounding the benchmark in a real NYC arrest-disparity report plus official NYPD reporting documentation.
- No backend changes were required for this case; the benchmark remains focused on evaluating reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one broader NYC source that links **all-category arrest or enforcement patterns**, not just cannabis enforcement, to neighborhood disadvantage. The case now has direct local support for the overlap logic, so the remaining gap is breadth across offense types rather than whether the problem is real.
