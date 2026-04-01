# Case 21 — Commercial corridors needing public-realm support

**Status:** drafted  
**Case ID:** 21  
**Theme:** economic development / public realm  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> A neighborhood commercial-district team wants to identify NYC areas where street-level business activity and pedestrian presence appear meaningful but visible public-realm support looks comparatively thin. Using the available data catalog, select the business, pedestrian, and public-space program datasets needed for a first-pass screen, choose a defensible common geography, and explain what the results can and cannot say about corridor vitality or investment priority.

## Why this benchmark matters

This is a benchmark for **economic-vitality reasoning under mixed data types and imperfect business proxies**.

It fits the current UrbanTrace copilot architecture well:

- `backend/llm_agent.py` gives the model dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports dataset-suggestion behavior, not a full corridor-evaluation or streetscape audit workflow;
- so benchmark quality depends on whether the agent can:
  1. choose the strongest local layers for business presence, pedestrian demand, and public-realm support,
  2. recognize which layers are program footprints rather than universal infrastructure coverage,
  3. pick a defensible neighborhood comparison geography, and
  4. keep the interpretation calibrated as a **screening for follow-up**, not a definitive corridor-investment decision.

A weak answer will say “use pedestrian counts and Open Streets.” A stronger answer should recognize that:

- `NYC_pedestrian_counts` is a sampled count program rather than a complete citywide pedestrian-demand surface;
- `NYC_Issued_Licenses` is the strongest broad local point layer for regulated business presence, but it is **not** a full census of all neighborhood commerce;
- `open_streets_locations` and `nyc_dot_pedestrian_plazas_point_feature` represent **public-realm support programs / facilities**, not total sidewalk quality or all business-support investments;
- a neighborhood polygon such as `NTA_Neighborhood_Tabulation_Areas` is needed to compare the mixed point and line layers in a first-pass screen.

That is exactly the kind of dataset-choice and interpretation discipline this benchmark should test.

## Source-grounded planning rationale

This case is grounded in real NYC planning and economic-development materials rather than invented scenario framing.

NYC Small Business Services’ **Neighborhood 360°** page says the program was created to identify, develop, and launch **commercial revitalization projects** in partnership with local stakeholders, and that it supports projects that strengthen and revitalize the **streets, small businesses, and community-based organizations** that anchor New York City neighborhoods. That directly supports a benchmark about where street-level commercial areas may merit additional public-realm attention.

The SBS **Commercial District Needs Assessments (CDNAs)** page is even more specific. It says each CDNA highlights the **existing business landscape, consumer characteristics, physical environment, and unique character of the commercial corridors and local businesses** that make up neighborhood identity, and that the assessments identify needs and opportunities for **merchant organizing, public programming, district marketing and branding, streetscape enhancements, business support services, and other quality-of-life improvements**. That is a close policy match to a benchmark asking whether commercially active, pedestrian-heavy places appear relatively under-supported by visible public-realm programs.

On the mobility / public-space side, NYC DOT’s **Pedestrian Mobility Plan** explicitly says NYC is a city of pedestrians, uses a **data-driven framework** to identify pedestrian needs, and treats businesses as one of the pedestrian generators that shape corridor demand. NYC DOT’s **Open Streets** and **Pedestrian Plazas** pages further show that the City treats street reclamation, plaza creation, and public-space programming as tools that can support community activity, mobility, commerce, and local quality of life.

That makes the benchmark-credible synthesis narrower and more defensible than a generic “best business districts” ranking:

