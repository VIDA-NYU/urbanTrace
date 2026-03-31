# Case 2 — Bike safety and infrastructure mismatch

**Status:** revised  
**Case ID:** 2  
**Theme:** mobility / safety  
**Language:** English  
**Reviewed on:** 2026-03-22

## Task

> NYC DOT describes a citywide goal of accelerating safe cycling through a connected bicycle network, especially in places where cycling demand is already strong, while tracking bike counts and bicycle crash outcomes as separate signals of network performance. Using UrbanTrace, identify which NYC neighborhoods look like plausible candidates for bike-network improvement because they combine **relatively strong observed bicycle activity**, **weaker or less protective bike-route coverage**, and **continued cyclist crash burden**. Select the datasets needed for that comparison, choose a common geography, and explain which neighborhoods would merit closer review for protected-lane expansion, route upgrades, or related safety interventions. Keep the analysis grounded in what the available datasets can actually support.

## Why this benchmark matters

This case is credible because the local catalog contains a realistic three-part planning stack:

- **observed cycling activity** from `NYC_bicycle_counts` point counters;
- **network supply and facility type** from `NYC_Bike_Routes`; and
- **safety outcomes** from `NYC_vehicle_collisions_crashes`, including cyclist injury/killed fields.

It also fits the current UrbanTrace agent architecture. `backend/llm_agent.py` builds answers from dataset descriptions, metadata, and dashboard context, while `backend/tool.py` only supports dataset-suggestion behavior. So benchmark quality here depends on whether the agent can pick the right datasets, avoid seductive but wrong substitutes, and articulate a defensible harmonization strategy.

## Recommended benchmark framing

A strong answer should:

1. identify the primary datasets listed below;
2. use **NTA** as the comparison geography, since counts and crashes are points while bike routes are lines;
3. explain that bike counters are **sampled monitoring locations**, not full neighborhood demand coverage;
4. distinguish route **presence** from route **quality/protection** using available bike-route attributes; and
5. produce a cautious shortlist of neighborhoods for follow-up rather than overclaiming causal proof.

### Expected core datasets
- `NYC_bicycle_counts`
- `NYC_Bike_Routes`
- `NYC_vehicle_collisions_crashes`
- `NTA_Neighborhood_Tabulation_Areas`

### Why each core dataset is expected
- `NYC_bicycle_counts`: provides observed cyclist volumes at monitored locations (`counts`, `date`, `name`).
- `NYC_Bike_Routes`: provides route geometry plus facility fields such as `facilitycl`, `allclasses`, `ft_facilit`, and `tf_facilit`, which let the agent distinguish protected vs conventional/shared facilities instead of treating all lanes as equivalent.
- `NYC_vehicle_collisions_crashes`: provides cyclist-specific safety signals through `NUMBER OF CYCLIST INJURED` and `NUMBER OF CYCLIST KILLED`.
- `NTA_Neighborhood_Tabulation_Areas`: provides the polygon geography needed to summarize point and line layers into neighborhood-scale comparisons.

### Likely distractors
- `NYC_pedestrian_counts`
- `NYC_automated_traffic_volume_counts`

### Why those are distractors
- `NYC_pedestrian_counts` measures a different travel mode and does not solve the cycling-demand problem.
- `NYC_automated_traffic_volume_counts` can sometimes help with corridor context, but it is not a substitute for bike activity, bike facility quality, or cyclist crash burden, so it should be optional at most.

## Selected supporting references

### 1) NYC DOT — Bike Network and Ridership
- **Type:** official NYC DOT program page
- **URL:** https://www.nyc.gov/html/dot/html/bicyclists/bikestats.shtml
- **Why relevant:** This page explicitly presents bike network growth, ridership trends, bike counts, and bicycle crash data as related components of cycling policy. It is the clearest source-level justification for a benchmark that asks the agent to synthesize demand, infrastructure, and safety instead of using only one of them.
- **Confidence:** high

### 2) Safe Streets for Cycling
- **Type:** official NYC DOT report
- **URL:** https://www.nyc.gov/html/dot/downloads/pdf/safe-streets-for-cycling.pdf
- **Why relevant:** This report grounds the policy motivation for safer cycling investments and network expansion. It supports a benchmark that looks for places where safety interventions and route upgrades may still be needed.
- **Confidence:** medium-high

### 3) A Plan for Cycling in New York City
- **Type:** official NYC DOT report
- **URL:** https://www.nyc.gov/html/dot/downloads/pdf/bike-safety-plan.pdf
- **Why relevant:** This planning document supports the benchmark’s emphasis on city-led network planning, route expansion, and safety-oriented cycling investment rather than generic recreation or commuting analysis.
- **Confidence:** medium-high

## Data access points for reproducibility

- Local benchmark-relevant datasets are documented in `data/descriptions.csv` and corresponding files under `data/metadata/`.
- Relevant repo files for agent behavior: `backend/llm_agent.py`, `backend/tool.py`.
- The benchmark is specifically aligned to the current metadata affordances:
  - `NYC_bicycle_counts` is a **point** dataset with repeated dated observations at a limited set of counters.
  - `NYC_Bike_Routes` is a **line** dataset with facility/protection attributes.
  - `NYC_vehicle_collisions_crashes` is a **point** dataset with cyclist injury/fatality columns.
  - `NTA_Neighborhood_Tabulation_Areas` is the natural polygon layer for neighborhood summarization.

## Suggested evaluation notes

### What a strong agent should do
- Select the four core datasets above.
- Explicitly say that the three operational layers require geographic harmonization and choose NTAs for that step.
- Treat bike counts as a **proxy for observed cycling activity at instrumented locations**, not a citywide census of all bike trips.
- Use bike-route facility attributes to reason about **protection/quality**, not only total route presence.
- Use cyclist-specific crash fields rather than all-person or all-vehicle crash counts if discussing bike safety.
- Return a measured neighborhood shortlist with caveats, not a false-precision ranking.

### Common failure modes
- Selecting only `NYC_Bike_Routes` and `NYC_vehicle_collisions_crashes` while ignoring observed bike activity.
- Treating bike counters as if they fully represent neighborhood ridership everywhere in NYC.
- Treating every bike route segment as equivalent, ignoring protected vs conventional/shared facility fields.
- Using general traffic or pedestrian datasets in place of cyclist-specific evidence.
- Making unsupported causal claims such as “lack of lanes caused crashes” from this benchmark alone.

## Retrieval / provenance notes

- This revision tightens the case around the actual local dataset affordances so it is more reliable for evaluating agent behavior under the current `backend/llm_agent.py` + `backend/tool.py` workflow.
- The benchmark intentionally asks for **plausible candidates for follow-up** rather than definitive engineering prescriptions, because the available counts are sparse counters and route quality is only partially captured through metadata fields.