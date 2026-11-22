# UrbanTrace — Implementation Plan

**Progress (2026-11-20):** Phases 0–5 built on the `autark-map` branch, one commit each (not pushed).
61 backend tests pass and 1 is skipped (dasymetric, which needs urbanweave newer than 0.1.0a1). All
tests use synthetic data, so the 17.7 GB Git LFS catalog is not needed. Phase 6 has not started; it
needs the decisions listed under it.

Design doc: [docs/REDESIGN.md](docs/REDESIGN.md). It says why; this file tracks what is done.

UrbanTrace helps an analyst find and prepare urban data, record the selected collection with its
provenance, export it as a package other applications can import, and analyse it. Integration runs
on [urbanweave](https://github.com/VIDA-NYU/urbanweave).

The order below is a hypothesis about what analysts need first. After each phase, the tool should
be tried on real tasks and the remaining phases reordered by what that shows.

## Decisions

| Question | Decision |
| --- | --- |
| Engine | urbanweave 0.1.0a1, pinned; `URBANTRACE_ENGINE=legacy` keeps the original operators for one cycle |
| Paper reproducibility | Tag `vis2026-camera-ready` (existing tag, used instead of a new `vis2026`) |
| Conventions | Legacy conventions on the classic Integration node; urbanweave's defaults (per km², overlap weighting, missing stays missing) on plan steps |
| Plan schema | urbanweave's plan JSON (`"version": 1`) unchanged inside the collection, which holds UrbanTrace's own data beside it |
| Package standard | Frictionless Data Package v2; RO-Crate only when someone deposits a package |
| Redistribution | Embed only with a recorded license and ≤ 50 MB; otherwise reference the source URL |
| Tests | Synthetic fixtures only; never the large catalog |

Still open: see [Open questions](#open-questions) at the end.

---

## Phase 0 — Foundations and the new engine

- [x] Paper revision tagged (`vis2026-camera-ready`)
- [x] Configurable backend address (`VITE_API_BASE_URL`, `frontend/src/config/api.js`)
- [x] API tests on synthetic fixtures; `requirements-dev.txt`; GitHub Actions CI without LFS
- [x] Pin `urbanweave==0.1.0a1`
- [x] `/api/integrate_multivariate` on urbanweave with the same request and response shapes (`backend/weave_engine.py`)
  - Uses a thin adapter on the public API, not `compat.urbantrace.run` per variable, which would give each variable its own grid
- [x] `/api/operators` from the registry; duplicate route removed
- [x] Legacy fixes, named in `weave_engine.CHANGES`: `grid_covers_sources`, `own_zoning_mapping`, `own_cells_only`
- [x] Invalid polygons repaired with `make_valid` and reported, not excluded
- [x] Refusals (corrupt coordinates) shown with their reason, not as a generic 500
- [ ] Run the 38 large corpus cases before deleting the legacy engine — *skipped: no testing on the large catalog*
- [ ] Delete the legacy engine and `URBANTRACE_ENGINE` after one cycle
- [ ] Delete `OperationNode` and `/run-operation` (REDESIGN §6 proposes deleting them; nothing on the canvas creates the node)

## Phase 1 — Catalog and collections

### Catalog
- [x] Origin records: `data/origins.json` from NYC Open Data metadata (`tools/fill_origins.py`): 96 found, 25 not on the portal
- [ ] Record licenses — *the portal states none, so every dataset is referenced, not embedded*
- [x] Upload records source URL, publisher and license
- [x] SHA-256 hashes for served files (cached in `data/.hash_cache.json`)
- [x] Catalog reads a GeoParquet copy when present (`backend/catalog.py`)
- [ ] Convert the lake to GeoParquet (`tools/convert_to_geoparquet.py` exists, not run)

### Collections
- [x] Server-side collections: CRUD `/api/collections` (`backend/collections_store.py`, schema `urbantrace.collection/1`)
- [x] Goal, datasets, integrations, accepted rationale, canvas saved and reopened
- [x] Collection bar: name, goal, status, new, open, save

### Export
- [x] `datapackage.json` (Frictionless v2, `urbantrace:*` fields), sources as GeoParquet / GeoPackage / GeoJSON
- [x] Embed rule (license + size), referenced otherwise
- [x] README with datasets, rationale, caveats and load snippets
- [x] Result Map downloads in the same formats with a provenance record (`/api/results/export`)
- [x] Package import back into a collection (`/api/collections/import`)

## Phase 2 — Study area, coverage and time

- [x] Study area on the collection: zones from a catalog dataset (optionally filtered) or a box
- [x] Study area bounds the grid, clips sources and exports; zones that only touch it are dropped
- [x] Coverage view from atlas-profiler density grids (`/api/coverage`)
- [x] Search filtered by study area and years (`/api/catalog/index`)
- [x] Time windows on dataset nodes, applied before matching
- [x] Checks: periods that don't overlap, partial coverage, invalid study area (`/api/collections/check`)

## Phase 3 — Registry and reports in the interface

- [x] Method picker with icons, hover card with figure, parameter form (`OperatorSelect`, `MethodIcon`, `ParamForm`)
- [x] Choices that don't fit the geometry disabled, with the reason
- [x] Method figures exported from urbanweave's tutorials (`tools/export_method_figures.py`)
- [x] Report cards on result maps and in the provenance sidebar
- [x] Copilot operator recommendation reads the registry and is checked against it
- [x] Exports include each integration's result under `data/results/`, with its report in the README

## Phase 4 — Plans and derived variables

- [x] `/api/plan/validate`, `/api/plan/run`, `/api/plan/replay` (`backend/plans.py`)
- [x] Canvas converts to plan JSON (`frontend/src/lib/plans.js`); tested with a frontend-built plan (`tests/data/canvas_plan.json`)
- [x] H3 Grid, Step and Combine & Calculate nodes; reductions with value-kind chips and `where` filters; validation markers
- [x] Value kinds suggested from profiles (`/api/datasets/{id}/value-kinds`)
- [x] Plan menu: run all and record, replay, download `plan.json`
- [x] Results in columns; the `count` sum is gone for plan results
- [x] Derived variables evaluated by UrbanTrace after the plan runs (AST whitelist), since urbanweave plans have no calculation step
- [x] Exports add `plan.json`, `manifest.json`, `collection.json` and rerun instructions
- [ ] Port the copilot's operator suggestions to Step nodes, then retire the classic Integration node — *kept as "Spatial Integration (classic)" until then*

## Phase 5 — Analysis

- [x] Sensitivity sweep over resolutions, zone systems and methods; rank-stability map; Spearman agreement
- [x] Validate node: coverage, baseline and lift per quantile, with a note when ties make quantiles coincide
- [x] Dasymetric node with point priors
- [ ] Pin an urbanweave prerelease that has `uw.dasymetric` — *needs publishing urbanweave; the node says it's unavailable until then*
- [x] Priority indexes from Result Maps recorded as analyses and recomputed server-side
- [x] Report: `/api/collections/{id}/report`, printable HTML (≈60 KB), included in exports as `report.html`
- [x] Exports include the analyses and README sections for them
- [ ] Interactive check in a real browser — *done only in headless Chrome over CDP; the Chrome extension was unavailable*

## Phase 6 — More data and other tools

Decisions needed before starting (each adds an outside service or a heavy dependency):

- [ ] Geocoding: which service (NYC GeoSearch proposed), and off unless explicitly enabled?
- [ ] OSM: live downloads for the study area, or only GraphML files provided by the user? (adds `osmnx`)
- [ ] Rasters: add `rasterio` + `exactextract`; which rasters first (heat, tree canopy)?
- [ ] Catalog growth: download and profile automatically when added, or confirm each time?
- [ ] MCP server: read-only apart from creating collections?

Work:

- [ ] Attribute joins on identifiers (BBL, BIN, ZIP) — *needs no decision; can start now*
- [ ] Direct source → zones steps
- [ ] More matching methods: `within_distance`, `largest_overlap`, `representative_point`
- [ ] More reductions: `median`, `shares`
- [ ] OSM streets and intersections as targets (`urbanweave[osm]`), per-road-km densities
- [ ] Icons for `nearest_segment`, `nearest_node`, `within_distance`, `largest_overlap`, `representative_point`
- [ ] Rasters in the catalog and profiler; raster sources through `zonal_stats` (`urbanweave[raster]`)
- [ ] Geocoding of addresses
- [ ] Catalog growth on demand from NYC Open Data and Auctus
- [ ] MCP server: catalog search, profiles, collections, export (can move up any time a consumer asks)

## Tryout fixes

Found while using the tool (started 2026-11-22).

- [x] Collection bar squeezed its labels ("A" for the goal, "No study area" on three lines, buttons past the edge): items no longer shrink, the bar sits right of Link Maps and wraps on narrow canvases
- [x] "In study area" couldn't judge 35 polygon and line datasets (their profiles have no extent or grid), so it always showed them: a coverage grid is now computed once from the data and cached (`scope.dataset_cells`, `data/.extent_cache.json`); the coverage view uses it too
- [x] Dataset bbox taken from the profile's density grid rather than its envelope
- [ ] Three datasets have corrupt coordinates in the file itself: `2018_2019_school_locations` (latitude and longitude swapped, so it is excluded from every study area), `raised_crosswalk_locations` and `street_closures_due_to_construction_activities_by_intersection` (NY State Plane feet labelled EPSG:4326). Fix the files, or record a per-dataset correction applied on load
- [ ] "In study area" barely narrows the list for a borough, because almost the whole catalog is citywide (83 of 86 datasets with a grid have data in Brooklyn). Show each dataset's share of rows inside the study area on its card and sort by it?

---

## Release

- [ ] Push `autark-map` and open a PR to `main`
- [ ] Try the tool on the paper's case studies and with expert users; reorder phase 6 by what that shows
- [ ] Settle the size threshold for embedding and whether clipping to the study area is the default (REDESIGN §6)
- [ ] Scoring rule for the operator-selection benchmark in urbanweave's vocabulary (REDESIGN §6)

## Open questions

- Unknown `registry_version`: refuse, or show what the frontend can?
- Cache run results for large grids server-side by manifest?
- Should the copilot propose a whole plan from a goal, accepted node by node?
- Should UrbanTrace publish a collection (data portal, repository), or is the package the end of its job?
- Full atlas-profiler HTML reports in packages, or only the summary in `datapackage.json`?
