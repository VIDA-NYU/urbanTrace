# Case 10 — Income diversity and public amenity mismatch

**Status:** revised  
**Case ID:** 10  
**Theme:** inequality / public services  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are helping an urban policy team explore whether neighborhoods with **lower income diversity** also appear comparatively underserved by visible public amenities such as libraries or public Wi‑Fi hotspots. The benchmark is not asking for a generic demographic summary. It is testing whether the agent can connect an abstract neighborhood-structure indicator to concrete civic infrastructure, choose a defensible comparison geography from the local UrbanTrace catalog, and explain what the result would and would not mean in a realistic planning workflow.

## Why this benchmark matters

This is a benchmark for **dataset selection, geography discipline, and proxy interpretation** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. stop at `NYC_income_diversity_ratio` and describe neighborhood inequality without selecting any amenity dataset;
2. select `NYC_libraries` or `NYC_Wi-Fi_Hotspot_Locations` but fail to connect them to the income-diversity layer;
3. default to `NTA_Neighborhood_Tabulation_Areas` because the point datasets contain NTA fields, even though the income-diversity layer is not natively on NTA geography; or
4. treat amenity counts as definitive evidence of service adequacy rather than a first-pass screening proxy.

A stronger agent should recognize that this case is really about **whether a neighborhood-structure indicator can be compared to public-facing amenity access signals**. That fits the current architecture well because `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` supports suggesting relevant datasets rather than executing a full GIS workflow. So benchmark quality depends on choosing the right 1–5 datasets, resisting plausible distractors, and clearly explaining the comparison geography and limits of the proxy.

## Source-grounded planning rationale

The local repo already contains a neighborhood-scale income-diversity indicator: `NYC_income_diversity_ratio`. In the repo metadata, it is a **55-row MultiPolygon** layer on the same **Sub-Borough Area** geography used by `NYC_population`, with annual values through 2023 and shared geographic keys including `Sub-Borough Area`, `Official_SBA_name`, and `bor_subb`.

That matters because it gives the benchmark a clean need-side anchor inside the repo itself. The amenity side then has to be represented by visible, citywide public-service proxies that the repo actually contains:

- `NYC_libraries`, a citywide point inventory with public/non-public distinctions and NTA / tract attributes; and/or
- `NYC_Wi-Fi_Hotspot_Locations`, a much larger point layer of public hotspot locations with NTA, council district, tract, and provider/type attributes.

