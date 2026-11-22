# UrbanTrace — Implementation Plan

**Progress (2026-11-22):** Phases 0–5 built on the `autark-map` branch, followed by a tryout on one
real task (Brooklyn schools and libraries) that found and fixed 17 problems, listed under
[Tryout fixes](#tryout-fixes); it became [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md). Release work:
items 1–5 of [Release](#release) done (clean-ups, Autark doing the maps, the copilot on Step nodes
with the classic node retired, atlas-clean's checks, dasymetric on urbanweave 0.1.0a2); next are a
second real task, the documentation and the release itself. 40 commits are not pushed (one push at
release). Backend tests pass, none skipped; all use synthetic data.

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
- [ ] Run the 38 large corpus cases before deleting the legacy engine — *not run (no testing on the large catalog); the engine was removed without them, by decision*
- [x] *(in Release)* Delete the legacy engine and `URBANTRACE_ENGINE` after one cycle
- [x] *(in Release)* Delete `OperationNode` and `/run-operation` (REDESIGN §6 proposes deleting them; nothing on the canvas creates the node)

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
- [x] Port the copilot's operator suggestions to Step nodes, then retire the classic Integration node — *done in the release work (item 3)*

## Phase 5 — Analysis

- [x] Sensitivity sweep over resolutions, zone systems and methods; rank-stability map; Spearman agreement
- [x] Validate node: coverage, baseline and lift per quantile, with a note when ties make quantiles coincide
- [x] Dasymetric node with point priors
- [x] Pin an urbanweave prerelease that has `uw.dasymetric` — *0.1.0a2*
- [x] Priority indexes from Result Maps recorded as analyses and recomputed server-side
- [x] Report: `/api/collections/{id}/report`, printable HTML (≈60 KB), included in exports as `report.html`
- [x] Exports include the analyses and README sections for them
- [x] Interactive check in a real browser — *the tryout on 2026-11-22, by the user; fixes under Tryout fixes*

## Phase 6 — More data and other tools

Decisions needed before starting (each adds an outside service or a heavy dependency):

- [ ] Geocoding: which service (NYC GeoSearch proposed), and off unless explicitly enabled?
- [ ] OSM: live downloads for the study area, or only GraphML files provided by the user? (adds `osmnx`)
- [ ] Rasters: add `rasterio` + `exactextract`; which rasters first (heat, tree canopy)?
- [ ] Catalog growth: download and profile automatically when added, or confirm each time?
- [ ] MCP server: read-only apart from creating collections?

Work:

- [ ] Attribute joins on identifiers (BBL, BIN, ZIP) — *needs no decision; can start now*
- [x] Direct source → zones steps — *Step nodes match a source onto zones directly (phase 4)*
- [x] More matching methods: `within_distance`, `largest_overlap`, `representative_point` — *in the picker from urbanweave's registry*
- [x] More reductions: `median`, `shares` — *`shares` writes one column per category (`share_a`, ...), now carried through plan results; `median` takes intensive values, as the registry says*
- [ ] OSM streets and intersections as targets (`urbanweave[osm]`), per-road-km densities
- [x] Icons for `nearest_segment`, `nearest_node`, `within_distance`, `largest_overlap`, `representative_point`
- [ ] Rasters in the catalog and profiler; raster sources through `zonal_stats` (`urbanweave[raster]`)
- [ ] Geocoding of addresses
- [ ] Catalog growth on demand from NYC Open Data and Auctus
- [ ] MCP server: catalog search, profiles, collections, export (can move up any time a consumer asks)

## Tryout fixes

Found while using the tool (started 2026-11-22). The tryout became [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md).

- [x] Collection bar squeezed its labels ("A" for the goal, "No study area" on three lines, buttons past the edge): items no longer shrink, the bar sits right of Link Maps and wraps on narrow canvases
- [x] "In study area" couldn't judge 35 polygon and line datasets (their profiles have no extent or grid), so it always showed them: a coverage grid is now computed once from the data and cached (`scope.dataset_cells`, `data/.extent_cache.json`); the coverage view uses it too
- [x] Dataset bbox taken from the profile's density grid rather than its envelope
- [x] Three datasets have corrupt coordinates in the file itself: `2018_2019_school_locations` (latitude and longitude swapped, so it is excluded from every study area), `raised_crosswalk_locations` and `street_closures_due_to_construction_activities_by_intersection` (NY State Plane feet labelled EPSG:4326). To be flagged by atlas-clean (its PLAN.md, M5 Spatial data), with the accepted recipe applied on load and recorded in provenance
- [x] "In study area" barely narrows the list for a borough, because almost the whole catalog is citywide (83 of 86 datasets with a grid have data in Brooklyn). Show each dataset's share of rows inside the study area on its card and sort by it?
- [x] Coverage "share of study area" misled for points: it counts ~500 m cells with any feature, so ~60 libraries spread over Brooklyn score 7% and schools 46%, shown in orange, and the checks warn "partial coverage". Points are now measured by spread (the part of the area inside the hull of their cells) with the count inside; the cell share is kept for polygons and lines and now divides by the study area's own cells, not those of the other datasets; a dataset with nothing in the area gets "no data in the study area"
- [x] Coverage map showed a blue box with the study area as a dot: shapely's counterclockwise rings read by d3-geo as the globe minus the polygon. Polygons are rewound for d3 (`frontend/src/lib/geo.js`), in the coverage map and the dataset preview
- [x] Coverage map drawn with Autark (`CoverageMap.jsx`, `autk-map`) over the basemap, with pan, zoom and a hover listing the datasets in each cell, instead of a static d3 SVG
- [x] Removed the unused `maplibre-gl` and `d3-scale` dependencies
- [x] No basemap on any Autark map: Autark now defaults the workspace CRS to EPSG:3395 and refused the EPSG:3857 tiles. Maps are created with `crs: 'EPSG:3857'` (`autarkMap.js`)
- [ ] Let Autark project the data (`sourceCrs: 'EPSG:4326'`) instead of UrbanTrace's own Web Mercator code in `autarkMap.js`
- [x] No numbers visible after running a step: the report card started collapsed, the result map had no totals, and the new map opened behind the right sidebar. The closed card now shows "68 of 253 in study area · 68/68 matched · 44/69 targets"; the map shows the column's total, range and units with 0; new result maps are brought into view
- [x] Zone names on hover ("Park Slope", not "Zone 0"): the label column is chosen as a unique name-like text column (never Socrata's `:id`), else a whole-number code; the old check missed pandas 3's string type
- [x] Zones touching the study area by rounding were kept (Brooklyn had 77 NTAs instead of 69): a zone now needs 1% of its area inside (`scope.zones_in_area`), everywhere zones are filtered
- [x] Classic Integration results are brought into view too (`revealNodes`)
- [x] Unsaved work was lost on reload without warning, and a reload always started empty: the browser now asks before leaving with unsaved changes, keeps them as a draft in the browser, and on reload restores the draft or reopens the last saved collection. Results are not saved (decided 2026-11-22: they are rerun)
- [x] Couldn't connect to Combine & Calculate: it took only Step nodes and refused anything else silently, while the visible end of a chain is the step's Result Map. A Result Map now stands for the Step (or Calculate) that made it, for Calculate, Sweep and Validate; refused connections say why in the collection bar
- [x] Map tooltips (and the feature they name) were off whenever the canvas was zoomed: React Flow scales nodes with a CSS transform, and pointer offsets were used unscaled. `pointerInElement` in `autarkMap.js`, used by the result, dataset and coverage maps
- [x] `dycd_program_sites` preview was blank: one site geocoded to Los Angeles, and when the densest area held over 95% of the points the frame took every feature, strays included. It now frames the central 99.6% (`framingBounds` in `autarkMap.js`); affects every Autark map's first view
- [x] Export file names used internal node ids (`plan-node-1795370671161_output`, `sweep-7016_analysis`): results are named after their output (`libraries`, `schools_per_library`), unnamed analyses after kind and column (`sweep_libraries`)
- [x] Frontend lint: no errors (13 warnings remain, mostly hook dependencies)
- [ ] Lint in CI: blocked while `@urban-toolkit/autk-map` is a `file:` dependency outside the repository, which CI cannot install; needs a published Autark package or a vendored build
- [ ] Commit `data/metadata_v2/` (atlas-profiler profiles, 46 MB, through Git LFS like the rest of the catalog) or a script that regenerates it: coverage, value kinds, data checks and in-area shares read it, and it is untracked, so a fresh clone lacks it (`data/reports_v2/`, 522 MB of HTML, can stay out)
- [ ] Uploads are profiled with datamart-profiler only (`upload_new_data.py`), so an uploaded dataset has no atlas-profiler profile: coverage falls back to the data, but value-kind suggestions are missing; profile uploads with atlas-profiler too
- [ ] Add a LICENSE: the repository has none (urbanweave and atlas-clean are MIT); the README's acknowledgements section makes no license claim until one is chosen
- [ ] Console warning: a `<button>` nested inside another `<button>` on the canvas (React reports it on every load)
- [ ] The canvas lists a `shares` reduction as one output (`share`) in Combine & Calculate and the sweep, not its per-category columns

---

## Documentation

- [x] Update `README.md` for the redesigned tool: what UrbanTrace is for (find, prepare, analyse, export), collections and export, study area and coverage, plans and Step nodes, analyses, the report; the integration model, API and project structure sections predate phases 1–5
- [x] Update the documentation (`docs/`): REDESIGN.md's status, the walkthrough (screenshots, Check data), the API table in the README
- [x] New screenshots of the current interface for the README and the walkthrough (collection bar, coverage map, Step with its report card, result map, sweep and validation, report, export); `docs/screenshots/` holds previews of earlier versions
- [x] Move `Supplementary_Material.pdf` from the repository root to a directory that says what it is (e.g. `paper/`), with a README: supplementary material for the arXiv paper [2607.25124](https://arxiv.org/abs/2607.25124), which describes an earlier version of UrbanTrace (tag `vis2026-camera-ready`); update the README's link

---

## Release

One push, as a major release, when everything below is done (decided 2026-11-22). Scope chosen
by the user; in order:

1. Clean-ups
   - [x] Delete `OperationNode` and `/run-operation`
   - [x] Remove the legacy engine and `URBANTRACE_ENGINE` (without the 38 large corpus cases; the paper's results stay reproducible from `vis2026-camera-ready`): `integration_engine.py`, `h3_engine.py`, `operators/`, `grids/` and two commented-out endpoints are gone
   - [x] Show each dataset's share inside the study area on its card, and sort by it (`/api/catalog/in-area`; "In study area" keeps datasets with data there, most first)
2. - [x] Autark does the projection (`sourceCrs: 'EPSG:4326'`), hover and tooltips (`setTooltip`, `MapEvent.HOVER`) and framing (`fitBounds`); `autarkMap.js` lost its hit-testing, pointer correction and screen↔Mercator helpers (−137 lines). It needed a fix in Autark for canvases under a CSS transform: `fix/pointer-css-scale` in `~/src/autark` (local, with a test)
3. - [x] The copilot's method suggestions on Step nodes (`/api/copilot/suggest-step`, `backend/suggest.py`: LLM offered only registry-valid choices, answer re-checked, rules as fallback; rationale kept on the node and in the export); the classic Integration node is retired with `/api/integrate_multivariate`, the zoning recommendation and `weave_engine.py` (geometry repair moved to `geometry.py`). Old collections open without their classic nodes and say so. The paper's operator-selection benchmark notebook calls the removed endpoint: it runs against `vis2026-camera-ready` until its scoring rule is redone (after the release)
4. - [x] atlas-clean in UrbanTrace (`backend/cleaning.py`): **Check data** on a dataset node runs atlas-clean's spatial checks against the catalog's region and proposes fixes; accepted fixes are saved as a recipe in `data/recipes/<stem>.json` and replayed on every load (`catalog.load`), so previews, plans, coverage and exports use the corrected data; plans report it under `inputs.<source>.cleaning`, exports include the recipe and a Corrections section. atlas-clean became light for this (atlas-profiler and autoddg are extras now, `dc5b831` on its `feat/spatial`). Verified on `2018_2019_school_locations` (swap found and fixed; recipe removed again afterwards)
5. - [x] Dasymetric working: urbanweave 0.1.0a2 published to PyPI on 2026-11-22 (with the user's uncommitted dasymetric work committed into it: per-target priors, several totals, the 2016–2025 taxi notebook) and pinned; UrbanTrace's dasymetric test runs; checked on Brooklyn (2023 population over 351 H3 cells with schools as prior, total kept)
6. Whole-catalog run, then a second real task
   - [ ] Run all 121 datasets through every stage (load, profile and coverage, in-area share, atlas-clean checks, a step onto neighborhoods and onto an H3 grid, the map preview, export), with timings: `tools/corpus_check.py`; list what fails, what is slow and what looks wrong, and fix or log each
   - [ ] A second real task, one of the paper's case studies, through the tool; fix what it finds
7. - [x] Documentation (section above): README, docs, screenshots, supplementary material (2026-11-22)
8. Release mechanics
   - [ ] Version and CHANGELOG
   - [ ] Settle the size threshold for embedding and whether clipping to the study area is the default (REDESIGN §6)
   - [ ] Autark: release `fix/pointer-css-scale` (and `fitBounds`, newer than the build UrbanTrace had) with the rest of Autark; UrbanTrace links Autark from a local checkout, so a fresh clone needs it published or vendored
   - [ ] atlas-clean: release `feat/spatial` (spatial checks, light install); then pin `atlas-clean[geo]` in `backend/requirements.txt` (optional and unpinned until then; its tests skip without it)
   - [ ] Decide which catalog corrections to keep: check the three broken datasets (school locations, raised crosswalks, street closures) and commit their recipes in `data/recipes/`
   - [ ] Push `autark-map`, open the PR to `main`, tag the release

After the release: phase 6, licenses, the GeoParquet conversion, the benchmark's scoring rule in
urbanweave's vocabulary, lint in CI.

## Open questions

- Unknown `registry_version`: refuse, or show what the frontend can?
- Cache run results for large grids server-side by manifest?
- Should the copilot propose a whole plan from a goal, accepted node by node?
- Should UrbanTrace publish a collection (data portal, repository), or is the package the end of its job?
- Full atlas-profiler HTML reports in packages, or only the summary in `datapackage.json`?
