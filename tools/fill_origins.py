"""Fill the catalog's origin records (docs/REDESIGN.md, section 2.2) from NYC Open Data.

For each dataset in data/descriptions_origin.csv, whose raw file is named by its portal ID, read the
portal's public metadata and write data/origins.json:

    {"<dataset stem>": {"portal": ..., "portal_id": ..., "source_url": ..., "publisher": ...,
                        "license": ..., "source_updated_at": ..., "catalog_added_at": ...,
                        "derived_from": {"raw_file": ...}, "status": ...}}

Fields the portal does not provide are null, with the reason in "notes"; nothing is guessed.
Content hashes are computed when a dataset is exported, not here, so this does not read the data.

    python tools/fill_origins.py            # all datasets
    python tools/fill_origins.py --only NYC_libraries
"""
import argparse
import csv
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PORTAL = "https://data.cityofnewyork.us"
USER_AGENT = "urbantrace-catalog/0.1"


def portal_metadata(portal_id: str):
    req = urllib.request.Request(f"{PORTAL}/api/views/{portal_id}.json", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": True, "message": f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"error": True, "message": str(e)}


def git_added_date(path: Path):
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%as", "--", str(path.relative_to(ROOT))],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    return out[-1] if out else None


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None


def origin_for(stem: str, raw_name: str) -> dict:
    portal_id = raw_name.removesuffix(".geojson")
    raw = DATA / "geojson_raw" / raw_name
    rec = {"portal": "NYC Open Data", "portal_id": portal_id, "source_url": None, "publisher": None,
           "license": None, "source_updated_at": None, "catalog_added_at": git_added_date(DATA / "geojson" / f"{stem}.geojson"),
           "retrieved_at": None, "derived_from": {"raw_file": f"data/geojson_raw/{raw_name}" if raw.exists() else None},
           "status": None, "notes": []}
    meta = portal_metadata(portal_id)
    if meta.get("error"):
        rec.update(portal=None, status="not_found", notes=[f"{portal_id} not found on NYC Open Data ({meta.get('message')}); origin unknown"])
        return rec
    lic = meta.get("license") or {}
    rec.update(
        source_url=f"{PORTAL}/d/{portal_id}",
        publisher=meta.get("attribution"),
        license=lic.get("name") or meta.get("licenseId"),
        source_updated_at=iso(meta.get("rowsUpdatedAt")),
        title=meta.get("name"),
        category=meta.get("category"),
        status="found",
    )
    if not rec["license"]:
        rec["notes"].append("license not stated in portal metadata; the portal's terms of use apply")
    rec["notes"].append("retrieval date not recorded; catalog_added_at is when the file entered this repository")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="dataset stems to refresh")
    args = ap.parse_args()
    out_path = DATA / "origins.json"
    origins = json.loads(out_path.read_text()) if out_path.exists() else {}
    rows = list(csv.DictReader(open(DATA / "descriptions_origin.csv")))
    for row in rows:
        stem = row["dataset"].removesuffix(".geojson")
        if args.only and stem not in args.only:
            continue
        origins[stem] = origin_for(stem, row["dataset_raw"])
        print(f"{stem:60s} {origins[stem]['status']}", file=sys.stderr)
        time.sleep(0.2)
    out_path.write_text(json.dumps(dict(sorted(origins.items())), indent=1) + "\n")
    found = sum(o["status"] == "found" for o in origins.values())
    print(f"{found} of {len(origins)} found on NYC Open Data -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
