import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_env(repo_root: Path) -> None:
    if not load_dotenv:
        return
    for p in [repo_root / "backend" / ".env", repo_root / ".env"]:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)
            break


def _load_cases(benchmark_json_path: Path) -> list[dict[str, Any]]:
    with open(benchmark_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("cases", [])


def _load_datalake(repo_root: Path) -> list[dict[str, Any]]:
    data_dir = repo_root / "data"
    geojson_dir = data_dir / "geojson_raw"
    metadata_dir = data_dir / "metadata_raw"

    nodes: list[dict[str, Any]] = []
    if not geojson_dir.exists():
        return nodes

    for file in sorted(geojson_dir.glob("*.geojson")):
        dataset_id = file.stem
        meta_path = metadata_dir / f"{dataset_id}.json"
        metadata = None
        if meta_path.exists():
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                metadata = None

        nodes.append(
            {
                "id": dataset_id,
                "type": "dataset",
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": dataset_id,
                    "name": dataset_id.replace("_", " "),
                    "filename": file.name,
                    "metadata": metadata,
                },
            }
        )
    return nodes
def _load_descriptions_raw(repo_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Load data/descriptions_raw.csv and return (descriptions_by_stem, rawid_to_stem).

    descriptions_by_stem: dataset_stem -> description
    rawid_to_stem: raw_dataset_id (no extension) -> dataset_stem
    """
    desc_path = repo_root / "data" / "descriptions_raw.csv"
    descriptions: dict[str, str] = {}
    rawmap: dict[str, str] = {}
    if not desc_path.exists():
        return descriptions, rawmap

    with desc_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id_field = (row.get("dataset_raw") or "").strip()
            if raw_id_field.endswith(".geojson"):
                raw_id_field = raw_id_field[:-len(".geojson")]
            raw_id_field = raw_id_field.strip()

            raw_dataset_field = (row.get("dataset") or "").strip()

            description = (row.get("description") or "").strip()
            if raw_id_field:
                descriptions[raw_id_field] = description
            
            # normalize stem from 'dataset' column (may include .geojson)
            stem = raw_dataset_field
            if stem.endswith(".geojson"):
                stem = stem[:-len(".geojson")]
            stem = stem.strip()

            # map raw socrata id / provider id to stem using dataset_raw column
            if raw_id_field and stem:
                rawmap[raw_id_field] = stem
            

    return descriptions, rawmap



# ── Ablation helpers ──────────────────────────────────────────────────────────

_TOKEN_LIMIT = 272_000
_OVERHEAD_TOKENS = 20_000   # reserved for system prompts, user message, tool schemas
_CHARS_PER_TOKEN = 4        # conservative approximation


def _build_context_for_ablation(
    nodes: list[dict[str, Any]],
    ablation: str,
    descriptions: dict[str, str],
) -> str:
    """
    Build the dataset catalog system-message string with ablation-controlled depth.
    Mirrors UrbanTraceCopilot._build_dataset_context but:
      - each dataset entry is capped to its fair share of the token budget
      - ablation decides which metadata fields are included

    Hierarchy (most → least information):
      full           – description + per-column schema
      no_description – per-column schema  (no text description)
      no_profile     – description  (no column schema)
      name_only      – dataset id only

    Token budget: (_TOKEN_LIMIT - _OVERHEAD_TOKENS) * _CHARS_PER_TOKEN / num_datasets
    """
    num_datasets = max(len(nodes), 1)
    max_chars_per_entry: int = (
        (_TOKEN_LIMIT - _OVERHEAD_TOKENS) * _CHARS_PER_TOKEN // num_datasets
    )

    lines = [
        "UrbanTrace dataset catalog:",
        "Use this context when answering dataset questions.",
    ]

    for node in nodes:
        data = node.get("data", {})
        dataset_id = data.get("id") or node.get("id", "")
        meta = data.get("metadata") or {}
        description = descriptions.get(dataset_id, "")

        if ablation == "name_only":
            lines.append(f"- id={dataset_id}")
            continue

        parts: list[str] = [
            f"geometry={meta.get('geometricType', 'unknown')}",
        ]

        if ablation in ("full", "no_description"):
            nb_columns = meta.get("nb_columns")
            if nb_columns is not None:
                parts.append(f"nb_columns={nb_columns}")
            columns = meta.get("columns", [])
            if columns:
                col_summaries = []
                for c in columns:
                    if not isinstance(c, dict):
                        continue
                    col_parts = [c["name"]] if c.get("name") else []
                    if c.get("structural_type"):
                        col_parts.append(f"type={c['structural_type']}")
                    sem = c.get("semantic_types")
                    if sem:
                        col_parts.append(f"semantic={sem}")
                    geo = c.get("geo_classifier")
                    if geo:
                        col_parts.append(f"geo={geo}")
                    col_summaries.append("(" + ", ".join(col_parts) + ")")
                if col_summaries:
                    parts.append(f"columns=[{'; '.join(col_summaries)}]")

        if ablation in ("full", "no_profile") and description:
            parts.append(f"description={description}")

        entry = f"- id={dataset_id}: {'; '.join(parts)}"
        if len(entry) > max_chars_per_entry:
            entry = entry[:max_chars_per_entry - 3] + "..."
        lines.append(entry)

    return "\n".join(lines)


# ── Scoring ───────────────────────────────────────────────────────────────────

def _extract_predicted_dataset_ids(
    result: dict[str, Any], rawid_to_stem: dict[str, str] | None = None
) -> list[str]:
    """
    Extract predicted dataset ids exclusively from copilot `suggestions`.
    """
    predicted: set[str] = set()
    suggestions = result.get("suggestions", [])
    if not isinstance(suggestions, list):
        return []

    for s in suggestions:
        if not isinstance(s, dict):
            continue
        dataset_id = s.get("datasetId")
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            action = s.get("action", {})
            if isinstance(action, dict):
                dataset_id = action.get("datasetId")
        if isinstance(dataset_id, str):
            # normalize and try direct stem match first
            candidate = dataset_id.strip()
            if candidate.endswith(".geojson"):
                candidate = candidate[:-len(".geojson")]
            candidate = candidate.strip()

            # If candidate looks like a raw/provider id, map to canonical stem using rawid_to_stem
            if rawid_to_stem:
                mapped = rawid_to_stem.get(candidate)
                if mapped:
                    predicted.add(mapped)
            else:
                predicted.add(candidate)

    if predicted:
        return sorted(predicted)
    return []



def _metrics(expected: set[str], predicted: set[str]) -> tuple[float, float, float]:
    tp = len(expected & predicted)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


# ── Main ──────────────────────────────────────────────────────────────────────

ABLATION_LEVELS = ["full", "no_description", "no_profile", "name_only"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        default="benchmark/urbantrace_agent_benchmark.json",
    )
    parser.add_argument(
        "--output",
        default="benchmark/results/dataset_discovery_results.csv",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model to use for the benchmark (overrides the provider-specific model env var)",
    )
    parser.add_argument(
        "--ablation",
        choices=ABLATION_LEVELS + ["all"],
        default="full",
        help=(
            "Metadata ablation level. "
            "'full'=baseline, 'no_description'=strip description text fields, "
            "'no_profile'=strip per-column stats and sample data, "
            "'name_only'=no metadata. Use 'all' to run every level in one pass."
        ),
    )
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument(
        "--start-from",
        type=int,
        default=None,
        metavar="CASE_ID",
        help="Skip all cases before this case id (inclusive start).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to run each case per ablation level (results are averaged).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    _load_env(repo_root)

    backend_dir = repo_root / "backend"
    sys.path.insert(0, str(backend_dir))
    from llm_agent import UrbanTraceCopilot  # type: ignore
    from tool import COPILOT_FRONTEND_TOOLS  # type: ignore

    benchmark_path = (repo_root / args.benchmark).resolve()
    out_path = (repo_root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cases = _load_cases(benchmark_path)
    if args.start_from is not None:
        case_ids = [c.get("id") for c in cases]
        if args.start_from not in case_ids:
            print(f"WARNING: case id {args.start_from} not found; running all cases.")
        else:
            idx = case_ids.index(args.start_from)
            cases = cases[idx:]
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    base_nodes = _load_datalake(repo_root)

    levels_to_run = ABLATION_LEVELS if args.ablation == "all" else [args.ablation]
    copilot = UrbanTraceCopilot(llm_model=args.llm_model)
    # Prefer descriptions_raw.csv if available (map raw ids -> stems)
    descriptions_raw, rawid_to_stem = _load_descriptions_raw(repo_root)
    if descriptions_raw:
        descriptions = descriptions_raw
        # also update copilot cache so downstream code that inspects it sees the same descriptions
        copilot.dataset_descriptions = descriptions_raw
    else:
        descriptions = copilot.dataset_descriptions

    fieldnames = [
        "llm_model", "ablation", "case_id", "slug", "run",
        "expected_datasets", "predicted_datasets", "predicted_distractors",
        "precision", "recall", "f1",
        "assistant_message",
    ]
    write_header = not out_path.exists()
    csv_file = open(out_path, "a", encoding="utf-8", newline="")  # noqa: SIM115
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()
        csv_file.flush()
    rows_for_summary: list[dict[str, Any]] = []

    for ablation in levels_to_run:
        # Inject the ablated catalog into the system message; dashboard stays empty.
        copilot.dataset_context = _build_context_for_ablation(base_nodes, ablation, descriptions)
        print(f"\n=== Ablation: {ablation} ===")

        for case in cases:
            case_id = case.get("id")
            slug = case.get("slug", "")
            query = case.get("query", "")
            expected = case.get("expected_relevant_datasets") or []
            distractors = case.get("possible_distractors") or []

            run_precisions, run_recalls, run_f1s = [], [], []
            last_message = ""

            for run_idx in range(1, args.runs + 1):
                result = copilot.run_copilot_turn(
                    user_message=query,
                    thinking_budget_tokens=None,
                    dashboard_nodes=[],
                    dashboard_edges=[],
                    tools=COPILOT_FRONTEND_TOOLS,
                    max_tool_rounds=3,
                    retries=3,
                )
                predicted = _extract_predicted_dataset_ids(result, rawid_to_stem)
                print(f"  [{case_id}] {slug} | run {run_idx}/{args.runs} | predicted: {predicted}")
                p, r, f1 = _metrics(set(expected), set(predicted))
                run_precisions.append(p)
                run_recalls.append(r)
                run_f1s.append(f1)
                last_message = (result.get("message", "") or "").replace("\n", " ").strip()
                predicted_distractors = sorted(set(predicted) & set(distractors))

                rows_for_summary.append(
                    {
                        "llm_model": args.llm_model,
                        "ablation": ablation,
                        "case_id": case_id,
                        "slug": slug,
                        "run": run_idx,
                        "expected_datasets": json.dumps(expected, ensure_ascii=False),
                        "predicted_datasets": json.dumps(predicted, ensure_ascii=False),
                        "predicted_distractors": json.dumps(predicted_distractors, ensure_ascii=False),
                        "precision": p,
                        "recall": r,
                        "f1": f1,
                        "assistant_message": last_message,
                    }
                )
                writer.writerow(rows_for_summary[-1])
                csv_file.flush()
                if args.runs > 1:
                    print(f"    run {run_idx}/{args.runs} | P={p} R={r} F1={f1}")

            avg_p = round(sum(run_precisions) / args.runs, 4)
            avg_r = round(sum(run_recalls) / args.runs, 4)
            avg_f1 = round(sum(run_f1s) / args.runs, 4)
            print(f"  [{case_id}] {slug} | avg P={avg_p} R={avg_r} F1={avg_f1} (n={args.runs})")

    csv_file.close()

    # Re-read the full CSV for summary (includes pre-existing rows)
    with open(out_path, "r", encoding="utf-8") as f:
        rows_for_summary = list(csv.DictReader(f))

    # Print macro averages per ablation level (averaged over cases and runs)
    from collections import defaultdict
    # group by (ablation, case_id) first, average runs, then macro-avg over cases
    case_f1s: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows_for_summary:
        case_f1s[row["ablation"]][str(row["case_id"])].append(float(row["f1"]))
    print("\n── Macro-avg F1 by ablation (avg runs per case, then avg over cases) ──")
    for level in levels_to_run:
        per_case_avgs = [sum(v) / len(v) for v in case_f1s[level].values() if v]
        avg = round(sum(per_case_avgs) / len(per_case_avgs), 4) if per_case_avgs else 0.0
        print(f"  {level:20s}  F1={avg}  (cases={len(per_case_avgs)})")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
