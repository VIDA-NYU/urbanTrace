# Case 10 — High-poverty neighborhoods and public digital-access support

**Status:** revised  
**Case ID:** 10  
**Theme:** digital equity / public access / neighborhood need  
**Language:** English  
**Reviewed on:** 2026-03-31

## Task

> A digital-equity planner wants to identify NYC neighborhoods where poverty is high but visible public digital-access support appears comparatively thin. Using the available data catalog, identify the datasets needed for a neighborhood-level screen, choose a defensible geography, and explain how the results should guide later siting, outreach, or program-level review.

## Why this benchmark matters

This is a benchmark for **dataset selection + geography harmonization + calibrated proxy reasoning**, not just for naming a poverty dataset or a technology dataset.

A weak agent may:
1. stop at a socioeconomic layer and describe need without selecting any public-access infrastructure;
2. select a digital-access point layer but fail to normalize or contextualize it by neighborhood population;
3. choose a geography only because the point layer exposes extra administrative fields, rather than because it is the cleanest comparison surface supported in the repo; or
4. treat the count of access sites as definitive evidence of digital adequacy rather than a first-pass screening proxy.

A stronger agent should recognize that:
1. neighborhood poverty is the main need-side signal;
2. public computer centers are the clearest repo-native public digital-access support layer;
3. population is needed so low-support patterns can be interpreted fairly across neighborhoods of different size; and
4. the resulting neighborhood screen is only a first-pass prioritization before site-level, institutional, or programmatic follow-up.

That behavior is well aligned with the current UrbanTrace copilot design, where the agent is evaluated on selecting the right local datasets and proposing a coherent workflow over the datalake rather than executing a full outside planning study.

## Source-grounded planning rationale

This case is grounded in a real NYC digital-equity planning problem.

The **NYC Digital Equity Roadmap** states that digital access, devices, skills, and support remain uneven across the city and reports that nearly **30 percent of NYC households — almost 2.5 million residents — lack the combination of mobile and home broadband needed for full connectivity**. The roadmap also says the city provides free digital-device access at **more than 450 public computer centers** and digital-skills programming at **more than 100 sites**. That makes neighborhood screening for where public digital-access support may still be thin a realistic city planning task, not a hypothetical one.

The city’s public-services connectivity strategy reinforces that logic. NYC explicitly identifies **community computer centers** in libraries, community centers, and senior centers as critical resources for residents who lack home access and says the city seeks to support them particularly in areas and populations where home access lags.

This benchmark also reflects real neighborhood need. The **NYC Council Data Team** reports that **24.5 percent of households lacked broadband subscription at home**, with higher rates among **low-income households**, and that in several community districts — many in the Bronx and other high-poverty areas — **more than 40 percent of households lacked broadband**. That makes a screen for places where poverty is high and public digital-access support appears thin a credible cross-agency planning question.

The case is also tied to real intervention pathways. In March 2025, the Adams administration announced **$2.4 million** to renovate computer labs in **libraries and older adult centers**, explicitly linking digital-equity investments to neighborhood-serving public institutions. NYC’s library performance reporting also treats libraries as active digital-access infrastructure, tracking **computers for public use, computer sessions, and wireless sessions**.

Finally, broader urban research supports the analytical logic. A 2023 peer-reviewed study covering **905 U.S. cities** found that although broadband access improved between 2017 and 2021, **income and racial disparities persisted**. That makes a descriptive screening workflow that combines neighborhood poverty and public-access infrastructure analytically credible.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Need / vulnerability signal:** `NYC_poverty_rate`
2. **Population normalization / scale:** `NYC_population`
3. **Public digital-access support:** `citywide_public_computer_centers`
4. **Neighborhood rollup layer:** use the shared **Sub-Borough Area** polygon geography already carried by the poverty and population layers
5. **Interpretation rule:** flag sub-borough areas where poverty is elevated while public digital-access support appears comparatively thin relative to population, then use those neighborhoods to motivate later siting, outreach, library, senior-center, or digital-skills follow-up

