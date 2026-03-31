# Case 28 — Academic recovery vs neighborhood conditions after 2022

**Status:** drafted  
**Case ID:** 28  
**Theme:** education recovery / safety / youth  
**Language:** English  
**Reviewed on:** 2026-03-25

## Task

> Which NYC community districts should be screened as higher-priority candidates for cross-sector follow-up where post-2022 academic recovery appears comparatively weak while neighborhood crime burden remains comparatively high? Use the available UrbanTrace datalake to identify the datasets needed for a community-district screen, choose the planning geography that is most defensible for this repo, and explain how the resulting screen should guide later school-support, youth-service, trauma-informed, or place-based safety follow-up.

## Why this benchmark matters

This is a benchmark for **dataset selection + recovery-period reasoning + aligned neighborhood screening**, not just for naming an education table or a crime table.

A weak agent will stop at a single subject table, ignore the post-pandemic assessment gap, or reach for raw incident points. A stronger agent should recognize that:

1. ELA and math together are the main academic recovery signals;
2. neighborhood crime burden is a relevant contextual layer for screening;
3. the cleanest first-pass comparison in this repo is at **community-district** scale because the strongest candidate tables already align there; and
4. the output is a **prioritization layer**, not a causal claim about why recovery differs.

That behavior matches the current UrbanTrace benchmark logic well: the agent is being tested on whether it can retrieve the right local tables, reject weaker substitutes, and articulate a plausible cross-agency planning workflow.

## Source-grounded planning rationale

This benchmark is grounded in both real NYC policy framing and NYC-specific research.

NYC Public Schools has publicly framed the 2022–2025 period as one of system recovery and instructional transition, especially through citywide literacy and math initiatives such as **NYC Reads** and **NYC Solves**. The City’s 2024 and 2025 test-score releases discuss post-pandemic improvement, uneven subject-specific recovery, and the need to interpret year-to-year performance carefully.

At the same time, NYC’s **Community Violence Prevention Framework** and the **Office of Neighborhood Safety (ONS)** treat violence as a place-based public-health issue that affects the conditions in which people live, grow, and learn. ONS explicitly targets high-need geographies with youth, family, crisis-response, and place-based interventions.

On the research side, NYC-based studies have found that neighborhood violent crime exposure and heavy neighborhood policing can be associated with lower educational outcomes, including ELA and math performance. That does **not** mean this benchmark should claim causality. It does mean the benchmark is realistic: a planner could reasonably ask where academic recovery still looks weak in neighborhoods that also continue to experience elevated crime burden.

Finally, NYSED’s own documentation makes the recovery framing necessary. Spring 2020 Grades 3–8 assessments were suspended due to COVID-19, and 2021 participation was so low that NYSED said those results were not representative and should not be compared with prior years. That means a careful benchmark should focus the recovery window on **2022–2024** rather than pretending 2019–2024 is a continuous comparable series.

## Recommended benchmark framing

A strong answer should identify the following core workflow:

1. **Academic recovery signals:**  
   `NYC_students_performing_english_language_arts`  
   `NYC_students_performing_math`

2. **Neighborhood crime context:**  
   `NYC_crime_rate_per_1000_residents`  
   `NYC_crime_rate_property`

3. **Planning geography:**  
   community districts, using the shared `BoroCD` / `Community District` fields already present in the core tables

4. **Interpretation rule:**  
   flag community districts where post-2022 academic recovery appears comparatively weak while neighborhood crime burden remains comparatively elevated, then use those districts to motivate deeper school-, corridor-, precinct-, youth-program, or trauma-support review.

A good gold-standard answer does **not** need to build a causal model. It does need to show the right analytical logic:

- combine both ELA and math rather than choose one alone;
- use a post-2022 recovery window rather than a naive long-run trend;
- prefer normalized neighborhood crime rates over raw incident points;
- use the shared community-district geography; and
- keep the result framed as a screening and prioritization tool.

## Expected UrbanTrace dataset mapping

### Core datasets

1. **`NYC_students_performing_english_language_arts`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: direct academic recovery outcome
   - Relevant local columns confirmed in metadata:
     - `BoroCD`
     - `Community District`
     - `2013`–`2019`
     - `2022`
     - `2023`
     - `2024`
   - Best benchmark interpretation: recent ELA recovery signal, not a continuous pandemic-era time series

