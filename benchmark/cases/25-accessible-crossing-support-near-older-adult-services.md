# Case 25 — Accessible crossing support near older-adult services

**Status:** drafted  
**Case ID:** 25  
**Theme:** accessibility / aging / pedestrian infrastructure  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> An accessibility or aging-services analyst wants to identify NYC community districts where older-adult service destinations appear present but nearby accessible pedestrian-crossing support may be comparatively thin. Using the available data catalog, select the older-adult destination and crossing-accessibility datasets needed for a first-pass screen, explain why community districts are the most defensible comparison geography here, distinguish between different crossing-support features, and describe how the results should be interpreted.

## Why this benchmark matters

This is a benchmark for **pedestrian-accessibility reasoning with underused DOT accessibility layers plus a real public-service destination inventory**.

It fits the current UrbanTrace copilot architecture well:

- `backend/llm_agent.py` supplies dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports dataset suggestion and explanation, not a turnkey accessibility-audit workflow;
- so benchmark quality depends on whether the agent can:
  1. identify the strongest local destination layer for older-adult services,
  2. identify the most relevant crossing-accessibility layers already present in the repo,
  3. choose a geography that actually lines up with available attributes rather than forcing a weaker join, and
  4. interpret the result as a **follow-up screen** rather than proof that any district is compliant or noncompliant.

A weak answer will say “use older-adult centers and pedestrian signals.” A stronger answer should notice that:

- `department_for_the_aging_nyc_aging_all_contracted_providers` is the repo’s clearest official destination inventory for older-adult services, with fields such as `programname`, `programzipcode`, `borough`, `communityboard`, and `nta`;
- `accessible_pedestrian_signal_locations` and `pedestrian_ramp_locations` both matter, but they represent different aspects of accessible crossing support and should not be casually treated as interchangeable;
- `Community_Districs` is unusually useful here because the provider layer already includes `communityboard`, while the APS layer includes `borocd`, making community districts a more defensible common geography than ZIP or NTA for a first-pass screen;
- `exclusive_pedestrian_signal_barnes_dance_locations` may be relevant as optional context, but it is not a substitute for APS coverage or curb-ramp presence.

That combination of destination selection, infrastructure-type distinction, and geography discipline is exactly what this benchmark should test.

## Source-grounded planning rationale

This case is grounded in official NYC materials rather than invented scenario framing.

NYC Aging’s official **Older Adult Center** page states that there are more than 300 older adult centers and affiliated sites across the five boroughs, that membership is free and open to New Yorkers age 60 and older, and that centers provide meals, classes, fitness programs, social services, and other supports. The page also notes that some centers serve special populations, including **VISIONS at Selis Manor Senior Center for blind and visually impaired older adults**. That gives direct official grounding for treating older-adult service locations as meaningful pedestrian destinations whose surrounding street accessibility matters.

The City’s official **Accessible NYC 2025** guide, published by the Mayor’s Office for People with Disabilities, provides broader policy grounding that accessible routes, curb ramps, pedestrian signals, and street-crossing conditions are core parts of inclusive city access. That supports a benchmark focused on whether the agent can identify relevant pedestrian-accessibility infrastructure rather than defaulting to generic mobility or safety layers.

NYC DOT’s **Safe Streets for Seniors** program makes the pedestrian-risk problem direct. The agency states that older adults represent less than 15 percent of the city population but more than 45 percent of pedestrian fatalities, and it describes engineering responses such as longer crossing times, safety islands, signal improvements, and ADA-compliant ramp work in senior-priority areas. That is precisely the kind of urban problem statement this benchmark needs.

The official NYC Open Data documentation for **Accessible Pedestrian Signal Locations** and **Pedestrian Ramp Locations** then provides the concrete local infrastructure layers already present in the repo. Those datasets make this a credible UrbanTrace benchmark because the task can be framed around real local evidence already in the datalake, not around imagined access measures.

The benchmark-credible synthesis is therefore:

- use the NYC Aging provider inventory as the older-adult destination layer;
- use APS and pedestrian ramps as the core crossing-accessibility layers;
- use community districts as the first-pass comparison geography because the local attributes line up unusually well there; and
- interpret the result as a screen for districts where older-adult destinations may merit closer accessibility review, not as a legal or engineering compliance finding.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `department_for_the_aging_nyc_aging_all_contracted_providers` as the core older-adult service destination layer.
- Use `accessible_pedestrian_signal_locations` and `pedestrian_ramp_locations` as the main accessible-crossing support layers.
- Use `Community_Districs` as the main rollup geography, because the providers carry `communityboard` and the APS layer carries `borocd`, which is cleaner than forcing a ZIP or NTA comparison.
- Mention that APS and curb ramps reflect different accessibility functions and should not simply be merged into one undifferentiated “access score” without explanation.
- Treat `exclusive_pedestrian_signal_barnes_dance_locations` as optional context only if the agent explicitly says that Barnes Dance / all-pedestrian phases are not the same thing as APS coverage or curb-ramp provision.
- Interpret the output as an **accessible-destination screening exercise**: districts with many older-adult service destinations but comparatively sparse mapped crossing-accessibility infrastructure may warrant follow-up.
- Avoid claiming that fewer mapped APS or ramps automatically means a district is inaccessible, unsafe, or out of ADA compliance.

