# Tryout: libraries and schools by neighborhood in Brooklyn

Started 2026-11-22. One task through every new part of UrbanTrace (phases 1–5). Tick steps as you
go and write notes under each step. Fixes go to the "Tryout fixes" section of [PLAN.md](../PLAN.md).

## Before you start: the collection bar

The collection is what UrbanTrace produces: the datasets picked for one analysis, plus what makes
them reusable. That means what they're for, where and when, how they were combined, and where each
came from. The canvas fills it as you work; the bar at the top of the canvas names it and acts on it.

| Item | What it does |
|---|---|
| **Name** | The collection's name. It titles the report and the export. |
| **Add a goal** | One or two sentences on what the data is for. It goes into the README and report so someone else knows why these datasets were picked. |
| **No study area** | Where the analysis is. It narrows search to datasets that cover the area, builds grids over it, and clips data and exports to it. |
| **Grid icon** | Coverage: how much of the study area each dataset on the canvas actually reaches. |
| **✓ / ⚠** | Checks. They warn when datasets' time periods don't overlap, or when a dataset misses most of the study area. |
| **Saved / Unsaved** | Whether the canvas has changes not yet saved to the server. |
| **New, Open, Save** | Collections are stored on the backend. Open also imports an exported zip. |
| **Plan** (once there are Step nodes) | Run all steps and record the run, replay a recorded run, download `plan.json`. |
| **Report** | A printable page for people: datasets, sources, maps, analyses, caveats. |
| **Export** | A zip for other tools: the data, `datapackage.json` describing it, the README, and the plan to rerun it. |

The left half says what the analysis is for and where it applies; the right half saves it and gets
it out to people or other tools.

Worth judging while you use it: the bar mixes three kinds of things (what the collection is, checks
on its data, and file actions) in one row.

## Setup

Backend on `localhost:8000` (`cd backend && ./venv/bin/uvicorn main:app --port 8000`),
frontend on `localhost:5173` (`cd frontend && npm run dev`).

## 1. Set up the collection (bar at the top)

- [ ] Name the collection
- [ ] **Add a goal**, e.g. "Neighborhoods in Brooklyn with schools but few libraries"
- [ ] **No study area** → NTA neighborhoods, filtered to borough = Brooklyn
- [ ] Sidebar: tick **In study area**; does the dataset list shrink sensibly?

Notes:

## 2. Bring in data

- [ ] Drag `NYC_libraries`, `NYC_Schools` and `NTA_Neighborhood…` onto the canvas
- [ ] Coverage (grid icon in the bar): does each dataset's share of Brooklyn look right?

Notes:

## 3. Build two steps (toolbox → Plan (urbanweave))

**What it's for.** The datasets don't share units yet: libraries and schools are points,
neighborhoods are polygons. A Step turns one dataset into a number per unit you choose, e.g. "how
many libraries in each Brooklyn neighborhood". Every Step has three parts:

- **Source**: the data being counted or summarised (libraries).
- **Target**: the units the result is reported in (NTA neighborhoods, or an H3 hexagon grid).
- **How the two are joined and summarised**: *Matching* decides which neighborhood each library
  belongs to; *Aggregate* decides what to compute per neighborhood (a count, a sum of a column, a
  mean, ...).

Doing it for libraries and for schools gives two per-neighborhood numbers that can be mapped,
compared and combined; the rest of the tryout builds on them.

**What to do**

- [ ] **Add the Step**: drag **Step** from the toolbox onto the canvas
- [ ] **Connect it**: the Step has two handles on its left edge
  - upper (purple) = **Source**: drag from `NYC_libraries`' right-hand handle to it
  - lower (light blue) = **Target**: drag from the NTA dataset to it
  - the Step's Source and Target rows should name the datasets ("NYC libraries · Point")
- [ ] **Matching**: open the picker and hover the options. `contain` (point inside polygon) fits
  points into neighborhoods. Methods that don't fit should be greyed out with a reason
- [ ] **Aggregate**: click **+ add**; a row appears with `count`. Rename the output (e.g.
  `libraries`) and leave "0 when empty" ticked, so neighborhoods with no library show 0, not missing
- [ ] **Run step**: a result map opens and a report card appears on the Step
- [ ] Check: Brooklyn's 69 neighborhoods, coloured by count; the summary on the map says 68 libraries
  in total (not 253, the citywide count), 0–3 per neighborhood, 25 with none; the report card says
  "68 of 253 in study area · 68/68 matched · 44/69 targets"; hovering a neighborhood shows its name
- [ ] Repeat with `NYC_Schools` as source and the same NTA target, output `schools`
- [ ] Optional: **Combine & Calculate** with both steps, e.g. `schools / (libraries + 1)`

