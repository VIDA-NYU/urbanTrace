# Case 24 — Cooling-water access in heat-vulnerable ZIP areas

**Status:** drafted  
**Case ID:** 24  
**Theme:** climate resilience / parks access / public health  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> A resilience analyst wants to identify NYC ZIP-like areas where heat vulnerability is high but visible access to outdoor cooling-water amenities may be comparatively thin. Using the available data catalog, select the heat-vulnerability and parks-amenity datasets needed for the screen, explain the most defensible ZIP-like geography choice, distinguish everyday cooling-water amenities from the city's formal cooling-center system, and describe how the results should guide heat-resilience follow-up.

## Why this benchmark matters

This is a benchmark for **heat-resilience reasoning with underused parks datasets and imperfect ZIP geography**.

It fits the current UrbanTrace copilot architecture well:

- `backend/llm_agent.py` supplies dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports dataset suggestion and explanation, not a turnkey accessibility or heat-risk model;
- so benchmark quality depends on whether the agent can:
  1. identify the strongest local layers for neighborhood heat burden and outdoor cooling-water access,
  2. recognize that drinking fountains and spray showers are meaningful but **not interchangeable** resources,
  3. choose a defensible ZIP-like geography for comparing heat burden and amenity presence, and
  4. interpret the result as a **follow-up screen** rather than proof that residents in a place are protected or unprotected from extreme heat.

A weak answer will say “use `NYC_HVI` and parks amenities.” A stronger answer should notice that:

- `NYC_HVI` is already on a ZIP/ZCTA-like geography, which makes it the natural anchor layer;
- `nyc_parks_drinking_fountains` and `nyc_parks_spray_showers` are both point datasets, but they represent different forms of warm-weather relief and should not be casually merged into one identical service count;
- `MODZCTA` is useful because it is the repo’s local modified-ZIP boundary layer with `pop_est`, but it is **not automatically identical** to the HVI layer’s ZCTA 2020 polygons;
- the City’s official cooling-center / cool-options system is a separate operational resource, so a strong answer should avoid relabeling fountains or spray showers as formal cooling centers.

That combination of dataset choice, proxy discipline, and geography honesty is exactly what this benchmark should test.

## Source-grounded planning rationale

This case is grounded in official NYC materials rather than invented scenario framing.

NYC Emergency Management’s **Extreme Heat: Beat the Heat!** page states that extreme heat kills, that more than 500 New Yorkers die prematurely from preventable heat illness in an average year, and that people without home air conditioning should plan to use free public places and the City’s **Cool Options NYC** map. That provides direct official grounding for treating neighborhood heat protection as a real planning concern.

NYC Health’s **Interactive heat vulnerability index** page further grounds the benchmark by explicitly framing heat risk as a neighborhood inequity issue. The page says Black New Yorkers are disproportionately affected by heat and that structural inequities limit access to health-protective resources such as air conditioning, green space, and **neighborhood cooling resources**. That is strong official support for a benchmark about place-based heat protection assets.

The City also makes the outdoor-amenity connection directly. Official heat-emergency guidance tells New Yorkers to use the City’s **Cool It! NYC** resources for spray showers, drinking fountains, and other outdoor cooling options, and DEP’s Water-On-the-Go materials explicitly present public drinking fountains as a way to help New Yorkers **stay cool** and beat the heat. That is the missing direct support for treating parks water amenities as part of neighborhood heat-relief infrastructure rather than as unrelated park features.

On the amenity side, the official NYC Open Data documentation for **NYC Parks Drinking Fountains** states that the dataset inventories outdoor drinking fountains in parks, while the official documentation for **NYC Parks Spray Showers** states that it provides the locations of spray showers under the jurisdiction of NYC Parks and points users to the Parks spray-shower program page. Those are legitimate city-managed warm-weather amenity layers already present in the local repo.

The benchmark-credible synthesis is therefore narrower and more defensible than a generic “best cooling resources” map:

- use `NYC_HVI` as the heat-burden anchor;
- use parks drinking fountains and spray showers as **outdoor cooling-water amenity proxies** already present in the repo;
- use `MODZCTA` only as optional ZIP-like reporting support and rough population context;
- interpret the result as a first-pass screen for ZIP-like areas where visible outdoor cooling-water amenities may warrant closer review.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `NYC_HVI` as the core heat-vulnerability layer.
- Use `nyc_parks_drinking_fountains` and `nyc_parks_spray_showers` as the main outdoor cooling-water amenity layers.
- Use `MODZCTA` as optional reporting / harmonization support because it provides a local modified-ZIP boundary layer and `pop_est`, while also acknowledging that MODZCTA and the HVI polygons are not exactly the same geography.
- Prefer a **ZIP-like screening workflow** rather than forcing the case onto sub-borough poverty or unemployment layers by default.
- Mention that drinking fountains and spray showers serve different functions; a strong answer should not treat them as perfectly interchangeable measures of heat protection.
- Interpret the output as a **heat-resilience amenity screen**: ZIP-like areas with high heat vulnerability and comparatively sparse outdoor cooling-water amenities may merit follow-up.
- Avoid claiming that fewer fountains or spray showers automatically means residents there are unsafe, or that these amenities substitute for indoor cooling, home air conditioning, or the City’s official cooling-center system.

