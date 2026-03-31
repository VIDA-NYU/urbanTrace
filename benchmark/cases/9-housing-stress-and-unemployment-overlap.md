# Case 9 — Housing stress and unemployment overlap

**Status:** revised  
**Case ID:** 9  
**Theme:** housing / inequality  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are supporting a policy researcher who wants to screen for neighborhoods facing **compounded housing and economic stress**. The goal is to identify areas where housing pressure plausibly overlaps with labor-market distress and poverty, so the city can prioritize follow-up on neighborhood instability and affordability risk. Using UrbanTrace, determine which datasets should be combined, what geography should anchor the comparison, and how the result should be interpreted for a realistic, source-grounded housing-stress workflow.

## Why this benchmark matters

This benchmark is really about **proxy discipline, geography discipline, and explanation quality** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. treat `NYC_housing_units` as if more units automatically means more housing stress;
2. select only unemployment or only poverty and miss the compounded-burden framing;
3. default to `NTA_Neighborhood_Tabulation_Areas` without noticing that the core socioeconomic layers in the repo are actually on a shared **sub-borough-area** geography; or
4. make broad claims about “housing insecurity” without acknowledging that the local catalog does **not** appear to contain a direct neighborhood cost-burden or eviction layer for this case.

A stronger agent should recognize that the best locally supported benchmark answer is about **housing pressure proxied by rent levels, interpreted together with unemployment and poverty**, with housing-unit counts used carefully as contextual stock/supply information rather than as the primary stress signal.

That fits the current architecture well because `backend/llm_agent.py` answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` supports suggestion-oriented dataset selection rather than full downstream GIS execution. So benchmark quality depends on choosing the right 1–5 datasets, resisting plausible distractors, and clearly explaining proxy logic and limitations.

## Source-grounded planning rationale

Official and public policy materials support a benchmark that connects housing stress with broader economic hardship rather than treating housing as a standalone inventory problem.

The New York State Comptroller’s report *New Yorkers in Need: The Housing Insecurity Crisis* explicitly frames housing insecurity as driven primarily by affordability pressure and links it to broader economic hardship. The report notes that in 2022 nearly 3 million New York households were housing insecure, that cost burdens were the primary driver, and that households were often forced into tradeoffs with other essentials. That is a strong policy basis for a benchmark centered on **housing pressure**, not merely housing stock.

NYC Opportunity’s poverty-measure materials reinforce the same logic from the economic side: the NYC poverty measure is designed in part to reflect the City’s unusually high housing costs, and the 2022 writeup emphasizes that when temporary aid receded and the cost of basic necessities rose, many New Yorkers faced growing financial pressure. That supports a benchmark where poverty and unemployment are not side notes but part of the explanation for why housing stress matters.

In the local UrbanTrace repo, that source-grounded framing has an important consequence: `NYC_housing_units` alone is **not** the best primary housing-stress layer. The metadata shows it is a sub-borough time series of annual housing-unit counts. That is useful context for stock and trend, but it is not itself an affordability or instability measure. By contrast, `NYC_median_rent` is a much more defensible local proxy for housing pressure because it directly captures neighborhood rent levels over time on the same sub-borough geography as the unemployment, poverty, and population layers.

So the most benchmark-credible first-pass formulation is:

- use `NYC_median_rent` as the main housing-pressure proxy;
- use `NYC_unemployment_rate` and `NYC_poverty_rate` as the economic-stress layers;
- use `NYC_population` to distinguish burdens affecting many residents from small-population areas; and
- use `NYC_housing_units` only as optional supporting context about neighborhood stock and growth.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_median_rent`, `NYC_unemployment_rate`, `NYC_poverty_rate`, and `NYC_population`.
- Treat `NYC_housing_units` as an optional support layer, not the main measure of stress.
- Anchor the comparison on the shared **sub-borough-area** geography already used by the rent, unemployment, poverty, and population datasets.
- Interpret the result as a **screen for neighborhoods where affordability pressure and economic hardship coincide**, not as proof of eviction risk or direct housing insecurity.
- Explicitly note that this is a proxy-based benchmark because the repo does not appear to include a direct local layer for rent burden, eviction filings, or homelessness by matching neighborhood geography.

