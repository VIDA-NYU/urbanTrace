"""Collection export (docs/REDESIGN.md, section 2.3): one zip another tool can open.

    datapackage.json   Frictionless Data Package (v2): one resource per embedded file, with its
                       SHA-256, schema (columns used, types, value kinds), origin and profile summary.
                       Datasets that are referenced rather than embedded are listed under
                       "urbantrace:references" with their landing page and the hash of the file
                       UrbanTrace used, so a recipient can fetch and check them.
    data/sources/      the selected datasets, reduced to the columns used, as GeoParquet and/or GeoPackage
    data/results/      integration results (added by callers that pass results)
    README.md          what the collection is for, the datasets and why each was chosen, caveats, and
                       how to load the files in Python and R

Embedding redistributes data, so ``embed="auto"`` (the default) embeds a dataset only when its
license is recorded and it is under the size limit; ``"always"`` embeds everything (the analyst has
checked the terms) and ``"never"`` references everything that can be referenced. A dataset with
no known origin cannot be referenced, so with ``"auto"`` or ``"never"`` it is listed as not included.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pandas.api.types import (is_bool_dtype, is_datetime64_any_dtype, is_float_dtype,
                              is_integer_dtype)

import catalog

EMBED_LIMIT_BYTES = 50 * 1024 * 1024
FORMATS = {"parquet": ("parquet", "application/vnd.apache.parquet"),
           "gpkg": ("gpkg", "application/geopackage+sqlite3"),
           "geojson": ("geojson", "application/geo+json")}


def _slug(text: str, fallback: str = "collection") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or fallback


def _field_type(series: pd.Series) -> str:
    if is_bool_dtype(series):
        return "boolean"
    if is_integer_dtype(series):
        return "integer"
    if is_float_dtype(series):
        return "number"
    if is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _schema(gdf: gpd.GeoDataFrame, value_kinds: dict, units: dict | None = None) -> dict:
    fields = []
    for col in gdf.columns:
        if col == gdf.geometry.name:
            fields.append({"name": col, "type": "any",
                           "description": "geometry (WKB in GeoParquet, native in GeoPackage), EPSG:4326"})
            continue
        f = {"name": str(col), "type": _field_type(gdf[col])}
        if col in value_kinds:
            f["urbantrace:value_kind"] = value_kinds[col]
        if units and col in units:
            f["urbantrace:unit"] = units[col]
        fields.append(f)
    return {"fields": fields}


def _write(gdf: gpd.GeoDataFrame, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "parquet":
        gdf.to_parquet(path, index=False)
    elif fmt == "gpkg":
        gdf.to_file(path, driver="GPKG", layer=path.stem)
    elif fmt == "geojson":
        gdf.to_file(path, driver="GeoJSON")
    else:
        raise ValueError(f"Unknown format {fmt!r}")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resource(name: str, rel: str, fmt: str, file: Path, schema: dict, extra: dict) -> dict:
    ext, mediatype = FORMATS[fmt]
    return {"name": name, "path": rel, "format": ext, "mediatype": mediatype,
            "bytes": file.stat().st_size, "hash": f"sha256:{_file_sha256(file)}",
            "schema": schema, **extra}


def _embed_decision(mode: str, origin: dict, size: int) -> tuple[bool, str]:
    referenceable = bool(origin.get("source_url"))
    if mode == "always":
        return True, "embedded on request"
    if mode == "never":
        return False, "referenced on request" if referenceable else "not included: origin unknown, cannot be referenced"
    if not origin.get("license"):
        return False, ("referenced: license not recorded" if referenceable
                       else "not included: license and origin unknown")
    if size > EMBED_LIMIT_BYTES:
        return False, "referenced: larger than the embedding limit" if referenceable else "not included: too large and origin unknown"
    return True, "embedded: license recorded"


def _clean(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """WGS84 and string column names; drops columns GeoParquet/GeoPackage cannot hold."""
    out = gdf.to_crs(4326) if gdf.crs is not None and not gdf.crs.equals("EPSG:4326") else gdf
    out = out.rename(columns={c: str(c) for c in out.columns})
    for col in out.columns:
        if col != out.geometry.name and out[col].dtype == object:
            sample = out[col].dropna().head(20)
            if any(isinstance(v, (dict, list)) for v in sample):
                out = out.assign(**{col: out[col].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)})
    return out


def build(data_dir, collection: dict, out_path: Path, *, embed: str = "auto",
          formats: tuple[str, ...] = ("parquet", "gpkg"), results: list[dict] | None = None,
          extra_files: dict[str, bytes] | None = None, readme_sections: list[str] | None = None,
          area=None, warnings: list[dict] | None = None) -> dict:
    """Write the export zip for *collection* to *out_path*; return the data package descriptor.

    *results* are integration results to include, each ``{"name", "frames": {"grid": gdf, "zones":
    gdf}, "value_kinds", "units", "request", "reports", "description"}``. *extra_files* are added
    verbatim (path in zip → bytes), for plans and manifests.
    """
    if embed not in ("auto", "always", "never"):
        raise ValueError("embed must be 'auto', 'always' or 'never'")
    formats = tuple(f for f in formats if f in FORMATS) or ("parquet",)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resources, references, not_included, rows = [], [], [], []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for entry in collection.get("datasets", []):
            stem = catalog.stem_of(entry.get("id"))
            if not catalog.valid_stem(stem):
                continue
            path = catalog.dataset_path(data_dir, stem)
            origin = catalog.origin(data_dir, stem)
            prof = catalog.profile(data_dir, stem)
            if path is None:
                not_included.append({"name": stem, "reason": "dataset not found in the catalog"})
                continue
            served_hash = catalog.sha256(data_dir, path)
            columns = [c for c in (entry.get("columns") or []) if c]
            value_kinds = entry.get("value_kinds") or {}
            info = {"description": catalog.description(data_dir, stem) or None, "urbantrace:origin": origin,
                    "urbantrace:profile": catalog.profile_summary(prof),
                    "urbantrace:columns_used": columns or None,
                    "urbantrace:selection": {"added_by": entry.get("added_by", "user"),
                                             "rationale": entry.get("rationale")},
                    "urbantrace:served_file": {"name": path.name, "sha256": served_hash}}
            embedded, why = _embed_decision(embed, origin, path.stat().st_size)
            row = {"name": stem, "rows": (prof or {}).get("nb_rows"), "geometry": (prof or {}).get("geometricType"),
                   "columns": columns, "origin": origin, "status": why, "rationale": entry.get("rationale")}
            rows.append(row)
            if embedded:
                gdf = catalog.load(data_dir, stem)
                if columns:
                    keep = [c for c in columns if c in gdf.columns]
                    gdf = gdf[keep + [gdf.geometry.name]]
                if area is not None:
                    import scope
                    gdf, clip_report = scope.clip_to_area(gdf, area)
                    info = {**info, "urbantrace:clipped_to_study_area": clip_report}
                    row["status"] += "; clipped to the study area"
                gdf = _clean(gdf)
                row["rows"] = len(gdf)
                schema = _schema(gdf, value_kinds)
                for fmt in formats:
                    rel = f"data/sources/{stem}.{FORMATS[fmt][0]}"
                    _write(gdf, root / rel, fmt)
                    name = stem.lower() if fmt == formats[0] else f"{stem.lower()}-{fmt}"
                    resources.append(_resource(re.sub(r"[^a-z0-9._-]", "-", name), rel, fmt, root / rel, schema, info))
            elif origin.get("source_url"):
                references.append({"name": stem, "url": origin["source_url"], "reason": why, **info})
            else:
                not_included.append({"name": stem, "reason": why, **info})

        for res in results or []:
            for level, gdf in (res.get("frames") or {}).items():
                if gdf is None or len(gdf) == 0:
                    continue
                gdf = _clean(gdf)
                base = _slug(res["name"], "result")
                schema = _schema(gdf, res.get("value_kinds") or {}, res.get("units"))
                for fmt in formats:
                    rel = f"data/results/{base}_{level}.{FORMATS[fmt][0]}"
                    _write(gdf, root / rel, fmt)
                    name = f"{base}-{level}" if fmt == formats[0] else f"{base}-{level}-{fmt}"
                    resources.append(_resource(name, rel, fmt, root / rel, schema, {
                        "description": res.get("description"),
                        "urbantrace:result": {"level": level, "request": res.get("request"),
                                              "reports": res.get("reports"), "changes": res.get("changes")}}))

        package = {
            "$schema": "https://datapackage.org/profiles/2.0/datapackage.json",
            "name": _slug(collection.get("name")),
            "title": collection.get("name") or "Untitled collection",
            "description": collection.get("goal") or None,
            "created": now,
            "resources": resources,
            "urbantrace:collection": {k: collection.get(k) for k in ("id", "goal", "notes", "study_area", "analyses")},
            "urbantrace:references": references,
            "urbantrace:not_included": not_included,
            "urbantrace:export": {"embed": embed, "formats": list(formats), "clipped": area is not None},
            "urbantrace:warnings": warnings or [],
        }
        (root / "datapackage.json").write_text(json.dumps(package, indent=1, default=str))
        (root / "README.md").write_text(_readme(collection, rows, results or [], package, readme_sections or []))
        for rel, data in (extra_files or {}).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    z.write(file, file.relative_to(root).as_posix())
    return package


def _origin_text(origin: dict) -> str:
    if origin.get("source_url"):
        who = origin.get("publisher") or origin.get("portal") or "source"
        return f"[{who}]({origin['source_url']})"
    return "unknown"


def _readme(collection: dict, rows: list[dict], results: list[dict], package: dict, extra: list[str]) -> str:
    title = collection.get("name") or "Untitled collection"
    lines = [f"# {title}", ""]
    if collection.get("goal"):
        lines += [f"**Goal:** {collection['goal']}", ""]
    lines += [f"Exported from UrbanTrace on {package['created'][:10]}. `datapackage.json` describes every file "
              "(a [Frictionless Data Package](https://datapackage.org/)).", ""]
    if collection.get("notes"):
        lines += ["## Notes", "", collection["notes"], ""]
    area = collection.get("study_area")
    if area:
        if area.get("kind") == "zones":
            sel = f" where {area['column']} is {', '.join(map(str, area.get('values') or []))}" if area.get("column") else ""
            desc = f"the zones of `{area.get('dataset')}`{sel}"
        else:
            desc = f"the box {area.get('bbox')}"
        lines += ["## Study area", "", f"{area.get('name') or 'Study area'}: {desc}."
                  + (" Embedded datasets are clipped to it." if package["urbantrace:export"].get("clipped") else ""), ""]

    lines += ["## Datasets", "", "| Dataset | Rows | Geometry | Columns used | Source | In this package |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        cols = ", ".join(f"`{c}`" for c in r["columns"]) or "all"
        lines.append(f"| {r['name']} | {r['rows'] if r['rows'] is not None else ''} | {r['geometry'] or ''} | "
                     f"{cols} | {_origin_text(r['origin'])} | {r['status']} |")
    lines.append("")
    reasons = [r for r in rows if r.get("rationale")]
    if reasons:
        lines += ["### Why each dataset was chosen", ""]
        lines += [f"- **{r['name']}**: {r['rationale']}" for r in reasons]
        lines.append("")

    if results:
        lines += ["## Integrations", ""]
        for res in results:
            lines += [f"### {res['name']}", "", res.get("description") or "", ""]
            for line in res.get("summary_lines", []):
                lines.append(f"- {line}")
            lines.append("")

    lines += extra

    caveats = []
    unknown = [r["name"] for r in rows if not r["origin"].get("source_url")]
    if unknown:
        caveats.append(f"Origin unknown for: {', '.join(unknown)}.")
    unlicensed = [r["name"] for r in rows if not r["origin"].get("license")]
    if unlicensed:
        caveats.append("No license is recorded for: " + ", ".join(unlicensed) + ". Check the publisher's terms "
                       "before redistributing them.")
    if package["urbantrace:not_included"]:
        caveats.append("Not included: " + "; ".join(f"{n['name']} ({n['reason']})"
                                                    for n in package["urbantrace:not_included"]) + ".")
    if package["urbantrace:references"]:
        caveats.append("Referenced datasets are not in this package; fetch them from the listed source and "
                       "compare with `urbantrace:served_file` in `datapackage.json` (the portal may have "
                       "updated them since).")
    for res in results:
        caveats += res.get("caveats", [])
    caveats += [w["message"] for w in package.get("urbantrace:warnings") or []]
    if caveats:
        lines += ["## Caveats", ""] + [f"- {c}" for c in caveats] + [""]

    first = next((r["path"] for r in package["resources"] if r["path"].endswith(".parquet")), None)
    first_gpkg = next((r["path"] for r in package["resources"] if r["path"].endswith(".gpkg")), None)
    if first or first_gpkg:
        lines += ["## Loading the data", "", "Python:", "", "```python", "import geopandas as gpd"]
        lines.append(f'gdf = gpd.read_parquet("{first}")' if first else f'gdf = gpd.read_file("{first_gpkg}")')
        lines += ["```", "", "R:", "", "```r", "library(sf)"]
        lines.append(f'gdf <- st_read("{first_gpkg}")' if first_gpkg else
                     f'gdf <- sfarrow::st_read_parquet("{first}")')
        lines += ["```", ""]
    return "\n".join(lines)
