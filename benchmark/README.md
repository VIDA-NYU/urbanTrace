# UrbanTrace Benchmark

## Quantitative Ablation: Dataset Discovery Performance

Dataset discovery is the first and most open-ended step in UrbanTrace. This benchmark evaluates whether the discovery agent can recover the datasets needed for a realistic urban analysis goal, and whether retrieval quality comes from structured metadata, dataset-level descriptions, or from dataset names alone.

The benchmark is designed as a controlled ablation over the dataset context shown to the agent at inference time. The central question is whether richer metadata grounding helps the agent map a high-level planning or policy objective to the right local data layers.

The earlier `No profile` setting did not provide a clean test of removing the profiler, because AutoDDG-generated descriptions can already contain information derived from dataset profiles. We therefore add a **Source description only** condition that uses the original NYC OpenData page descriptions — authored without profiles — so the benefit of profiling can be assessed directly. The runner keeps AutoDDG/profile-derived descriptions and source catalog descriptions as separate evidence channels: the `Source description only` condition reads from a dedicated CSV of source-authored descriptions and includes no explicit profile fields such as geometry type, column types, semantic labels, value ranges, or column counts.

## Benchmark Tasks and Data Lake Scope

The benchmark contains **28 real-world urban research scenarios** built over a curated NYC OpenData lake of **112 profiled geospatial datasets**. Each case consists of:

- a natural-language prompt describing a realistic urban research or planning goal;
- a manually validated gold set of core relevant datasets, typically **3 to 5** per case;
- supporting references that ground the task in real policy, planning, or public-service contexts.

The prompts describe the analytical objective without explicitly naming the correct datasets, so the benchmark measures **semantic dataset discovery** rather than keyword matching.

> Repository note: the paper-facing benchmark refers to **112 profiled datasets**. In the current checkout, [`data/geojson_raw/`](../data/geojson_raw/) contains one additional raw GeoJSON asset without a matching metadata profile in [`data/metadata_raw/`](../data/metadata_raw/), so the ablation setup should be interpreted against the 112 profiled datasets.

## Task Construction and Annotation

The benchmark was constructed with an **LLM-assisted, human-validated** workflow. Candidate research scenarios were first proposed from trusted public sources such as NYC government materials, NYC OpenData, agency reporting, and related policy documents. Those candidates were then manually curated, rewritten for realism and ambiguity, and validated against the datasets actually available in the UrbanTrace repository.

This process was intended to preserve realistic discovery conditions: the agent must connect a high-level analysis goal to the appropriate local datasets, common geography, and analytical framing, while avoiding trivial name-based retrieval.

Detailed task rationales, gold mappings, and references are maintained in [`benchmark/cases/`](./cases/). The runner-facing manifest lives in [`benchmark/urbantrace_agent_benchmark.json`](./urbantrace_agent_benchmark.json).

## Ablation Conditions

For each benchmark task, the discovery agent receives the task prompt together with an ablation-specific view of the local dataset catalog and returns a set of recommended dataset identifiers. We evaluate **five conditions**. Dataset names are included in every condition because the benchmark requires a reference handle for the agent to identify and return candidate datasets.

| Condition | Runner id | Context shown to the agent |
| --- | --- | --- |
| **Name only** | `name_only` | Dataset names only |
| **Source description only** | `no_profile` | Names plus original NYC OpenData source descriptions, with blanks where no source description exists |
| **Profile only** | `no_description` | Names plus explicit profile metadata (geometry type, column types, semantic labels, value ranges, column counts), without descriptions |
| **AutoDDG description only** | `profiled_description` | Names plus AutoDDG descriptions derived from profiles, with no explicit profile metadata at inference time |
| **Full** | `full` | Names, AutoDDG profile-derived descriptions, and explicit profile metadata (no original source description) |

This comparison isolates the contribution of lexical names, source-authored descriptions, structured profiles, and profile-derived semantic descriptions to urban dataset discovery. **Source description only** provides a clean test of removing the profiler: the original NYC OpenData descriptions are authored without profiles, so contrasting them with **AutoDDG description only** (profile-derived) directly measures the profiler's contribution. The comparison between **AutoDDG description only** and **Full** estimates the additional value of also providing profiles explicitly.

## Evaluation Protocol

The paper evaluates the discovery agent with two model backbones:

- **Gemini 3 Pro** (`@vertexai/gemini-3-pro`)
- **GPT-5 mini** (`@gpt-5-mini/gpt-5-mini`)

For each combination of task, model, and ablation condition, the benchmark runs the discovery process **5 times** to account for stochastic variance in LLM outputs.

Predictions are scored against the manually validated gold dataset set using **precision**, **recall**, and **F1** over set overlap. Raw accuracy is not emphasized because the discovery problem is highly imbalanced: most datasets in the lake are irrelevant to any one task, so true negatives would dominate the metric.

## Main Results

Both **Full** and **AutoDDG description only** achieve strong retrieval performance across models. The largest gains come from profile-derived AutoDDG descriptions: contrasting the source-authored descriptions with AutoDDG descriptions isolates the profiler's contribution.

- **Gemini 3 Pro**: F1 rises from `0.426` (**Source description only**) to `0.654` (**AutoDDG description only**)
- **GPT-5 mini**: F1 rises from `0.403` to `0.651`

This shows that the profiler contributes substantial value when its structured profiles are used by AutoDDG to generate richer dataset descriptions. Explicit profiles alone (**Profile only**) also improve substantially over **Name only**, but do not match the performance of profile-derived natural-language descriptions. Adding explicit profiles on top of AutoDDG descriptions (**Full**) does not consistently improve over **AutoDDG description only**, suggesting partial redundancy between the generated descriptions and the structured profile metadata. At the other extreme, **Name only** performs near zero across all metrics, confirming that dataset names alone provide almost no useful signal for realistic urban data discovery.

![Dataset discovery ablation barplots](./results/ablation1_results.png)

The result barplots are stored under [`benchmark/results/`](./results/). The checked-in figure at [`benchmark/results/ablation1_results.png`](./results/ablation1_results.png) is regenerated from the result CSVs by [`benchmark/scripts/visualize_results.ipynb`](./scripts/visualize_results.ipynb) across the five conditions above.


## Reproducing the Benchmark

Run all commands from the repository root.

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

The runner loads `backend/.env` first and then `.env`. Configure the backend model provider as needed, including `LLM_PROVIDER` and the matching credential/model variables for either Portkey or OpenAI.

Before running the **Source description only** condition (`no_profile`), create the source-description file, by default:

```text
data/descriptions_profile_free.csv
```

It should contain `dataset`, `description`, and `dataset_raw` columns. Descriptions should be copied from the original NYC OpenData page metadata where available. For source pages whose metadata has no accessible description, the scraper can use conservative OSCUR Hugging Face dataset-card fallbacks; rows without a clear fallback keep `description` empty.

The repository includes a scraper for this file. It reads raw Socrata IDs from `data/geojson_raw`, fetches `https://data.cityofnewyork.us/api/views/{dataset_raw_id}.json`, copies only the API `description` field, and fills selected blanks from `https://huggingface.co/oscur/datasets` when there is a clear matching OSCUR dataset. It then writes the CSV expected by the benchmark:

```bash
python3 benchmark/scripts/scrape_nyc_opendata_descriptions.py \
  --geojson-dir data/geojson_raw \
  --output data/descriptions_profile_free.csv
```

HTTP 403/404 responses and missing `description` fields are written as blank descriptions.
Use `--no-hf-fallback` to keep strictly to NYC OpenData metadata and leave all missing source descriptions blank.

To reproduce the revised ablation, run all canonical conditions with five repeated trials per case and write to a fresh output path:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py \
  --ablation all \
  --runs 5 \
  --llm-model @vertexai/gemini-3-pro \
  --output benchmark/results/dataset_discovery_results_gemini.csv
```

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py \
  --ablation all \
  --runs 5 \
  --llm-model @gpt-5-mini/gpt-5-mini \
  --output benchmark/results/dataset_discovery_results_gpt5mini.csv
```

The runner appends to the target CSV, so use a new `--output` path for clean benchmark runs. Each row records the case, ablation, run index, predicted dataset IDs, and the resulting precision/recall/F1 scores.

For smaller debugging runs, the runner also supports `--max-cases`, `--start-from`, and single-ablation execution via `--ablation`. Each condition accepts a paper-aligned alias in addition to its runner id: `name_only`, `source_description_only` (= `no_profile`, also `no_profiler`), `profile_only` (= `no_description`), `autoddg_description_only` (= `profiled_description`), and `full`.

## Benchmark Assets

- [`benchmark/urbantrace_agent_benchmark.json`](./urbantrace_agent_benchmark.json): machine-readable benchmark manifest consumed by the runner
- [`benchmark/cases/`](./cases/): per-case benchmark writeups, gold mappings, and supporting references
- [`benchmark/scripts/run_dataset_discovery_benchmark.py`](./scripts/run_dataset_discovery_benchmark.py): discovery benchmark runner
- [`benchmark/scripts/visualize_results.ipynb`](./scripts/visualize_results.ipynb): notebook for aggregating and plotting result CSVs
- [`benchmark/results/`](./results/): saved benchmark outputs and rendered figures



## Quantitative Ablation: Spatial Operator Selection

The notebook [`benchmark/scripts/operator_selection/quantitative_ablation-operator_selection_accuracy.ipynb`](./scripts/operator_selection/quantitative_ablation-operator_selection_accuracy.ipynb) implements the quantitative ablation study described in Section 4.2, evaluating the UrbanTrace Copilot's automated spatial operator selection against four baselines across 100 real-world NYC spatial integration scenarios.

## Pipeline Summary

### Data & Artifacts Location
All input and generated files (e.g., `dataset_metadata_map.json`) are stored in:
[`input_output_operator_selection/`](./scripts/operator_selection/input_output_operator_selection/).

**1. Build Dataset Registry** (`dataset_metadata_map.json`)
Scans all GeoJSON datasets and their metadata to extract geometry types and semantically
meaningful numeric columns, filtering out identifiers and boundary datasets.

**2. Inspect Registry Statistics**
Summarizes the corpus: dataset count, geometry type distribution, and target column counts.

**3. LLM-Assisted Ground Truth Annotation** (`ground_truth_llm_annotation.json`)
Uses GPT-4o-Mini via Portkey to classify each column by semantic class (`C_ext`, `C_int`,
`C_ord`) and assign a default aggregation operator — producing a preliminary annotation
for expert review. 

**4. Generate Evaluation Scenarios** (`scenarios_from_benchmark.json`)
Randomly pairs source dataset columns (from the human-curated ground truth (`ground_truth_curated.json`)) with target
boundary datasets to produce 100 distinct spatial mapping scenarios.

**5. Run Master Benchmark** (`benchmark_results_operator_selection.json`)
Evaluates all 5 conditions — Rule-Based, GPT-4o-Mini, Claude Sonnet, Claude Opus, and the
UrbanTrace Copilot — on every scenario, measuring **Geometric Validity** (correct mapping
operator) and **Semantic Validity** (correct aggregation operator). Results are compiled into
the accuracy table reported in the paper.