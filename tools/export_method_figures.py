"""Export urbanweave's tutorial figures as SVGs for the method cards (docs/REDESIGN.md, section 3.6).

The figures are drawn by urbanweave's tutorials/diagrams.py (not part of the installed package), so
this reads them from an urbanweave checkout and writes frontend/public/methods/<figure>.svg plus
index.json, which maps each matching method to its figure. Rerun when the tutorials change.

    URBANWEAVE_REPO=../urbanweave python tools/export_method_figures.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("URBANWEAVE_REPO", ROOT.parent / "urbanweave")).resolve()
OUT = ROOT / "frontend" / "public" / "methods"

# figure function -> the methods it explains
FIGURES = {
    "contain": ["contain"],
    "centroid_and_representative_point": ["centroid", "representative_point"],
    "area_overlap": ["area_overlap", "largest_overlap"],
    "nearest_and_within_distance": ["nearest", "nearest_segment", "nearest_node", "within_distance"],
    "gaussian": ["gaussian"],
    "grid_to_targets": ["sample", "polygon_to_lines"],
    "along_lines_and_split": ["length_weighted"],
    "match_and_aggregate": [],
    "value_kinds": [],
}


def main():
    sys.path.insert(0, str(REPO / "tutorials"))
    try:
        import diagrams
    except ImportError as e:
        sys.exit(f"Cannot import diagrams from {REPO / 'tutorials'}: {e}")
    OUT.mkdir(parents=True, exist_ok=True)
    index = {"figures": {}, "methods": {}, "source": "urbanweave tutorials/diagrams.py"}
    for name, methods in FIGURES.items():
        fn = getattr(diagrams, name, None)
        if fn is None:
            print(f"skip {name}: not in diagrams.py", file=sys.stderr)
            continue
        fig = fn()
        (OUT / f"{name}.svg").write_text(fig.to_svg())
        index["figures"][name] = {"file": f"{name}.svg", "title": getattr(fig, "title", "")}
        for m in methods:
            index["methods"][m] = name
        print(f"{name}.svg", file=sys.stderr)
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n")


if __name__ == "__main__":
    main()
