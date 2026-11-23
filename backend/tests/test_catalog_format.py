"""The copilot's catalog index: polygon datasets say how many polygons they have and what keys them."""
from catalog_format import dataset_details, index_entry, render_catalog, zone_keys


def _col(name, structural="Text", distinct=None):
    return {"name": name, "structural_type": f"http://schema.org/{structural}", "num_distinct_values": distinct}


NTA = {
    "geometricType": "MultiPolygon", "nb_rows": 262, "nb_columns": 6,
    "columns": [_col(":id", distinct=262), _col("borocode", "Integer", 5), _col("nta2020", distinct=262),
                _col("ntaname", distinct=262), _col("shape_area", "Float"), _col("geometry")],
}
SBA = {
    "geometricType": "MultiPolygon", "nb_rows": 55, "nb_columns": 5,
    "columns": [_col("Sub-Borough Area", distinct=55), _col("2019", "Integer", 55),
                _col("pop_est", "Integer", 55), _col("bor_subb", "Integer", 55), _col("geometry")],
}
POINTS = {"geometricType": "Point", "nb_rows": 1000, "nb_columns": 2,
          "columns": [_col("name", distinct=1000), _col("geometry")]}


def test_zone_keys_are_unique_identifiers_not_values():
    assert zone_keys(NTA) == ["nta2020", "ntaname"]          # not :id, not borocode (5 values)
    assert zone_keys(SBA) == ["Sub-Borough Area", "bor_subb"]  # not the year or a count


def test_polygon_lines_carry_the_count_and_keys():
    assert index_entry("NTA", NTA, "Neighborhoods.").endswith("[262 polygons, keys nta2020/ntaname]")
    assert "[55 polygons, keys Sub-Borough Area/bor_subb]" in index_entry("SBA", SBA, "Population.")


def test_other_lines_are_unchanged():
    assert index_entry("pts", POINTS, "Trees. More text.") == "- pts (Point, 2 columns): Trees."
    assert index_entry("x", {"geometricType": "Polygon", "columns": []}, "") == "- x (Polygon, 0 columns): no description"


def test_render_and_details():
    catalog = {"NTA": {"meta": NTA, "description": "Neighborhoods."}, "pts": {"meta": POINTS, "description": ""}}
    text = render_catalog("index", catalog)
    assert text.splitlines()[1].startswith("- NTA") and "keys nta2020" in text
    details = dataset_details(catalog, ["NTA", "nope"])
    assert "nta2020:Text" in details["datasets"] and details["unknown_ids"] == ["nope"]