### Expected core datasets
- `department_for_the_aging_nyc_aging_all_contracted_providers`
- `accessible_pedestrian_signal_locations`
- `pedestrian_ramp_locations`
- `Community_Districs`

### Important optional support dataset
- `exclusive_pedestrian_signal_barnes_dance_locations`

### Likely distractors
- `MODZCTA`, because ZIP-like geography is not the cleanest first-pass match for the provider and APS attributes in this case
- `NTA_Neighborhood_Tabulation_Areas`, when used as the default reporting surface without explaining why community districts were skipped
- `NYC_vehicle_collisions_crashes`, which may be relevant for a different safety-oriented case but is not the primary accessibility-support layer here
- `NYC_HVI`, which may matter for broader vulnerability analysis but is not the core question in this benchmark
- treating Barnes Dance locations as if they replace APS or curb-ramp infrastructure

## Expected UrbanTrace dataset mapping

### 1) `department_for_the_aging_nyc_aging_all_contracted_providers`
- Geometry in local metadata: `Point`
- Rows: `445`
- Confirmed useful fields in local metadata:
  - `providertype`
  - `programname`
  - `programaddress`
  - `programzipcode`
  - `borough`
  - `communityboard`
  - `councildist`
  - `nta`
- Best benchmark interpretation: official NYC Aging destination inventory for older-adult service sites and programs
- Important caveat: this is a contracted-provider inventory, not a direct measure of foot traffic, client volume, disability status of participants, or the exact crossing paths people use to reach the site

### 2) `accessible_pedestrian_signal_locations`
- Geometry in local metadata: `Point`
- Rows: `2153`
- Confirmed useful fields in local metadata:
  - `borocd`
  - `boroname`
  - `location`
  - `borough`
  - `date_insta`
  - `ntaname`
- Best benchmark interpretation: official inventory of accessible pedestrian signal locations that can support first-pass screening of audible / accessible signal coverage around destinations
- Important caveat: APS presence at some intersections is not a full measure of accessible pedestrian travel conditions across a district

### 3) `pedestrian_ramp_locations`
- Geometry in local metadata: `Point`
- Rows: `217679`
- Confirmed useful fields in local metadata:
  - `cornerid`
  - `rampid`
  - `ramp_onstr`
  - `borough`
  - `dws_conditions`
  - `ponding`
  - `obstacles_ramp`
  - `obstacles_landing`
- Best benchmark interpretation: very large DOT curb-ramp / pedestrian-ramp inventory that can provide district-level context on crossing accessibility infrastructure
- Important caveat: raw ramp counts can be misleading because ramps are extremely numerous, vary in condition, and do not directly indicate route quality, maintenance status, or whether specific older-adult destinations have good approaches

### 4) `Community_Districs`
- Geometry in local metadata: `MultiPolygon`
- Rows: `71`
- Confirmed useful fields:
  - `BoroCD`
- Best benchmark interpretation: common polygon geography for first-pass aggregation because it lines up well with `communityboard` and `borocd`
- Important caveat: community districts are administrative planning areas, not natural walking sheds around specific providers

### 5) `exclusive_pedestrian_signal_barnes_dance_locations` (optional support)
- Geometry in local metadata: `Point`
- Rows: `686`
- Confirmed useful fields in local metadata:
  - `borocd`
  - `main_stree`
  - `cross_stre`
  - `barnes_dan`
  - `installati`
  - `ntaname`
- Best benchmark interpretation: optional context for intersections with all-pedestrian or related signal treatments
- Important caveat: these locations are not a substitute for APS coverage and should not be treated as equivalent accessibility features for blind, low-vision, or mobility-limited pedestrians

## Common geography guidance

The cleanest first-pass answer should use community districts.

Why:

- the NYC Aging provider inventory includes a `communityboard` field;
- `accessible_pedestrian_signal_locations` includes `borocd`;
- `Community_Districs` provides the corresponding polygon layer in the local datalake;
- using community districts reduces unnecessary harmonization compared with ZIP or NTA for this specific case.

A strong answer may say something like:

> “Because the older-adult provider data already includes `communityboard` and the APS layer includes `borocd`, I would use `Community_Districs` as the first-pass comparison geography. I would summarize provider sites, APS locations, and pedestrian ramps to those districts, then look for districts with relatively many older-adult destinations but comparatively sparse crossing-accessibility support.”

That is more benchmark-credible than defaulting to ZIP or NTA just because those geographies are common elsewhere in the repo.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for community districts where older-adult service destinations are present but mapped crossing-accessibility support appears comparatively limited;
- a first-pass comparison of destination presence and crossing-accessibility infrastructure using only the repo’s local layers;
- follow-up questions about whether certain districts merit more detailed field review, route auditing, or targeted accessibility investment.

### What it cannot prove
- that a district or route is truly inaccessible in practice;
- that older adults at these sites are unable to travel safely;
- that APS or ramp counts measure route quality, maintenance, wayfinding, sidewalk condition, or building accessibility;
- that lower infrastructure counts imply legal noncompliance;
- that all providers or all ramps have equal importance, usage, or functional quality.

### Important caveats a strong agent should mention
- **Infrastructure-type caveat:** APS and curb ramps serve different accessibility functions; they should not be collapsed into one generic metric without explanation.
- **Destination caveat:** provider locations are destinations, not observed trip origins or actual pedestrian demand counts.
- **Geography caveat:** community districts are useful for comparison, but they are still coarse areas rather than walk-sheds around each site.
- **Condition caveat:** the ramp dataset includes condition-related fields, but the benchmark is still not a full engineering audit.
- **Compliance caveat:** this is an accessibility-support screen, not an ADA determination.

## Selected supporting references

### 1) Older Adult Center - NYC Aging
- **Type:** official NYC Aging service page
- **URL:** https://www.nyc.gov/site/dfta/services/older-adult-center.page
- **Why relevant:** Officially establishes older-adult centers as real service destinations across the five boroughs and notes programming for older adults, including specialized support for blind and visually impaired older adults.
- **Confidence:** high

### 2) Accessible NYC 2025: An Accessibility Guide for City Agencies
- **Type:** official NYC guide
- **URL:** https://www.nyc.gov/assets/mopd/downloads/pdf/accessible-nyc-2025.pdf
- **Why relevant:** Provides official citywide accessibility guidance that supports treating curb ramps, pedestrian signals, and accessible routes as meaningful parts of equitable access.
- **Confidence:** high

### 3) Accessible Pedestrian Signal Locations - NYC Open Data
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/de3m-c5p4
- **Why relevant:** Official documentation for the APS inventory represented locally in the repo.
- **Confidence:** high

### 4) Pedestrian Ramp Locations - NYC Open Data
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/ufzp-rrqu
- **Why relevant:** Official documentation for the curb-ramp / pedestrian-ramp inventory represented locally in the repo.
- **Confidence:** high

### 5) Department for the Aging (NYC Aging) - All Contracted Providers
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/cqc8-am9x
- **Why relevant:** Official documentation for the older-adult provider inventory used as the destination layer in this case.
- **Confidence:** high

### 6) Safe Streets for Seniors
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/safeseniors.shtml
- **Why relevant:** Directly states that older adults face disproportionate pedestrian fatality risk and links that risk to signal timing, crossings, ramps, and other street-design interventions.
- **Confidence:** high

## Data access points for reproducibility

1. **Older-adult service destination layer**
   - Local dataset: `department_for_the_aging_nyc_aging_all_contracted_providers`
   - Local repository evidence: `data/metadata/department_for_the_aging_nyc_aging_all_contracted_providers.json`
   - Official source: `https://data.cityofnewyork.us/api/views/cqc8-am9x`

2. **Accessible pedestrian signal layer**
   - Local dataset: `accessible_pedestrian_signal_locations`
   - Local repository evidence: `data/metadata/accessible_pedestrian_signal_locations.json`
   - Official source: `https://data.cityofnewyork.us/api/views/de3m-c5p4`

3. **Pedestrian ramp layer**
   - Local dataset: `pedestrian_ramp_locations`
   - Local repository evidence: `data/metadata/pedestrian_ramp_locations.json`
   - Official source: `https://data.cityofnewyork.us/api/views/ufzp-rrqu`

4. **Community-district polygon layer**
   - Local dataset: `Community_Districs`
   - Local repository evidence: `data/metadata/Community_Districs.json`

5. **Optional all-pedestrian signal-treatment context**
   - Local dataset: `exclusive_pedestrian_signal_barnes_dance_locations`
   - Local repository evidence: `data/metadata/exclusive_pedestrian_signal_barnes_dance_locations.json`

## Coverage note

This case expands benchmark coverage into **pedestrian accessibility infrastructure**, an area that was largely underused in Cases 1-24. It brings `accessible_pedestrian_signal_locations`, `pedestrian_ramp_locations`, `Community_Districs`, and optionally `exclusive_pedestrian_signal_barnes_dance_locations` into the benchmark set while reusing the NYC Aging provider inventory in a different way from Case 23. That improves datalake coverage and tests whether an agent can reason carefully about accessibility-support proxies without overclaiming what point inventories prove.