- use pedestrian counts as evidence of observed foot-traffic activity;
- use issued-license locations as a broad local proxy for business presence;
- use Open Streets and pedestrian plazas as visible public-realm support layers already present in the repo; and
- interpret the result as a screen for commercially active places that may deserve deeper corridor review.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_pedestrian_counts` as the local observed pedestrian-activity layer.
- Use `NYC_Issued_Licenses` as the broadest local business-presence point layer available in the repo.
- Use `open_streets_locations` and `nyc_dot_pedestrian_plazas_point_feature` as the public-realm support layers.
- Prefer `NTA_Neighborhood_Tabulation_Areas` as the first-pass comparison geography because the operational layers are points and lines while the task asks about neighborhood-scale commercial areas.
- Interpret the result as a **commercial-corridor support screen**: NTAs with relatively strong pedestrian and business signals but comparatively limited visible public-realm support may merit closer review.
- Avoid overstating the result as proof of weak corridor performance, low merchant satisfaction, or causal business underinvestment.

### Expected core datasets
- `NYC_pedestrian_counts`
- `NYC_Issued_Licenses`
- `open_streets_locations`
- `nyc_dot_pedestrian_plazas_point_feature`
- `NTA_Neighborhood_Tabulation_Areas`

### Important optional context datasets
- `open_storefronts_applications_historical` only if the agent clearly explains that it reflects a specific historical curb/sidewalk-use program rather than a general measure of corridor vitality
- `street_seats_2014_2019` only if the agent explicitly notes that it is a very small historical program layer and therefore weak as a citywide comparison surface

### Likely distractors
- `NYC_population` — useful context, but the core prompt is about **pedestrian-rich commercial areas**, not resident population alone
- `NYC_Wi-Fi_Hotspot_Locations` and `NYC_libraries` — meaningful public assets, but not the strongest public-realm / corridor-support layers for this economic-vitality case
- `open_storefronts_applications_historical` when treated as though it were a complete citywide measure of commercial vitality or sidewalk quality
- `street_seats_2014_2019` when treated as a robust current citywide infrastructure layer

## Expected UrbanTrace dataset mapping

### 1) `NYC_pedestrian_counts`
- Geometry in local metadata: `Point`
- Rows: `11970`
- Confirmed useful fields in local metadata:
  - `Street_Nam`
  - `From_Stree`
  - `To_Street`
  - `Borough`
  - `start_date`
  - `end_date`
  - `count`
- Best benchmark interpretation: observed pedestrian activity at monitored locations
- Important caveat: this is a sampled count program, **not** a complete citywide pedestrian-demand surface

### 2) `NYC_Issued_Licenses`
- Geometry in local metadata: `Point`
- Rows: `10479`
- Confirmed useful fields in local metadata:
  - `Business Name`
  - `Business Category`
  - `License Type`
  - `License Status`
  - `Initial Issuance Date`
  - `Expiration Date`
  - `Borough`
  - `Community Board`
  - `Council District`
  - `NTA`
  - `Latitude`
  - `Longitude`
- Best benchmark interpretation: point locations for DCWP-regulated licensed business activity / covered commercial presence
- Important caveat: this is **not** a full census of all neighborhood businesses, and license categories vary substantially

### 3) `open_streets_locations`
- Geometry in local metadata: `MultiLineString`
- Rows: `386`
- Confirmed useful fields in local metadata:
  - `orgname`
  - `boroughname`
  - `appronstre`
  - `apprfromst`
  - `apprtostre`
  - `apprdayswe`
  - `reviewstat`
  - `apprstartd`
  - `apprenddat`
  - `shape_stle`
- Best benchmark interpretation: corridor-scale public-realm support and activation footprint through the Open Streets program
- Important caveat: Open Streets are program locations with operating rules and schedules, **not** a complete inventory of pedestrian-oriented street quality

### 4) `nyc_dot_pedestrian_plazas_point_feature`
- Geometry in local metadata: `Point`
- Rows: `90`
- Confirmed useful fields in local metadata:
  - `borocd`
  - `coundist`
  - `plazaname`
  - `partner`
  - `onstreet`
  - `fromstreet`
  - `tostreet`
- Best benchmark interpretation: durable pedestrian-plaza locations that can represent stronger public-space support than a corridor segment alone
- Important caveat: plazas are discrete assets and are not interchangeable with full corridor redesign or merchant support programs

### 5) `NTA_Neighborhood_Tabulation_Areas`
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed useful fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: the most defensible neighborhood comparison geography for rolling up the point and line layers in this case

## Common geography guidance

For this benchmark, NTA is the cleanest first-pass answer.

Why:

- `NYC_pedestrian_counts` is a point layer.
- `NYC_Issued_Licenses` is a point layer.
- `open_streets_locations` is a line layer.
- `nyc_dot_pedestrian_plazas_point_feature` is a point layer.
- the prompt asks about **commercial areas / neighborhoods**, not one storefront frontage, one Open Street segment, or one block-level engineering design.

That makes `NTA_Neighborhood_Tabulation_Areas` the most defensible common geography in the current repo for a first-pass screen.

A strong answer may say something like:

> “Because the task asks for neighborhood-scale commercial screening and the operational layers are points and lines, I would aggregate pedestrian counts, issued-license locations, Open Streets segments, and plaza locations to NTAs first. Then I would flag NTAs where observed pedestrian activity and business presence look relatively strong but public-realm support features appear comparatively limited.”

That is more benchmark-credible than pretending the repo already contains a validated commercial-corridor boundary layer, merchant-sales data, or a full sidewalk-quality audit.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for NTAs where commercially active, pedestrian-oriented places may have relatively little visible public-realm support in the local catalog;
- identification of areas that may deserve follow-up in neighborhood revitalization, merchant-organizing, streetscape, or public-space-planning conversations;
- a first-pass comparison of observed foot traffic, regulated business presence, and public-space program footprints using only the repo’s available local layers.

### What it cannot prove
- total neighborhood business vitality, revenue, or storefront occupancy;
- that an NTA with fewer plazas or Open Streets is actually underinvested in every public-realm dimension;
- that adding one Open Street or one plaza would automatically improve local commerce;
- that DCWP-issued-license counts are equivalent to all small-business activity;
- that pedestrian counts capture all corridor demand rather than only sampled locations.

### Important caveats a strong agent should mention
- **Pedestrian-count caveat:** count locations are sampled and uneven, not comprehensive.
- **Business-data caveat:** issued licenses cover regulated categories only, not all commerce.
- **Program-footprint caveat:** Open Streets and plazas are specific public-space programs, not universal measures of corridor quality.
- **Temporal caveat:** these layers span different time windows; a strong answer may note that the comparison is screening-oriented rather than perfectly time-synchronized.
- **Scale caveat:** NTAs are useful for neighborhood screening, but actual corridor investment decisions would require finer-grained review.

## Selected supporting references

### 1) Neighborhood 360° - SBS
- **Type:** official NYC SBS program page
- **URL:** https://www.nyc.gov/site/sbs/neighborhoods/neighborhood-360.page
- **Why relevant:** SBS says Neighborhood 360° supports commercial revitalization projects that strengthen the streets, small businesses, and community-based organizations that anchor NYC neighborhoods.
- **Confidence:** high

### 2) Commercial District Needs Assessments - SBS
- **Type:** official NYC SBS program / reports page
- **URL:** https://www.nyc.gov/site/sbs/neighborhoods/commercial-district-needs-assessments.page
- **Why relevant:** SBS says CDNAs highlight the business landscape, consumer characteristics, physical environment, and streetscape conditions of commercial corridors, and identify opportunities for revitalization, public programming, streetscape enhancements, and business support.
- **Confidence:** high

### 3) NYC DOT — Pedestrian Mobility Plan
- **Type:** official NYC DOT planning page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/pedestrian-mobility.shtml
- **Why relevant:** The page explicitly frames businesses as pedestrian generators and describes a data-driven approach to pedestrian needs, which supports using pedestrian counts in a commercial-corridor benchmark.
- **Confidence:** high

### 4) NYC DOT — Open Streets
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/openstreets.shtml
- **Why relevant:** NYC DOT says Open Streets can promote economic development, support community uses, and create new public space, making it a strong public-realm support layer for this case.
- **Confidence:** high

### 5) NYC DOT — Pedestrian Plazas
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/pedestrians/nyc-plaza-program.shtml
- **Why relevant:** NYC DOT says plazas enhance walkability, access, community, commerce, and culture, which directly supports using plaza locations as a public-realm support signal.
- **Confidence:** high

### 6) Issued Licenses - NYC Open Data / DCWP
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/w7w3-xahh
- **Why relevant:** Official source for the regulated business-license dataset used as the local business-presence layer.
- **Confidence:** high

## Data access points for reproducibility

1. **Observed pedestrian activity**
   - Local dataset: `NYC_pedestrian_counts`
   - Local repository evidence: `data/metadata/NYC_pedestrian_counts.json`

2. **Business-presence proxy**
   - Local dataset: `NYC_Issued_Licenses`
   - Local repository evidence: `data/metadata/NYC_Issued_Licenses.json`
   - Official source: `https://data.cityofnewyork.us/api/views/w7w3-xahh`