### Expected core datasets
- `NYC_median_rent`
- `NYC_unemployment_rate`
- `NYC_poverty_rate`
- `NYC_population`

### Important optional support datasets
- `NYC_housing_units`
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explains why it is being used for display/reporting rather than as the default harmonization surface

### Likely distractors
- `NYC_housing_units` when treated as if stock counts alone represent housing stress
- `NYC_income_diversity_ratio` — interesting inequality context, but weaker than direct poverty and unemployment measures for this specific case
- `MODZCTA` — tempting as a familiar reporting geography, but mismatched to the local core socioeconomic layers here

## Expected UrbanTrace dataset mapping

### 1) `NYC_median_rent`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual rent fields through `2023`
- Best benchmark interpretation: the strongest local proxy for neighborhood housing pressure / affordability strain in this case

### 2) `NYC_unemployment_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: neighborhood labor-market distress layer aligned to the same geography as the rent proxy

### 3) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: concentrated economic vulnerability layer that makes the housing-pressure screen more credible than a rent-only comparison

### 4) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: scale / exposure layer so the analysis does not treat every high-stress area as equally consequential regardless of resident count

### 5) `NYC_housing_units` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual housing-unit counts through `2023` with `2020` missing
- Important benchmark caveat:
  - this is a stock / trend layer, **not** a direct distress measure
- Best benchmark interpretation: contextual evidence on neighborhood housing stock, growth, or limited supply growth when paired with rent and economic stress

### 6) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed key fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
- Best benchmark interpretation: optional neighborhood reporting geography, not the cleanest default comparison surface for this case

## Common geography guidance

This is the central benchmark correction.

The prior draft listed `NTA_Neighborhood_Tabulation_Areas` as a core layer and implied `NYC_housing_units` was the primary housing-side dataset. The repo evidence supports a more careful framing:

- `NYC_median_rent`, `NYC_unemployment_rate`, `NYC_poverty_rate`, `NYC_population`, and `NYC_housing_units` are all already aligned to the same **55-row sub-borough-area polygon geography**.
- `NTA_Neighborhood_Tabulation_Areas` is a different 262-row geography.
- Because the core candidate layers already share geography, the cleanest benchmark answer is to **stay on the sub-borough-area polygons** rather than forcing an unnecessary NTA conversion.

So the most credible first-pass workflow is:

1. Anchor the analysis on the shared sub-borough-area polygons.
2. Compare recent rent levels (or recent rent trends) with recent unemployment and poverty.
3. Use population to contextualize scale.
4. Optionally consult housing-unit counts to discuss stock growth or whether stress is being observed despite substantial stock.
5. Only bring in NTAs if the agent explicitly says they are being used for display, communication, or a later crosswalk step.

A strong answer may phrase this as:

> “Because the rent, unemployment, poverty, population, and housing-unit layers already live on the same sub-borough geography in the local repo, I would anchor the benchmark there. NTA is optional reporting geography, not the default harmonization surface.”

That is much more benchmark-credible than defaulting to NTAs without explanation.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Median rent is a proxy for housing pressure, not a direct burden measure.** High rent does not by itself prove that residents are cost-burdened.
- **Housing-unit counts are not stress.** More or fewer units may matter for context, but the variable is not itself a hardship indicator.
- **This is a screening exercise.** It can flag neighborhoods where housing pressure and economic stress plausibly overlap, but it does not prove eviction risk, homelessness risk, or legal housing inadequacy.
- **Population matters.** Stress affecting a larger resident base may deserve different prioritization than similar rates in a smaller area.
- **Time alignment matters.** Since these are annual time-series layers, a strong answer should prefer comparable recent years such as 2022 or 2023 and note that `2020` is missing in several local files.

## Source-grounded rationale