Official NYC materials make the amenity-equity framing credible. NYC’s Digital Equity materials explicitly treat public-facing connectivity resources and community access infrastructure as policy-relevant. The City’s FY2026 Preliminary Mayor’s Management Report also treats libraries as active public-service infrastructure, tracking usage outputs such as circulation, programs, computer sessions, and Wi‑Fi sessions. Together, those sources support using libraries and public Wi‑Fi as meaningful amenity-side signals in an exploratory neighborhood-equity screen.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_income_diversity_ratio` as the socioeconomic anchor layer.
- Use at least one concrete public-amenity layer: `NYC_libraries` and/or `NYC_Wi-Fi_Hotspot_Locations`.
- Use `NYC_population` as an important scale/context layer so the comparison does not ignore how many residents are represented by a polygon.
- Prefer the **income-diversity / population polygon geography** as the first-pass comparison unit, because those repo-native layers already share the same sub-borough-area structure.
- Treat `NTA_Neighborhood_Tabulation_Areas` as optional reporting or display geography only if the agent explicitly explains an additional overlay/crosswalk step.
- Interpret the output as an **inclusive-development / amenity-equity screening product**, not proof that any neighborhood is inadequately served.

### Expected core datasets
- `NYC_income_diversity_ratio`
- `NYC_population`
- `NYC_libraries` and/or `NYC_Wi-Fi_Hotspot_Locations`

### Important optional support / reference datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains why it is being used for reporting or display rather than as the default harmonization surface

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when treated as the automatic common geography
- `City_Council_Districs` / council-district layers — the amenity point datasets expose council attributes, but the income-diversity layer is not natively a council-district dataset
- `NYC_poverty_rate` — a meaningful equity layer in other cases, but weaker than the directly requested income-diversity indicator for this specific prompt
- `NYC_median_household_income` if used as a substitute for diversity without explanation

## Expected UrbanTrace dataset mapping

### 1) `NYC_income_diversity_ratio`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: a neighborhood-structure indicator on sub-borough polygons that should anchor the comparison geography for this case

### 2) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: a scale/control layer that helps distinguish a thin-amenity pattern affecting many residents from one affecting far fewer residents

### 3) `NYC_libraries`
- Geometry in local metadata: `Point`
- Rows: `253`
- Confirmed key fields relevant to harmonization / filtering:
  - `factype`
  - `optype`
  - `opname`
  - `nta2020`
  - `ct2020`
  - `zipcode`
  - `count`
- Important local caveat from repo evidence:
  - `factype` includes `PUBLIC LIBRARY`, `SPECIAL LIBRARIES`, `ACADEMIC LIBRARIES`, and `NYCHA COMMUNITY CENTER - LIBRARY`
  - `optype` includes both `Public` and `Non-public`
- Best benchmark interpretation: a visible civic-amenity layer that is strongest when filtered toward public-serving library sites

### 4) `NYC_Wi-Fi_Hotspot_Locations`
- Geometry in local metadata: `Point`
- Rows: `3319`
- Confirmed key fields relevant to harmonization / interpretation:
  - `Type`
  - `Provider`
  - `Neighborhood Tabulation Area Code (NTACODE)`
  - `Neighborhood Tabulation Area (NTA)`
  - `Council Distrcit`
  - `BoroCD`
  - `Census Tract`
  - `count`
- Best benchmark interpretation: a broad public-connectivity amenity layer whose counts can be summarized into polygons, while recognizing that hotspot types and service quality vary

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed key fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: optional neighborhood reporting geography, not the cleanest default comparison surface for this case

## Common geography guidance

This is the key benchmark correction.

The earlier draft treated `NTA_Neighborhood_Tabulation_Areas` as an expected core layer. The local repo evidence does **not** support that as the cleanest first choice:

- `NYC_income_diversity_ratio` is a **polygon** layer on 55 sub-borough areas.
- `NYC_population` shares that same **sub-borough-area** polygon structure.
- `NYC_libraries` and `NYC_Wi-Fi_Hotspot_Locations` are **point** datasets.
- The point layers contain NTA fields, but the income-diversity layer does **not** natively live on NTA geography.

So the most benchmark-credible first-pass workflow is:

1. **Anchor the analysis on the income-diversity polygons.**
2. Bring in `NYC_population` because population scale matters for interpretation.
3. Count or summarize libraries and/or Wi‑Fi hotspots into those polygons using spatial overlay.
4. Compare amenity presence, counts, or simple densities against the income-diversity pattern.
5. Flag polygons where income diversity appears lower and public-facing amenity presence also looks comparatively thin.
6. Only convert the result to NTA-based reporting if the agent explicitly describes a second overlay or crosswalk step.

A strong answer may phrase this as:

> “Because the income-diversity and population layers already share the same sub-borough polygon geography and the amenity layers are points, I would anchor the comparison on the sub-borough polygons and summarize amenity points into them. I would treat NTAs as optional reporting geography, not as the default join surface.”

That is materially more credible than defaulting to NTAs without explanation.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Income diversity is not the same thing as poverty.** A low-diversity neighborhood is not automatically disadvantaged in the same way a high-poverty neighborhood is.
- **Amenity counts are only a proxy.** One library branch or hotspot cluster is not equivalent to another in quality, hours, capacity, or accessibility.
- **Library filtering matters.** The local library dataset includes non-public and special institutions, so public-facing filtering improves the benchmark answer.
- **Hotspot counts can mislead.** Public Wi‑Fi points may cluster in transit, parks, commercial corridors, or specialized venues, which is not the same as evenly distributed neighborhood service.
- **This is a screening exercise.** The result should identify places for follow-up, not prove that residents are underserved.
- **Population context matters.** Thin amenity presence means something different in a polygon with 200,000 residents than in one with far fewer residents.

## Source-grounded rationale

### 1) Digital Equity — NYC Office of Technology and Innovation
- **Type:** official program page
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/content/oti/pages/digital-equity
- **What it supports:** NYC formally treats equitable access to connectivity and digital-support infrastructure as a city policy concern.
- **Why it matters for this benchmark:** It supports using public Wi‑Fi and community-serving access amenities as credible neighborhood-equity signals rather than arbitrary map layers.

### 2) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **What it supports:** The roadmap frames digital inequity in terms of affordability, device access, skills, and community-based support infrastructure.
- **Why it matters for this benchmark:** It supports treating public-facing access points like hotspots and community institutions as meaningful infrastructure in an amenity-equity screening task.

### 3) Public Libraries | New York City Preliminary Mayor’s Management Report FY2026
- **Type:** official NYC service report
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **What it supports:** The City tracks library circulation, programs, computer sessions, and Wi‑Fi sessions as active service outputs.
- **Why it matters for this benchmark:** It supports treating libraries as meaningful public-service infrastructure rather than as neutral building points.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_income_diversity_ratio` plus at least one real amenity layer (`NYC_libraries` and/or `NYC_Wi-Fi_Hotspot_Locations`).
- Bring in `NYC_population` to keep the interpretation grounded in neighborhood scale.
- Use the income-diversity/population polygon geography as the preferred first-pass comparison unit.
- Explain why `NTA_Neighborhood_Tabulation_Areas` is optional support geography rather than the automatic common join surface.
- Keep the conclusion calibrated: this is an amenity-equity screen for follow-up, not a definitive service adequacy finding.

### What a very strong agent may also mention
- `NYC_libraries` should ideally be filtered using `factype` and/or `optype` so non-public and special libraries do not overstate public access.
- `NYC_Wi-Fi_Hotspot_Locations` varies by `Type` and `Provider`, so raw point counts alone may overstate comparable service.
- A per-capita or density-style normalization could improve downstream analysis, but it is not required for a valid benchmark answer.
- The case is about linking an abstract neighborhood indicator to concrete civic infrastructure, so the agent should explicitly narrate the proxy logic rather than assume it is obvious.

### Common failure modes
- Returning only `NYC_income_diversity_ratio`.
- Choosing `NTA_Neighborhood_Tabulation_Areas` as the default join geography without explaining the mismatch.
- Ignoring `NYC_population` and therefore missing neighborhood scale.
- Treating all libraries as equivalent public access points without acknowledging the public/non-public distinction.
- Making unsupported claims such as “low income diversity proves amenity deprivation.”

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYC_income_diversity_ratio` is the correct socioeconomic anchor because it directly matches the prompt and already lives on a sub-borough polygon geography;
- `NYC_libraries` and/or `NYC_Wi-Fi_Hotspot_Locations` are the most credible repo-native amenity layers to compare against it;
- `NYC_population` should be added so the screen does not ignore how many residents are represented by each polygon;
- the cleanest first pass is to summarize the amenity points into the income-diversity/population polygons rather than forcing everything into NTAs;
- polygons with lower income diversity and comparatively thinner public-facing amenity presence should be flagged for planning follow-up;
- the output is an exploratory inclusive-development screen, not proof of unmet service obligations.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYC_income_diversity_ratio.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NYC_libraries.json`
  - `data/metadata/NYC_Wi-Fi_Hotspot_Locations.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - replacing an NTA-centric draft with the repo-supported sub-borough income-diversity geography;
  - adding `NYC_population` as an important interpretation layer;
  - clarifying that libraries and Wi‑Fi are amenity-side proxies rather than guaranteed measures of service adequacy; and
  - grounding the planning scenario in official NYC digital-equity and library-service materials rather than generic equity language.
- No backend changes were required for this case; the benchmark remains focused on evaluating reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one stronger source specifically documenting the provenance or official interpretation of the income-diversity indicator itself. The case is already benchmark-usable now because the repo metadata clearly supports the geography and dataset-mapping corrections, and the official NYC digital-equity / library-service materials are sufficient to justify the amenity-equity planning frame.