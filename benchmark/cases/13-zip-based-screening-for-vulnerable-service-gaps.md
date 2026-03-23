# Case 13 — ZIP-based screening for vulnerable service gaps

**Status:** revised  
**Case ID:** 13  
**Theme:** service planning / geography discipline  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are helping a city planning or outreach team do a **ZIP-like screening** for places where vulnerability appears high but public-service coverage may be comparatively weak. The benchmark is intentionally tricky: the original seed mentions `MODZCTA`, poverty, unemployment, libraries, and Wi‑Fi, but the local UrbanTrace repo does **not** place all of those layers on the same geography. A benchmark-credible answer therefore has to do more than name plausible datasets. It needs to recognize the ZIP-level requirement, choose the most defensible comparison geography available in the repo, and explain whether the result is a strict ZIP-based screen or a looser cross-geography approximation.

## Why this benchmark matters

This is a benchmark for **dataset selection, geography discipline, and benchmark honesty** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. blindly repeat the seed and claim `MODZCTA`, `NYC_poverty_rate`, and `NYC_unemployment_rate` are a clean common geography when they are not;
2. pick only `NYC_Wi-Fi_Hotspot_Locations` and `NYC_libraries` without any vulnerability layer;
3. ignore stronger repo-native service-access evidence such as `citywide_public_computer_centers`; or
4. fail to distinguish between a **true ZIP-level screen** and a **crosswalk-heavy approximation**.

A stronger agent should recognize that the case is really testing whether it can stay honest about geography under the current architecture. That fits the repo well because `backend/llm_agent.py` and `backend/tool.py` are built to suggest the strongest candidate datasets and explain why, not to hide harmonization problems behind confident prose. So a credible benchmark answer should surface the mismatch and choose the cleanest available path.

## Source-grounded planning rationale

Two official NYC policy domains support this case.

First, NYC’s digital-equity materials make clear that residents’ ability to access services depends partly on neighborhood public-access infrastructure. The **Digital Equity** program and the **New York City Digital Equity Roadmap** frame digital inequity in terms of access, affordability, skills, and community support infrastructure. That supports a service-gap benchmark built around libraries, public Wi‑Fi, and public computer access sites rather than a generic amenity count.

Second, NYC’s official **Heat Vulnerability Index** materials explicitly frame neighborhood vulnerability as an equity and planning issue. The HVI portal explains that heat risk is shaped by structural and social inequities and that neighborhoods differ in access to protective resources. In the local repo, `NYC_HVI` is also the strongest vulnerability layer already tied to a **ZIP/ZCTA-like geography**.

That matters because the seed’s socioeconomic layers are **not** ZIP-native in this repo:

- `NYC_poverty_rate` is on **55 Sub-Borough Area polygons**;
- `NYC_unemployment_rate` is on the same **55 Sub-Borough Area polygons**;
- `MODZCTA` is a separate **178-row ZIP-like polygon layer**;
- `NYC_HVI` is a **184-row ZCTA 2020 polygon layer** with a direct ZIP-style framing.

So the cleanest benchmark-credible reading is:

- if the task must stay genuinely ZIP-like, prefer a **ZIP-native vulnerability layer** (`NYC_HVI`) plus service-access layers;
- if the agent insists on using poverty or unemployment, it should explicitly say that this becomes a **cross-geography approximation**, not a clean ZIP-level benchmark.

## Recommended benchmark framing

A strong answer should say, in substance:

- For a **strict ZIP-like screen**, use `NYC_HVI` as the vulnerability polygon layer because it is already organized by **ZIP Code Tabulation Area (ZCTA) 2020**.
- Use `NYC_Wi-Fi_Hotspot_Locations`, `NYC_libraries`, and ideally `citywide_public_computer_centers` as public-service / public-access coverage layers.
- Use spatial overlay to count or summarize those point assets into the ZIP-like vulnerability polygons.
- Treat `MODZCTA` as optional supporting geography only if the agent explains why a separate ZIP-boundary layer is needed.
- If the agent also brings in `NYC_poverty_rate` or `NYC_unemployment_rate`, it should clearly label them as **secondary context layers** requiring an additional overlay or approximation because they are not natively on ZIP geography.
- Interpret the output as a **screening product for follow-up**, not proof that a ZIP area is underserved in any definitive operational sense.

### Preferred strict ZIP-native dataset set
- `NYC_HVI`
- `NYC_Wi-Fi_Hotspot_Locations`
- `NYC_libraries`
- `citywide_public_computer_centers`

### Important optional support datasets
- `MODZCTA` if the agent explicitly explains why it needs a separate ZIP-like boundary layer for reporting or harmonization
- `NYC_poverty_rate`
- `NYC_unemployment_rate`
- `NYC_population`

### Likely distractors
- `MODZCTA` when treated as if it automatically harmonizes the whole task by itself
- `NYC_poverty_rate` / `NYC_unemployment_rate` when presented as though they are already ZIP-level layers
- `NYC_Schools`, which may sound like a service-access layer but is not the strongest match for the digital/public-access framing supported by the available sources

## Expected UrbanTrace dataset mapping

### 1) `NYC_HVI`
- Geometry in local metadata: `MultiPolygon`
- Rows: `184`
- Confirmed key fields:
  - `ZIP Code Tabulation Area (ZCTA) 2020`
  - `Heat Vulnerability Index (HVI)`
  - `geometry`
- Best benchmark interpretation: the strongest **repo-native ZIP/ZCTA vulnerability surface** for a genuine ZIP-like screening workflow

### 2) `NYC_Wi-Fi_Hotspot_Locations`
- Geometry in local metadata: `Point`
- Rows: `3319`
- Confirmed key fields relevant to screening / harmonization:
  - `Type`
  - `Provider`
  - `Neighborhood Tabulation Area Code (NTACODE)`
  - `Neighborhood Tabulation Area (NTA)`
  - `Postcode`
  - `Census Tract`
  - `count`
- Best benchmark interpretation: public connectivity locations that can be spatially summarized into ZIP-like polygons or inspected using postal-code fields with caution

### 3) `NYC_libraries`
- Geometry in local metadata: `Point`
- Rows: `253`
- Confirmed key fields relevant to screening / harmonization:
  - `zipcode`
  - `factype`
  - `optype`
  - `nta2020`
  - `ct2020`
  - `count`
- Best benchmark interpretation: library locations as durable public-service anchors; strongest when the agent notes that not all library points are identical public-access facilities

### 4) `citywide_public_computer_centers`
- Geometry in local metadata: `Point`
- Rows: `508`
- Confirmed key fields relevant to service-access interpretation:
  - `zip_code`
  - `wi_fi_available`
  - `workstation`
  - `staffed`
  - `open_lab_hrs_per_wk`
  - `training_hours_per_wk`
  - `wheelchair_accessible`
- Best benchmark interpretation: a stronger direct public digital-access layer than Wi‑Fi or libraries alone because it reflects workstations, staffing, training, and accessibility

### 5) `MODZCTA` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `178`
- Confirmed key fields:
  - `modzcta`
  - `label`
  - `zcta`
  - `pop_est`
  - `geometry`
- Best benchmark interpretation: ZIP-like reporting geography that may help with communication, but does not by itself solve the repo’s cross-geography mismatch

### 6) `NYC_poverty_rate` / `NYC_unemployment_rate` (secondary context only)
- Geometry in local metadata: `MultiPolygon`
- Rows: `55` each
- Confirmed shared key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: valid vulnerability context for NYC, but **not** a clean ZIP-level layer in this repo

## Common geography guidance

This is the core correction for the case.

The seed’s headline logic sounds ZIP-based, but the local repo does not make the original dataset combination equally defensible at ZIP geography:

- `MODZCTA` is ZIP-like polygon geography.
- `NYC_HVI` is also ZIP-like, but specifically organized by **ZCTA 2020** and already carries a vulnerability measure.
- `NYC_poverty_rate` and `NYC_unemployment_rate` are instead on **sub-borough-area** polygons.
- Libraries, Wi‑Fi hotspots, and public computer centers are **point** layers.

So the most benchmark-credible first-pass workflow is:

1. **Anchor the strict ZIP-like screen on `NYC_HVI`.**
2. Spatially summarize `NYC_Wi-Fi_Hotspot_Locations`, `NYC_libraries`, and ideally `citywide_public_computer_centers` into those ZIP-like polygons.
3. Flag ZIP/ZCTA-like areas where vulnerability is higher and public-access coverage looks comparatively thin.
4. Use `MODZCTA` only if the agent explicitly wants a reporting boundary and acknowledges that ZCTA / MODZCTA are not automatically identical.
5. Add poverty or unemployment only as a second-pass context layer if the agent openly describes the extra overlay step and the resulting approximation.

A strong answer may phrase this as:

> “Because the prompt asks for ZIP-level screening, I would prefer the repo’s ZIP-native vulnerability layer (`NYC_HVI`) and count public-access service points into that geometry. I would only bring in poverty or unemployment as secondary context if I explain the cross-geography approximation, since those indicators are not natively on ZIP polygons here.”

That is materially more credible than pretending the seed’s MODZCTA + poverty + unemployment combination is already harmonized.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **ZIP-like geography is administratively convenient, not analytically perfect.** ZCTA and MODZCTA are related but not interchangeable.
- **Service coverage is multi-dimensional.** Wi‑Fi hotspots, libraries, and public computer centers capture different forms of access.
- **Counts are only a screening proxy.** One site may differ from another in hours, capacity, staffing, accessibility, or quality.
- **This is a screening exercise.** Thin service coverage in a vulnerable ZIP-like area does not prove unmet need; it identifies places for closer review.
- **Seed-faithful socioeconomic context is weaker here.** Poverty and unemployment are useful NYC vulnerability indicators, but in this repo they are not native to ZIP geography.

