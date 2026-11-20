# UrbanTrace redesign: collections, export and urbanweave

Status: draft for discussion (2026-11-20). Author: Claudio Silva, with Claude.

## Summary

UrbanTrace helps an analyst **find, prepare and analyze urban data**: discover datasets with the
copilot, understand them through their profiles, bring them onto common places (grid cells, zones,
streets), synthesize them into priority maps and compare alternatives, and then take the
collection and its results into other tools: a notebook, a GIS, a report. Today it does the
discovery, integration and analysis but stops short of the hand-over: nothing records which
datasets were chosen, where they came from or what was done to them, and the only export is a bare
GeoJSON of one zone result.

This document proposes two changes:

- **The collection becomes the main object** (section 2). The datasets an analyst selects, the
  columns they use, the integrations they run and the reasons behind each choice form a
  collection, which UrbanTrace exports as one package: a manifest in an open standard, the data in
  formats GIS and data tools read, and an urbanweave plan that reruns in a notebook. The catalog
  starts recording where each dataset came from, so the manifest can say.
- **Integration moves to urbanweave** (section 3). UrbanTrace's operators now exist, corrected and
  generalized, as the [urbanweave](https://github.com/VIDA-NYU/urbanweave) package
  (`pip install --pre urbanweave`). UrbanTrace stops doing integration math and becomes a visual
  editor and viewer for urbanweave plans, keeping what is its own: the canvas, the catalog and
  profiles, the copilot, the linked maps and the comparison views.

Section 4 adds what the new profiles and urbanweave make possible: time and coverage awareness,
joins by identifier, derived variables, dasymetric disaggregation, sensitivity sweeps, validation,
reports and an MCP server, on a GeoParquet data lake with tests and CI. The work is ordered in
seven phases (section 5), each ending with something usable, and the order is meant to be revised
as analysts use each phase. The first replaces the engine behind the current API and changes
nothing visible; the second delivers collections and a dataset export; later phases add data
understanding, the new integration interface, plans, analysis features and new kinds of data.

## 1. Where things stand

**Nothing leaves UrbanTrace in a usable form.**

- The Result Map node downloads a zone result as GeoJSON (`handleDownloadGeoJson` in
  `ResultMapNode.jsx`). Grid-only results have no download, and the file holds geometry and values
  only: no record of the datasets, columns or operators that produced it.
- The canvas, the selected datasets and the integration settings cannot be saved or reopened.
  The provenance panel's record lives in the browser and is lost on reload.
- The catalog does not record where a dataset came from. The profiles in `data/metadata_v2` have
  the name, file, size, CRS, columns, and spatial and temporal coverage, but no source URL,
  publisher, license, retrieval date or content hash. `data/descriptions_origin.csv` maps many files
  to their NYC Open Data IDs (`2020_doe_high_school_directory.geojson` → `23z9-6uk9`), from which the
  rest can be recovered.

**The engine duplicates urbanweave, with less.** About 1,300 lines (`backend/operators/`,
`backend/grids/`, `backend/integration_engine.py` and the integration parts of `backend/main.py`)
implement a subset of what urbanweave does. urbanweave fixes the errors a review found in this
code: densities from Web Mercator areas (about 1.74× too large at NYC's latitude, so densities
come out too small), missing values turned into zeros, points on a cell boundary counted twice,
and aggregators that modify their input. (The Gaussian kernel's distances in degrees were fixed
here on 2026-11-19.)

**The operator rules are written in three places:**

- `GEOMETRY_CONSTRAINTS` in `backend/main.py`;
- `ALLOCATION_OPS`, `AGGREGATION_OPS`, `ZONING_MAPPING_OPS`, `ZONING_AGGREGATION_OPS` and
  `GEOMETRY_TO_ALLOCATION` at the top of `frontend/src/components/canvas/nodes/IntegrationNode.jsx`;
- the copilot's fallbacks in `backend/main.py` (`_classify_variable`, `_pick_mapping_operator`,
  `_pick_aggregation_operator`, `_heuristic_recommendations`).

urbanweave's `registry()` is generated from the code that runs the operators, and `problems()`
says why a combination is not supported. Together they are meant to replace all three.

