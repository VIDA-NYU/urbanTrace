# UrbanTrace — Implementation Plan

**Progress (2026-11-23):** Phases 0–5 built on the `autark-map` branch, then two real tasks through
the tool: Brooklyn schools and libraries (the tryout, [Tryout fixes](#tryout-fixes),
[docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)) and the paper's case study 2, Opportunity Bargains
(`notebook/case_study_2/`). Release items 1–7 done; next is item 8, the release itself. Phase 6:
joins on a key, geocoding, the copilot's LLM switch (with local models), OSM streets and
intersections, rasters with tree canopy (6-inch), and fetching whole NYC Open Data datasets are done;
catalog growth from inside the app and Auctus remain. The paper's provenance graph, priority map
(now opt-in) and Spatial Delta Map work on plan results. 71 commits are not pushed (one push at
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
| Engine | urbanweave 0.1.0a2, pinned; the original operators were removed with the classic Integration node |
| Paper reproducibility | Tag `vis2026-camera-ready` (existing tag, used instead of a new `vis2026`) |
| Conventions | urbanweave's defaults (per km², overlap weighting, missing stays missing) |
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
- [ ] Convert the lake to GeoParquet (`tools/convert_to_geoparquet.py` exists, not run) — *the whole-catalog run shows GeoJSON parsing dominates on the largest datasets (10–25 s per stage)*

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

Decisions (2026-11-22, by the user):

- [x] Geocoding: NYC GeoSearch (free, no key). Sends address columns to that service, so it is off unless the analyst asks for it per dataset
- [x] OSM: live downloads for the study area; adds `osmnx` (`urbanweave[osm]`)
- [x] Rasters: add `rasterio` + `exactextract` (`urbanweave[raster]`, which already uses both); tree canopy first (user, 2026-11-23), alongside the street-tree points
- [x] Catalog growth: download and profile automatically when an analyst adds a dataset
- [x] MCP server: on hold

Work:

- [x] Attribute joins on identifiers (BBL, BIN, ZIP) — *plan steps with urbanweave's `reduce` (sum, ratio_of_sums) join rows onto zones by a key; zones are identified by a code column (`urbantrace.id_column`), keys compared as text (11211 = "11211" = 11211.0), unknown keys reported. The Step node has a "Join on a key" mode (source key, zones key, guessed from familiar names such as zipcode or modzcta; sum and ratio of sums), and the report card says how many keys matched no zone. Checked on DYCD program sites by `zipcode` onto MODZCTA: 178 areas, 656,642 participants by key and 656,051 by location; the 12 unmatched keys are building ZIPs (10020, 10118, ...) that MODZCTA folds into neighbours. Not yet: a count (urbanweave's reduce offers sum and ratio_of_sums), and a key join combined with a location step onto the same zones (they are different targets, so Combine & Calculate refuses them)*
- [x] Direct source → zones steps — *Step nodes match a source onto zones directly (phase 4)*
- [x] More matching methods: `within_distance`, `largest_overlap`, `representative_point` — *in the picker from urbanweave's registry*
- [x] More reductions: `median`, `shares` — *`shares` writes one column per category (`share_a`, ...), now carried through plan results; `median` takes intensive values, as the registry says*
- [x] OSM streets and intersections as targets (`urbanweave[osm]`), per-road-km densities — *a **Streets (OSM)** node (segments or intersections; drive, walk, bike or all) is a Step's target. The network is downloaded live from OpenStreetMap for the study area's polygon (`osm.py`, OSMnx), in the background from the node, once per area and network type, and kept as GraphML in `data/osm/`; plans hand urbanweave that file, so runs are fast, fingerprinted and replayable. Matching: `nearest_segment`, `within_distance`, `gaussian` (segments), `nearest_node` (intersections); `density` gives per km of street. Results come back as lines or points on the result map; exports carry the ODbL attribution. Needs a study area (at most 1,000 km², `URBANTRACE_OSM_MAX_KM2`). Greenpoint (3.3 km²): 106 s to download, 473 segments; 7 schools onto 6 segments. Downloads go through the public Overpass API and are slow: a borough takes minutes*
- [x] Icons for `nearest_segment`, `nearest_node`, `within_distance`, `largest_overlap`, `representative_point`
- [x] Rasters in the catalog; raster sources through `zonal_stats` (`urbanweave[raster]`) — *`rasters.py`: a GeoTIFF in `data/raster/` with a sidecar JSON (title, band, units, value kind, no-data, source, license); listed with the datasets (preview image on the node), in the catalog index and study-area shares, copied into exports. A Step with a raster source does zonal statistics (exact cell coverage) onto zones or an H3 grid. First raster: NLCD Tree Canopy Cover 2021, 30 m, fetched from MRLC's WCS in its native Albers grid for the catalog's region (`tools/fetch_nlcd_canopy.py`, 1.7 MB, 2 s; any year 2011–2021). Brooklyn's 69 neighborhoods in 3.4 s: Prospect Park 45 %, East Flatbush 0.3 %. Caveat: 30 m canopy undercounts street trees (one tree rarely fills a cell), so compare with the street-tree points. Not yet: atlas-profiler profiles for rasters, NYC's 6-inch LiDAR land cover, committing the raster file. **Finding (2026-11-23):** per neighborhood citywide (243 NTAs, 10 s), Parks' tree density and NLCD canopy are slightly *negatively* correlated (Spearman −0.25): the Upper East Side and West Village have ~2,800 inventory trees per km² but 0.8–1.4 % NLCD canopy. At 30 m, NLCD misses street canopy in dense neighborhoods, so it is not fit for neighborhood canopy in NYC; the 6-inch LiDAR land cover (NYC 2017, or TNC 2021 as Cloud-Optimized GeoTIFFs, read by window) should replace it*
- [x] 6-inch tree canopy — *`tools/fetch_tnc_canopy.py`: The Nature Conservancy's 2021 land cover of NYC (6-inch, LiDAR and imagery; Zenodo, CC BY-NC-SA 4.0), downloaded once (1.74 GB, resumable, `data/raster/source/`, not committed) and aggregated to percent canopy of land per 30 ft cell (share of 60x60 six-inch pixels classed as canopy, water left out): `tnc_tree_canopy_2021`, 5 MB, 285 s, citywide 23.7 %. Per neighborhood: Upper East Side 16.8 % (NLCD 0.8 %), West Village 18.4 % (1.4 %), Prospect Park 63.5 % (45.1 %); median 20.2 % against NLCD's 5.5 %; Spearman with NLCD 0.78, with street-tree density 0.11 (most canopy is in parks and yards). Exports carry the citation and the share-alike, non-commercial terms; NLCD's description now points to this raster for NYC neighborhoods*
- [x] Street-tree points: `forestry_tree_points` refreshed to Parks' full inventory, 1,125,266 trees (the catalog copy stopped at 500,000, a download cap) — *`tools/fetch_open_data.py <stem>` pages through the NYC Open Data API for every row, writes GeoParquet (158 MB, 11 min; the catalog prefers it to the GeoJSON), re-profiles with atlas-profiler in its own environment (50 s) and records the retrieval in `origins.json`. The GeoParquet and the origins change are not committed (data files: the user's call). The same tool serves catalog growth from NYC Open Data*
- [x] Geocoding of addresses — *`geocode.py` and the Check data dialog's "Locate rows from their addresses" section: per dataset, on the analyst's request, rows without a location are located from their address columns (suggested, changeable) with NYC GeoSearch. Before sending, the dialog counts the rows, the distinct addresses with a house number and those without, and names the service. Each answer is checked (house number, street, borough; GeoSearch's own confidence is 0.8 for everything); streets are sent normalised ("E42nd Street" as "EAST 42 STREET"), which GeoSearch reads reliably. Checked locations are saved (`data/geocoded/<stem>.json`), filled on load and reported in plans and exports; the dataset node says Located. Veteran-owned businesses: 4 of 17 rows located, 1 rejected (an upstate address answered in Queens), 12 without a house number; certificates of occupancy: 212 of 322*
- [ ] Catalog growth on demand from NYC Open Data and Auctus
- [ ] MCP server: catalog search, profiles, collections, export — *on hold (user, 2026-11-22)*

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
- [x] Let Autark project the data (`sourceCrs: 'EPSG:4326'`) instead of UrbanTrace's own Web Mercator code in `autarkMap.js` — *done in release item 2*
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
- [x] Commit `data/metadata_v2/` (atlas-profiler profiles, 46 MB, through Git LFS like the rest of the catalog) — *committed 2026-11-23 with the rasters and the full tree inventory (GeoParquet), all through LFS;* or a script that regenerates it: coverage, value kinds, data checks and in-area shares read it, and it is untracked, so a fresh clone lacks it (`data/reports_v2/`, 522 MB of HTML, can stay out)
- [ ] Uploads are profiled with datamart-profiler only (`upload_new_data.py`), so an uploaded dataset has no atlas-profiler profile: coverage falls back to the data, but value-kind suggestions are missing; profile uploads with atlas-profiler too
- [x] Add a LICENSE: MIT (user, 2026-11-23), like urbanweave and atlas-clean; the README has a License section, and says the datasets keep their own terms
- [ ] Console warning: a `<button>` nested inside another `<button>` on the canvas (React reports it on every load)
- [x] Dropdowns in plan nodes were blank (white text on white) when the OS is in dark mode: `index.css` was Vite's starter sheet, which turns unstyled text white and buttons black in dark mode; the interface is now light everywhere
- [x] Map preview of MODZCTA returned 500: rounding coordinates with `set_precision` refused its invalid polygons; it now rounds point by point. The whole-catalog run had checked previews before the rounding was added; re-checked after the fix: all 121 previews load, the largest 6.5 MB
- [x] The provenance panel drew one line per column, so a step with two columns from one dataset repeated a React key; one line per dataset and row now
- [x] The Integration Provenance Graph (paper, Fig. 1D: data cards, triangles for mapping operators, circles for aggregations, the rationale on hover) was empty of operators since phase 4: it reads each variable's mapping and aggregation, which only the retired Integration node filled. Plan results now fill them per column (the step's method, the column's reduction, the copilot's rationale or the step's report), Calculate columns are traced to their own steps and datasets, and runs onto zones are labelled by the zones instead of `rnull`
- [x] The Multivariate Priority Map (hotspot synthesis) failed on plan results (400): it sent output names (`libraries`, `fill_rate`) as dataset columns. It now sends how each column was computed (count of features, sum of a column, a Calculate formula)
- [x] Zoom out stopped at 50% (React Flow's default), too close to fit a workflow with its result maps: now 10%
- [x] The priority map's rule-based directions guessed "more means more need" for anything no keyword matched (libraries ranked as need), with nothing on the card saying so. Rules now say "unknown" when no rule applies (and for ratios and Calculate formulas), facilities (library, park, clinic, station, ...) count as resources, unknown variables are left out of the score until the analyst chooses ↑ or ↓ on the card, and the card says when keyword rules rather than an LLM set the directions; saved priority analyses and reports leave undecided variables out and name them
- [x] The copilot's LLM can be turned on from the interface: an **LLM** chip in the copilot bar opens settings (on/off, provider, model, test). Keys stay in `backend/.env`; providers without one are shown as not available. New `local` provider: any OpenAI-compatible server on the machine (Ollama, LM Studio, llama.cpp, vLLM), no key; checked against a stand-in server, not yet against a real local model
- [x] LLM providers are checked when the backend starts (in the background): keys found in its environment, the shell's or `backend/.env`, are verified with their provider by a free request (the model list, or the token's owner), and a local server is asked for its models; the log says what is available. When the LLM is off and a provider works, the chip reads "LLM available · turn on" and the settings open with it chosen; a provider named in `.env` that does not work gives way to the first that does (local, OpenAI, Hugging Face, Portkey). Nothing turns on without the analyst
- [x] Every result with two or more columns became a Hotspot Priority map (red header, 0–1 score), including a single Step with unrelated reductions. The priority map is now opt-in: a Combine & Calculate result opens as one, any other result with two or more columns has a **Priority** button in its header; the choice is kept with the node, and turning it off takes the priority analysis out of the report and the export
- [ ] The canvas lists a `shares` reduction as one output (`share`) in Combine & Calculate and the sweep, not its per-category columns
- [x] The copilot's one-line catalog couldn't tell zone datasets apart: NTAs (262) and sub-borough areas (55) both read as "neighborhood/community district", and in the discovery trial it chose `NYC_population` where `NTA_Neighborhood_Tabulation_Areas` was expected. Polygon lines now end with their number of polygons and key columns (`catalog_format.zone_keys`, about 200 tokens more) — *two-case rerun (`benchmark/results/catalog_zone_hint_trial.csv`): case 1 now picks the NTAs, citing the counts; case 2 still picks sub-borough areas, on purpose (for the population denominator), though it calls them the finer of the two*

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
   - [x] Run all 121 datasets through every stage (2026-11-22; `benchmark/results/corpus_check/summary.md`). Fixed from it: steps without a study area are bounded by the catalog's region (every yellow-taxi year failed on a few thousand 0,0 rows); map previews sent every feature with every column (up to 856 MB; now geometry, the coloring column and at most 50,000 features, 3.6–6.5 MB on the largest); GeoJSON reads only the columns asked for; Check data pre-ticks only coordinate and geometry fixes (32 datasets have placeholder values flagged as errors, whose fixes change attributes). Left: the three datasets with broken coordinates fail until corrected (Check data fixes them); the largest datasets take 10–25 s per stage, mostly parsing GeoJSON (the GeoParquet conversion would cut it)
   - [x] A second real task, one of the paper's case studies, through the tool; fix what it finds — *the paper's case study 2, Opportunity Bargains (`notebook/case_study_2/`): six 2017 indicators from Community Districts and Sub-Borough Areas onto the 197 residential NTAs, violent crime derived, a priority score with and without rent, and the Spatial Delta Map. The notebook runs on the current code in 7 s and reproduces its numbers (107 NTAs up, 90 down; Brownsville +0.25, West Village −0.25). On the canvas (headless): every step matched 59/59 or 55/55 source areas onto 197/197 NTAs. Found and fixed: (1) the Spatial Delta Map never received scores from results created by a run or an opened collection (their callbacks were attached only when an unrelated input changed): it showed "Waiting for inputs"; (2) the priority map never sent the collection's goal to the copilot, so every score meant "need": for this opportunity question it inverted math, poverty, crime and rent. It now sends the goal and the score means what the goal looks for; (3) the copilot counted crime twice (all crimes, property, and violent = all − property); told to weight the parts and not the total, it now proposes math 28 %, English 28 %, poverty 19 %, violent 15 %, property 10 % (the paper's figure: 28/26/25/12/10) and rent 18 %; (4) result maps of successive steps were placed on top of other nodes: now in the nearest free space. Delta map: 193–197 NTAs changed*
