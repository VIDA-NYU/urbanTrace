# The VIS 2026 paper and its supplementary material

**UrbanTrace: LLM-Assisted Discovery and Semantics-Aware Integration of Spatial Data**
Sonia Castelo, Eden Wu, Joao Rulff, Harish Doraiswamy, Juliana Freire, Claudio Silva.
Accepted to IEEE VIS 2026 (Full Papers Track); to appear in IEEE Transactions on Visualization and
Computer Graphics. [arXiv:2607.25124](https://arxiv.org/abs/2607.25124)

[`Supplementary_Material.pdf`](Supplementary_Material.pdf) is the paper's supplementary material
(submission #2151): the specifications and prompt templates of the three LLM agents (semantic data
discovery, the operator copilot and hotspot synthesis), the open benchmark (28 urban research
scenarios, the dataset-discovery and operator-selection ablations; see [`benchmark/`](../benchmark/README.md)),
and implementation details.

**Both describe an earlier version of UrbanTrace.** Integration then ran on UrbanTrace's own
operators (allocation, grid aggregation, zoning mapping and zone aggregation, as in the paper), through
a single Spatial Integration node whose operators the copilot recommended. The current version runs
on [urbanweave](https://github.com/VIDA-NYU/urbanweave) with plan steps instead; the main differences
are summarized in [docs/REDESIGN.md](../docs/REDESIGN.md).

To reproduce the paper's results, use the tagged revision:

```bash
git checkout vis2026-camera-ready
```
