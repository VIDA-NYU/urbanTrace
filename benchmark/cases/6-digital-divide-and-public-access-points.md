# Case 6 — Digital divide and public access points

**Status:** revised  
**Case ID:** 6  
**Theme:** digital equity / public services  
**Language:** English  
**Reviewed on:** 2026-03-23

## Task

> You are helping a digital equity team identify NYC areas where residents may have **greater reliance on public digital-access infrastructure**. The task is not just to map Wi‑Fi or libraries separately. It should screen for neighborhoods where public access points — especially public Wi‑Fi hotspots, libraries, and public computer centers — may matter more because poverty burden is higher and resident population is large. Using UrbanTrace, determine which datasets should be selected, what comparison geography is most defensible given the local repo, and how the result should be interpreted for a realistic NYC digital-equity planning workflow.

## Why this benchmark matters

This is a benchmark for **dataset selection, proxy reasoning, and geography discipline** under the current UrbanTrace copilot design.

A weak agent may do one of the following:

1. stop at `NYC_Wi-Fi_Hotspot_Locations` only;
2. mention libraries without connecting them to digital access need;
3. miss the stronger repo-native digital access dataset `citywide_public_computer_centers`; or
4. force everything into NTAs because the access-point layers contain NTA fields, even though the socioeconomic layers in the repo are not natively on NTA geography.

A stronger agent should recognize that this case is really about **public digital access infrastructure relative to neighborhood need**, not about one facility type in isolation. That is a good fit for the current architecture because `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` supports suggestion of the strongest matching datasets rather than running a full GIS workflow. So benchmark quality depends on selecting the right 1–5 datasets, resisting attractive-but-weaker distractors, and clearly explaining the comparison geometry.

## Source-grounded planning rationale

NYC’s Office of Technology and Innovation explicitly frames digital equity as a citywide public-policy priority. The City’s Digital Equity Roadmap describes digital inequity in terms of broadband affordability, device access, skills, and the need for community support infrastructure. The more recent Neighborhood Tech Help announcement makes the same logic concrete: the City is funding neighborhood-based technical assistance to help residents get online, use devices, and navigate digital services.

That policy framing supports a benchmark about **where public digital-access infrastructure may be especially important**. In the local UrbanTrace catalog, the most credible public-access proxies are:

- `NYC_Wi-Fi_Hotspot_Locations` for free or limited-free public connectivity points;
- `citywide_public_computer_centers` for staffed or programmatic access sites with computers, Wi‑Fi, accessibility, and training-related fields; and
- `NYC_libraries` because libraries are durable, citywide civic institutions that often function as public digital-access anchors.

To turn that into a credible equity screen, the infrastructure layers should be paired with neighborhood-need layers already in the repo: `NYC_poverty_rate` and `NYC_population`.

## Recommended benchmark framing

A strong answer should say, in substance:

- Use **all three public-access infrastructure datasets**: Wi‑Fi hotspots, public computer centers, and libraries.
- Use `NYC_poverty_rate` and `NYC_population` to represent neighborhood need.
- Prefer the **poverty/population polygon geography** as the first-pass comparison geography, because those two need layers already share the same sub-borough-area structure and are the policy-need anchor in the local repo.
- Treat `NTA_Neighborhood_Tabulation_Areas` as optional reference geography only if the agent explicitly explains an overlay or crosswalk step.
- Interpret the output as a **screening product for digital-equity follow-up**, not proof that any neighborhood is digitally excluded.

### Expected core datasets
- `NYC_Wi-Fi_Hotspot_Locations`
- `citywide_public_computer_centers`
- `NYC_libraries`
- `NYC_poverty_rate`
- `NYC_population`

### Important optional support / reference datasets
- `NTA_Neighborhood_Tabulation_Areas` only if the agent explains why it is using NTA for display or reporting

### Likely distractors
- `MODZCTA` — tempting because digital-access conversations often use ZIP-like geography, but the local poverty/population layers here are sub-borough polygons
- `NYC_Schools` — may sound relevant for digital access, but is a weaker public-access proxy than libraries or public computer centers for this specific task
- `NTA_Neighborhood_Tabulation_Areas` when selected as though it automatically resolves the geography mismatch

## Expected UrbanTrace dataset mapping

