# Case 27 — Affordability stress despite housing growth

**Status:** drafted  
**Case ID:** 27  
**Theme:** housing / affordability / neighborhood change  
**Language:** English  
**Reviewed on:** 2026-03-25

## Task

> A housing-policy analyst wants to identify NYC sub-borough areas where the housing stock has grown but rents have still risen faster than median household income. Using the available data catalog, select the housing-stock, rent, and income datasets needed for that comparison, confirm the most defensible common geography, and explain how the results should guide later anti-displacement, preservation, rezoning, or affordable-housing review.

## Why this benchmark matters

This is a benchmark for **dataset selection + clean neighborhood geography alignment + calibrated housing-policy reasoning**, not just for naming a rent table or a housing-supply table.

A weak agent will stop at one housing indicator, or reach for a generic poverty table. A stronger agent should recognize that:

1. housing-unit growth is only part of the story;
2. rent must be interpreted together with local household income;
3. the cleanest first-pass comparison in this repo is at **Sub-Borough Area** scale because the strongest candidate tables already align there; and
4. the output is only a **screening layer** for deeper housing-policy review, not a definitive displacement or affordability model.

That behavior matches the current UrbanTrace benchmark logic well: the agent is being tested on whether it can retrieve the right local tables, reject weaker substitutes, and articulate a plausible neighborhood planning workflow.

## Source-grounded planning rationale

This benchmark is grounded in real NYC housing policy and research.

NYC’s housing problem page explicitly frames the city’s affordability crisis in terms of both **high rent burden** and a **mismatch between housing demand and supply**. That is exactly the analytical logic this benchmark should reward: neighborhood housing growth should not be interpreted in isolation from what is happening to local housing costs and local incomes.

The Adams administration’s **Housing Our Neighbors** blueprint reinforces that framing. It describes the city’s housing shortage as a root cause of the affordability crisis, reports persistent rent burden, and ties housing policy to broader equity, health, and neighborhood outcomes.

The City Planning Department’s **City of Yes for Housing Opportunity Final Plan** sharpens the neighborhood-planning angle even further. It argues that NYC has not built enough housing for decades, that new housing has been concentrated in relatively few neighborhoods, and that increasing housing opportunity is part of a broader fair-housing and anti-segregation strategy linked to **Where We Live NYC**.

At the same time, NYC’s **Displacement Risk Index** shows why “more units” is not enough as a standalone policy signal. The city explicitly defines displacement risk in terms of neighborhood combinations of market pressure, rent burden, housing conditions, poverty, and injustice in the housing market. That makes a case about “housing growth but still worsening affordability pressure” a realistic planning screen.

Finally, recent NYC-focused rezoning research supports the need for a calibrated benchmark. New housing supply increases can matter, but neighborhood change can remain complex: recent evidence from NYC finds that upzoning increased housing supply while also modestly changing who moves in and who moves out. So the benchmark should reward an agent that treats unit growth as important but not sufficient.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Housing stock / supply signal:**  
   `NYC_housing_units`

2. **Housing-cost signal:**  
   `NYC_median_rent`

3. **Local affordability capacity:**  
   `NYC_median_household_income`

4. **Planning geography:**  
   Sub-Borough Area, using the shared `Sub-Borough Area`, `Official_SBA_name`, and `bor_subb` fields

5. **Interpretation rule:**  
   flag sub-borough areas where housing units have grown but rent has still outpaced local household income, then use those areas to motivate deeper preservation, subsidy, anti-displacement, rezoning, or tenant-protection review.

A good gold-standard answer does **not** need to claim that unit growth “failed,” nor does it need to build a full displacement model. It does need to show the right reasoning:

