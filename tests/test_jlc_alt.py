"""Tests for live JLCPCB Basic-alternative lookup."""

from __future__ import annotations

from kicad_jlcimport.imp_lib.jlc_alt import find_jlc_basic_alternatives


def _make_search(results):
    def _fn(_query, page_size=20, part_type=None):
        assert part_type == "base"
        return {"total": len(results), "results": results}

    return _fn


def test_returns_basic_only_with_matching_spec():
    # Importing an Extended 100nF 50V X7R 0402 cap; one Basic match + one
    # Extended dropped + one wrong-value dropped.
    results = [
        {
            "lcsc": "C1001",
            "name": "CL05B104KO5NNNC",
            "description": "100nF 50V X7R 0402 MLCC",
            "type": "Basic",
            "price": 0.0042,
            "stock": 100000,
        },
        {
            "lcsc": "C9999",
            "name": "CCEXT222",
            "description": "100nF 50V X7R 0402 MLCC",
            "type": "Extended",
            "price": 0.012,
            "stock": 5000,
        },
        {
            "lcsc": "C1002",
            "name": "WrongValueCap",
            "description": "10nF 50V X7R 0402 MLCC",
            "type": "Basic",
            "price": 0.0044,
            "stock": 200000,
        },
    ]
    hits = find_jlc_basic_alternatives(
        "100nF 50V X7R 0402 MLCC",
        part_name="CSomeExt100nF",
        search_fn=_make_search(results),
    )
    assert len(hits) == 1
    assert hits[0]["lcsc"] == "C1001"


def test_returns_empty_when_spec_unparseable():
    hits = find_jlc_basic_alternatives("Some random connector", part_name="X", search_fn=_make_search([]))
    assert hits == []


def test_returns_empty_when_no_basic_matches():
    results = [
        {
            "lcsc": "C1",
            "name": "EXT",
            "description": "100nF 50V X7R 0402",
            "type": "Extended",
        }
    ]
    hits = find_jlc_basic_alternatives("100nF 50V X7R 0402", search_fn=_make_search(results))
    assert hits == []


def test_swallows_search_exceptions():
    def _boom(*_a, **_k):
        raise RuntimeError("network down")

    hits = find_jlc_basic_alternatives("100nF 50V X7R 0402", search_fn=_boom)
    assert hits == []


def test_voltage_downrating_rejected():
    # Existing Basic part is only rated 25V — caller wants 50V, so reject.
    results = [
        {
            "lcsc": "C1",
            "name": "LowV",
            "description": "100nF 25V X7R 0402 MLCC",
            "type": "Basic",
        }
    ]
    hits = find_jlc_basic_alternatives("100nF 50V X7R 0402 MLCC", search_fn=_make_search(results))
    assert hits == []