### 1) New Yorkers in Need: The Housing Insecurity Crisis
- **Type:** public report
- **Agency / publisher:** Office of the New York State Comptroller
- **URL:** https://www.osc.ny.gov/reports/new-yorkers-need-housing-insecurity-crisis
- **What it supports:** Housing insecurity in New York is driven primarily by cost burden, and affordability strain is linked to broader household instability.
- **Why it matters for this benchmark:** It justifies a benchmark that evaluates housing pressure together with economic hardship rather than treating housing as a simple stock lookup.

### 2) Poverty Measure — NYC Opportunity
- **Type:** official NYC program/report page
- **Agency:** NYC Opportunity
- **URL:** https://www.nyc.gov/site/opportunity/poverty-in-nyc/poverty-measure.page
- **What it supports:** NYC’s poverty framework explicitly accounts for the city’s high housing costs and emphasizes the way rising living costs create financial pressure.
- **Why it matters for this benchmark:** It supports combining poverty with a housing-cost proxy instead of treating poverty and housing as unrelated topics.

### 3) New York City Government Poverty Measure 2022
- **Type:** official NYC report
- **Agency:** NYC Opportunity
- **URL:** https://www.nyc.gov/assets/opportunity/pdf/MOE-2022-Poverty-Measure-Comprehensive-Brief.pdf
- **What it supports:** Poverty rose as temporary supports receded and basic costs increased, reinforcing the relevance of compounded affordability and economic stress.
- **Why it matters for this benchmark:** It strengthens the economic-hardship side of the benchmark, even though the repo’s actual operational layer is `NYC_poverty_rate`.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_median_rent`, `NYC_unemployment_rate`, `NYC_poverty_rate`, and `NYC_population`.
- Optionally add `NYC_housing_units`, but explain that it is contextual rather than the primary stress measure.
- Use the shared sub-borough-area polygon geography as the preferred first-pass comparison unit.
- Explain that the case is proxy-based because direct cost-burden / eviction / homelessness layers are not the local benchmark core here.
- Keep the conclusion calibrated: this is a planning screen for overlap of housing pressure and economic hardship.

### What a very strong agent may also mention
- Recent-year alignment matters; `2022` or `2023` are the cleanest common targets, with `2020` missing in several series.
- Rent trend and unemployment trend may be as informative as absolute levels.
- `NYC_housing_units` can be used to discuss whether stress persists even where stock is relatively large, but not to infer burden directly.
- NTA reporting is possible later, but not necessary for a benchmark-valid answer.

### Common failure modes
- Returning only `NYC_housing_units`.
- Ignoring `NYC_median_rent` even though it is the more defensible local housing-pressure proxy.
- Defaulting to `NTA_Neighborhood_Tabulation_Areas` without explaining the geography mismatch.
- Using `NYC_income_diversity_ratio` in place of direct poverty or unemployment measures.
- Making unsupported claims such as “high housing-unit count means high housing stress” or “these neighborhoods are definitely housing insecure.”

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYC_median_rent` is the strongest available local housing-pressure proxy;
- `NYC_unemployment_rate` and `NYC_poverty_rate` capture the economic-stress side of the overlap;
- `NYC_population` helps interpret scale;
- `NYC_housing_units` is useful supporting context about stock, but not the main hardship variable;
- the cleanest first pass is to stay on the shared sub-borough-area geography and compare recent values there;
- the output is a screening product for follow-up, not a definitive measure of cost burden or eviction vulnerability.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYC_median_rent.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NYC_housing_units.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - replacing a housing-units-first framing with a rent-plus-economic-stress framing grounded in the actual repo;
  - correcting the geography guidance so the case stays on the repo’s shared sub-borough-area polygons;
  - clarifying that `NYC_housing_units` is contextual stock data rather than a direct hardship indicator; and
  - tightening the interpretation so the case evaluates dataset choice, proxy logic, and geography reasoning rather than generic prose about housing.
- No backend changes were required for this case; the benchmark remains focused on evaluating reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one NYC-specific official source directly on neighborhood rent burden, evictions, or Housing and Vacancy Survey affordability conditions that can be cleanly tied to the local dataset inventory. The case is benchmark-usable now because the available official/public sources justify the policy scenario, and the repo metadata clearly supports the rent-proxy and sub-borough-geography corrections.