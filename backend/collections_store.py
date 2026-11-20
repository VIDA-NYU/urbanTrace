"""Collections (docs/REDESIGN.md, section 2.1): what an analyst assembles for one analysis.

A collection is a JSON document stored as ``<collections dir>/<id>.json``:

    {
      "schema": "urbantrace.collection/1",
      "id": "c_...", "name": "...", "goal": "...", "notes": "...",
      "created_at": "...", "updated_at": "...",
      "datasets": [{"id": "<stem>", "columns": [...], "value_kinds": {"<column>": "extensive"},
                    "added_by": "user" | "copilot", "rationale": "..." | null}],
      "integrations": [{"id": "...", "node_id": "...", "request": {<integration request>},
                        "rationale": {...}, "created_at": "..."}],
      "analyses": [],
      "study_area": null,
      "canvas": {"nodes": [...], "edges": [...]}
    }

The server owns ``schema``, ``id``, ``created_at`` and ``updated_at``; everything else is what the
interface sends. Writes are atomic.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "urbantrace.collection/1"
_ID = re.compile(r"c_[0-9a-f]{12}")
_FIELDS = ("name", "goal", "notes", "datasets", "integrations", "analyses", "study_area", "canvas")
_DEFAULTS = {"name": "Untitled collection", "goal": "", "notes": "", "datasets": [], "integrations": [],
             "analyses": [], "study_area": None, "canvas": {"nodes": [], "edges": []}}


class NotFound(KeyError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, root):
        self.root = Path(root)

    def _path(self, cid: str) -> Path:
        if not _ID.fullmatch(cid or ""):
            raise NotFound(cid)
        return self.root / f"{cid}.json"

    def _write(self, doc: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(doc["id"])
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str))
        os.replace(tmp, path)

    def list(self) -> list[dict]:
        """Summaries, most recently updated first."""
        out = []
        for path in self.root.glob("c_*.json"):
            try:
                doc = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            out.append({"id": doc["id"], "name": doc.get("name"), "goal": doc.get("goal", ""),
                        "updated_at": doc.get("updated_at"), "datasets": len(doc.get("datasets", [])),
                        "integrations": len(doc.get("integrations", []))})
        return sorted(out, key=lambda d: d.get("updated_at") or "", reverse=True)

    def get(self, cid: str) -> dict:
        path = self._path(cid)
        if not path.exists():
            raise NotFound(cid)
        return json.loads(path.read_text())

    def create(self, fields: dict | None = None) -> dict:
        now = _now()
        doc = {"schema": SCHEMA, "id": f"c_{uuid.uuid4().hex[:12]}", "created_at": now, "updated_at": now}
        doc.update({k: json.loads(json.dumps(v)) for k, v in _DEFAULTS.items()})
        doc.update({k: v for k, v in (fields or {}).items() if k in _FIELDS})
        self._write(doc)
        return doc

    def update(self, cid: str, fields: dict) -> dict:
        doc = self.get(cid)
        doc.update({k: v for k, v in fields.items() if k in _FIELDS})
        doc["updated_at"] = _now()
        self._write(doc)
        return doc

    def delete(self, cid: str) -> None:
        path = self._path(cid)
        if not path.exists():
            raise NotFound(cid)
        path.unlink()