### Expected core datasets
- `NYC_HVI`
- `nyc_parks_drinking_fountains`
- `nyc_parks_spray_showers`

### Important support dataset
- `MODZCTA`

### Important optional support datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains why it is moving away from the cleaner ZIP-like framing already supported by HVI and ZIP-like reporting needs
- `NYC_population` only as very rough context if the agent clearly says it is not on the same native geography as HVI and is weaker than `MODZCTA` for this particular case

### Likely distractors
- `NYC_poverty_rate` and `NYC_unemployment_rate` when treated as default core layers, because they are not ZIP-native in this repo and would weaken the geography discipline of this case
- `NTA_Neighborhood_Tabulation_Areas` when chosen casually instead of the cleaner ZIP-like path
- `NYC_libraries` or `NYC_Schools` when treated as the primary heat-resource answer for this case, because the specific benchmark is about **outdoor cooling-water amenities**
- treating fountains and spray showers as formal cooling centers or as equivalent assets without caveat

## Expected UrbanTrace dataset mapping

### 1) `NYC_HVI`
- Geometry in local metadata: `MultiPolygon`
- Rows: `184`
- Confirmed useful fields:
  - `ZIP Code Tabulation Area (ZCTA) 2020`
  - `Heat Vulnerability Index (HVI)`
- Best benchmark interpretation: ZIP/ZCTA-like polygon surface for neighborhood heat vulnerability
- Important caveat: HVI is a composite vulnerability measure, not a direct measure of the quantity of cooling amenities or of actual heat-related illness in each area

### 2) `nyc_parks_drinking_fountains`
- Geometry in local metadata: `Point`
- Rows: `3619`
- Confirmed useful fields in local metadata:
  - `fountainty`
  - `position`
  - `gispropnum`
  - `propertyna`
  - `borough`
  - `fountainco`
  - `department`
  - `decription`
- Best benchmark interpretation: official inventory of outdoor drinking fountains in NYC Parks properties
- Important caveat: fountains are seasonal / operational amenities whose presence does not guarantee current functionality, water availability, hours, or accessibility at all times

### 3) `nyc_parks_spray_showers`
- Geometry in local metadata: `Point`
- Rows: `761`
- Confirmed useful fields in local metadata:
  - `boro`
  - `propnum`
  - `propname`
  - `sitename`
  - `district`
  - `coundist`
- Best benchmark interpretation: official inventory of spray showers under NYC Parks jurisdiction, useful as stronger warm-weather cooling amenities than fountains alone
- Important caveat: spray showers are seasonal recreational water features and are not equivalent to indoor cooling space, hydration access, or formal emergency cooling sites

### 4) `MODZCTA`
- Geometry in local metadata: `MultiPolygon`
- Rows: `178`
- Confirmed useful fields:
  - `modzcta`
  - `label`
  - `zcta`
  - `pop_est`
- Best benchmark interpretation: local modified-ZIP reporting / boundary layer that can help with communication and rough population context in ZIP-like analyses
- Important caveat: MODZCTA is related to, but not automatically identical with, the HVI layer’s ZCTA 2020 polygons

### 5) `NTA_Neighborhood_Tabulation_Areas` (optional support)
- Geometry in local metadata: `MultiPolygon`
- Rows: `262`
- Confirmed useful fields:
  - `nta2020`
  - `ntaname`
  - `boroname`
  - `cdta2020`
- Best benchmark interpretation: optional neighborhood reporting geography, but weaker than the ZIP-like path for this particular case because HVI is already ZIP-based

## Common geography guidance

The cleanest first-pass answer should stay ZIP-like.

Why:

- `NYC_HVI` is already organized on **ZCTA 2020** polygons.
- `nyc_parks_drinking_fountains` and `nyc_parks_spray_showers` are point datasets that can be spatially summarized into those polygons.
- `MODZCTA` is the repo’s strongest local modified-ZIP reporting boundary and includes rough population context.
- the prompt is specifically about **heat-vulnerable ZIP-like areas**, not about sub-borough socioeconomic comparison or arbitrary neighborhood labels.

That makes a ZIP-like workflow much more benchmark-credible than defaulting to NTA or Sub-Borough Area.

A strong answer may say something like:

> “Because the heat layer is already ZCTA-based and the parks amenity layers are points, I would keep this as a ZIP-like screen. I would use `NYC_HVI` as the vulnerability surface, summarize drinking fountains and spray showers into those polygons, and use `MODZCTA` only if I need a local reporting boundary and rough population context while acknowledging it is not exactly the same geography as the HVI polygons.”

