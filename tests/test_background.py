from paper_trends import background as bg


def _rec(title):
    return {"publication_year": 2020, "title": title, "abstract": None}


def test_build_pools_venues_into_fields_and_common_fields():
    corpora = {
        "ectc": [_rec("low cost hybrid bonding")] * 10,
        "eptc": [_rec("low cost hybrid bonding")] * 10,       # same field as ectc: must not count twice
        "iedm": [_rec("low cost transistor")] * 10,
        "isscc": [_rec("low cost amplifier")] * 10,
        "cvpr": [_rec("low cost segmentation")] * 10,
    }
    table = bg.build(corpora)
    assert set(table["fields"]) == {"packaging", "devices", "circuits", "vision"}
    assert table["fields"]["packaging"] == {"papers": 20, "venues": ["ectc", "eptc"]}
    assert bg.common_fields("low cost", "packaging", table) == ["circuits", "devices", "vision"]
    assert bg.is_common("low cost", "packaging", table)
    assert bg.common_fields("hybrid bonding", "devices", table) == ["packaging"]
    assert not bg.is_common("hybrid bonding", "devices", table)
    assert bg.common_fields("never seen", None, table) == []


def test_shipped_table_loads_and_knows_generic_phrases():
    table = bg.load()
    assert table and len(table["fields"]) >= 5
    assert bg.is_common("high performance", "packaging")
    assert not bg.is_common("hybrid bonding", "packaging")
    assert bg.field_of("ECTC") == "packaging" and bg.field_of("unknown-venue") is None