Possible confusion: the two handles aren't labelled at the handles, only by the rows beside them.

Notes:

## 4. Analyse

**What it's for.** Step 3 produced numbers per neighborhood. Step 4 asks how far to trust them,
in two ways:

- **Sensitivity sweep: would the answer change with other reasonable choices?** The libraries count
  depends on choices you made: neighborhoods as units, `contain` as the method. The sweep reruns the
  step with alternatives (an H3 grid, other zones such as community districts, another method),
  brings each result back to the neighborhoods, and ranks them. Neighborhoods in the top under every
  variant are robust findings; those in the top only under some depend on the choice.
- **Validate: does the ranking line up with something observed?** It takes the units ranked highest
  by a result and counts how many outcome points (here, youth program sites) fall in them, compared
  with what their share of units would predict.

**Sensitivity sweep**

- [ ] Drag **Sensitivity Sweep** (toolbox → Analysis) onto the canvas; connect the **libraries Step**
  (or its Result Map) to its left handle. The node says "Reruns step_1 under each alternative"
- [ ] **Column**: `libraries`
- [ ] Alternatives: tick H3 resolution **8**; under **Through other zones** pick `Community_Districs`;
  tick another matching method if one is offered
- [ ] Leave **top** at 20% and click **Run**
- [ ] Read the result: "N of 69 units are in the top under every variant; M only under some", the
  agreement between variants (Spearman, 1 = same ranking), and any variant that couldn't run, with
  its reason. The map shows how often each neighborhood is in the top
- [ ] Does the summary make sense? Is it clear what a "variant" is?

**Validate against outcomes**

- [ ] Drag `dycd_program_sites` (youth and community program sites, 2020–22; 3,036 in Brooklyn) onto
  the canvas
- [ ] Drag **Validate** (toolbox → Analysis); connect the **Combine & Calculate** node (or the
  schools Step) to its upper handle (**Result**) and `dycd_program_sites` to its lower handle
  (**Outcomes**)
- [ ] **Column**: `schools_per_library`; keep the quantiles `0.5, 0.6, 0.7`; click **Run**
- [ ] Read the table, one row per quantile (0.7 = the top 30% of neighborhoods):
  - **Coverage**: the share of program sites inside those top neighborhoods
  - **In top**: how many program sites that is
  - **Baseline**: the share of neighborhoods that are in the top (what coverage would be by chance)
  - **Lift** = coverage / baseline. Above 1: program sites concentrate in the neighborhoods your
    ratio ranks highest; below 1: they're elsewhere
  - A note appears when tied values put more units at the threshold than the quantile implies
- [ ] Is the table understandable without this explanation?

The libraries-and-schools question has no true outcome here, so read the lift as "do youth programs
already sit where schools outnumber libraries?", not as proof the ranking is right.

Notes:

## 5. Keep and share

**What it's for.** This is what UrbanTrace produces: a collection someone else (or you, later, in
another tool) can pick up without redoing your work. Three outputs:

- **The saved collection**: on the server, reopened in UrbanTrace. Holds the canvas and its settings,
  not the results (they are rerun).
- **The report**: a printable page for people: goal, datasets and where they came from, maps of each
  result, the analyses' tables, caveats.
- **The export**: a zip for other tools (QGIS, GeoPandas, R, a notebook): the data, a
  `datapackage.json` describing it, a README, and the plan to rerun the steps with urbanweave.

**Saved collection**

- [ ] **Save**, reload the page: it reopens the collection (no results; that's expected)
- [ ] Rerun with **Plan → Run all steps and record the run**: results come back, and the run is kept
  with a manifest so it can be replayed later (**Plan → Replay**)

**Report**

- [ ] Click **Report**: a page opens in a new tab
- [ ] Is it something you'd hand to someone? What's missing or in the way?

**Export**

- [ ] Click **Export**. Under **Datasets**, choose **Embed every dataset** for this tryout: no dataset
  in the catalog records a license yet, so the default embeds none and only references them by URL
- [ ] Keep GeoParquet and GeoPackage; click **Download zip** and unzip it
- [ ] Read `README.md`: does it explain what's there, why, and how to load it?
- [ ] Skim `datapackage.json`: one entry per dataset and result, with source, hash and description
- [ ] `plan.json` and `manifest.json`: the steps as urbanweave runs them, and the recorded run
- [ ] Open a result in QGIS, or load it in a notebook with the README's snippet
- [ ] Optional: **Open → import zip** brings the package back into UrbanTrace as a collection

Notes:

## Things to note

Anything that fits these, wherever it happens:

- Didn't know what to click next
- Labels or words that don't make sense
- Slow
- Expected but missing (a dataset, a method, an output format)

Notes:
