"""Locating rows from their addresses with NYC GeoSearch (PLAN.md, phase 6).

Some catalog rows have an address but no location (40,314 of the property valuation rows, 322
certificates of occupancy, ...). An analyst can ask, per dataset, for those rows to be located:
their addresses are sent to NYC GeoSearch (https://geosearch.planninglabs.nyc, NYC Planning's free
geocoder, no key), each answer is checked against the address sent, and the locations that check
out are saved in ``data/geocoded/<stem>.json``. From then on every load of the dataset
(``catalog.load``) fills those rows, and plans, coverage, previews and exports report it.

Nothing is sent unless the analyst asks for it, and the server can turn geocoding off altogether
(``URBANTRACE_GEOCODER=off``).

GeoSearch always answers with something: its confidence is 0.8 for an exact address and for a
guess alike ("1 Nowhere Lane, Queens" comes back as "1 49 LANE"). So each answer is checked here:
the house number and street must be the ones sent (after normalising "ST" to "STREET", "5TH" to
"5", ...), and the borough and ZIP code must agree when the data has them. Answers that do not
are reported as "different" and not used; addresses without a house number are not sent, since
GeoSearch cannot place a street name alone on one building.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SERVICE = "NYC GeoSearch"
DEFAULT_URL = "https://geosearch.planninglabs.nyc/v2/search"
MAX_ADDRESSES = 20_000                  # unique addresses per run
WORKERS = 4                             # requests in flight: polite to a free public service


class GeocodeError(ValueError):
    pass


def enabled() -> bool:
    return (os.getenv("URBANTRACE_GEOCODER") or "nyc-geosearch").lower() not in ("off", "none", "0", "false")


def _url() -> str:
    return os.getenv("URBANTRACE_GEOSEARCH_URL") or DEFAULT_URL


def result_path(data_dir, stem: str) -> Path:
    return Path(data_dir) / "geocoded" / f"{stem}.json"


def _cache_path(data_dir) -> Path:
    return Path(data_dir) / "geocoded" / "_cache.jsonl"


def has_result(data_dir, stem: str) -> bool:
    return result_path(data_dir, stem).exists()


# --- addresses -----------------------------------------------------------------------------------

BOROUGHS = {
    "manhattan": "Manhattan", "new york": "Manhattan", "mn": "Manhattan", "1": "Manhattan",
    "bronx": "Bronx", "the bronx": "Bronx", "bx": "Bronx", "2": "Bronx",
    "brooklyn": "Brooklyn", "kings": "Brooklyn", "bk": "Brooklyn", "3": "Brooklyn",
    "queens": "Queens", "qn": "Queens", "4": "Queens",
    "staten island": "Staten Island", "richmond": "Staten Island", "si": "Staten Island", "5": "Staten Island",
}

_ROLES = {
    "address": re.compile(r"^(.*_)?(street_?address|address|addr|staddr|incident_address|programaddress|address_?line_?1?)$", re.I),
    "house": re.compile(r"^(house_?(no|number|num)|housenumber|number|bldg_?num)$", re.I),
    "street": re.compile(r"^(street_?name|street|stname)$", re.I),
    "borough": re.compile(r"^(.*_)?(boro|borough|boroname|boro_?nm|borough_?name)$", re.I),
    "zip": re.compile(r"^(.*_)?(zip|zipcode|zip_?code|postcode|postal_?code)$", re.I),
}


def suggest_columns(columns: list[str]) -> dict:
    """Which columns hold the address: {address} or {house, street}, plus {borough, zip} if found."""
    found = {}
    for role, pattern in _ROLES.items():
        hit = next((c for c in columns if pattern.match(c)), None)
        if hit:
            found[role] = hit
    if "house" in found and "street" in found:
        found.pop("address", None)
    else:
        found.pop("house", None)
        found.pop("street", None)
    return found


def _text(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)                                          # ZIP 10038.0
    return re.sub(r"\s+", " ", str(v)).strip()


def borough_name(v) -> str:
    return BOROUGHS.get(_text(v).lower(), "")


def address_of(row: dict, spec: dict) -> dict:
    """The parts of one row's address: {house, street, borough, zip}."""
    if spec.get("address"):
        text = _UNIT.split(_text(row.get(spec["address"])))[0].strip()      # "68 Jay Street; Suite 201"
        m = re.match(r"^\s*(\d+ \d/\d|\d[\d\-]*[A-Z]?)\s+(.+)$", text, re.I)
        house, street = (m.group(1), m.group(2)) if m else ("", text)
        if house and norm_street(street) in _STREET_TYPES:                # "1 AVENUE" is First Avenue, no number
            house, street = "", text
    else:
        house, street = _text(row.get(spec.get("house"))), _UNIT.split(_text(row.get(spec.get("street"))))[0].strip()
    zip_ = _text(row.get(spec["zip"])) if spec.get("zip") else ""
    return {"house": house, "street": street,
            "borough": borough_name(row.get(spec["borough"])) if spec.get("borough") else "",
            "zip": zip_[:5] if re.fullmatch(r"\d{5}(-\d{4})?", zip_) else ""}


_UNIT = re.compile(r"\s*(?:[;,]|\b(?:SUITE|STE|APT|FL|FLOOR|UNIT|RM|ROOM)\b\.?|#)\s*", re.I)
_STREET_TYPES = {"STREET", "AVENUE", "PLACE", "ROAD", "DRIVE", "LANE", "COURT", "TERRACE", "BOULEVARD", "PARKWAY"}


def query_of(addr: dict) -> str:
    """The text sent to GeoSearch. The street goes in normalised ("E42nd Street" as "EAST 42 STREET"):
    GeoSearch reads the long form reliably and guessed another street for the short one."""
    return ", ".join(p for p in (f"{addr['house']} {norm_street(addr['street'])}".strip(), addr["borough"], addr["zip"]) if p)


# --- checking an answer --------------------------------------------------------------------------

_WORDS = {
    "ST": "STREET", "STR": "STREET", "AVE": "AVENUE", "AV": "AVENUE", "AVENU": "AVENUE", "BLVD": "BOULEVARD",
    "RD": "ROAD", "PL": "PLACE", "DR": "DRIVE", "LN": "LANE", "CT": "COURT", "TER": "TERRACE", "TERR": "TERRACE",
    "PKWY": "PARKWAY", "PKY": "PARKWAY", "HWY": "HIGHWAY", "EXPY": "EXPRESSWAY", "SQ": "SQUARE", "CIR": "CIRCLE",
    "TPKE": "TURNPIKE", "PLZ": "PLAZA", "BCH": "BEACH", "HTS": "HEIGHTS", "FT": "FORT", "MT": "MOUNT", "ST.": "STREET",
    "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH", "B'WAY": "BROADWAY", "BWAY": "BROADWAY",
    "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5", "SIXTH": "6", "SEVENTH": "7",
    "EIGHTH": "8", "NINTH": "9", "TENTH": "10", "ELEVENTH": "11", "TWELFTH": "12",
}


def norm_street(s: str) -> str:
    s = re.sub(r"\b([NSEW])(\d)", r"\1 \2", _text(s).upper())          # E42ND -> E 42ND
    words = re.sub(r"[.,#]", " ", s).split()
    out = []
    for w in words:
        w = _WORDS.get(w, w)
        w = re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w)           # 5TH -> 5
        out.append(w)
    return " ".join(out)


def norm_house(s: str) -> str:
    return re.sub(r"[\s\-]", "", _text(s).upper())


def verdict(addr: dict, props: dict | None) -> tuple[str, str]:
    """("matched" | "different", why) for GeoSearch's answer *props* to *addr*."""
    if not props:
        return "not_found", "no answer"
    same_whole = norm_street(f"{props.get('housenumber') or ''} {props.get('street') or ''}") == \
        norm_street(f"{addr['house']} {addr['street']}")      # "255 REAR" + "BENEDICT ROAD" = "255" + "REAR BENEDICT ROAD"
    if not same_whole and norm_house(props.get("housenumber")) != norm_house(addr["house"]):
        return "different", f"house number {props.get('housenumber')!r}"
    if not same_whole and norm_street(props.get("street")) != norm_street(addr["street"]):
        return "different", f"street {props.get('street')!r}"
    if addr["borough"] and props.get("borough") and props["borough"] != addr["borough"]:
        return "different", f"borough {props['borough']}"
    if addr["zip"] and props.get("postalcode") and props["postalcode"] != addr["zip"] and not addr["borough"]:
        return "different", f"ZIP {props['postalcode']}"           # ZIPs only decide without a borough
    return "matched", ""


# --- the service ---------------------------------------------------------------------------------

def _search(query: str) -> dict | None:
    """GeoSearch's best answer for *query*: {lon, lat, label, housenumber, street, borough,
    postalcode, bbl, bin} or None. Retries briefly when the service is busy."""
    import httpx
    for attempt in range(4):
        try:
            r = httpx.get(_url(), params={"text": query, "size": 1}, timeout=15,
                          headers={"User-Agent": "UrbanTrace geocoding"})
        except httpx.HTTPError:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (429, 502, 503, 504):
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        feats = r.json().get("features") or []
        if not feats:
            return None
        f = feats[0]
        p = f.get("properties") or {}
        lon, lat = f["geometry"]["coordinates"][:2]
        pad = (p.get("addendum") or {}).get("pad") or {}
        return {"lon": lon, "lat": lat, "label": p.get("label"), "housenumber": p.get("housenumber"),
                "street": p.get("street"), "borough": p.get("borough"), "postalcode": p.get("postalcode"),
                "bbl": pad.get("bbl"), "bin": pad.get("bin")}
    raise GeocodeError(f"{SERVICE} did not answer; try again later.")


_cache_lock = threading.Lock()


def _load_cache(data_dir) -> dict:
    path = _cache_path(data_dir)
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                q, ans = json.loads(line)
                out[q] = ans
            except ValueError:
                continue
    return out


def _remember(data_dir, query: str, answer):
    path = _cache_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock, path.open("a") as f:
        f.write(json.dumps([query, answer]) + "\n")


# --- what a run would do, and running it ---------------------------------------------------------

def _rows_to_locate(data_dir, stem: str, spec: dict):
    import shapely
    import catalog
    cols = [c for c in {spec.get(k) for k in ("address", "house", "street", "borough", "zip")} if c]
    gdf = catalog.load(data_dir, stem, columns=cols, geocoded=False)
    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        raise GeocodeError(f"{stem} has no column {', '.join(missing)}.")
    geoms = gdf.geometry.to_numpy()
    no_location = shapely.is_missing(geoms) | shapely.is_empty(geoms)
    rows = gdf.loc[no_location, cols]
    return int(len(gdf)), rows


def preview(data_dir, stem: str, spec: dict | None = None) -> dict:
    """What locating would do, without sending anything: {rows, missing, columns, suggested,
    addresses (unique, with a house number), without_house_number, sample, service, enabled}."""
    import catalog
    prof = catalog.profile(data_dir, stem) or {}
    columns = [c["name"] for c in prof.get("columns", []) if c.get("name")]
    suggested = suggest_columns(columns)
    spec = spec or suggested
    out = {"dataset": stem, "columns": columns, "suggested": suggested, "spec": spec, "service": SERVICE,
           "url": _url(), "enabled": enabled(), "saved": info(data_dir, stem)}
    if not (spec.get("address") or spec.get("street")):
        return {**out, "rows": None, "missing": None, "addresses": 0, "without_house_number": 0, "sample": []}
    total, rows = _rows_to_locate(data_dir, stem, spec)
    addrs = [address_of(r, spec) for r in rows.to_dict("records")]
    queries = {query_of(a) for a in addrs if a["house"] and a["street"]}
    return {**out, "rows": total, "missing": int(len(rows)), "addresses": len(queries),
            "without_house_number": sum(1 for a in addrs if not a["house"]),
            "sample": sorted(queries)[:5], "too_many": len(queries) > MAX_ADDRESSES}


def run(data_dir, stem: str, spec: dict, progress=None) -> dict:
    """Locate the dataset's rows without a location from their addresses and save the locations
    that check out. *progress(done, total)* is called as answers arrive."""
    if not enabled():
        raise GeocodeError("Geocoding is turned off on this server (URBANTRACE_GEOCODER=off).")
    if not (spec.get("address") or (spec.get("house") and spec.get("street"))):
        raise GeocodeError("Choose the address column, or the house number and street columns.")
    total, rows = _rows_to_locate(data_dir, stem, spec)
    addrs = {int(i): address_of(r, spec) for i, r in zip(rows.index, rows.to_dict("records"))}
    by_query: dict[str, list[int]] = {}
    without_house = 0
    for i, a in addrs.items():
        if not (a["house"] and a["street"]):
            without_house += 1
            continue
        by_query.setdefault(query_of(a), []).append(i)
    if len(by_query) > MAX_ADDRESSES:
        raise GeocodeError(f"{len(by_query):,} different addresses; at most {MAX_ADDRESSES:,} per run.")
    cache = _load_cache(data_dir)
    todo = [q for q in by_query if q not in cache]
    done = len(by_query) - len(todo)
    if progress:
        progress(done, len(by_query))

    def ask(q):
        ans = _search(q)
        _remember(data_dir, q, ans)
        return q, ans

    with ThreadPoolExecutor(WORKERS) as pool:
        for q, ans in pool.map(ask, todo):
            cache[q] = ans
            done += 1
            if progress and (done % 25 == 0 or done == len(by_query)):
                progress(done, len(by_query))

    import cleaning
    region = cleaning.catalog_region(data_dir)
    located, counts, examples = {}, {"matched": 0, "different": 0, "not_found": 0, "outside_region": 0}, []
    for q, idx in by_query.items():
        ans = cache.get(q)
        status, why = verdict(addrs[idx[0]], ans)
        if status == "matched" and not (region[0] <= ans["lon"] <= region[2] and region[1] <= ans["lat"] <= region[3]):
            status, why = "outside_region", "outside the catalog's region"
        counts[status] += len(idx)
        if status == "matched":
            for i in idx:
                located[str(i)] = [round(ans["lon"], 6), round(ans["lat"], 6)]
        elif len(examples) < 8:
            examples.append({"address": q, "status": status, "why": why, "answer": (ans or {}).get("label")})
    result = {"dataset": stem, "service": SERVICE, "url": _url(), "spec": spec,
              "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "rows": total, "missing": len(addrs), "addresses": len(by_query), "located": len(located),
              "rows_by_status": {**counts, "without_house_number": without_house}, "examples": examples}
    path = result_path(data_dir, stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**result, "locations": located}))
    return result


def info(data_dir, stem: str) -> dict | None:
    """The saved result without its locations, or None."""
    path = result_path(data_dir, stem)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    data.pop("locations", None)
    return data


def delete(data_dir, stem: str) -> bool:
    path = result_path(data_dir, stem)
    if path.exists():
        path.unlink()
        return True
    return False


def apply(data_dir, stem: str, gdf):
    """Fill the rows of *gdf* (the whole dataset, as read) that have no location with the saved
    locations. Returns the frame and a report, or the frame unchanged and None."""
    if not has_result(data_dir, stem):
        return gdf, None
    import shapely
    data = json.loads(result_path(data_dir, stem).read_text())
    locs = data.get("locations") or {}
    if data.get("rows") != len(gdf):                       # the dataset changed since: positions no longer hold
        return gdf, {"skipped": "the dataset changed since its rows were located; locate them again",
                     "service": data.get("service")}
    idx = [int(i) for i in locs]
    geoms = gdf.geometry.to_numpy().copy()
    pos = [i for i in idx if 0 <= i < len(geoms) and (shapely.is_missing(geoms[i]) or shapely.is_empty(geoms[i]))]
    if not pos:
        return gdf, None
    pts = shapely.points([locs[str(i)] for i in pos])
    if gdf.crs is not None and not gdf.crs.equals("EPSG:4326"):
        import geopandas as gpd
        pts = gpd.GeoSeries(pts, crs="EPSG:4326").to_crs(gdf.crs).to_numpy()
    geoms[pos] = pts
    out = gdf.set_geometry(gpd_series(geoms, gdf.crs, gdf.index))
    return out, {"rows_located": len(pos), "service": data.get("service"), "saved": data.get("saved"),
                 "file": f"geocoded/{stem}.json"}


def gpd_series(values, crs, index):
    import geopandas as gpd
    return gpd.GeoSeries(values, crs=crs, index=index)


# --- jobs: a run can take minutes, so the API starts it and the client polls ---------------------

_JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def start(data_dir, stem: str, spec: dict, on_done=None) -> dict:
    with _jobs_lock:
        job = _JOBS.get(stem)
        if job and job["state"] == "running":
            return job
        job = _JOBS[stem] = {"dataset": stem, "state": "running", "done": 0, "total": None, "result": None, "error": None}

    def progress(done, total):
        job.update(done=done, total=total)

    def work():
        try:
            job["result"] = run(data_dir, stem, spec, progress)
            job["state"] = "done"
            if on_done:
                on_done()
        except Exception as e:                              # reported to the client
            job.update(state="failed", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return job


def status(stem: str) -> dict | None:
    return _JOBS.get(stem)
