# UrbanTrace 🏙️

> LLM-assisted discovery and semantics-aware integration of urban spatial data.

UrbanTrace is a visual analytics system for combining heterogeneous geospatial datasets. You build an analysis as a node-based workflow on an infinite canvas: find datasets with the help of an LLM copilot, bring them onto a common H3 grid with explicit, inspectable operators, aggregate the results into reporting zones such as neighborhoods or ZIP codes, and compare how conclusions change across spatial configurations.

![Status](https://img.shields.io/badge/status-research_prototype-yellow)
![Stack](https://img.shields.io/badge/stack-React%20%2B%20FastAPI%20%2B%20Autark%20(WebGPU)-blue)

![UrbanTrace Screenshot](docs/screenshots/urbantrace_v4_preview.png)

---

## 📄 Paper

**UrbanTrace: LLM-Assisted Discovery and Semantics-Aware Integration of Spatial Data**
Sonia Castelo, Eden Wu, Joao Rulff, Harish Doraiswamy, Juliana Freire, Claudio Silva
*Accepted to IEEE VIS 2026 (Full Papers Track); to appear in IEEE Transactions on Visualization and Computer Graphics.*

[arXiv:2607.25124](https://arxiv.org/abs/2607.25124) · [PDF](https://arxiv.org/pdf/2607.25124) · [Supplementary material](Supplementary_Material.pdf)

The paper presents UrbanTrace as a visual analytics system that turns manual spatial data wrangling into a transparent, node-based workflow in which users collaborate with context-aware LLM agents. An offline profiler extracts semantic and geometric metadata from each dataset, which grounds the agents when they discover datasets and recommend integration operators. Three linked views show how analytical conclusions change across spatial configurations. The evaluation covers 28 urban scenarios; the dataset discovery and operator selection studies are in [`benchmark/`](benchmark/README.md).

If you use UrbanTrace, please cite:

```bibtex
@misc{castelo2026urbantrace,
  title         = {UrbanTrace: LLM-Assisted Discovery and Semantics-Aware Integration of Spatial Data},
  author        = {Castelo, Sonia and Wu, Eden and Rulff, Joao and Doraiswamy, Harish and Freire, Juliana and Silva, Claudio},
  year          = {2026},
  eprint        = {2607.25124},
  archivePrefix = {arXiv},
  primaryClass  = {cs.HC},
  doi           = {10.48550/arXiv.2607.25124},
  note          = {Accepted to IEEE VIS 2026; to appear in IEEE Transactions on Visualization and Computer Graphics}
}
```

---

## ✨ Features

### 🗂️ Data library (left sidebar)
- Lists the profiled datasets served by the backend, with geometry type, row count and column tags; search by name.
- **Info** opens a details view of a dataset's metadata profile.
- Drag a dataset onto the canvas to create a dataset node.
- Upload a new `.geojson`; the backend profiles it and writes its metadata so it joins the catalog.

### 🖼️ Analysis canvas (center)
Built on React Flow. The workflow is made of nodes:

| Node | What it does |
|---|---|
| **Dataset** | A source dataset with a map preview; color it by any numeric column. |
| **Spatial Integration** | Brings one or more variables onto an H3 grid and, optionally, into reporting zones, using the operators below. |
| **Result Map** | Shows an integration result as H3 cells or zones, with hotspot palettes. |
| **Compare Maps** | Takes two hotspot result maps and shows where values went up or down, with direction symbols. |

**Link Maps** syncs the camera across every map on the canvas.

### 🧭 Integration provenance (right sidebar)
Shows which datasets, variables and operators produced each result, so every number on a map can be traced back to its inputs and choices. Hovering or focusing a row highlights the result map it produced.

### ✨ Copilot (LLM agent)
- **Dataset discovery:** suggests datasets for an analysis goal from the catalog's metadata and descriptions; suggestions are added only when you accept them.
- **Operator recommendation:** proposes zoning operators per variable from its metadata statistics and geometry.
- **Hotspot synthesis:** interprets which direction of each variable signals a hotspot.

Operator recommendation and hotspot synthesis fall back to built-in heuristics when no LLM is configured or the copilot is disabled.

---

## 🧮 Integration model

An integration composes four operator families (`backend/integration_engine.py`), written as **I = A₂ ∘ Z_map ∘ A₁ ∘ R**:

| Step | Role | Operators |
|---|---|---|
| **R**, allocation | Distributes each source feature onto H3 cells | `BinaryContainment`, `BinaryCentroidContainment`, `ProportionalAreaWeighted`, `ProportionalLengthWeighted`, `NearestAssignment`, `GaussianKernel` |
| **A₁**, grid aggregation | Combines the allocated values in each cell | `SumAggregation`, `MeanAggregation`, `WeightedMeanAggregation`, `DensityAggregation`, `MajorityAggregation`, `MaxAggregation`, `MinAggregation`, `LengthWeightedAggregation` |
| **Z_map**, zoning mapping | Maps H3 cells to reporting zones | `CentroidZoning`, `AreaWeightedZoning`, `LengthWeightedZoning` |
| **A₂**, zone aggregation | Combines cell values in each zone | `SumZoning`, `WeightedMeanZoning`, `DensityZoning`, `MajorityZoning`, `MaxZoning`, `MinZoning`, `LengthWeightedZoning` |

Each allocation operator declares the geometry types it supports. Multivariate integrations run one track per variable and then merge them on the shared grid or zones.

The operators run on [urbanweave](https://github.com/VIDA-NYU/urbanweave), which measures in the local UTM zone, keeps missing values missing, and reports what each step matched and left out (`backend/weave_engine.py`; the reports are returned under `reports`). Each difference from the original operators has a name, listed in `weave_engine.CHANGES`. The original engine is kept for now and selected with `URBANTRACE_ENGINE=legacy`; the paper's results correspond to the tag `vis2026-camera-ready`. The plan for the next version is in [docs/REDESIGN.md](docs/REDESIGN.md).

---

## 🏗️ Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, React Flow (`@xyflow/react`), Lucide icons, Axios |
| Maps | [Autark](https://autarkjs.org/) `autk-map` (WebGPU), with an Esri light-gray basemap; `h3-js` |
| Backend | Python, FastAPI, GeoPandas, Shapely, H3 |
| Profiling | `datamart-profiler`; AutoDDG dataset descriptions |
| LLM | OpenAI, Hugging Face Inference Providers, or a Portkey gateway (configurable) |
| Data | GeoJSON, stored with Git LFS |

---

## 📁 Project structure

```text
urbantrace/
├── backend/
│   ├── main.py                  # FastAPI app and endpoints
│   ├── weave_engine.py          # Integrations on urbanweave (the default engine)
│   ├── integration_engine.py    # Original integration pipelines (URBANTRACE_ENGINE=legacy)
│   ├── operators/               # allocation/, aggregation/, zoning/
│   ├── grids/h3_grid.py         # H3 grid system
│   ├── h3_engine.py             # Quick H3 rasterization for previews
│   ├── llm_agent.py, tool.py    # Copilot (LLM agent and its tools)
│   ├── upload_new_data.py       # Upload, profiling and metadata generation
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── canvas/          # AnalysisCanvas and node types
│       │   ├── visualization/   # Autark map previews
│       │   ├── layout/          # Sidebars and provenance panel
│       │   ├── catalog/         # Dataset cards and details
│       │   ├── copilot/         # Copilot input and agent trace
│       │   └── toolbox/         # Operations toolbox
│       └── config/operations.js # Toolbox entries
├── data/                        # Dataset lake (Git LFS)
├── benchmark/                   # Discovery and operator-selection studies
├── notebook/case_study_1/       # Case study validation notebook
└── docs/screenshots/
```

---

## 🛠️ Setup

### Prerequisites
- **Node.js** 20.19+ (required by Vite 7)
- **Python** 3.10+
- **Git LFS**, to get the datasets
- A browser with **WebGPU** for the maps: a recent Chrome, Edge or Safari

### Data
The datasets are stored with Git LFS, about 17.7 GB in total. After cloning:

```bash
git lfs install
git lfs pull
```

To fetch only the app's datasets (`data/geojson`, about 8.8 GB): `git lfs pull --include="data/geojson/*"`. The dataset discovery benchmark reads `data/geojson_raw`; see [Data](#-data).

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install openai          # needed for the OpenAI and Hugging Face copilot; portkey-ai for Portkey
uvicorn main:app --reload --port 8000
```

The backend loads `backend/.env` automatically. The copilot is optional; without it, operator recommendation and hotspot synthesis use heuristics.

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai`, `huggingface` or `portkey` (default `portkey`) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI credentials and model (default `gpt-5-mini`) |
| `HF_TOKEN`, `HF_MODEL` | Hugging Face token and model, served through [Inference Providers](https://huggingface.co/docs/inference-providers) (default `openai/gpt-oss-120b`; append `:<provider>` to pin a provider) |
| `PORTKEY_API_KEY`, `PORTKEY_MODEL` | Portkey gateway credentials and model |
| `COPILOT_DISABLED` | Set to `1` to turn off every LLM call |
| `URBANTRACE_ENGINE` | `urbanweave` (default) or `legacy`, the original operators |
| `COPILOT_CATALOG` | How the dataset catalog is sent to the model: `index` (default), `compact` or `full` |

Tests use small synthetic datasets, so they need no LFS data:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The copilot needs a model that supports tool calling. With the default `index` catalog, each request carries one line per dataset (about 5k tokens for the 121 datasets), and the model reads the full description and columns of the datasets it is considering through a `get_dataset_details` tool. `compact` sends every dataset's description and columns tersely (about 42k tokens), and `full` sends the complete metadata (about 86k tokens, which needs a context window well above that). The formats are defined in `backend/catalog_format.py`; the dataset-discovery benchmark can compare them with `--ablation catalog_compact` or `--ablation catalog_index`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

The app runs at **http://localhost:5173**. It expects the backend at `http://localhost:8000`; set `VITE_API_BASE_URL` (for example in `frontend/.env.local`) to use another address.

The maps use Autark's `autk-map`. On this branch it is linked from a local Autark checkout (`file:../../autark/autk-map` in `frontend/package.json`), because the tile basemap is not yet in the npm release; clone and build Autark next to this repository, or switch the dependency to a published version that includes tile layers.

---

## 🌐 API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/datasets` | Catalog: datasets with their metadata |
| GET | `/dataset/{name}?simplify=` | A dataset as GeoJSON (WGS84), optionally simplified |
| POST | `/datasets/upload` | Upload and profile a GeoJSON file |
| GET | `/api/operators` | Available operators and geometry constraints |
| POST | `/api/integrate_multivariate` | Run a multivariate integration |
| POST | `/run-operation` | Quick H3 preview, union or intersection |
| POST | `/api/copilot/chat` | Copilot chat with the current canvas as context |
| POST | `/api/v1/copilot/recommend-operators` | Zoning operator recommendations |
| POST | `/api/v1/copilot/synthesize-hotspot` | Hotspot direction per variable |

---

## 📦 Data

The data lake covers 121 profiled NYC datasets, including demographics, income and poverty, housing, air quality and heat vulnerability, crime and collisions, pedestrian and bicycle counts, schools, libraries, street trees and taxi trips, plus reporting zones (NTAs, MODZCTA ZIP areas, community districts and council districts).

| Path | Contents |
|---|---|
| `data/geojson/` | Datasets used by the app, by name |
| `data/metadata/` | Metadata profile for each dataset |
| `data/geojson_raw/`, `data/metadata_raw/` | The same datasets by their NYC Open Data IDs, used by the discovery benchmark |
| `data/descriptions_ddg.csv` | AutoDDG descriptions, generated from the profiles |
| `data/descriptions_origin.csv` | Original source-catalog descriptions |

Some source datasets contain bad geocodes outside NYC; map previews frame the area where most features are.

---

## 🔬 Benchmark and case study

- [`benchmark/`](benchmark/README.md): the dataset discovery ablation (28 scenarios, five metadata conditions, two LLM backbones) and the operator selection study, with scripts and results.
- [`notebook/case_study_1/`](notebook/case_study_1/): validation notebook for the NYC after-school case study.

---

*Last updated: November 2026*
