"""How the dataset catalog is written into the copilot's prompt.

Three formats, chosen with the COPILOT_CATALOG setting:

- ``full``: every dataset with every column, as the copilot has always sent it (about 86,000
  tokens for 125 datasets). Built by ``UrbanTraceCopilot._build_dataset_context``.
- ``compact``: the same information written tersely: types as ``Integer`` instead of
  ``http://schema.org/Integer``, no repeated keyword list, no empty fields.
- ``index``: one line per dataset (id, geometry, number of columns, first sentence of the
  description). The model asks for the columns and full description of the datasets it is
  considering with the ``get_dataset_details`` tool, which the backend answers itself.
"""

from __future__ import annotations

import re
from typing import Any

CATALOG_MODES = ("full", "compact", "index")
INDEX_SUMMARY_CHARS = 160
MAX_DETAIL_DATASETS = 12

# Types that say nothing beyond the structural type, or nothing useful at all
_UNINFORMATIVE_SEMANTIC = {"Text"}


def _short(uri: Any) -> str:
    """'http://schema.org/Integer' -> 'Integer'."""
    return str(uri).rstrip("/").rsplit("/", 1)[-1]


def _column(c: dict[str, Any]) -> str:
    name = c.get("name")
    if not name:
        return ""
    kinds = []
    structural = c.get("structural_type")
    if structural:
        kinds.append(_short(structural))
    for s in c.get("semantic_types") or []:
        short = _short(s)
        if short not in _UNINFORMATIVE_SEMANTIC and short not in kinds:
            kinds.append(short)
    geo = c.get("geo_classifier")
    if isinstance(geo, dict) and geo.get("label") and geo["label"] not in kinds:
        kinds.append(geo["label"])
    return f"{name}:{'/'.join(kinds)}" if kinds else str(name)


def _header(dataset_id: str, meta: dict[str, Any]) -> str:
    geometry = meta.get("geometricType") or "unknown geometry"
    n = meta.get("nb_columns")
    if n is None:
        n = len(meta.get("columns") or [])
    return f"{dataset_id} ({geometry}, {n} columns)"


def compact_entry(dataset_id: str, meta: dict[str, Any] | None, description: str = "") -> str:
    """The dataset's description and all its columns, tersely."""
    meta = meta or {}
    lines = [f"- {_header(dataset_id, meta)}: {description.strip() or 'no description'}"]
    columns = [s for s in (_column(c) for c in meta.get("columns") or [] if isinstance(c, dict)) if s]
    if columns:
        lines.append(f"  columns: {', '.join(columns)}")
    return "\n".join(lines)


def _first_sentence(text: str, limit: int = INDEX_SUMMARY_CHARS) -> str:
    text = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rsplit(" ", 1)[0] + "…"
    return sentence


def index_entry(dataset_id: str, meta: dict[str, Any] | None, description: str = "") -> str:
    """One line: id, geometry, number of columns, and the description's first sentence."""
    summary = _first_sentence(description) if description else "no description"
    return f"- {_header(dataset_id, meta or {})}: {summary}"


CATALOG_HEADERS = {
    "compact": (
        "UrbanTrace dataset catalog (id (geometry, number of columns): description; "
        "then columns as name:type):"
    ),
    "index": (
        "UrbanTrace dataset catalog, one line per dataset (id (geometry, number of columns): summary). "
        "Before suggesting or comparing datasets, call get_dataset_details with the ids of the "
        "candidates you are considering to read their full descriptions and columns."
    ),
}


def render_catalog(mode: str, catalog: dict[str, dict[str, Any]]) -> str:
    """The catalog text for the ``compact`` or ``index`` format.

    ``catalog`` maps a dataset id to ``{"meta": <profile metadata>, "description": <text>}``.
    """
    entry = compact_entry if mode == "compact" else index_entry
    lines = [CATALOG_HEADERS[mode]]
    for dataset_id in sorted(catalog):
        item = catalog[dataset_id]
        lines.append(entry(dataset_id, item.get("meta"), item.get("description", "")))
    return "\n".join(lines)


GET_DATASET_DETAILS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_dataset_details",
        "description": (
            "Read the full description and the columns (name:type) of catalog datasets. "
            f"Pass up to {MAX_DETAIL_DATASETS} dataset ids from the catalog."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dataset ids exactly as written in the catalog.",
                },
            },
            "required": ["dataset_ids"],
            "additionalProperties": False,
        },
    },
}


def dataset_details(catalog: dict[str, dict[str, Any]], dataset_ids: Any) -> dict[str, Any]:
    """The tool's answer: compact entries for known ids, and the ids that are not in the catalog."""
    if not isinstance(dataset_ids, list):
        dataset_ids = [dataset_ids] if dataset_ids else []
    wanted = [str(i).strip().removesuffix(".geojson") for i in dataset_ids if str(i).strip()]
    known = [i for i in dict.fromkeys(wanted) if i in catalog][:MAX_DETAIL_DATASETS]
    unknown = [i for i in dict.fromkeys(wanted) if i not in catalog]
    response: dict[str, Any] = {
        "datasets": "\n".join(
            compact_entry(i, catalog[i].get("meta"), catalog[i].get("description", "")) for i in known
        )
    }
    if unknown:
        response["unknown_ids"] = unknown
    if len([i for i in wanted if i in catalog]) > MAX_DETAIL_DATASETS:
        response["note"] = f"Only the first {MAX_DETAIL_DATASETS} datasets are returned; ask again for the rest."
    return response