**The model is a fixed pipeline.** UrbanTrace integrates in one shape: sources onto an H3 grid,
then optionally onto zones (I = A₂ ∘ Z_map ∘ A₁ ∘ R). urbanweave's model is a chain of
`match` + `aggregate` steps onto any target: H3 cells, zones, street segments, intersections, and
zones summarizing a raster. The second stage of UrbanTrace's pipeline is the same operation as the
first, with the cells as sources. urbanweave plans are JSON graphs of steps, which is what the
canvas already draws.

**Provenance is built by the client.** `IntegrationNode` builds a `provenance` object in the
browser from the settings it sent: resolution, operators, the copilot's rationale. It cannot say
what the run did. urbanweave returns a report for every step: what matched, what was left out and
why, how totals moved, which CRS measured the step, and whether the method conserves totals. It
also writes run manifests that record inputs by content hash and can be replayed.

**The grid response has a correctness bug.** `/api/integrate_multivariate` builds
`{cell_id: {"count": sum(all variables), "variables": ..., "sample_props": ...}}` with
`iterrows`. `count` adds unrelated variables (crashes plus median income), and building the
response row by row is slow on large grids.

**Leftover code.** `OperationNode` and `/run-operation` (H3 intersect and union previews through
`h3_engine.py`) are marked deprecated in `main.py`. The node is still registered in
`AnalysisCanvas.jsx`, but the toolbox can no longer create it: its entries in
`frontend/src/config/operations.js` are commented out. A block of commented-out endpoint code
follows `/run-operation` in `main.py`, and `/api/operators` is defined twice.

## 2. The collection and its export

### 2.1 The collection

A collection is what an analyst is assembling for one analysis:

- the datasets they selected, from the catalog, the copilot's suggestions or an upload, each with
  the columns they use and each column's value kind (section 3.3);
- the integrations they ran on them, as urbanweave plan steps, with each step's report;
- the analyses built on them: each priority map's variables, normalization, weights and
  polarities (as inferred by the Synthesis Agent and as overridden by the analyst), and each
  Delta Map's pair of inputs;
- the reasons: the analyst's goal, the copilot's rationale for each dataset and method it
  suggested and the analyst accepted, and notes the analyst adds.

The collection is stored on the server as a JSON document (`collections/<id>.json`), so it survives
a reload and can be reopened, duplicated and exported. Dataset nodes on the canvas belong to it;
a dataset can also be added from the catalog without placing it on the canvas. A collection can be
exported at any point: datasets alone, before any integration, or with results and plans once they
exist.

### 2.2 Where each dataset came from

The manifest is only as good as the catalog behind it. Each catalog entry gains an `origin` record:

| Field | Example | Filled from |
|---|---|---|
| `source_url` | the dataset's page on NYC Open Data | portal ID |
| `portal_id` | `23z9-6uk9` | `descriptions_origin.csv` |
| `publisher` | NYC Department of Education | portal metadata |
| `license` | the portal's terms, or a named license | portal metadata |
| `retrieved_at` | the date the file was downloaded | file history, or asked |
| `source_updated_at` | the portal's last update at retrieval | portal metadata |
| `sha256` | the hash of the file UrbanTrace serves | computed |
| `derived_from` | how the served file differs from the raw download, if it does | recorded once |

A one-off script fills the record for the existing catalog from the portal IDs and the portal's
metadata; the upload form asks for source URL and license, and computes the hash. Entries whose
origin cannot be found are marked as such, and the manifest says so instead of leaving the field
out. The catalog keeps both `data/geojson` and `data/geojson_raw`; `derived_from` records what the
step between them did, so a manifest can point to the published data and still describe the file
that was used.

### 2.3 The export package

**Export collection** writes one zip:

| Part | Contents | Opens in |
|---|---|---|
| `datapackage.json` | a [Frictionless Data Package](https://datapackage.org/): one resource per dataset and per result, with path, format, SHA-256, row count, CRS, schema (the columns used, with types, units and value kinds), the `origin` record, the profile summary and the AutoDDG description | Frictionless tools for Python and R, data portals, any JSON reader |
| `data/sources/` | each selected dataset, optionally clipped to the study area and reduced to the columns used, as GeoParquet and GeoPackage | QGIS, ArcGIS, GeoPandas, R `sf`, DuckDB |
| `data/results/` | each integrated result, keyed by its target IDs (H3 cell, zone ID), in the same formats; H3 results also as a plain table of cell IDs and values | the same, plus spreadsheets |
| `data/analyses/` | each priority map (the composite index per zone, with its normalized inputs) and each delta map (the signed difference per zone and its tier), in the same formats; a JSON record of the weights, polarities, normalization and the Synthesis Agent's rationale | the same |
| `plan.json`, `manifest.json` | the urbanweave plan and its run manifest, with each step's report | `uw.Plan`, to rerun or extend in a notebook |
| `README.md` | the goal, the datasets and why each was chosen, what each integration did in plain words (from the reports), how each priority map was built
and what the Delta Maps showed, caveats (unmatched features, non-conserving methods, unknown origins), and a load snippet in Python and R | people |

Choices in the export dialog:

- **Embed or reference.** Sources can be embedded, or referenced by `source_url` and `sha256` so
  the package stays small and the recipient fetches the data and checks it. Referencing is the
  default above a size limit, and required when a dataset's license does not allow redistribution
  or its origin is unknown.
- **Clip and select.** Clip sources to the study area and keep only the columns used, or export
  them whole.
- **Formats.** GeoParquet and GeoPackage by default; GeoJSON and CSV as options for small data.

The same package can be produced without the interface: `GET /api/collections/<id>/export`
returns the zip, and a small Python function reads a package back into GeoDataFrames and a
`uw.Plan`.

### 2.4 Why these formats

- **Frictionless Data Package** is an open, plain-JSON standard for describing a set of data files,
  with libraries in Python, R and JavaScript, and it allows custom fields, which carry the origin
  records, value kinds and profile summaries. RO-Crate is the alternative if the packages are meant
  for research repositories; the two can be produced from the same collection.
- **GeoParquet** keeps types and is fast and compact for large data; **GeoPackage** is the
  single-file format desktop GIS opens without configuration.
- **urbanweave plans** carry the integration itself, so the recipient can rerun it on newer data
  rather than only receiving its output.

## 3. Integration on urbanweave

### 3.1 Nodes follow the plan model

| Node | Role | Plan element |
|---|---|---|
| **Source** | a vector dataset from the catalog; later a raster | `sources` |
| **Target** | an H3 grid at a resolution, a zones dataset; later OSM streets or intersections | `targets` |
| **Step** | a matching method plus one or more reductions | `steps` (`match` + `aggregate`) |
| **Result Map** | shows a step's output | |
| **Compare Maps** | the difference between two results on the same target | |

An edge from a Source (or a Step) to a Target, through a Step, is one integration. Chains are
steps that read earlier steps (`"source": "@step_id"`): points → H3 → neighborhoods, or points
→ neighborhoods directly. H3 becomes the default way to line variables up for comparison, not a
required stage, so a user who only wants zone values avoids the H3 resolution's effect on them.

A multivariate analysis is several steps onto the same target. Their outputs share the target's
IDs, so UrbanTrace joins them on `target_id` for display and comparison.

### 3.2 Operator choices from the registry

- `/api/operators` returns urbanweave's registry: methods, the geometries and supports they
  accept, parameters with units and defaults, the quantities each method provides, and its
  assignment (exclusive, normalized, independent, replicated, sampling).
- The Step node fills its dropdowns from the registry and filters them with `problems()` for the
  connected source and target geometries. The three hard-coded copies are deleted.
- `/api/plan/validate` calls `Plan.validate` before a run and returns problems keyed by step, so
  the canvas can mark the node at fault.

### 3.3 Value kinds

Each column used in a step has a value kind: **extensive** (counts and totals, which split with
space and are summed), **intensive** (averages, rates and medians, which are averaged by overlap)
or **categorical** (shares or a majority). urbanweave refuses a reduction that does not fit the
declared kind, such as summing median incomes.

- The default kind comes from the atlas-profiler 0.1.0 profiles (`data/metadata_v2`): its column
  types, plus name and unit cues. The user or the copilot confirms or changes it on the Source
  node. This replaces `_classify_variable`.
- Operator recommendation becomes "choose a method and reductions for this source geometry,
  target and value kind". The copilot gets the registry as context, and every suggestion is
  checked with `problems()` before it is shown. The heuristic fallback becomes a small table from
  (geometry, value kind) to a default method and reduction, also checked against the registry.
- Hotspot synthesis is interpretation, not integration, and stays in UrbanTrace unchanged.

### 3.4 Provenance from reports and manifests

- The provenance panel shows each step's urbanweave report beside the configuration and the
  copilot's rationale: sources matched and unmatched by cause (outside the grid, invalid geometry,
  beyond the kernel's reach), totals before and after, the measuring CRS, and whether totals are
  conserved. A surprising number on a map can then be explained from the panel.
- Saving an analysis writes the plan JSON (with the canvas layout as UrbanTrace's own metadata)
  and the run manifest. Opening one rebuilds the canvas; replay reruns it from pinned inputs and
  names any dataset that changed since.
- The same plans run in a notebook with `uw.Plan`, so an analysis built on the canvas can be
  continued, checked or published outside UrbanTrace.

### 3.5 Results in columns

`/api/plan/run` returns, per step, the target IDs plus one typed array per output column, as
JSON arrays at first and Arrow or GeoParquet if size calls for it. Geometry is sent once per
target (H3 cells need none: the client builds them from the IDs with `h3-js`). Variables stay
separate and the Result Map chooses which to color by. Autark's layers read typed arrays
directly.

### 3.6 Interface components and icons

The current Integration node is four dropdowns of operator names. The new model needs components
that explain each method, collect its parameters, and show what a run did. Most can be generated
from the registry, so a method added to urbanweave appears in UrbanTrace without new UI code.

**What the registry already describes.** For each matching method: accepted source and target
geometries and supports, `params` (type, default, unit, choices, minimum, required, a one-line
summary), the quantities it provides, its `assignment`, its `conservation` conditions, a summary,
and the legacy operators it `replaces`. For each reduction: the value kinds it suits, the
quantities it requires, its params and a summary. What it does not describe is presentation:
display labels, grouping, icons. Labels come from the names (`area_overlap` → "Area overlap");
groups and icons are UrbanTrace's.

**Components:**

| Component | What it does | Built from |
|---|---|---|
| **Method picker** | replaces the allocation and zoning dropdowns; methods grouped by what they do (containment, overlap, distance, kernel, sampling); unsupported methods shown disabled with the reason from `problems()` | registry, `problems()` |
| **Method card** | on hover or focus in the picker: a schematic figure of the method, its summary, and badges for its assignment and whether it conserves totals | registry; figures from urbanweave's tutorial diagrams |
| **Parameter form** | one control per param: number with its unit (`bandwidth` in m), choices as a segmented control, booleans as a toggle, required fields marked, minimums enforced | `params` |
| **Reduction list** | a step's reductions, each with column, output name, `fill_empty` and `where`; only reductions that suit the column's value kind and the method's quantities are offered | registry, value kinds |
| **Value-kind chip** | on each column of a Source node: extensive, intensive or categorical, defaulted from the profile, editable | profiles (section 3.3) |
| **Target nodes** | H3 (resolution with cell size and an estimated cell count), Zones (a catalog dataset); later Streets and Intersections | plan `targets` |
| **Report card** | on each Step and in the provenance panel: matched out of total, unmatched by cause, totals in and out, measuring CRS; expands to the sample of IDs per cause; a warning state on the node when much is unmatched | urbanweave reports |
| **Validation markers** | problems from `/api/plan/validate` on the node or edge at fault | `Plan.validate` |
| **Plan menu** | save, open, export JSON, replay; a replay names the inputs that changed | plans and manifests |

Copilot suggestions use the same picker, card and icons, so a recommendation looks like the choice
it proposes.

**Icons.** Lucide (`lucide-react` 0.575, already a dependency) fits the node types: `Hexagon` for
H3 targets, a map or shapes icon for zones, a route icon for streets. It has nothing for the
matching methods themselves, so they need a small custom set, drawn on Lucide's 24 px grid with
its 2 px stroke so they sit with the rest of the interface:

| Method | Glyph |
|---|---|
| `contain` | a dot inside a square |
| `centroid` | a polygon with a cross at its centre, inside a square |
| `representative_point` | a concave polygon with a dot inside it |
| `nearest` | a dot with an arrow to the closest of two shapes |
| `nearest_segment` | a dot with a perpendicular tick to a line |
| `nearest_node` | a dot with an arrow to a node where three lines meet |
| `within_distance` | a dot inside a dashed circle |
| `area_overlap` | two overlapping squares, the overlap filled |
| `length_weighted` | a line crossing a square, the inside part bold |
| `largest_overlap` | a polygon across two squares, the larger share filled |
| `polygon_to_lines` | a filled square with a line through it, the line bold inside |
| `gaussian` | a dot with fading concentric rings |
| `sample` | a filled cell with a dot taking its colour |

Reductions are clearer as typographic labels than as pictures (Σ, mean, med, min, max, mode, %,
per km²). Value kinds get small coloured chips with a letter (E, I, C) and a tooltip with the
definition.

Icons live in `frontend/src/components/icons/`, keyed by registry name, with a generic fallback so
an unknown method still renders. The method cards' figures come from urbanweave's
`tutorials/diagrams.py` (`contain()`, `area_overlap()`, `gaussian()`...), exported once as static
SVGs into UrbanTrace's assets, so the interface and the tutorials teach the methods with the same
pictures. Whether those figures should ship with urbanweave is already an open question there
(its DESIGN.md, section 10).

### 3.7 What leaves UrbanTrace

- `backend/operators/`, `backend/grids/`, `backend/integration_engine.py`, `backend/tests/test_kernel.py`
  (its cases are ported in urbanweave);
- `GEOMETRY_CONSTRAINTS` and the operator registries in `main.py`, the hard-coded operator lists in
  `IntegrationNode.jsx`;
- `OperationNode`, `/run-operation`, `h3_engine.py`, and the commented-out endpoint code, unless
  the H3 set operations are wanted back (they would then be urbanweave steps).

## 4. Beyond integration: data, analysis and reach

Since the paper was accepted, UrbanTrace gained atlas-profiler 0.1.0 profiles (time coverage,
fine-grained spatial density, histograms, HTML reports), AutoDDG descriptions in the interface, a
compact copilot catalog and Autark maps, and its operators grew into urbanweave (rasters, streets,
dasymetric disaggregation, reports, plans). Several of these produce information or capabilities
that nothing in UrbanTrace uses yet. The additions below put them to work.

### 4.1 Understanding the data

**Time.** The profiles describe time coverage for 70 of the 121 datasets: ranges, precision,
regularity, and gaps. UrbanTrace ignores it and will combine 2009 taxi trips with 2023 poverty
rates without comment.

- A time window on each source, applied before matching.
- A warning when the selected datasets' periods do not overlap, shown on the collection and in the
  export's caveats.
- Search filtered by period ("datasets covering 2019–2023").
- Later: time-binning steps (per month, per year) and a time slider on result maps. urbanweave lists
  temporal binning as an open question; this is the use that would settle it. Experts E3 and E4
  asked for temporal operators in the paper's interviews.

**Study area and coverage.** The profiles record where each dataset has data (a density grid of
geohash counts).

- A study area, drawn or picked from a zone layer, stored on the collection. It bounds the H3 grid,
  clips sources and exports, and filters search to datasets that cover it.
- A coverage view: where the selected datasets overlap and where they leave gaps, so a
  Manhattan-only dataset integrated with citywide ones is noticed before its zeros reach a priority
  map.

**Joining by identifier and address.** The profiles mark 278 columns as administrative areas
(BBL, BIN, ZIP code, community district...) and 145 as addresses. Many NYC Open Data tables have
such columns but no geometry, and the catalog cannot use them today.

- An attribute join from a table to a geometry layer on a shared identifier, suggested when the
  profiles find a matching pair, reporting matched and unmatched keys like any other step.
- Geocoding of address columns (E2's request), with match rates and unmatched rows reported.
  urbanweave lists geocoding on its roadmap; whether it lives there or in UrbanTrace is open.

**Rasters in the catalog.** urbanweave reads rasters, but the catalog and the profiler describe
vector files only. Heat, tree canopy, land cover and population surfaces need catalog entries,
profiles (extent, resolution, bands, units, nodata) and descriptions before raster sources mean
anything in the interface.

**Growing the catalog on demand.** Search NYC Open Data (and Auctus) from UrbanTrace, then
download, profile and describe a dataset when the analyst adds it. This removes the paper's
limitation of offline profiling, fills the `origin` record at the source, and is the path to
other cities.

### 4.2 Analysis

**Derived variables.** Rates per capita, ratios of two integrated variables, and filtered counts
are the most common reasons an analyst would leave the tool. A Calculate node computes a new column
from results on the same target (crashes per 1,000 residents), declares its value kind, and records
its formula in the collection. Filtered counts use urbanweave's `where` on reductions. The old
toolbox sketched Filter, Calculate Field and Join; those entries are commented out in
`frontend/src/config/operations.js`.

**Dasymetric disaggregation.** The paper's main future-work item, and `uw.dasymetric` already does
it: spread zone totals onto finer targets in proportion to a prior (tract population onto blocks by
building footprints or residential units). In the interface it is a Step variant with a second
input, the prior.

**Sensitivity sweeps.** The paper's thesis is that sensitivity to the spatial unit is information,
but the Delta Map compares two configurations. A sweep reruns one analysis over a set of
alternatives (H3 resolutions 7–9, two zone systems, alternative methods for one variable) and maps
how stable each zone's rank or hotspot status is, with the Delta Map available for any pair. This
needs plans (phase 4), since each alternative is a variant of the same plan.

**Validation against known outcomes.** Case Study 1 validated the priority map against 114 geocoded
program sites with capture and lift by quantile (Table 3 of the paper). A Validate node takes a
point layer of outcomes and a priority map and computes that table, so any analysis can be checked
the way the paper checked its own.

**Reports.** The experts asked for provenance with a narrative summary for municipal reports. A
report (HTML, printable to PDF) assembles the goal, the maps, the provenance graph, the copilot's
rationale, each step's report and the validation table. It ships in the export package beside the
data.

### 4.3 Reach

**An MCP server.** UrbanTrace's catalog search, profiles, collections and export, exposed as tools
for other assistants (Claude Code, notebook assistants). An analyst working in a notebook can then
ask for "the datasets in my after-school collection" and receive the package. This is export in
the other direction, and it reuses the copilot's tools.

### 4.4 Foundations

- **GeoParquet data lake.** The catalog is about 8.8 GB of GeoJSON. Stored as GeoParquet it loads
  faster, supports reading only the needed columns and rows, and export becomes a copy rather than a
  conversion. GeoJSON stays available for previews.
- **Configurable backend address.** The frontend hard-codes `http://localhost:8000` 12 times in 9
  files, which blocks a hosted instance. One configuration value (a Vite environment variable) and
  one API module replace them.
- **Tests and CI.** UrbanTrace has one test file (`backend/tests/test_kernel.py`), which moves to
  urbanweave in phase 0, and no CI. It needs API tests for each endpoint, a smoke test of a full
  integration on small catalog datasets, and a frontend build check, run on every pull request.

## 5. Order of work

The order below is a hypothesis about what analysts need first. Each phase ends with something an
analyst can use; after each one, the tool should be tried on real tasks (the paper's case studies,
the experts it interviewed, OSCUR partners), and the remaining phases reordered by what that shows.
Phases on the data side (1, 2, 6) and the integration side (3, 4) touch different code and can
overlap when people are available.

**Status (2026-11-20).** Phases 0 to 4 are built on the `autark-map` branch, each in its own commit,
with backend tests on synthetic data (no Git LFS data needed). Where the build departed from the
plan below:

- Phase 0 uses a thin adapter (`backend/weave_engine.py`) on urbanweave's public API rather than
  calling `compat.urbantrace.run` per variable, which would give each variable its own grid. It
  fixes three legacy bugs, named in `weave_engine.CHANGES`: edge features dropped by the grid
  (`grid_covers_sources`), the first variable's zoning mapping applied to all (`own_zoning_mapping`),
  and zone means counting other variables' cells as zeros (`own_cells_only`). Invalid polygons are
  repaired and reported. The 38 large corpus cases were not run.
- Phase 1: `data/origins.json` covers the 121 datasets; 96 were found on NYC Open Data, 25 were
  not, and no dataset states a license, so `embed="auto"` references rather than embeds. The
  GeoParquet conversion tool exists (`tools/convert_to_geoparquet.py`) but has not been run over
  the lake.
- Phase 4 keeps the classic Integration node (as "Spatial Integration (classic)") because the
  copilot's operator suggestions are not yet ported to Step nodes; plan steps use urbanweave's own
  defaults while the classic node keeps the legacy conventions. Derived variables are computed by
  UrbanTrace after the plan runs and recorded in the collection and the export README, since
  urbanweave plans have no calculation step.
- The interface was checked by building it, rendering it in headless Chrome, and driving one
  collection through open, run and report over the DevTools protocol; the Chrome extension was not
  available for interactive testing.

### Phase 0: foundations and the new engine

- Tag the current revision as `vis2026`, so the paper's results stay reproducible.
- Configurable backend address; API tests, a smoke test and CI (section 4.4).
- Pin `urbanweave` (the 0.1.0a1 prerelease) in `backend/requirements.txt`. Inside
  `/api/integrate_multivariate`, run each variable through `urbanweave.compat.urbantrace.run`. It
  takes UrbanTrace's operator names and returns its column names, wire units and weighting basis,
  so the request and response shapes stay the same. Serve `/api/operators` from
  `compat.urbantrace.operators_payload()`.
- Keep the old engine behind a switch (for example `URBANTRACE_ENGINE=legacy`) for one cycle, with
  the smoke test running both, then delete it.

Risk is low: urbanweave ran 319 operator cases on this catalog against a copy of the legacy code,
and every difference has a named cause (`compat.urbantrace.CHANGES`: `boundary_once`,
`utm_measurement`, `missing_not_zero`, `h3_index_lookup`, `overlap_basis`). Fifteen cases, on
three datasets with corrupt or mislabelled coordinates, are refused with the reason where the old
code crashed or ran on nonsense; the UI must show that reason instead of a generic failure. 38
cases were skipped for size and should run before the switch.

### Phase 1: catalog and collections

- The data lake as GeoParquet (section 4.4), then the `origin` record (section 2.2): the script
  that fills it from the NYC Open Data IDs and portal metadata, the source URL and license fields
  on upload, hashes for every served file.
- Collections stored on the server, with the goal, the selected datasets and columns, and the
  copilot's accepted rationale; the canvas reads and writes them.
- **Export collection** for datasets (section 2.3): `datapackage.json`, sources as GeoParquet and
  GeoPackage (embedded or referenced), and the README. Result Map downloads gain the same formats
  and a provenance record next to the data.

Only the GeoParquet loading touches the engine's inputs, so this phase can start alongside phase 0.

### Phase 2: study area, coverage and time

- The study area on the collection; it bounds the grid and clips sources and exports.
- The coverage view, and search filtered by area and period.
- Time windows on sources and warnings for periods that do not overlap (section 4.1).

### Phase 3: registry and reports in the interface

- The method picker, method cards and parameter form (section 3.6) replace the Integration
  node's dropdowns, filtered by `problems()`; icons for the methods that replace the legacy
  operators (`contain`, `centroid`, `area_overlap`, `length_weighted`, `nearest`, `gaussian`,
  `polygon_to_lines`, `sample`), reached through `compat.urbantrace.OPERATORS` while requests
  still use legacy names.
- Report cards on the node and in the provenance panel, from the reports that phase 0's responses
  carry.
- The copilot's operator recommendation reads the registry and is checked against it.
- Exports gain each integrated result under `data/results/`, with its report summarized in the
  README.

### Phase 4: plans and derived variables

- `/api/plan/validate` and `/api/plan/run`; the canvas converts to and from plan JSON.
- New nodes (Source, Target, Step) replace the Integration node, with the reduction list,
  value-kind chips (defaulted from the profiles, section 3.3), validation markers and the plan menu
  (save, load, replay).
- The Calculate node for derived variables, and filtered counts with `where` (section 4.2).
- Results in columns (section 3.5); the `count` sum goes away.
- urbanweave's own defaults replace the legacy conventions (section 6).
- Exports gain `plan.json` and `manifest.json`, and a package can be opened back into UrbanTrace
  or loaded in a notebook.

This is the largest change in the frontend: `IntegrationNode.jsx` and `AnalysisCanvas.jsx` (about
1,000 lines each) are mostly rewritten.

### Phase 5: analysis

- Sensitivity sweeps over resolutions, zone systems and methods, with rank-stability maps.
- The Validate node, and the report (section 4.2).
- Dasymetric disaggregation as a Step with a prior.
- Exports gain the analyses under `data/analyses/` and the report.

### Phase 6: more data and other tools

- Direct source → zones steps; more matching methods (`within_distance`, `largest_overlap`,
  `representative_point`) and reductions (`median`, `shares`).
- OSM streets and intersections as targets (`urbanweave[osm]`), with per-road-km densities, and
  icons for the remaining methods (`nearest_segment`, `nearest_node`, `within_distance`,
  `largest_overlap`, `representative_point`).
- Rasters in the catalog and the profiler, then raster sources through `zonal_stats`
  (`urbanweave[raster]`).
- Attribute joins on identifiers, and geocoding of addresses.
- Growing the catalog on demand from NYC Open Data and Auctus.
- The MCP server (section 4.3). It needs only the catalog, collections and export, so it can move
  up to any point after phase 1 if a consumer asks for it.

## 6. Decisions

- **Legacy or corrected defaults.** The compatibility layer keeps UrbanTrace's conventions: density
  per m², means weighted by allocation fraction, and grid rows only for cells that received a
  value. urbanweave's defaults are density per km², means weighted by overlap area, and missing
  stays missing. Switching changes numbers relative to the paper. Proposal: keep the legacy
  conventions through phase 3, switch in phase 4, and rely on the `vis2026` tag to reproduce the
  paper.
- **The operator-selection benchmark.** The study in `benchmark/` scores answers by the legacy
  operator names. `compat.urbantrace.OPERATORS` maps each one to urbanweave's method and reduction,
  so old answers can be scored against new ones, but the benchmark needs a rule for scoring answers
  in the new vocabulary, and the copilot's prompts change in phase 3.
- **H3 set operations.** Delete `OperationNode` and `/run-operation`, or bring intersect and union
  back as steps. Proposal: delete them; nothing on the canvas can create the node today.
- **Who owns the plan schema.** UrbanTrace should store plans in urbanweave's schema
  (`"version": 1`) and keep its own data (node positions, colors, copilot rationale) under a
  separate key, so a plan saved by UrbanTrace runs unchanged in a notebook. That needs a place for
  application metadata in urbanweave's schema, or a wrapper file in UrbanTrace. The collection
  (section 2.1) is the natural wrapper: it holds the plan unchanged beside UrbanTrace's own data.
- **Package standard.** Frictionless Data Package by default, with RO-Crate as a second output if
  packages are meant for research repositories (Zenodo, institutional archives)? Proposal:
  Frictionless first; add RO-Crate when someone deposits a package.
- **Redistribution.** Embedding data in a package redistributes it. Open data portals generally
  permit it, but the terms vary by publisher and dataset and have not been checked here; each
  license has to be recorded before export can decide, and until it is, sources with an unknown
  license are referenced, not embedded.
- **Size.** The catalog is about 8.8 GB of GeoJSON, and single datasets reach hundreds of MB. The
  size above which sources are referenced rather than embedded, and whether clipping to the study
  area is the default, need settling with real collections.

## 7. Open questions

- The registry's shape changes with `registry_version`; should the frontend refuse an unknown
  version or show what it can?
- Run results for large grids: cache them server-side by manifest, so linked views and comparisons
  do not rerun steps?
- Should the copilot be able to propose a whole plan from a goal (discovery, then steps), with the
  user accepting it node by node as datasets are accepted today?
- Should a collection be publishable from UrbanTrace (to a data portal or a repository), or is
  the downloaded package the end of UrbanTrace's job?
- Should the profiles in a package be the full atlas-profiler reports (HTML) or only the summary
  in `datapackage.json`?
- urbanweave's DESIGN.md names "UrbanTrace running on the compatibility layer in production" as
  one condition for its 0.1.0 release; phase 0 meets it.