2. **`NYC_students_performing_math`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: second academic recovery outcome that should be interpreted jointly with ELA
   - Relevant local columns confirmed in metadata:
     - `BoroCD`
     - `Community District`
     - `2013`–`2019`
     - `2022`
     - `2023`
     - `2024`
   - Best benchmark interpretation: paired academic recovery signal, not a substitute for ELA

3. **`NYC_crime_rate_per_1000_residents`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: normalized overall neighborhood crime-burden context
   - Relevant local columns confirmed in metadata:
     - `BoroCD`
     - `Community District`
     - `2006`–`2024`
   - Best benchmark interpretation: first-pass neighborhood crime context for cross-district screening

4. **`NYC_crime_rate_property`**
   - Geometry in local metadata: `MultiPolygon`
   - Why it matters: secondary crime lens for a more stable multi-signal safety context
   - Relevant local columns confirmed in metadata:
     - `BoroCD`
     - `Community District`
     - `2006`–`2024`
   - Best benchmark interpretation: companion crime-rate signal rather than a standalone substitute

### Acceptable secondary context, but not substitutes

- `Community_Districs`
  - Acceptable as a canonical boundary reference if an agent wants an explicit boundary layer, but not required because the four core tables already carry aligned community-district geometry and keys.
- `NYC_poverty_rate`
  - Plausible context for a broader deprivation case, but weaker than the direct crime-context tables for this recovery-plus-safety benchmark.
- `NYC_unemployment_rate`
  - Also plausible context, but not the strongest neighborhood-condition signal for this specific framing.

### Plausible distractors that should usually lose to the core set

- `nypd_complaint_data_current_year_to_date`
  - Too raw and incident-level for this benchmark; requires aggregation, denominator construction, and temporal reconciliation.
- `2017_2018_schools_nypd_crime_data_report`
  - School-building-specific and temporally narrow; changes the construct from neighborhood conditions to school-site incidents.
- `2020_doe_high_school_directory`
  - High-school-specific and school-level, not a community-district recovery panel.
- `NTA_Neighborhood_Tabulation_Areas`
  - A plausible geography in general, but weaker here because the strongest core tables already align on community districts.
- `MODZCTA`
  - A plausible geography in general, but not the best match for these particular outcome and crime tables.

## Temporal harmonization notes

A very strong answer should explicitly acknowledge the recovery-period caveats:

- **2020:** spring Grades 3–8 state assessments were suspended.
- **2021:** participation was unusually low and NYSED said results were not representative and should not be compared with prior years.
- **2022–2024:** best first-pass “recovery” window for this benchmark.

For that reason, the benchmark should reward answers that compare **2022 to 2024** or use a **2022–2024 recent-period screen**, rather than treating 2019–2024 as a clean continuous trend.

## Suggested evaluation notes

### What a strong agent should do
- Select the four core datasets above.
- Explain why both ELA and math should be considered together.
- Use community districts via `BoroCD` / `Community District`.
- Prefer normalized crime-rate tables over raw incident points.
- Explicitly mention the 2020 suspension / 2021 comparability caveat.
- Keep the interpretation framed as screening first, then deeper follow-up.

### What a very strong agent may also mention
- Because post-pandemic and standards-related comparability can be messy, percentile-based or rank-based recovery screens may be more robust than naive raw-difference comparisons.
- `Community_Districs` can be used as a QA boundary layer, but it is not required if the aligned derived tables are trusted.
- A 3-year crime average across 2022–2024 may be more stable than a single-year snapshot.

### Common failure modes
- Returning only one education table.
- Ignoring the 2020 / 2021 assessment caveats.
- Recommending raw NYPD complaint points instead of aligned rate tables.
- Reframing the task as school-level crime analysis.
- Treating the result as proof of causation rather than a prioritization screen.

## Selected supporting references

### 1) NYC Public Schools Releases Grades 3–8 State Test Score Data for 2023–24 School Year
- **Type:** official NYC education release
- **Agency:** New York City Public Schools
- **URL:** https://www.schools.nyc.gov/home/2024/08/21/new-york-city-public-schools-releases-grades-3-8-state-test-score-data-for-2023-24-school-year
- **Why relevant:** anchors the post-2022 recovery period and shows the city is actively interpreting recent ELA and math performance trends.
- **Confidence:** high

### 2) Mayor Adams, Chancellor Aviles-Ramos Celebrate Grades 3–8 State Test Score Data Showing Increased Proficiency for 2024–25 School Year
- **Type:** official NYC education release
- **Agency:** New York City Public Schools
- **URL:** https://www.schools.nyc.gov/home/2025/08/11/mayor-adams-chancellor-aviles-ramos-celebrate-grades-3-8-state-test-score-data-showing-increased-proficiency-for-2024-2025-school-year
- **Why relevant:** shows that NYC continues to treat this period as one of system recovery and instructional investment.
- **Confidence:** high

### 3) Community Violence Prevention Framework
- **Type:** official NYC public health framework
- **Agency:** NYC Department of Health and Mental Hygiene
- **URL:** https://www.nyc.gov/assets/doh/downloads/pdf/vio/community-violence-prevention-framework.pdf
- **Why relevant:** grounds the benchmark in a place-based, public-health framing of neighborhood violence.
- **Confidence:** high

### 4) ONS Annual Report 2023
- **Type:** official NYC annual report
- **Agency:** NYC Office of Neighborhood Safety
- **URL:** https://criminaljustice.cityofnewyork.us/wp-content/uploads/2025/06/ONS-Annual-Report-2023-FINAL.pdf
- **Why relevant:** shows that NYC actually targets violence-prevention and youth/family supports geographically.
- **Confidence:** high

### 5) School Climate and the Impact of Neighborhood Crime on Test Scores
- **Type:** peer-reviewed NYC-focused research
- **Authors:** Agustina Laurito et al.
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC6545988/
- **Why relevant:** provides NYC-based evidence that neighborhood violent crime exposure is associated with lower ELA outcomes and interacts with school climate.
- **Confidence:** high

### 6) Policing and Educational Outcomes
- **Type:** NYC research / policy brief
- **Organization:** NYU Research Alliance for New York City Schools
- **URL:** https://steinhardt.nyu.edu/research-alliance/research/policing-and-educational-outcomes
- **Why relevant:** supports the broader idea that neighborhood safety and enforcement conditions can shape educational trajectories.
- **Confidence:** high

### 7) Suspension of the Spring 2020 Grades 3–8 English Language Arts Test Shipments and Computer-based Test Window Opening
- **Type:** official state assessment memo
- **Agency:** New York State Education Department
- **URL:** https://www.nysed.gov/memo/state-assessment/suspension-spring-2020-grades-3-8-english-language-arts-test-shipments-and
- **Why relevant:** justifies excluding 2020 from any continuous assessment trend.
- **Confidence:** high

### 8) State Education Department Releases Spring 2021 Grades 3–8 ELA and Math Assessment Data
- **Type:** official state assessment release
- **Agency:** New York State Education Department
- **URL:** https://www.nysed.gov/news/2023/state-education-department-releases-spring-2021-grades-3-8-ela-and-math-assessment-data
- **Why relevant:** explicitly says 2021 participation was low and results were not representative, supporting a 2022–2024 recovery window.
- **Confidence:** high

### 9) Community Districts
- **Type:** official NYC geography / boundary dataset
- **Agency:** NYC Department of City Planning
- **URL:** https://catalog.data.gov/dataset/community-districts-74cf7
- **Why relevant:** confirms the formal planning geography and explains that NYC has 59 community districts plus 12 Joint Interest Areas.
- **Confidence:** high

## Data access points for reproducibility

1. **ELA recovery**
   - Local dataset: `NYC_students_performing_english_language_arts`
   - Upstream public access point: https://catalog.data.gov/dataset/english-language-arts-ela-test-results-2013-2023

2. **Math recovery**
   - Local dataset: `NYC_students_performing_math`
   - Upstream public access point: https://catalog.data.gov/dataset/math-test-results-2013-2023

3. **Neighborhood crime-rate context**
   - Local datasets:
     - `NYC_crime_rate_per_1000_residents`
     - `NYC_crime_rate_property`
   - Underlying public data anchor: https://catalog.data.gov/dataset/nypd-complaint-data-historic
   - Important note: the exact derived construction of the community-district rate tables is local to the UrbanTrace datalake, so this is the best upstream public anchor rather than a one-to-one public table match.

## Retrieval / provenance notes

- Core local dataset viability is confirmed by the UrbanTrace datalake metadata for:
  - `NYC_students_performing_english_language_arts`
  - `NYC_students_performing_math`
  - `NYC_crime_rate_per_1000_residents`
  - `NYC_crime_rate_property`
- This case is intentionally scoped to current UrbanTrace copilot behavior: selecting the right local tables, rejecting weaker alternatives, and proposing a coherent community-district recovery screen.
- The benchmark is strongest when graded on **dataset choice + temporal reasoning + geography reasoning + calibrated interpretation**, not on producing a single “correct” district ranking.