### 1) `NYC_Wi-Fi_Hotspot_Locations`
- Geometry in local metadata: `Point`
- Rows: `3319`
- Confirmed key fields relevant to harmonization / screening:
  - `Type`
  - `Provider`
  - `Neighborhood Tabulation Area Code (NTACODE)`
  - `Neighborhood Tabulation Area (NTA)`
  - `BoroCD`
  - `Census Tract`
  - `count`
- Best benchmark interpretation: public connectivity points that can be counted by polygon geography or screened by density

### 2) `citywide_public_computer_centers`
- Geometry in local metadata: `Point`
- Rows: `508`
- Confirmed key fields relevant to digital-access interpretation:
  - `wi_fi_available`
  - `workstation`
  - `staffed`
  - `open_lab_hrs_per_wk`
  - `training_hours_per_wk`
  - `wheelchair_accessible`
  - `nta_code`
  - `nta_name`
  - `census_tract`
- Best benchmark interpretation: direct public digital-access sites, often richer than a simple point inventory because the dataset includes workstations, training, and accessibility attributes

### 3) `NYC_libraries`
- Geometry in local metadata: `Point`
- Rows: `253`
- Confirmed key fields relevant to harmonization / counting:
  - `factype`
  - `opname`
  - `nta2010`
  - `nta2020`
  - `ct2020`
  - `zipcode`
  - `count`
- Best benchmark interpretation: durable civic-access locations that can serve as neighborhood digital-access anchors, even if not every library is equivalent to a formal computer center

### 4) `NYC_poverty_rate`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: neighborhood-need layer representing concentrated economic vulnerability

### 5) `NYC_population`
- Geometry in local metadata: `MultiPolygon`
- Rows: `55`
- Confirmed key fields:
  - `Sub-Borough Area`
  - `Official_SBA_name`
  - `bor_subb`
  - recent annual values including `2021`, `2022`, `2023`
- Best benchmark interpretation: population scale layer that helps distinguish a low-access, high-need area from a low-access area with relatively few residents

## Common geography guidance

This is the key correction for the case.

The previous draft treated `NTA_Neighborhood_Tabulation_Areas` as an expected core layer. That is not the cleanest benchmark choice given the local repo evidence:

- `NYC_Wi-Fi_Hotspot_Locations`, `citywide_public_computer_centers`, and `NYC_libraries` are all **point** datasets.
- `NYC_poverty_rate` and `NYC_population` are both **polygon** datasets with matching **sub-borough-area** structure (`Sub-Borough Area`, `Official_SBA_name`, `bor_subb`).
- The access-point layers do contain NTA fields, but the poverty and population layers do **not** natively live on NTA geography.

So the most benchmark-credible first-pass workflow is:

1. **Anchor the analysis on the poverty/population polygon layers.**
2. Count Wi‑Fi hotspots, public computer centers, and libraries into those polygons using spatial overlay.
3. Compare infrastructure counts or densities against poverty burden and resident population.
4. Flag polygons where poverty is high and population is substantial but public digital-access infrastructure appears comparatively thin.
5. Only convert the result to NTA reporting if the agent explicitly describes a second overlay/crosswalk step.

A strong answer may phrase this as:

> “Because the need layers already share the same polygon geography and the access layers are points, I would anchor the comparison on the poverty/population polygons and count public access points into them. I would use NTAs only as an optional reporting geography, not as the default join unit.”

That is materially more credible than defaulting to NTAs without explanation.

## Important interpretation caveats

A benchmark-credible answer should also note several limits:

- **Public access is multi-dimensional.** Wi‑Fi hotspots, libraries, and public computer centers are not interchangeable.
- **Do not double-count casually.** Some libraries may also appear in the Wi‑Fi hotspot inventory, so a careful downstream analysis should acknowledge potential overlap.
- **Access quality differs.** Public computer centers are often the strongest direct digital-access proxy because they may include workstations, staffing, training, and accessibility information.
- **This is a screening exercise.** Fewer points in a polygon does not prove residents lack home broadband, devices, or skills; it identifies places where public-access infrastructure may deserve closer review.

## Source-grounded rationale

### 1) Digital Equity — NYC Office of Technology and Innovation
- **Type:** official program page
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/content/oti/pages/digital-equity
- **What it supports:** NYC formally treats digital equity as a city policy priority rather than a narrow telecom issue.
- **Why it matters for this benchmark:** It justifies a benchmark framed around neighborhood digital-access need and public digital support infrastructure.