7. - [x] Documentation (section above): README, docs, screenshots, supplementary material (2026-11-22); brought up to date with phase 6 on 2026-11-23: README sections on streets, rasters, joins, geocoding, the copilot's LLM, priority maps and the Delta Map; the walkthrough corrected (Combine & Calculate opens as a priority map) and pointing to the new features; `docs/CASE_STUDY_2.md`, the opportunity-bargains case study on the canvas; seven new screenshots
8. Release mechanics
   - [x] Version and CHANGELOG — *2.0.0-alpha.1 (user, 2026-11-23; `2.0.0a1` in Python, tag `v2.0.0-alpha.1`; the paper's version is 1.0, `vis2026-camera-ready`): `backend/version.py`, recorded in the API, saved collections (`saved_with`) and exports (`urbantrace:software`, with urbanweave's version); `frontend/package.json`; `CHANGELOG.md`, dated when the release is pushed*
   - [ ] Settle the size threshold for embedding and whether clipping to the study area is the default (REDESIGN §6)
   - [ ] Autark: release `fix/pointer-css-scale` (and `fitBounds`, newer than the build UrbanTrace had) with the rest of Autark; UrbanTrace links Autark from a local checkout, so a fresh clone needs it published or vendored
   - [ ] atlas-clean: release `feat/spatial` (spatial checks, light install); then pin `atlas-clean[geo]` in `backend/requirements.txt` (optional and unpinned until then; its tests skip without it)
   - [ ] Decide which catalog corrections to keep: check the three broken datasets (school locations, raised crosswalks, street closures) and commit their recipes in `data/recipes/`
   - [ ] Push `autark-map`, open the PR to `main`, tag `v2.0.0-alpha.1`

After the release: phase 6, licenses, the GeoParquet conversion, the benchmark's scoring rule in
urbanweave's vocabulary, lint in CI.

## Open questions

- Unknown `registry_version`: refuse, or show what the frontend can?
- Cache run results for large grids server-side by manifest?
- Should the copilot propose a whole plan from a goal, accepted node by node?
- Should UrbanTrace publish a collection (data portal, repository), or is the package the end of its job?
- Full atlas-profiler HTML reports in packages, or only the summary in `datapackage.json`?
