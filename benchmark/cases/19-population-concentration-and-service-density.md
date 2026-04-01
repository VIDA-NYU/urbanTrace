# Case 19 — Population concentration and service density

**Status:** revised  
**Case ID:** 19  
**Theme:** public services / capacity  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> An urban-services team wants a first-pass screen of NYC areas where resident population is large but visible civic service presence, such as libraries, schools, or public computer centers, appears relatively sparse. Using the available data catalog, identify the population layer and the most relevant service-point datasets, choose a defensible comparison geography, distinguish between different kinds of service sites, and explain what the screen can and cannot say about service adequacy.

## Why this benchmark matters

This is a benchmark for **population-pressure reasoning, service-proxy discipline, and geography harmonization** under the current UrbanTrace copilot design.

A weak agent may do one or more of the following:

1. name `NYC_population`, `NYC_libraries`, `NYC_Schools`, and `NYC_Wi-Fi_Hotspot_Locations` and stop there, without explaining how they would actually be compared;
2. default to `NTA_Neighborhood_Tabulation_Areas` just because the service-point datasets contain NTA-related fields, without noticing that the local population layer is natively stored on a different polygon system;
3. treat libraries, schools, and Wi‑Fi hotspots as if they were identical measures of public service capacity;
4. count all school points as equivalent public-access assets even though the local schools file mixes public and non-public institutions and is not a generic city-service inventory; or
5. imply that a low count of mapped points proves a neighborhood is underserved, even though the repo does not contain complete capacity, hours, catchment, or utilization data for these services.

A stronger agent should recognize that this case is really about **screening high-population areas for comparatively thin visible civic-service presence in the local catalog**. That fits the current evaluation target in `backend/llm_agent.py` and `backend/tool.py`: the benchmark rewards selecting the best 1–5 datasets, choosing a defensible geography, and narrating caveats clearly. It does not reward pretending the repo already contains a validated service-capacity model.

## Source-grounded planning rationale

This case is supported by real NYC planning and service materials, but the framing must stay narrow and credible.

First, NYC Planning’s population-reporting pages establish that the city actively tracks current and future population patterns for planning purposes. That is enough official grounding to treat **population concentration** as a legitimate service-planning context rather than an invented benchmark setup.

Second, the City’s **Preliminary Mayor’s Management Report** treats libraries as active public-service infrastructure by tracking circulation, programming, computer sessions, and Wi‑Fi sessions. The FY2024 Mayor’s Management Report goes further by explicitly describing the libraries as part of the City’s **social infrastructure**, prioritizing equitable access across boroughs and highlighting lower-income neighborhoods and **book deserts**. That gives the benchmark a much more direct service-access rationale than a generic amenity framing.

Third, NYC’s **Digital Equity** program and the **Digital Equity Roadmap** explicitly frame public connectivity and community access infrastructure as policy-relevant. That makes public Wi‑Fi hotspots a defensible service-side layer in a benchmark about resident concentration and neighborhood access.

Fourth, the City’s **Neighborhood Tech Help** expansion materials make the access problem more explicit: they describe in-person technology support for low-income New Yorkers at public libraries, affordable housing developments, and older-adult centers, and present the service as a response to digital-literacy and service-navigation barriers. That gives the benchmark a more direct urban-services grounding than relying on infrastructure inventories alone.

Fifth, recent school-facilities reporting from the Independent Budget Office and planning materials from the School Construction Authority make clear that school buildings, enrollment pressure, and facilities planning are real city concerns. But those same sources also imply an important limitation: school points are not a simple all-purpose civic-service count. The local `NYC_Schools` layer contains public and non-public institutions and does not directly measure seat availability or catchment access.

So the benchmark-credible synthesis is:

- **population** is the pressure side of the screen;
- **libraries** and **public Wi‑Fi hotspots** are the strongest broadly public-facing service-presence layers in the local repo for this specific question;
- **schools** are useful as a qualified supplementary service layer, but they should not be treated as interchangeable with libraries or Wi‑Fi;
- the result should be interpreted as an exploratory **population concentration versus visible service presence** screen for follow-up.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_population` as the pressure anchor layer.
- Use `NYC_libraries` and `NYC_Wi-Fi_Hotspot_Locations` as the strongest broadly public-facing service layers in the local repo.
- Treat `NYC_Schools` as **optional or qualified support**, not automatically as a core public-service-equivalency layer, unless the agent explicitly explains that school presence is being used as a rough institutional-support proxy rather than a direct public-access service measure.
- Prefer the population layer’s own **sub-borough-area polygons** as the first-pass comparison geography, then summarize service points into those polygons.
- Avoid defaulting to NTA unless the agent explicitly explains that it is introducing a second harmonization step for reporting or display.
- Interpret the result as a **service-density screening exercise** for high-population areas, not as proof of unmet demand, inadequate capacity, or service inequity.

### Expected core datasets
- `NYC_population`
- `NYC_libraries`
- `NYC_Wi-Fi_Hotspot_Locations`

### Important optional / qualified support dataset
- `NYC_Schools` only if the agent explicitly acknowledges that:
  - the dataset mixes public and non-public institutions; and
  - school presence is a much rougher proxy for general civic service coverage than libraries or public Wi‑Fi

### Likely distractors
- `NTA_Neighborhood_Tabulation_Areas` when treated as the automatic common geography
- `MODZCTA`, which is familiar but does not solve the repo’s underlying population/service geography mismatch
- `City_Council_Districs`, a governance-facing reporting geography that is not the natural first-pass surface for this case
- treating `NYC_Schools` as an unquestioned peer to libraries and Wi‑Fi for general public-access service density

## Expected UrbanTrace dataset mapping

### 1) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed useful fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: the resident-population pressure anchor already available on a consistent polygon geography
- Important caveat: this is not stored at NTA level

### 2) `NYC_libraries`
- Geometry in local metadata: `Point`
- Rows: `253`
- Confirmed useful fields:
  - `factype`
  - `optype`
  - `opname`
  - `nta2020`
  - `ct2020`
  - `count`
- Best benchmark interpretation: broad civic-service presence layer, especially if interpreted cautiously or filtered toward public libraries
- Important caveat: local metadata shows the inventory includes public, special, academic, and some non-public library-related records

### 3) `NYC_Wi-Fi_Hotspot_Locations`
- Geometry in local metadata: `Point`
- Rows: `3319`
- Confirmed useful fields:
  - `Type`
  - `Provider`
  - `Neighborhood Tabulation Area (NTA)`
  - `BoroCD`
  - `Council Distrcit`
  - `Activated`
  - `count`
- Best benchmark interpretation: public connectivity presence layer that can be summarized into neighborhood polygons
- Important caveat: hotspot types vary, and not every hotspot is equivalent in reliability, access rules, or service intensity

### 4) `NYC_Schools` (qualified support)
- Geometry in local metadata: `Point`
- Rows: `3103`
- Confirmed useful fields:
  - `factype`
  - `facsubgrp`
  - `optype`
  - `student`
  - `nta2020`
  - `schooldist`
- Best benchmark interpretation: institutional-support context layer that may be useful in a broader facilities screen
- Important caveat: this is not a pure public-service-access layer and should not be treated as a direct measure of general neighborhood service coverage without explanation

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional reporting geography only)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed useful fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: optional reporting/display geography if the agent explicitly documents the added overlay step
- Important caveat: not the clean default comparison surface for this case because `NYC_population` is not natively stored on NTA polygons

## Common geography guidance

This is the key benchmark correction for Case 19.

The seed listed `NTA_Neighborhood_Tabulation_Areas` among expected relevant datasets, but the local repo evidence points to a stronger default workflow:

- `NYC_population` already provides the pressure side on **55 sub-borough-area polygons**;
- `NYC_libraries`, `NYC_Wi-Fi_Hotspot_Locations`, and `NYC_Schools` are **point** layers;
- those point layers may carry NTA, tract, or council identifiers, but the population layer does not natively match those geographies;
- using NTA as the default would therefore introduce an extra harmonization step rather than simplify the comparison.

So the most benchmark-credible first-pass workflow is:

1. Anchor the analysis on the existing `NYC_population` polygons.
2. Choose a recent population value such as `2023`.
3. Summarize library points and Wi‑Fi hotspots into those polygons.
4. Optionally summarize schools as supplementary institutional context, while stating clearly that schools are not directly equivalent to libraries or public Wi‑Fi for general access.
5. Flag places where population is relatively high while visible service-point coverage looks comparatively thin.

A strong answer may say something like:

> “Because the population layer already provides the pressure polygons and the service layers are points, I would keep the first-pass analysis on the population polygons and count service points into them. I would only move to NTA later if I needed neighborhood-style reporting and documented the extra overlay step.”

That is materially stronger than defaulting to NTA from habit.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for high-population areas where mapped libraries and public Wi‑Fi appear comparatively sparse;
- identification of sub-borough areas that may warrant follow-up in civic-service planning, digital-equity work, or facilities review;
- a first-pass comparison of visible service-point presence against resident concentration using only the repo’s local catalog.

### What it cannot prove
- that residents in a flagged area lack adequate services overall;
- that a low count of service points implies low service quality or insufficient capacity;
- that all libraries, schools, and Wi‑Fi hotspots serve the same populations or functions;
- that adding one more point location would solve local service pressure.

### Important caveats a strong agent should mention
- **Geography caveat:** the population layer is not natively NTA-based.
- **Capacity caveat:** the repo does not contain a clean cross-service capacity measure.
- **Comparability caveat:** libraries, hotspots, and schools represent different service models and should not be merged into a single count without explanation.
- **Access caveat:** libraries include non-public/special records, and schools include public and non-public institutions.
- **Screening caveat:** this is a prioritization screen for follow-up, not a definitive adequacy study.

## Selected supporting references

### 1) Population Reports — NYC Planning
- **Type:** official NYC planning page
- **URL:** https://www.nyc.gov/site/planning/planning-level/nyc-population/nyc-population-current-estimates.page
- **Why relevant:** Confirms that NYC Planning treats population measurement and change as a formal planning input, which grounds the population-pressure side of the benchmark.
- **Confidence:** high

### 2) Population Changes in NYC Neighborhoods — NYC Planning
- **Type:** official NYC planning page
- **URL:** https://www.nyc.gov/site/planning/planning-level/nyc-population/current-future-populations.page
- **Why relevant:** Supports the idea that neighborhood-scale population patterns are a legitimate city-planning concern rather than an invented benchmark framing.
- **Confidence:** medium-high

### 3) Public Libraries | New York City Preliminary Mayor’s Management Report FY2026
- **Type:** official NYC service report
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **Why relevant:** Treats libraries as active service infrastructure by tracking usage, programming, computer sessions, and Wi‑Fi sessions.
- **Confidence:** high

### 4) Digital Equity — NYC Office of Technology and Innovation
- **Type:** official program page
- **URL:** https://www.nyc.gov/content/oti/pages/digital-equity
- **Why relevant:** Establishes digital access and supporting public infrastructure as a real city policy domain, which makes public Wi‑Fi a defensible service-side layer.
- **Confidence:** high

### 5) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **Why relevant:** Supports the interpretation of public connectivity infrastructure as part of neighborhood service access rather than a mere amenity count.
- **Confidence:** high

### 6) Barriers to Learning: Age, Accessibility, Space Usage, and Air Conditioning in NYC School Buildings
- **Type:** policy report
- **URL:** https://www.ibo.nyc.gov/content/publications/2025-march-barriers-to-learning-age-accessibility-space-usage-and-air-conditioning-in-nyc-school-buildings
- **Why relevant:** Gives real NYC grounding for why school facilities matter in planning conversations, while also reinforcing that school presence should be interpreted carefully rather than as a generic service count.
- **Confidence:** medium-high

### 7) NYC School Construction Authority — Current Capital Plan
- **Type:** official NYC facilities-planning page
- **URL:** https://www.nycsca.org/Community/Overview/Capital-Plan-Reports-and-Data/Current-Capital-Plan
- **Why relevant:** Supports the broader planning context that service and facilities provision responds to population change, enrollment, and public input.
- **Confidence:** medium-high

### 8) HPD, NYC Aging, NYPL Announce Expansion of Neighborhood Tech Help to the Bronx and Upper Manhattan
- **Type:** official NYC press release
- **URL:** https://www.nyc.gov/site/hpd/news/058-25/hpd-nyc-aging-nypl-expansion-neighborhood-tech-help-the-bronx-upper-manhattan.page
- **Why relevant:** Directly frames neighborhood library and tech-support presence as a response to digital-literacy and service-access barriers facing low-income New Yorkers, which strengthens the public-service side of this screen.
- **Confidence:** high

### 9) Public Libraries | New York City Mayor’s Management Report FY2024
- **Type:** official NYC service report
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/mmr2024/lib.pdf
- **Why relevant:** The report describes libraries as part of the City’s social infrastructure and explicitly highlights equitable access, lower-income neighborhoods, and book deserts.
- **Confidence:** high

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_population`, `NYC_libraries`, and `NYC_Wi-Fi_Hotspot_Locations` as the core layers.
- Explain that the clean first-pass geography is the population layer’s sub-borough polygons, not automatically NTA.
- Treat `NYC_Schools` as optional or qualified support rather than unquestioned core evidence for general public-service density.
- Keep the interpretation calibrated: this is a population-pressure versus service-presence screen for follow-up.

