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
- [ ] Check: only Brooklyn's neighborhoods, coloured by count; about 60 libraries in total (Brooklyn's
  branches), not 253 (citywide); the report card says how many matched and how many were left out, and why
- [ ] Repeat with `NYC_Schools` as source and the same NTA target, output `schools`
- [ ] Optional: **Combine & Calculate** with both steps, e.g. `schools / (libraries + 1)`

Possible confusion: the two handles aren't labelled at the handles, only by the rows beside them.

Notes:

## 4. Analyse

- [ ] **Sensitivity Sweep** on the libraries step: is the top 20% stable across variants?
- [ ] **Validate** with schools as outcome points: is the table understandable?

Notes:

## 5. Keep and share

- [ ] **Save**, reload the page, **open** the collection: does it come back intact?
- [ ] **Report**: is it something you'd hand to someone?
- [ ] **Export**, unzip, read `README.md` and `datapackage.json`
- [ ] Load the data in a notebook with the README's snippet

Notes:

## Things to note

Anything that fits these, wherever it happens:

- Didn't know what to click next
- Labels or words that don't make sense
- Slow
- Expected but missing (a dataset, a method, an output format)

Notes:
