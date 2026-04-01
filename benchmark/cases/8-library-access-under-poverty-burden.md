# Case 8 — Library access under poverty burden

**Status:** revised  
**Case ID:** 8  
**Theme:** public services / equity  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> A civic-access analyst wants to identify NYC neighborhoods where higher poverty may coincide with comparatively thin library access. Using the available data catalog, choose the library, poverty, and population datasets needed for a neighborhood screen, select a defensible comparison geography, and explain how the results should inform public-service planning without over-claiming service adequacy.

## Why this benchmark matters

This is a benchmark for **dataset selection, geography discipline, and proxy interpretation** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. stop at `NYC_libraries` only;
2. choose `NTA_Neighborhood_Tabulation_Areas` as the default comparison geography without noticing that the repo’s poverty and population layers are actually on sub-borough polygons;
3. ignore neighborhood scale and therefore treat one library in a small, low-population area as equivalent to one library in a larger, higher-poverty area; or
4. miss the important caveat that the local `NYC_libraries` dataset includes **non-public and special libraries** as well as public branches.

A stronger agent should recognize that this case is really about **public library access relative to neighborhood need**, not about displaying a facilities layer in isolation. That fits the current architecture well because `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` currently supports suggestion of relevant datasets rather than executing a full GIS analysis. So benchmark quality depends on choosing the right 1–5 datasets, resisting plausible distractors, and clearly describing the comparison geography and any filtering logic.

## Source-grounded planning rationale

Official NYC materials support treating libraries as a meaningful public-service and civic-access resource. The City’s FY2026 Preliminary Mayor’s Management Report tracks circulation, program attendance, computer sessions, and Wi‑Fi sessions across the library systems, which is a strong official signal that libraries are not just buildings on a map: they are actively used public-service infrastructure. The FY2024 Mayor’s Management Report goes further by explicitly framing the libraries as part of the City’s social infrastructure, prioritizing equitable access across boroughs and highlighting lower-income neighborhoods and book deserts. NYC’s Digital Equity materials also reinforce that residents rely on community institutions for digital and service access, which makes library distribution relevant for equity screening even when the benchmark is broader than digital inclusion alone.

That policy framing supports a benchmark about **where public library access may be comparatively thin relative to poverty burden and resident population**. In the local UrbanTrace catalog, the most credible need-side datasets are `NYC_poverty_rate` and `NYC_population`, and the most credible facility-side dataset is `NYC_libraries`.

However, the metadata adds one crucial benchmark caveat: `NYC_libraries` is not purely a public-branch dataset. In the local file, `factype` includes `PUBLIC LIBRARY`, `SPECIAL LIBRARIES`, `ACADEMIC LIBRARIES`, and `NYCHA COMMUNITY CENTER - LIBRARY`, while `optype` includes both `Public` and `Non-public`. So a very strong answer should either:

- explicitly focus on **public libraries only** using fields like `factype` / `optype`; or
- acknowledge that counting all library points would slightly overstate neighborhood public access.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_libraries`, `NYC_poverty_rate`, and `NYC_population`.
- Prefer the **poverty/population polygon geography** as the first-pass comparison geography, because those two need layers already share the same sub-borough-area structure in the local repo.
- Count or summarize library points into those polygons using spatial overlay, rather than forcing the analysis into NTAs by default.
- If possible, filter `NYC_libraries` to **public libraries** rather than treating all library-related points as equivalent public access sites.
- Interpret the result as an **equity screening product for planning follow-up**, not proof that any neighborhood is underserved in a legal or operational sense.

### Expected core datasets
- `NYC_libraries`
- `NYC_poverty_rate`
- `NYC_population`

### Important optional support / reference datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains why it is being used for display or reporting rather than as the default harmonization surface

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when selected as if it automatically solves the geography mismatch
- `MODZCTA` — tempting because many civic-service discussions use ZIP-like geographies, but the local poverty/population layers here are sub-borough polygons
- `NYC_Wi-Fi_Hotspot_Locations` — relevant to digital-access cases, but not the primary access layer for this benchmark
- `NYC_median_household_income` — related to disadvantage, but weaker than the direct poverty measure for this specific prompt

## Expected UrbanTrace dataset mapping

### 1) `NYC_libraries`
- Geometry in local metadata: `Point`
- Rows: `253`
- Confirmed key fields relevant to harmonization / filtering:
  - `factype`
  - `optype`
  - `opname`
  - `opabbrev`
  - `nta2020`
  - `ct2020`
  - `zipcode`
  - `count`
- Important local caveat from repo evidence:
  - `factype` includes `PUBLIC LIBRARY`, `SPECIAL LIBRARIES`, `ACADEMIC LIBRARIES`, and `NYCHA COMMUNITY CENTER - LIBRARY`
  - `optype` includes both `Public` and `Non-public`
- Best benchmark interpretation: a citywide library-location inventory that is strongest when filtered to public branches for a public-access equity question

### 2) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: neighborhood-need layer representing concentrated economic vulnerability on a shared sub-borough geography

### 3) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: population scale layer that helps distinguish thin access in a lightly populated area from thin access affecting many residents

### 4) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed key fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
- Best benchmark interpretation: optional neighborhood reporting geography, not the cleanest default comparison unit for this case

## Common geography guidance

This is the key benchmark correction.

The previous draft listed `NTA_Neighborhood_Tabulation_Areas` as an expected core layer. The local repo evidence does **not** support that as the cleanest first choice:

- `NYC_libraries` is a **point** dataset.
- `NYC_poverty_rate` and `NYC_population` are both **polygon** datasets with matching **sub-borough-area** structure (`Sub-Borough Area`, `Official_SBA_name`, `bor_subb`).
- The library points contain NTA and tract fields, but the need layers do **not** natively live on NTA geography.

So the most benchmark-credible first-pass workflow is:

1. **Anchor the analysis on the poverty/population polygons.**
2. Filter `NYC_libraries` to public libraries if the agent is reasoning carefully.
3. Count library points within each poverty/population polygon using spatial overlay.
4. Compare those counts or simple densities against poverty burden and resident population.
5. Flag polygons where poverty is higher and population is substantial but public-library presence appears comparatively thin.
6. Only convert the result to NTAs if the agent explicitly describes an additional overlay or crosswalk step.

A strong answer may phrase this as:

> “Because the need layers already share the same polygon geography and the library layer is points, I would anchor the comparison on the poverty/population polygons and count library points into them. I would treat NTA as an optional reporting geography, not as the default join surface.”

That is materially more credible than defaulting to NTAs without explanation.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Not every library point is equivalent public access.** The local dataset includes non-public and special institutions, so public-branch filtering matters.
- **Counts are only a first-pass proxy.** One branch may differ from another in size, hours, staffing, programming, or specialized services.
- **This is a screening exercise.** Fewer libraries in a polygon does not prove residents lack reasonable access; it identifies areas that may deserve closer review.
- **Population matters.** Thin access should be interpreted differently in a polygon with 100,000+ residents than in one with many fewer residents.
- **Poverty matters because this is an equity benchmark.** The goal is not simply to find low-library areas, but to find low-library areas where need is plausibly greater.

## Source-grounded rationale

### 1) Public Libraries | New York City Preliminary Mayor’s Management Report FY2026
- **Type:** official NYC service report
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **What it supports:** The City tracks library circulation, programs, computer sessions, and Wi‑Fi sessions as meaningful service outputs.
- **Why it matters for this benchmark:** It supports treating libraries as active public-service infrastructure rather than just a passive amenity layer.

### 2) Public Libraries | New York City Mayor’s Management Report FY2024
- **Type:** official NYC service report
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/mmr2024/lib.pdf
- **What it supports:** The report describes the library systems as part of the City’s social infrastructure, says they prioritize equitable access across boroughs, and highlights lower-income neighborhoods and book deserts.
- **Why it matters for this benchmark:** It is direct official support for treating unequal library access as an equity and neighborhood-resource issue rather than a generic amenity count.

### 3) Digital Equity — NYC Office of Technology and Innovation
- **Type:** official program page
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/content/oti/pages/digital-equity
- **What it supports:** NYC formally frames equitable access to digital resources and support as a city policy concern.
- **Why it matters for this benchmark:** It reinforces the idea that libraries matter as access infrastructure for residents who may face higher barriers to information, services, and connectivity.

### 4) NYC’s Public Libraries to Expand Sunday Library Service to 11 Additional Branches Citywide
- **Type:** official NYC Council press release
- **Agency:** New York City Council
- **URL:** https://council.nyc.gov/press/2025/08/04/2933/
- **What it supports:** The city expanded Sunday service and described libraries as neighborhood public resources that provide educational and economic opportunity across communities.
- **Why it matters for this benchmark:** It gives direct NYC planning and budget context for treating branch access as a real service-distribution question rather than a generic amenity count.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_libraries`, `NYC_poverty_rate`, and `NYC_population`.
- Use the poverty/population polygon geography as the preferred first-pass comparison unit.
- Explain that `NTA_Neighborhood_Tabulation_Areas` is optional reference geography, not the automatic common join surface.
- Note that `NYC_libraries` contains non-public / special libraries and that filtering to public libraries would improve the benchmark answer.
- Keep the conclusion calibrated: this is an equity-planning screen for follow-up, not a definitive service adequacy finding.

### What a very strong agent may also mention
- Public-library filtering can be approximated from `factype` and/or `optype`.
- A per-capita or per-area normalization could improve downstream analysis, but is not required for a valid benchmark answer.
- Census tract or NTA codes in the point layer are useful hints, but geometry-based overlay is still more defensible than assuming those fields automatically match the need polygons.
- A branch count is a coarse proxy for access because branch size, service hours, and programming are not captured as robust capacity measures here.

### Common failure modes
- Returning only `NYC_libraries`.
- Treating `NTA_Neighborhood_Tabulation_Areas` as the default comparison geography without explaining the mismatch.
- Ignoring `NYC_population` and therefore missing neighborhood scale.
- Treating all library points as equally public-facing without acknowledging the public/non-public distinction.
- Making unsupported claims such as “few libraries means residents lack services” or “high poverty proves unmet library need.”

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- `NYC_libraries` is the correct facility layer, but it should ideally be filtered to public libraries;
- `NYC_poverty_rate` and `NYC_population` provide the neighborhood-need side of the comparison;
- the cleanest first pass is to count library points into the poverty/population polygons rather than forcing the analysis into NTAs;
- sub-borough areas with higher poverty, meaningful population, and relatively thinner public-library presence should be flagged for follow-up;
- the output is a planning screen, not a claim of definitive service inequity.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYC_libraries.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - replacing an NTA-centric framing with the repo-supported sub-borough poverty/population geography;
  - adding the important library-data caveat that the local inventory includes non-public and special libraries; and
  - tightening the interpretation so the case evaluates dataset choice, filtering logic, and geography reasoning rather than generic prose about libraries.
- No backend changes were required for this case; the benchmark remains focused on evaluating reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding branch-level **hours, staffing, or capital-condition data** so the benchmark can go beyond branch counts. The case now has direct NYC support for treating unequal library access as a planning issue, but the local repo still measures presence more cleanly than service intensity.