### What a very strong agent may also mention
- `NYC_libraries` should ideally be filtered toward public libraries if the question is interpreted strictly as public service access.
- Wi‑Fi hotspot counts may be dominated by certain provider or location types and should not be over-read as a direct measure of neighborhood digital support quality.
- Schools can enrich a broader facilities conversation, but they should usually be reported separately from libraries and public Wi‑Fi rather than folded into one naive service total.
- A later analytic pass could normalize service points per resident or per square mile, but the benchmark does not require a full scoring formula.

### Common failure modes
- Defaulting to NTA with no explanation.
- Treating all three service layers as directly interchangeable.
- Treating `NYC_Schools` as a clean general-public-access layer.
- Making definitive service-adequacy claims from simple point counts.
- Ignoring that the benchmark is about high-population areas specifically, not just areas with few amenities.

## Retrieval / provenance notes

- Local dataset viability was checked directly in repository metadata for:
  - `NYC_population`
  - `NYC_libraries`
  - `NYC_Wi-Fi_Hotspot_Locations`
  - `NYC_Schools`
  - `NTA_Neighborhood_Tabulation_Areas`
- Repo alignment was checked against:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrades in this case are:
  - restoring the missing seed case as a concrete per-case markdown file;
  - grounding the benchmark in real NYC planning / service materials rather than generic amenity language;
  - correcting the default geography away from automatic NTA usage and toward the repo’s native population polygons; and
  - downgrading schools from an assumed core service-equivalency layer to a qualified supplementary layer.
- No backend changes were required for this case; this remains a reasoning-quality benchmark under the current copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding a local source or layer on service **capacity, hours, or travel-time access** so the benchmark can move beyond visible site presence. The case now already has direct official support for unequal service access in lower-income neighborhoods.