- do not use housing units alone;
- interpret rent together with income;
- prefer the already aligned neighborhood geography;
- keep the result framed as a screening and prioritization tool.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_housing_units`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: direct neighborhood housing-stock / supply signal
   - Relevant local columns confirmed in metadata:
     - `Sub-Borough Area`
     - `2005`–`2019`
     - `2021`
     - `2022`
     - `2023`
     - `Official_SBA_name`
     - `bor_subb`
   - Important caveat for evaluation: `2020` is missing
   - Best benchmark interpretation: neighborhood housing-stock growth trend

2. **`NYC_median_rent`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: direct local housing-cost signal
   - Relevant local columns confirmed in metadata:
     - `Sub-Borough Area`
     - `2000`
     - `2005`–`2023`
     - `Official_SBA_name`
     - `bor_subb`
   - Best benchmark interpretation: neighborhood rent trend

3. **`NYC_median_household_income`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: local income capacity needed to interpret whether rents are becoming less affordable
   - Relevant local columns confirmed in metadata:
     - `Sub-Borough Area`
     - `2000`
     - `2005`–`2019`
     - `2021`
     - `2022`
     - `2023`
     - `Official_SBA_name`
     - `bor_subb`
   - Important caveat for evaluation: `2020` is missing
   - Best benchmark interpretation: neighborhood affordability-capacity trend

### Acceptable secondary context, but not substitutes

4. **`NYC_population`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: useful demand-pressure context if a strong agent wants to ask whether housing growth is keeping pace with neighborhood population pressure
   - Relevant local columns confirmed in metadata:
     - `Sub-Borough Area`
     - `2000`
     - `2005`–`2019`
     - `2021`
     - `2022`
     - `2023`
     - `Official_SBA_name`
     - `bor_subb`
   - Important caveat for evaluation: `2020` is missing
   - Best benchmark interpretation: optional enhancement, not a required substitute for rent or income

### Acceptable geometry explanation

- A very strong answer may explain why **Sub-Borough Area** is a defensible first-pass geography:
  - these are standard NYC neighborhood reporting units used in housing analysis when community-district-level data is unavailable;
  - there are **55 SBAs** versus **59 community districts**, because some community districts are combined for Census/HVS purposes;
  - this makes SBA-level analysis especially plausible for housing and neighborhood-trend work.

### Plausible distractors that should usually lose to the core set

- `NYC_poverty_rate`
  - Useful for broader social-vulnerability or displacement work, but weaker than rent + income for this specific affordability-under-supply-change question.
- `NYC_unemployment_rate`
  - Also useful context, but not the most direct affordability-capacity signal here.
- `NYC_income_diversity_ratio`
  - May support a neighborhood-change or stratification story, but is not the clearest answer to this benchmark.
- `Community_Districs`
  - A plausible planning geography in general, but weaker here because the strongest housing tables are already aligned at SBA scale.
- `NTA_Neighborhood_Tabulation_Areas`
  - Also a plausible neighborhood geography in general, but not the best match for these particular core housing tables.
- `MODZCTA`
  - Too coarse / differently motivated for this case.

## Selected supporting references

### 1) Problem - NYC Housing
- **Type:** official NYC housing policy background page
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/site/housing/about/problem.page
- **Why relevant:** Directly states that high rent burden affects nearly every income group and neighborhood, and that NYC’s affordable-housing crisis reflects a mismatch between demand and supply.
- **Confidence:** high

### 2) Mayor Adams Outlines Blueprint for “Housing Our Neighbors”
- **Type:** official NYC policy / press release
- **Agency:** NYC Mayor’s Office
- **URL:** https://www.nyc.gov/mayors-office/news/2022/06/mayor-adams-outlines-blueprint-housing-our-neighbors-plan-get-new-yorkers-safe
- **Why relevant:** Grounds the benchmark in an official citywide housing blueprint linking supply, affordability, rent burden, and equitable housing policy.
- **Confidence:** high

### 3) City of Yes for Housing Opportunity Final Plan
- **Type:** official NYC planning document
- **Agency:** NYC Department of City Planning
- **URL:** https://www.nyc.gov/assets/planning/download/pdf/plans-studies/city-of-yes/housing-opportunity/city-of-yes-for-housing-opportunity_final-plan.pdf
- **Why relevant:** Frames the housing crisis in terms of shortage, uneven neighborhood housing production, rent burden, fair housing, and anti-gentrification pressure.
- **Confidence:** high

### 4) Displacement Risk
- **Type:** official NYC planning / housing data explainer
- **Agencies:** NYC Department of City Planning and NYC Department of Housing Preservation and Development
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/displacement-risk/
- **Why relevant:** Supports treating this benchmark as a screening tool for anti-displacement follow-up rather than a simple supply-success metric.
- **Confidence:** high

### 5) State of New York City’s Housing and Neighborhood Report
- **Type:** research / data methodology reference
- **Organization:** NYU Furman Center
- **URL:** https://www.furmancenter.org/data-tool/state-of-the-city/
- **Why relevant:** Explains why sub-borough areas are a standard housing-analysis geography and why they differ from community districts.
- **Confidence:** high

### 6) The effect of rezoning on local housing supply and demand: Evidence from New York City
- **Type:** peer-reviewed academic research
- **Author:** Hsi-Ling Liao
- **URL:** https://www.sciencedirect.com/science/article/pii/S016604622500105X
- **Why relevant:** NYC-focused evidence that upzoning can increase housing supply while also changing neighborhood mobility and composition, reinforcing the need for a calibrated benchmark.
- **Confidence:** high

## Data access points for reproducibility

1. **Housing stock / supply**
   - Local dataset: `NYC_housing_units`
   - Benchmark role: core neighborhood housing-stock trend

2. **Housing cost**
   - Local dataset: `NYC_median_rent`
   - Benchmark role: core neighborhood rent trend

3. **Local affordability capacity**
   - Local dataset: `NYC_median_household_income`
   - Benchmark role: core neighborhood income trend

4. **Optional demand / pressure context**
   - Local dataset: `NYC_population`
   - Benchmark role: optional enhancement for stronger answers

## Suggested evaluation notes

### What a strong agent should do
- Select the three core datasets above.
- Explain why rent must be interpreted against income, not alone.
- Treat `NYC_housing_units` as an important but incomplete signal.
- Use **Sub-Borough Area** as the cleanest first-pass geography.
- Keep the interpretation calibrated: screening first, then deeper housing-policy review.

### What a very strong agent may also mention
- `NYC_population` is a strong optional enhancement because housing pressure is partly about how unit growth compares with demand pressure.
- The local series have missing `2020` values in multiple tables, so the agent should not treat 2020 as a continuous observation.
- The benchmark is not asking whether supply “works” in the abstract; it is asking where local affordability pressure appears to remain high despite local stock growth.
- The case could motivate multiple follow-up actions: affordable-housing subsidy review, preservation, tenant protections, rezoning, or anti-displacement planning.

### Common failure modes
- Returning only `NYC_median_rent`.
- Replacing income with a generic poverty or unemployment table.
- Treating housing-unit growth as automatically sufficient evidence of local affordability improvement.
- Choosing a different geography without explaining why it is better than SBA.
- Framing the result as a definitive displacement score rather than a screening tool.

## Retrieval / provenance notes

- This case is intentionally scoped to current UrbanTrace copilot behavior: selecting the strongest local tables, rejecting weaker substitutes, and proposing a coherent neighborhood-screening workflow over the local datalake.
- The benchmark is strongest when graded on **dataset choice + geography reasoning + calibrated policy interpretation**, not on producing one “correct” ranked output.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the most useful upgrade would be to add one NYC or Furman source specifically focused on neighborhood-level rent burden or production disparities by geography. The case is already benchmark-usable as written because the current official sources and recent NYC research are sufficient to justify the screening logic.