## Source-grounded rationale

### 1) Interactive heat vulnerability index — Environment & Health Data Portal
- **Type:** official NYC portal page
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/
- **What it supports:** NYC explicitly frames heat vulnerability as shaped by structural and social inequities and treats vulnerability mapping as a neighborhood planning tool.
- **Why it matters for this benchmark:** It provides the strongest official grounding for using a ZIP/ZCTA-like vulnerability layer already present in the local repo.

### 2) Digital Equity — NYC Office of Technology and Innovation
- **Type:** official program page
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/content/oti/pages/digital-equity
- **What it supports:** NYC formally treats digital equity and neighborhood access to digital support as a city policy priority.
- **Why it matters for this benchmark:** It supports a benchmark focused on public-access infrastructure such as Wi‑Fi, libraries, and public computer centers.

### 3) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **What it supports:** The roadmap frames digital inequity in terms of affordability, devices, skills, and community-based support infrastructure.
- **Why it matters for this benchmark:** It justifies using multiple public-access service proxies rather than a single facilities layer.

### 4) Public Libraries | New York City Preliminary Mayor’s Management Report FY2026
- **Type:** official NYC service report
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **What it supports:** NYC tracks library computer sessions, Wi‑Fi sessions, circulation, and programming as active public-service outputs.
- **Why it matters for this benchmark:** It supports treating libraries as real service-access infrastructure rather than a generic civic amenity.

## Suggested evaluation notes

### What a strong agent should do
- Notice that the seed’s ZIP-level framing and its poverty/unemployment layers are not natively aligned in the repo.
- Prefer a **strict ZIP-native path** built around `NYC_HVI` plus public-access service layers.
- Select `NYC_Wi-Fi_Hotspot_Locations`, `NYC_libraries`, and ideally `citywide_public_computer_centers`.
- Explain that point service layers need to be summarized into the ZIP-like vulnerability polygons.
- Keep the conclusion calibrated: this is a screening workflow for follow-up, not a definitive service-gap finding.

### What a very strong agent may also mention
- `MODZCTA` can still be useful for reporting, but should not be treated as a magic common geography.
- `citywide_public_computer_centers` is probably the strongest direct public-access layer in the repo because it includes workstations, training, staffing, and accessibility fields.
- Libraries can be filtered or interpreted carefully because the local dataset includes different library types.
- Poverty, unemployment, and population can still be brought in as secondary context if the agent openly acknowledges that they require a second overlay step.

### Common failure modes
- Repeating the seed’s dataset list without noticing the geography mismatch.
- Omitting a vulnerability layer entirely.
- Returning only Wi‑Fi and libraries and missing `citywide_public_computer_centers`.
- Treating `MODZCTA` and ZCTA as automatically interchangeable.
- Presenting a ZIP-level answer with poverty/unemployment as though no harmonization issue exists.

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- the cleanest strict ZIP-like vulnerability screen in the repo uses `NYC_HVI`;
- public-service coverage should be represented with Wi‑Fi hotspots, libraries, and ideally public computer centers;
- those point layers should be counted or summarized into the ZIP/ZCTA-like vulnerability polygons;
- `MODZCTA` is optional reporting support, not a substitute for explicit harmonization;
- poverty and unemployment are useful secondary context for NYC but are not native ZIP-level layers here;
- the output is a vulnerable-service-gap screening product for follow-up, not a definitive service adequacy judgment.

## Retrieval / provenance notes

- This case was created and revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYC_HVI.json`
  - `data/metadata/NYC_Wi-Fi_Hotspot_Locations.json`
  - `data/metadata/NYC_libraries.json`
  - `data/metadata/citywide_public_computer_centers.json`
  - `data/metadata/MODZCTA.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_unemployment_rate.json`
  - `data/metadata/NYC_population.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this revision are:
  - turning an under-specified seed into a geography-aware case that explicitly tests whether the agent notices cross-geometry problems;
  - replacing a naive MODZCTA-first assumption with a stricter ZIP-native path centered on `NYC_HVI`;
  - adding `citywide_public_computer_centers` as a stronger public-access service layer already present in the repo; and
  - clarifying that poverty/unemployment remain useful context, but only as secondary non-native overlays for this ZIP-level case.
- No backend changes were required for this case; the benchmark remains focused on dataset recommendation and reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one official NYC source specifically explaining MODZCTA versus ZCTA use in public-health reporting. The case is already benchmark-usable now because the repo metadata clearly exposes the geography mismatch, and the official HVI, digital-equity, and library-service materials are sufficient to ground the vulnerability-plus-service-access framing.