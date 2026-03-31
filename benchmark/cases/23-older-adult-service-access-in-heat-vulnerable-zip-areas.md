# Case 23 — Older-adult service access in heat-vulnerable ZIP areas

**Status:** drafted  
**Case ID:** 23  
**Theme:** aging / climate resilience / service access  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are helping a city analyst identify NYC areas where **heat vulnerability appears high and local access to NYC Aging contracted providers may be comparatively thin**. The benchmark should stay grounded in the actual UrbanTrace catalog and current copilot behavior. A strong answer should select the right aging-service and heat-vulnerability layers, explain the ZIP-like geography choices clearly, distinguish between provider types instead of treating every aging site as identical, and keep the result framed as a screening tool rather than a definitive measure of unmet need among older adults.

## Why this benchmark matters

This is a benchmark for **service-access reasoning under vulnerable-population targeting and imperfect ZIP geography**.

It fits the current UrbanTrace copilot architecture well:

- `backend/llm_agent.py` supplies dataset descriptions, metadata, and dashboard context;
- `backend/tool.py` supports dataset suggestion and explanation, not a turnkey accessibility or demand model;
- so benchmark quality depends on whether the agent can:
  1. identify the strongest local layer for older-adult services,
  2. recognize that the aging-provider inventory includes multiple service types with different implications for neighborhood access,
  3. choose a defensible ZIP-like geography for comparing heat burden and provider presence, and
  4. interpret the result as a **follow-up screen** rather than proof that older adults in a place are underserved.

A weak answer will say “use `NYC_HVI` and the aging providers dataset.” A stronger answer should notice that:

- `department_for_the_aging_nyc_aging_all_contracted_providers` is a broad administrative provider directory that includes **Older Adult Centers, transportation, caregiver services, home-delivered meals, case management, NORC, legal, and other contract types**, so provider-type filtering matters;
- `NYC_HVI` is already on a ZIP/ZCTA-like geography, which makes it a much better fit for this case than the repo’s sub-borough poverty and unemployment layers;
- `MODZCTA` is useful because it is the repo’s local modified-ZIP boundary layer with population estimates, but it is **not automatically identical** to the HVI layer’s ZCTA 2020 polygons;
- raw provider counts can be misleading without population context, but the repo does **not** contain an age-60-plus denominator aligned to the same geography, so a strong answer should say this explicitly.

That combination of dataset choice, provider-type discipline, and geography honesty is exactly what this benchmark should test.

## Source-grounded planning rationale

This case is grounded in official NYC materials rather than invented scenario framing.

NYC Aging’s **Older Adult Centers** page says there are **more than 300 older adult centers and affiliated sites** across the five boroughs that provide meals, activities, classes, fitness programs, and social services. The page also says membership is free and open to New Yorkers age 60 and older, and it explicitly positions centers as places that can reduce isolation and connect residents to benefits, transportation, and health-related support. That gives a direct official basis for treating neighborhood access to older-adult service locations as a meaningful planning question.

NYC Aging’s **Find Help** page further grounds the idea that the agency operates a citywide resource-and-referral system connecting older adults and their families to local services, programs, and opportunities in their communities. That supports a benchmark about where neighborhood-scale provider presence may deserve closer review.

The official **NYC Aging – All Contracted Providers** dataset documentation is especially important because it states that the City contracts with external organizations to provide services for adults age 60 and older and that the dataset includes **Older Adult Center, Abuse Prevention, Home Care, Legal Services, NORC, Transportation, Case Management, Home Delivered Meal, and Caregiver** contracts. That makes the local dataset a strong, real service-access layer rather than a hypothetical list of amenities.

On the heat-risk side, NYC Health’s **Interactive heat vulnerability index** page explicitly frames neighborhood heat vulnerability as an equity and planning problem. The page says Black New Yorkers are disproportionately affected by extreme heat and that structural inequities limit access to protective resources such as air conditioning, green space, and neighborhood cooling resources. The **2025 NYC Heat-Related Mortality Report** further shows that heat causes substantial preventable mortality in the city and emphasizes the importance of cooling and structural interventions.