That is better than saying “use poverty and unemployment too” without noticing that those layers would force the benchmark onto a different geography.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for ZIP-like areas where heat vulnerability is high and visible outdoor cooling-water amenities appear comparatively sparse;
- a first-pass comparison of heat burden and selected parks amenities using the repo’s actual local layers;
- follow-up questions about whether certain neighborhoods may merit closer review of hydration access, park amenity distribution, or complementary heat-resilience investments.

### What it cannot prove
- that residents in a ZIP area are truly unsafe or adequately protected from heat in practice;
- that fountains and spray showers are equivalent to cooling centers, indoor public space, or home air conditioning;
- that fewer mapped amenities mean lower capacity, poorer maintenance, or worse outcomes;
- that HVI is a direct measure of amenity demand rather than broader neighborhood vulnerability;
- that general population estimates are a valid substitute for a heat-sensitive or age-specific denominator.

### Important caveats a strong agent should mention
- **Amenity-type caveat:** fountains support hydration, while spray showers provide a different form of warm-weather cooling and recreation; they should not be collapsed into one metric without explanation.
- **Operational caveat:** the repo does not provide a clean citywide status field confirming current operation, hours, or seasonal availability for every amenity.
- **Geography caveat:** ZCTA and MODZCTA are similar but not identical; a strong answer should not blur them together casually.
- **Coverage caveat:** these are NYC Parks amenities, not all possible water or cooling resources citywide.
- **System-boundary caveat:** this benchmark is about visible outdoor cooling-water amenities, not the official Cool Options / cooling-center system.

## Selected supporting references

### 1) Extreme Heat: Beat the Heat! — NYC Emergency Management
- **Type:** official NYC preparedness page
- **URL:** https://www.nyc.gov/site/em/ready/extreme-heat.page
- **Why relevant:** The page states that extreme heat kills, notes substantial preventable mortality, and tells residents without home air conditioning to use free public places and the City’s cool-options resources. That supports the broader need for neighborhood heat-protection screening.
- **Confidence:** high

### 2) Interactive heat vulnerability index
- **Type:** official NYC Health portal page
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/
- **Why relevant:** The page explicitly frames heat as a neighborhood inequity issue and mentions reduced access to neighborhood cooling resources, directly supporting the vulnerability side of the benchmark.
- **Confidence:** high

### 3) NYC Parks Drinking Fountains — NYC Open Data
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/qnv7-p7a2
- **Why relevant:** Official documentation for the local drinking-fountain inventory, stating that it covers outdoor drinking fountains in parks and includes physical-environment attributes.
- **Confidence:** high

### 4) NYC Parks Spray Showers — NYC Open Data
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/ckaz-6gaa
- **Why relevant:** Official documentation for the local spray-shower inventory, stating that it provides the locations of spray showers under NYC Parks jurisdiction.
- **Confidence:** high

### 5) Cool Options NYC
- **Type:** official city finder / service page
- **URL:** https://finder.nyc.gov/coolingcenters/
- **Why relevant:** Useful as an explicit boundary condition: it is the City’s formal cool-options system, which helps a strong agent explain why fountains and spray showers should not be mislabeled as official cooling centers.
- **Confidence:** medium-high

### 6) DEP Helps New Yorkers Stay Cool With Launch of Water-On-the-Go Season
- **Type:** official NYC press release
- **URL:** https://www.nyc.gov/html/dep/html/press_releases/14-057pr.shtml
- **Why relevant:** This is a direct official statement that public drinking fountains are a heat-relief resource, not just a generic parks amenity. It strengthens the case for using fountains as a legitimate outdoor cooling-water layer.
- **Confidence:** high

## Data access points for reproducibility

1. **Heat-vulnerability layer**
   - Local dataset: `NYC_HVI`
   - Local repository evidence: `data/metadata/NYC_HVI.json`
   - Official context page: `https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/`

2. **Outdoor drinking-fountain amenity layer**
   - Local dataset: `nyc_parks_drinking_fountains`
   - Local repository evidence: `data/metadata/nyc_parks_drinking_fountains.json`
   - Official source: `https://data.cityofnewyork.us/api/views/qnv7-p7a2`

3. **Outdoor spray-shower amenity layer**
   - Local dataset: `nyc_parks_spray_showers`
   - Local repository evidence: `data/metadata/nyc_parks_spray_showers.json`
   - Official source: `https://data.cityofnewyork.us/api/views/ckaz-6gaa`

4. **ZIP-like reporting boundary / rough denominator support**
   - Local dataset: `MODZCTA`
   - Local repository evidence: `data/metadata/MODZCTA.json`

## Coverage note

This case expands benchmark coverage into **underused parks heat-resilience amenities**. Relative to Cases 5 and 23, it adds a different service-side lens: not libraries, schools, or aging providers, but **outdoor drinking fountains and spray showers** as visible warm-weather public amenities. That improves local datalake coverage and tests whether an agent can stay disciplined about the difference between informal heat-resilience assets and the City’s formal cooling-center system.