3. **Public-realm support corridors**
   - Local dataset: `open_streets_locations`
   - Local repository evidence: `data/metadata/open_streets_locations.json`

4. **Public-realm support places**
   - Local dataset: `nyc_dot_pedestrian_plazas_point_feature`
   - Local repository evidence: `data/metadata/nyc_dot_pedestrian_plazas_point_feature.json`

5. **Neighborhood rollup geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_pedestrian_counts`, `NYC_Issued_Licenses`, `open_streets_locations`, `nyc_dot_pedestrian_plazas_point_feature`, and `NTA_Neighborhood_Tabulation_Areas`.
- Explain why pedestrian counts and issued licenses together are stronger than either one alone for a commercial-corridor screen.
- Treat Open Streets and plazas as public-realm support signals rather than generic measures of sidewalk quality.
- Use NTAs as the common neighborhood geography for aggregating the point and line layers.
- Frame the result as a corridor-support screening exercise for follow-up, not a definitive investment ranking.

### What a very strong agent may also mention
- `License Status` and business-category filtering could improve downstream interpretation of issued-license counts.
- `shape_stle` from Open Streets could support a rough corridor-length proxy, but line length is still only a first-pass measure of support.
- `open_storefronts_applications_historical` is relevant only as narrow historical context, not as a full citywide vitality measure.
- A future corridor-level analysis would need storefront vacancy, land use, merchant survey, sidewalk width, or sales-tax-style data not currently represented here.

### Common failure modes
- Selecting only pedestrian counts and public-space layers while ignoring business presence.
- Treating issued licenses as a full small-business census.
- Treating Open Streets or plazas as complete measures of neighborhood streetscape quality.
- Ignoring the need for a common geography.
- Returning a generic amenity map instead of an economic-vitality / corridor-support screening workflow.

## Retrieval / provenance notes

- This case was drafted against the actual repo inventory in:
  - `data/metadata/NYC_pedestrian_counts.json`
  - `data/metadata/NYC_Issued_Licenses.json`
  - `data/metadata/open_streets_locations.json`
  - `data/metadata/nyc_dot_pedestrian_plazas_point_feature.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark framing was checked against the current agent/tool constraints in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The key benchmark value is that it tests whether the agent can combine business presence, pedestrian demand, and public-realm support without pretending the repo already contains a complete commercial-corridor performance model.
- No backend changes were required for this case.