A good gold-standard answer does **not** need to compute a perfect accessibility model. It does need to show the right analytical logic:

- use poverty as the need-side layer rather than a vaguer proxy like income diversity;
- add population so the comparison does not ignore neighborhood scale;
- summarize public computer center support into the polygon geography used by the socioeconomic layers;
- explain that this is a screening product for follow-up, not proof that residents are adequately or inadequately served.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_poverty_rate`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: primary socioeconomic need signal
   - Relevant local fields expected from repo pattern:
     - `Sub-Borough Area`
     - `Official_SBA_name`
     - `bor_subb`
     - annual poverty values
   - Best benchmark interpretation: neighborhood need / vulnerability anchor

2. **`NYC_population`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: population scale / normalization layer
   - Relevant local fields expected from repo pattern:
     - `Sub-Borough Area`
     - `Official_SBA_name`
     - `bor_subb`
     - annual population values
   - Best benchmark interpretation: helps distinguish thin digital-access support affecting many residents from a similar raw count in a much smaller neighborhood

3. **`citywide_public_computer_centers`**
   - Geometry in local metadata: expected `Point`
   - Why it matters: clearest repo-native public digital-access infrastructure layer
   - Likely relevant fields from the upstream source:
     - site / center name
     - location
     - host institution or agency
     - access / service descriptors
   - Best benchmark interpretation: visible neighborhood public-access support infrastructure to be summarized into polygons

### Acceptable secondary context, but not substitutes

- `NYC_Wi-Fi_Hotspot_Locations`
  - Useful supporting connectivity layer, but broader and noisier than dedicated public computer center infrastructure for this specific case.
- `NYC_libraries`
  - Useful institutional support layer, especially if the agent wants to connect digital-access follow-up to public-serving library sites, but not the cleanest single infrastructure dataset for the core benchmark.

### Likely distractors

- `NYC_income_diversity_ratio`
  - Too abstract and semantically unstable for this case; prior benchmark runs showed that models often replaced it with poverty anyway.
- `NYC_median_household_income`
  - A meaningful socioeconomic signal in other cases, but weaker than poverty for this specific digital-equity prompt.
- `NTA_Neighborhood_Tabulation_Areas`
  - A plausible reporting geography, but weaker than the repo-native sub-borough-area comparison surface already shared by the poverty and population layers.
- `NYC_Wi-Fi_Hotspot_Locations` when used alone
  - Too broad to serve as the only public-access support layer without explanation.

## Selected supporting references

### 1) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **Why relevant:** Directly grounds the benchmark in NYC’s current digital-equity strategy. The roadmap describes persistent connectivity gaps and documents the city’s existing public computer center and skills-program infrastructure.
- **Confidence:** high

### 2) Mayor Adams, Chief Technology Officer Fraser Announce $2.4 Million Investment, Release Roadmap to Advance Digital Equity in Disadvantaged Communities
- **Type:** official NYC policy / press release
- **Agency:** NYC Mayor’s Office
- **URL:** https://www.nyc.gov/office-of-the-mayor/news/129-25/mayor-adams-chief-technology-officer-fraser-2-4-million-investment-release-roadmap-to
- **Why relevant:** Shows that NYC is actively funding neighborhood digital-access infrastructure, including computer labs in libraries and older adult centers, making this a real intervention pathway rather than a speculative one.
- **Confidence:** high

### 3) Access to Internet in NYC
- **Type:** NYC policy-data analysis
- **Organization:** NYC Council Data Team
- **URL:** https://council.nyc.gov/data/internet-access/
- **Why relevant:** Provides neighborhood and demographic evidence that broadband gaps are worse among low-income households and in several high-poverty districts, supporting the need-side screening logic.
- **Confidence:** high

### 4) Strategy — Public Services
- **Type:** official NYC strategy page
- **Agency:** NYC Office of Technology and Innovation / Connected NYC
- **URL:** https://www.nyc.gov/site/connected/public-services/strategy.page
- **Why relevant:** Explicitly treats community computer centers, libraries, community centers, and senior centers as critical public digital-access resources.
- **Confidence:** high

### 5) Public Libraries — FY2026 Preliminary Mayor’s Management Report
- **Type:** official NYC service report
- **Agency:** City of New York
- **URL:** https://www.nyc.gov/assets/operations/downloads/pdf/pmmr2026/lib.pdf
- **Why relevant:** Confirms that libraries function as active digital-access institutions by tracking computers for public use, computer sessions, and wireless sessions.
- **Confidence:** high

### 6) Racial/ethnic and income disparities in neighborhood-level broadband access in 905 US cities, 2017–2021
- **Type:** peer-reviewed urban research
- **Authors:** Suhang Song et al.
- **URL:** https://www.sciencedirect.com/science/article/pii/S0033350623000550
- **Why relevant:** Provides broader urban evidence that neighborhood broadband inequality remains strongly patterned by income and race, supporting the analytical logic of the benchmark.
- **Confidence:** high

### 7) City Launches ‘Neighborhood Tech Help’ to Bridge Digital Divide Across the Boroughs
- **Type:** official NYC press release
- **Agency:** NYC Department of Housing Preservation and Development
- **URL:** https://www.nyc.gov/site/hpd/news/015-25/city-launches-neighborhood-tech-help-bridge-digital-divide-across-boroughs
- **Why relevant:** Adds direct NYC evidence that underserved neighborhoods often depend on libraries and community sites for internet and technology help, which closely matches the benchmark’s intervention logic.
- **Confidence:** high

## Data access points for reproducibility

1. **Neighborhood poverty**
   - Local dataset: `NYC_poverty_rate`
   - Benchmark role: need-side socioeconomic anchor

2. **Neighborhood population**
   - Local dataset: `NYC_population`
   - Benchmark role: normalization and interpretation layer

3. **Public digital-access support**
   - Local dataset: `citywide_public_computer_centers`
   - Upstream public access point: https://data.cityofnewyork.us/Social-Services/Citywide-Public-Computer-Centers/sejx-2gn3
   - Benchmark role: public-access infrastructure layer for polygon rollup

## Suggested evaluation notes

### What a strong agent should do
- Select exactly the three core datasets above, or at minimum make them central.
- Explain why poverty is the correct need-side signal for this case.
- Treat population as necessary for fair comparison.
- Use the poverty/population polygon geography as the common neighborhood comparison surface.
- Keep the interpretation calibrated: neighborhood screening first, then site/institution/program follow-up.

### What a very strong agent may also mention
- `NYC_Wi-Fi_Hotspot_Locations` can be used as secondary context, but point counts alone may not reflect comparable service quality.
- `NYC_libraries` may strengthen an institutional follow-up story because library systems are part of NYC’s digital-access ecosystem.
- Public computer center counts are a proxy for visible support, not a complete measure of digital adequacy, home broadband, or service quality.
- A per-capita or density-style normalization improves downstream analysis, even if the benchmark is only evaluating dataset selection and workflow framing.

### Common failure modes
- Returning only `NYC_poverty_rate`.
- Replacing poverty with `NYC_income_diversity_ratio` or `NYC_median_household_income`.
- Ignoring `NYC_population`.
- Defaulting to a different geography without explaining why it is better than the shared sub-borough-area structure.
- Treating public-access site counts as definitive proof of service adequacy.

## Retrieval / provenance notes

- This revised case is intentionally designed to avoid the failure mode of the previous “income diversity” task, where even strong LLMs converged on poverty and public digital-access infrastructure instead of the abstract target construct.
- The redesign keeps the benchmark challenging but makes it more aligned with both real NYC policy language and current UrbanTrace copilot behavior.
- The benchmark is strongest when graded on **dataset choice + geography reasoning + calibrated policy interpretation**, not on producing a single perfect adequacy score.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the most useful upgrade would be to add a source or local layer about **home broadband adoption or device ownership at neighborhood scale**. The case now has direct NYC support for poverty plus public-access intervention logic, but it still lacks a repo-native household connectivity outcome layer.