Together, those official materials support a benchmark-credible synthesis:

- use the aging-provider directory as the local older-adult service layer;
- use `NYC_HVI` as the heat-vulnerability layer;
- use `MODZCTA` when the workflow needs a local ZIP-like reporting boundary and population context;
- treat the result as a first-pass screen for heat-vulnerable ZIP-like areas where local aging-provider presence may warrant closer review.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use `department_for_the_aging_nyc_aging_all_contracted_providers` as the core older-adult service-site layer.
- Use `NYC_HVI` as the ZIP/ZCTA-like heat-vulnerability layer.
- Use `MODZCTA` as optional reporting / harmonization support because it provides a local modified-ZIP boundary layer and `pop_est`, while also acknowledging that MODZCTA and the HVI polygons are not exactly the same geography.
- Prefer a **ZIP-like screening workflow** rather than forcing in sub-borough poverty or unemployment layers by default.
- Mention that `providertype` and `programname` matter because an Older Adult Center, transportation provider, caregiver service, or home-delivered-meals contract should not automatically be treated as equivalent neighborhood-access assets.
- Interpret the output as an **older-adult heat-resilience service screen**: ZIP-like areas with high heat vulnerability and comparatively sparse aging-provider presence may merit follow-up.
- Avoid claiming that fewer listed providers automatically means older adults there have poor support, or that all contracted providers offer the same kind of in-person neighborhood access.

### Expected core datasets
- `department_for_the_aging_nyc_aging_all_contracted_providers`
- `NYC_HVI`

### Important support datasets
- `MODZCTA`

### Important optional support datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explicitly explains why it is moving away from the cleaner ZIP-like framing already supported by HVI and provider ZIP fields
- `NYC_population` only as very rough context if the agent clearly says it is not age-specific and is not on the same native geography as HVI

### Likely distractors
- `NYC_poverty_rate` and `NYC_unemployment_rate` when treated as default core layers, because they are not ZIP-native in this repo and would weaken the geography discipline of this case
- `NTA_Neighborhood_Tabulation_Areas` when chosen casually instead of the cleaner ZIP-like path
- treating all aging providers as interchangeable without discussing `providertype`
- using `MODZCTA` as if it were automatically the same as the HVI polygons with no harmonization caveat

## Expected UrbanTrace dataset mapping

### 1) `department_for_the_aging_nyc_aging_all_contracted_providers`
- Geometry in local metadata: `Point`
- Rows: `445`
- Confirmed useful fields in local metadata:
  - `providertype`
  - `dfta_id`
  - `programname`
  - `sponsorname`
  - `programaddress`
  - `programzipcode`
  - `borough`
  - `communityboard`
  - `councildist`
  - `nta`
  - `latitude`
  - `longitude`
  - `location1`
- Best benchmark interpretation: official directory of NYC Aging-contracted providers serving adults age 60 and older across multiple service categories
- Important caveat: this is a mixed provider inventory, not a clean inventory of identical neighborhood centers and not a direct measure of capacity, utilization, or service quality

### 2) `NYC_HVI`
- Geometry in local metadata: `MultiPolygon`
- Rows: `184`
- Confirmed useful fields:
  - `ZIP Code Tabulation Area (ZCTA) 2020`
  - `Heat Vulnerability Index (HVI)`
- Best benchmark interpretation: ZIP/ZCTA-like polygon surface for neighborhood heat vulnerability
- Important caveat: HVI is a composite vulnerability measure, not a direct measure of the number of older adults or service demand among older adults specifically

### 3) `MODZCTA`
- Geometry in local metadata: `MultiPolygon`
- Rows: `178`
- Confirmed useful fields:
  - `modzcta`
  - `label`
  - `zcta`
  - `pop_est`
- Best benchmark interpretation: local modified-ZIP reporting / boundary layer that can help with communication and rough population context in ZIP-like analyses
- Important caveat: MODZCTA is related to, but not automatically identical with, the HVI layer’s ZCTA 2020 polygons

### 4) `NTA_Neighborhood_Tabulation_Areas` (optional support)
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

- `department_for_the_aging_nyc_aging_all_contracted_providers` contains `programzipcode` as well as point coordinates.
- `NYC_HVI` is already organized on **ZCTA 2020** polygons.
- `MODZCTA` is the repo’s strongest local modified-ZIP boundary layer and includes population estimates.
- the prompt is specifically about **heat-vulnerable ZIP-like areas**, not about sub-borough socioeconomic comparisons or arbitrary neighborhood boundaries.

That makes a ZIP-like workflow much more benchmark-credible than defaulting to NTA or Sub-Borough Area.

A strong answer may say something like:

> “Because the heat layer is already ZCTA-based and the aging-provider directory includes ZIP information, I would keep this as a ZIP-like screen. I would use `NYC_HVI` as the vulnerability surface, summarize NYC Aging provider points by ZIP/ZCTA or via overlay, and use `MODZCTA` only if I need a local reporting boundary and rough population context while acknowledging it is not exactly the same geography as the HVI polygons.”

That is better than saying “use poverty and unemployment too” without noticing that those layers would force the benchmark onto a different geography.

## Interpretation guidance

A benchmark-credible answer should make the interpretation boundaries explicit.

### What this analysis can support
- an exploratory screen for ZIP-like areas where heat vulnerability is high and listed NYC Aging provider presence appears comparatively limited;
- a first-pass comparison of heat burden and older-adult service-site presence using the repo’s actual local layers;
- follow-up questions about whether certain neighborhoods may merit closer review of older-adult outreach, center access, transportation support, or resilience planning.

### What it cannot prove
- that older adults in a ZIP area are truly underserved in practice;
- that all contracted providers are equally walk-in, center-based, or neighborhood-facing services;
- that fewer provider records mean lower capacity, lower quality, or worse outcomes;
- that HVI is a direct measure of older-adult need rather than a broader neighborhood heat-vulnerability signal;
- that general population estimates are a valid substitute for an older-adult denominator.

### Important caveats a strong agent should mention
- **Provider-mix caveat:** `providertype` matters. Older Adult Centers are not the same as home-delivered meals, transportation, legal services, caregiver contracts, or NORC programs.
- **Capacity caveat:** the local provider directory does not provide a clean, comparable citywide seat-count or service-volume field for all provider types.
- **Geography caveat:** ZCTA and MODZCTA are similar but not identical; a strong answer should not blur them together casually.
- **Denominator caveat:** the repo lacks an age-60-plus population layer aligned to the same geography, so raw counts or counts per total population are only rough proxies.
- **Access caveat:** provider presence does not capture travel time, language access, hours, referral pathways, or whether services are home-based rather than site-based.

## Selected supporting references

### 1) Older Adult Center - NYC Aging
- **Type:** official NYC Aging service page
- **URL:** https://www.nyc.gov/site/dfta/services/older-adult-center.page
- **Why relevant:** NYC Aging says there are more than 300 older adult centers and affiliated sites citywide, open to adults age 60 and older, providing meals, activities, fitness programs, and social services.
- **Confidence:** high

### 2) Find Help - NYC Aging
- **Type:** official NYC Aging service / referral page
- **URL:** https://www.nyc.gov/site/dfta/services/find-help.page
- **Why relevant:** NYC Aging describes Aging Connect as the agency’s information and resource center connecting older adults, families, and community members to local services, programs, and opportunities.
- **Confidence:** high

### 3) Department for the Aging (NYC Aging) - All Contracted Providers
- **Type:** official dataset documentation
- **URL:** https://data.cityofnewyork.us/api/views/cqc8-am9x
- **Why relevant:** Official documentation for the local provider directory, stating that it includes Older Adult Center, Abuse Prevention, Home Care, Legal Services, NORC, Transportation, Case Management, Home Delivered Meal, and Caregiver contracts.
- **Confidence:** high

### 4) Interactive heat vulnerability index
- **Type:** official NYC Health portal page
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/hvi/
- **Why relevant:** Official city framing for neighborhood heat vulnerability and inequitable exposure to heat risk.
- **Confidence:** high

### 5) 2025 NYC Heat-Related Mortality Report
- **Type:** official NYC Health report page
- **URL:** https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/heat-report/
- **Why relevant:** Provides official evidence that heat remains a major public-health burden in NYC and that protection and cooling access matter for resilience planning.
- **Confidence:** high

## Data access points for reproducibility

1. **Older-adult service-site layer**
   - Local dataset: `department_for_the_aging_nyc_aging_all_contracted_providers`
   - Local repository evidence: `data/metadata/department_for_the_aging_nyc_aging_all_contracted_providers.json`
   - Official source: `https://data.cityofnewyork.us/api/views/cqc8-am9x`

2. **Heat-vulnerability layer**
   - Local dataset: `NYC_HVI`
   - Local repository evidence: `data/metadata/NYC_HVI.json`

3. **ZIP-like reporting / support geography**
   - Local dataset: `MODZCTA`
   - Local repository evidence: `data/metadata/MODZCTA.json`

4. **Optional alternate neighborhood geography**
   - Local dataset: `NTA_Neighborhood_Tabulation_Areas`
   - Local repository evidence: `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`

## Suggested evaluation notes

### What a strong agent should do
- Select `department_for_the_aging_nyc_aging_all_contracted_providers` and `NYC_HVI`.
- Bring in `MODZCTA` if a local ZIP-like reporting geography or rough population context is needed.
- Explain that `providertype` matters and that not all provider records should be interpreted as equivalent neighborhood-access assets.
- Keep the workflow ZIP-like because the heat layer already supports that framing.
- Frame the result as a heat-resilience / older-adult service-access screen for follow-up, not a definitive service-gap ranking.

### What a very strong agent may also mention
- A center-focused version of the analysis could emphasize `providertype` values that correspond to Older Adult Centers or other site-based services, while keeping home-based services as a separate support category.
- `programzipcode` is useful for ZIP-like summarization, but spatial overlay from provider coordinates is usually more defensible where possible.
- `MODZCTA.pop_est` can help avoid over-reading raw provider counts, but it is still only a total-population denominator.
- A fuller model would ideally add age-specific population, disability, air-conditioning access, language access, and travel-time measures that are not directly available in the current repo.

### Common failure modes
- Treating all aging providers as identical service sites.
- Ignoring `MODZCTA` and claiming there is no useful ZIP-like reporting geography in the repo.
- Defaulting to poverty and unemployment layers even though they break the cleaner ZIP-like framing.
- Treating ZCTA and MODZCTA as identical without explanation.
- Claiming that low provider counts prove unmet need among older adults.

## Coverage note

This case improves benchmark coverage for **underused aging-service and ZIP-like support datasets** in the local datalake.

Most existing cases heavily exercise transportation, poverty, unemployment, air-pollution, library, school, Wi-Fi, business-license, and DYCD program-site layers. By contrast, `department_for_the_aging_nyc_aging_all_contracted_providers` had not been meaningfully represented in the benchmark set, despite being a substantial official service directory for a clearly policy-relevant population. This case also gives `MODZCTA` a more defensible role than simply serving as a generic distractor or geography footnote: here it becomes a natural support layer for ZIP-like reporting and rough population context.

That means Case 23 broadens the benchmark suite toward:

- older-adult / aging-service planning;
- climate-resilience screening for a vulnerable population;
- mixed provider-type reasoning rather than simple amenity counting; and
- cleaner use of ZIP-like geographies already present in the repo.

## Retrieval / provenance notes

- This case was drafted against the actual repo inventory in:
  - `data/metadata/department_for_the_aging_nyc_aging_all_contracted_providers.json`
  - `data/metadata/NYC_HVI.json`
  - `data/metadata/MODZCTA.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
  - `data/descriptions.csv`
- The benchmark framing was checked against the current agent/tool constraints in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The key benchmark value is that it tests whether the agent can combine a real vulnerable-population service directory with a ZIP-based climate-risk layer while staying honest about provider heterogeneity and ZIP-boundary mismatch.
- No backend changes were required for this case.
