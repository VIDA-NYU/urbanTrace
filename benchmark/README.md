# UrbanTrace Benchmark

This directory contains the dataset-discovery benchmark used to evaluate the UrbanTrace agent over 28 benchmark cases.

## What Is Here

- `urbantrace_agent_benchmark.json`: machine-readable benchmark definition consumed by the runner.
- `cases/`: per-case markdown files with task framing, dataset rationale, and supporting references.
- `scripts/run_dataset_discovery_benchmark.py`: benchmark runner.
- `results/`: CSV outputs and rendered figures.

## Prerequisites

Run the benchmark from the repository root.

Install the backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Set your model credentials in `backend/.env` or `.env`. The runner loads `backend/.env` first and falls back to `.env`.

Relevant environment variables:

- `LLM_PROVIDER`: `portkey` or `openai`
- `PORTKEY_API_KEY`
- `PORTKEY_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

The runner can also override the model at runtime with `--llm-model`.

## Run All 28 Cases

The benchmark JSON currently contains 28 cases, so the default command runs all 28 once at the `full` ablation:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py
```

This appends rows to:

```text
benchmark/results/dataset_discovery_results.csv
```

If you want a clean output file for a new run, use a different `--output` path or remove the old CSV first.

## Common Commands

Run all 28 cases across all ablations:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py --ablation all
```

Run all 28 cases with repeated trials per case:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py --ablation all --runs 3
```

Run from a specific case onward:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py --start-from 15
```

Run only the first 5 cases:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py --max-cases 5
```

Run with an explicit model override:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py --llm-model @vertexai/gemini-3-pro
```

Write results to a separate CSV:

```bash
python3 benchmark/scripts/run_dataset_discovery_benchmark.py \
  --ablation all \
  --runs 3 \
  --output benchmark/results/dataset_discovery_results_gemini.csv
```

## Runner Behavior

The runner:

1. loads the benchmark cases from `benchmark/urbantrace_agent_benchmark.json`;
2. loads the local dataset catalog from `data/geojson_raw/` and `data/metadata_raw/`;
3. loads dataset descriptions from `data/descriptions_raw.csv` when present, otherwise from the copilot defaults;
4. builds an ablation-specific dataset-context prompt;
5. runs the UrbanTrace copilot once or multiple times per case;
6. extracts predicted dataset IDs from the copilot suggestions;
7. scores precision, recall, and F1 against the gold relevant datasets;
8. appends one CSV row per run; and
9. prints macro-average F1 by ablation at the end.

Supported ablations:

- `full`: description + profile metadata
- `no_description`: profile metadata without description text
- `no_profile`: description text without profile metadata
- `name_only`: dataset IDs only
- `all`: run all four ablations in one pass

## Output Schema

The CSV written by the runner contains:

- `llm_model`
- `ablation`
- `case_id`
- `slug`
- `run`
- `expected_datasets`
- `predicted_datasets`
- `predicted_distractors`
- `precision`
- `recall`
- `f1`
- `assistant_message`

## Benchmark Case Structure

Each case has two synchronized representations:

### 1. JSON case entry

Each object in `urbantrace_agent_benchmark.json` includes:

- `id`: numeric case ID
- `slug`: stable machine-friendly case name
- `file`: source markdown file under `benchmark/cases/`
- `title`
- `theme`
- `status`
- `query`: the prompt sent to the agent
- `expected_relevant_datasets`: gold datasets used for scoring recall/precision/F1
- `possible_distractors`: plausible but non-core datasets
- `why_relevant`
- `source_hint`
- `supporting_references`: structured references extracted from the case markdown when available, otherwise derived from `source_hint`
- `notes`
- `index_status`

For execution, the runner primarily depends on:

- `id`
- `slug`
- `query`
- `expected_relevant_datasets`
- `possible_distractors`

The other fields are benchmark documentation and provenance.

### 2. Markdown case file

Each file in `benchmark/cases/` is the human-readable source of truth for benchmark framing. In practice, the case files usually contain:

- case metadata (`Status`, `Case ID`, `Theme`, `Reviewed on`)
- the benchmark task
- why the benchmark matters
- source-grounded rationale or planning rationale
- recommended benchmark framing
- expected UrbanTrace dataset mapping
- selected supporting references when structured references are available
- reproducibility or evaluation notes

The markdown files are where benchmark rationale and supporting references are maintained. The JSON file is the runner-facing benchmark manifest.

## Notes On Supporting References

`supporting_references` is now stored directly in `urbantrace_agent_benchmark.json`.

- When a case markdown file contains a structured reference section such as `## Selected supporting references` or a structured `## Source-grounded rationale`, the JSON stores those references as structured objects.
- When a case does not yet have a structured reference block, the JSON falls back to a title list derived from `source_hint`.

This keeps the benchmark manifest aligned with the evidence stored under `benchmark/cases/` without forcing every case into the exact same markdown format immediately.
