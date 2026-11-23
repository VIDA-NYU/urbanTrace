# Changelog

## 2.0.0-alpha.1 — unreleased

The first alpha of 2.0: the interface, the collection format and exports may still change before
2.0.0. A redesign. UrbanTrace 1.0 (the version in the VIS 2026 paper) integrated datasets through its own
fixed pipeline (sources onto an H3 grid, then optionally onto zones) and kept its results in the
browser. 2.0 runs every integration on [urbanweave](https://github.com/VIDA-NYU/urbanweave), builds
analyses as urbanweave plans, and produces collections: a goal, sources with their provenance,
steps, analyses and a report, saved on the server and exported as packages other tools can open and
rerun. Why and how is in [docs/REDESIGN.md](docs/REDESIGN.md); [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)
and [docs/CASE_STUDY_2.md](docs/CASE_STUDY_2.md) show it in use.

To reproduce the paper, check out `vis2026-camera-ready` (1.0).

### Collections, catalog and export

- **Collections** saved on the server (`urbantrace.collection/1`): name, goal, datasets and why they
  were chosen, study area, the canvas, analyses. Unsaved changes survive a reload.
- **Study area** (zones from a dataset, optionally filtered, or a box): narrows search, clips sources
  before they are combined, bounds grids and exports. **Coverage** map and **checks** (periods that do
  not overlap, datasets with little or no data in the area).
- **Catalog** search filtered by study area (each dataset's share of it) and years; **origins** for
  every dataset (publisher, source URL, license when recorded) and file hashes.
- **Export**: a [Frictionless](https://datapackage.org/) data package with the sources (embedded when
  their license allows, referenced otherwise), results, analyses, `plan.json`, `manifest.json`, the
  report and a README with rationale, caveats and license terms. Packages import back as collections.
  Exports and saved collections record the UrbanTrace and urbanweave versions.
- **Report**: a printable page of the collection.

### Integration on urbanweave

- **Step** nodes: a source onto a target (zones, an H3 grid, street segments or intersections) with
  a matching method and reductions from urbanweave's registry; each column has a value kind
  (extensive, intensive, categorical). Methods that do not fit are disabled with the reason; each
  has a figure.
- **Reports** on every step: what matched, what was left out and why, and how it was measured.
- **Join on a key**: rows added to the zone whose code matches (ZIP, BBL, district).
- **Combine & Calculate**: derived variables from steps that share a target.
- **Plans**: the canvas is an urbanweave plan; runs are recorded in manifests and can be replayed.
- **Streets (OSM)**: the study area's street network from OpenStreetMap as a target (per segment, per
  intersection, per km of street).
- **Rasters** with zonal statistics (exact cell coverage): tree canopy from NYC's 2021 6-inch land
  cover and from NLCD.
- Fixes over 1.0's engine: densities measured in metres (1.0 used Web Mercator areas, about 1.74×
  off at NYC's latitude), missing values kept missing instead of zero, points on a cell boundary
  counted once, invalid polygons repaired and reported.

### Data quality

- **Check data** (atlas-clean): swapped coordinates, wrong coordinate systems, invalid or empty
  geometry, duplicates, ...; accepted fixes saved as recipes and replayed whenever a dataset loads.
- **Locate rows from their addresses** with NYC GeoSearch, on request, each answer checked.
- Whole NYC Open Data datasets fetched again without the old 500,000-row cap
  (`tools/fetch_open_data.py`); the street-tree inventory now has all 1,125,266 trees.

### Analyses

- **Sensitivity sweep** across resolutions, zone systems and methods; **Validate** against outcome
  points (coverage, baseline, lift); **Dasymetric** disaggregation with priors.
- **Priority maps** (the paper's Multivariate Priority Map) are opt-in: a Combine & Calculate result
  opens as one, other multi-column results have a Priority button. The copilot's directions and
  weights follow the collection's goal and do not count a total and its parts twice; recorded with
  the collection and recomputed in exports.
- **Spatial Delta Map** between two priority maps, on plan results.
- **Integration Provenance Graph** (datasets, matching methods, aggregations, with the reasons) on plan
  results.

### Copilot

- Suggestions for datasets, step methods and priority weights, each checked (methods against
  urbanweave's registry) and applied only when accepted.
- Works without an LLM, by rules; rules that cannot judge say so instead of guessing.
- The **LLM** chip turns an LLM on or off and chooses it; the backend finds working keys at startup
  (none is entered in the interface). Local models through any OpenAI-compatible server.

### Interface

- Maps drawn with [Autark](https://autarkjs.org/) (WebGPU), with a basemap, picking and tooltips.
- A canvas that zooms out to fit large workflows and places new results in free space.

### Removed

- The classic Integration node, `/api/integrate_multivariate` and UrbanTrace's own integration
  engine; the zoning recommendation; `OperationNode` and `/run-operation`. Collections that used the
  classic node open without it and say so.
- The paper's operator-selection benchmark scores answers in 1.0's operator vocabulary: run it
  against `vis2026-camera-ready`.

### License

- MIT (New York University). Datasets keep their own terms.

## 1.0 — VIS 2026 paper

The version described in *UrbanTrace: LLM-Assisted Discovery and Semantics-Aware Integration of
Spatial Data* (IEEE VIS 2026), tagged `vis2026-camera-ready`.
