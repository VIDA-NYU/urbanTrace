# Case 10 — High-poverty neighborhoods and public digital-access support

**Status:** revised  
**Case ID:** 10  
**Theme:** digital equity / public access / neighborhood need  
**Language:** English  
**Reviewed on:** 2026-03-27

## Task

> You are helping an urban policy or digital-equity team identify NYC sub-borough areas where **poverty appears comparatively high while visible public digital-access support may be comparatively thin**. The benchmark should stay grounded in the actual UrbanTrace catalog and current copilot behavior. A strong answer should select the right neighborhood poverty layer, add population so amenity counts can be interpreted fairly, choose the cleanest first-pass geography already supported in the repo, and distinguish public digital-access infrastructure from broader or weaker amenity proxies. The result should be framed as a screening tool for follow-up, not proof that any neighborhood is definitively underserved.

## Why this benchmark matters

This is a benchmark for **dataset selection + geography alignment + calibrated digital-equity reasoning**.

A weak agent may:
1. stop at a socioeconomic layer without adding a concrete public-access layer;
2. select digital-access points but ignore population normalization;
3. switch to a different geography just because point datasets expose extra administrative fields; or
4. treat point counts as proof of service adequacy.

A stronger agent should recognize that the cleanest first-pass comparison in this repo is:
- a **sub-borough-area poverty layer**,
- a **matching sub-borough-area population layer**, and
- a **public digital-access infrastructure layer** summarized into those polygons.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Need-side layer:**  
   `NYC_poverty_rate`

2. **Scale / normalization layer:**  
   `NYC_population`

3. **Public digital-access layer:**  
   `citywide_public_computer_centers`

4. **Planning geography:**  
   Sub-Borough Area

5. **Interpretation rule:**  
   flag sub-borough areas where poverty is comparatively high while public digital-access support appears comparatively thin relative to population, then use those areas to guide deeper digital-equity, library, or public-access follow-up.

## Expected core datasets
- `NYC_poverty_rate`
- `NYC_population`
- `citywide_public_computer_centers`

## Acceptable optional support
- `NYC_Wi-Fi_Hotspot_Locations`

## Likely distractors
- `NYC_income_diversity_ratio`
- `NYC_median_household_income`
- `NTA_Neighborhood_Tabulation_Areas`
- `NYC_libraries`

## Suggested evaluation notes

### What a strong agent should do
- Select all three core datasets.
- Explain why poverty is the need-side layer for this task.
- Explain why population is needed for fair comparison.
- Use sub-borough area as the default comparison geography.
- Keep the output framed as a screening product rather than a definitive adequacy finding.

### Common failure modes
- Returning only poverty.
- Replacing poverty with income diversity or median income.
- Ignoring population normalization.
- Treating Wi-Fi or amenity counts as direct proof of service quality.
- Defaulting to NTA without explaining why.

## Why this redesign is better

This version is more machine-checkable and much less ambiguous than the earlier income-diversity case. It uses a directly retrievable social-need indicator, a necessary normalization layer, and a specific public digital-access infrastructure dataset. That makes the benchmark challenging but realistically solvable under current UrbanTrace copilot behavior.