### 2) The New York City Digital Equity Roadmap
- **Type:** official NYC report
- **Agency:** NYC Office of Technology and Innovation
- **URL:** https://www.nyc.gov/assets/oti/downloads/pdf/DE-Roadmap.pdf
- **What it supports:** The roadmap frames digital inequity in terms of affordability, device access, skills, and community-based support.
- **Why it matters for this benchmark:** It supports using public computer centers, libraries, and Wi‑Fi access points as meaningful public-facing infrastructure for digital inclusion.

### 3) City Launches ‘Neighborhood Tech Help’ to Bridge Digital Divide Across the Boroughs
- **Type:** official NYC announcement
- **Agency:** NYC Department of Housing Preservation and Development / connected city initiative
- **URL:** https://www.nyc.gov/site/hpd/news/015-25/city-launches-neighborhood-tech-help-bridge-digital-divide-across-boroughs
- **What it supports:** NYC is actively investing in neighborhood-based technical help to bridge the digital divide.
- **Why it matters for this benchmark:** It confirms that a neighborhood screening product is a realistic planning use case, not an invented scenario.

## Suggested evaluation notes

### What a strong agent should do
- Select `NYC_Wi-Fi_Hotspot_Locations`, `citywide_public_computer_centers`, `NYC_libraries`, `NYC_poverty_rate`, and `NYC_population`.
- Explain why `citywide_public_computer_centers` is especially relevant for a digital-divide case.
- Use the poverty/population polygon geography as the preferred first-pass comparison unit.
- Treat NTAs as optional reporting geography rather than the automatic join surface.
- Keep the conclusion calibrated: this is a digital-equity screening for follow-up, not a definitive measure of household connectivity.

### What a very strong agent may also mention
- Public computer centers are likely the most direct public-access infrastructure layer in the repo because they include workstation, Wi‑Fi, staffing, and training-related fields.
- Libraries are still important because they are durable civic institutions with citywide coverage and strong public legitimacy.
- Wi‑Fi hotspot counts alone can be misleading if many are concentrated in transit, parks, or commercial corridors.
- A per-capita or per-area normalization could strengthen downstream analysis, but is not required for the benchmark to be valid.

### Common failure modes
- Returning only `NYC_Wi-Fi_Hotspot_Locations`.
- Missing `citywide_public_computer_centers` entirely.
- Treating `NTA_Neighborhood_Tabulation_Areas` as the default common geography without explaining the mismatch.
- Recommending unrelated civic datasets such as schools as if they were equally strong public digital-access proxies.
- Making unsupported claims like “few hotspots means residents lack internet at home.”

## Example of a benchmark-credible answer shape

A high-quality agent response would likely say that:

- the strongest public digital-access layers in the repo are Wi‑Fi hotspots, public computer centers, and libraries;
- `NYC_poverty_rate` and `NYC_population` provide the neighborhood-need side of the comparison;
- the cleanest first pass is to count those point assets into the poverty/population polygons rather than forcing the analysis into NTAs;
- areas with higher poverty, larger populations, and relatively thinner public digital-access infrastructure should be flagged for follow-up by digital-equity staff;
- the output is a planning screen, not a direct measurement of household broadband adoption.

## Retrieval / provenance notes

- This case was revised against the actual repo inventory in `data/metadata/`, especially:
  - `data/metadata/NYC_Wi-Fi_Hotspot_Locations.json`
  - `data/metadata/citywide_public_computer_centers.json`
  - `data/metadata/NYC_libraries.json`
  - `data/metadata/NYC_poverty_rate.json`
  - `data/metadata/NYC_population.json`
  - `data/metadata/NTA_Neighborhood_Tabulation_Areas.json`
- The benchmark was also checked against the current agent/tool behavior in:
  - `backend/llm_agent.py`
  - `backend/tool.py`
- The main benchmark upgrade in this revision is replacing an overly narrow Wi‑Fi-plus-library framing with a broader and more repo-faithful public digital-access infrastructure framing that includes `citywide_public_computer_centers`.
- No backend changes were required for this case; the benchmark remains focused on evaluating dataset choice and reasoning quality under the current suggestion-oriented copilot design.

## Single-case next step if more rigor is wanted

If this case gets one more pass later, the best upgrade would be adding one stronger official source specifically about public access computing or library-based digital inclusion in NYC. The case is already benchmark-usable now because the Digital Equity program materials and Neighborhood Tech Help announcement are sufficient to justify the planning scenario, and the repo metadata clearly supports the dataset and geography corrections.
