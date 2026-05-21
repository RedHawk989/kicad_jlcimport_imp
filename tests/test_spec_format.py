"""Tests for the generalized spec-comparison renderer."""

from __future__ import annotations

from kicad_jlcimport.imp_lib.spec_format import (
    detect_kind,
    parse_spec_table,
    render_comparison,
)


def test_detect_kind_cap_from_mpn_when_description_lacks_specs():
    # Description has no value/voltage/dielectric — MPN does
    assert detect_kind("CSA0402C0G101F500GT", "0402 Multilayer Ceramic Capacitors MLCC") == "C"


def test_detect_kind_resistor():
    assert detect_kind("RC0402FR-0710KL", "10kΩ ±1% 0402 Chip Resistor") == "R"


def test_detect_kind_inductor():
    assert detect_kind("TNR4030S-3R9MTF", "3.9uH ±20% Wirewound Inductor 4030") == "L"


def test_detect_kind_led():
    assert detect_kind("XL-1608UBC-04", "Blue LED 1608") == "D"


def test_detect_kind_connector():
    assert detect_kind("TYPE-C-31-M-12", "USB Type-C Receptacle 24Pin") == "J"


def test_detect_kind_fet():
    assert detect_kind("AO3401A", "P-Channel MOSFET 30V SOT-23") == "Q"


def test_parse_spec_table_cap_uses_mpn():
    kind, rows = parse_spec_table("CSA0402C0G101F500GT", "0402 Multilayer Ceramic Capacitors MLCC")
    assert kind == "C"
    rd = dict(rows)
    assert rd["Value"] == "100pF"
    assert rd["Voltage"] == "50V"
    assert rd["Dielectric"] == "C0G"
    assert rd["Size"] == "0402"
    assert rd["Tolerance"] == "±1%"  # 'F' tolerance letter in MPN


def test_parse_spec_table_resistor():
    kind, rows = parse_spec_table("RC0402FR-0710KL", "10kΩ ±1% 0402 Chip Resistor 1/16W")
    assert kind == "R"
    rd = dict(rows)
    assert "10k" in rd["Value"]
    assert rd["Size"] == "0402"
    assert rd["Tolerance"] == "±1%"
    assert "W" in rd["Power"]


def test_parse_spec_table_inductor():
    kind, rows = parse_spec_table("TNR4030S-3R9MTF", "3.9uH ±20% 4030 Wirewound Inductor 3.5A")
    assert kind == "L"
    rd = dict(rows)
    assert "3.9" in rd["Value"]
    assert rd["Size"] == "4030"
    assert "A" in rd["Current"]


def test_parse_spec_table_led_color_from_mpn():
    kind, rows = parse_spec_table("XL-1608UBC-04", "1608 SMD LED")
    rd = dict(rows)
    assert kind == "D"
    assert rd["Color"] == "Blue"
    assert rd["Size"] == "1608"


def test_parse_spec_table_fallback_description():
    kind, rows = parse_spec_table("Mystery1234", "Some random part with no parseable spec")
    # Falls through to generic Description row
    assert rows[0][0] == "Description"


def test_render_comparison_caps_table_format():
    new = {"name": "CSA0402C0G101F500GT", "description": "0402 Multilayer Ceramic Capacitors MLCC"}
    cands = [
        {
            "name": "CL05C101JB5NNNC",
            "category": "Basic_Capacitors_Resistors",
            "description": "100pF 50V C0G ±5% 0402 MLCC",
            "tier": "basic",
        },
        {
            "name": "CC0402J101J500RT",
            "category": "Capacitor_SMD",
            "description": "100pF 50V C0G ±5% 0402 MLCC",
            "tier": "extended",
        },
    ]
    txt = render_comparison(new, cands, new_tier="extended")
    # Sanity: all critical labels present
    for needle in ["NEW:", "EXISTING (", "Value", "Voltage", "Dielectric", "Tolerance", "Size", "100pF", "50V", "C0G"]:
        assert needle in txt, f"missing {needle!r} in:\n{txt}"
    # Basic alternative warning appears since new is Extended
    assert "Basic alternative" in txt
    # Tolerance differs (new is ±1%, existing ±5%)
    assert "±5%" in txt
    assert "±1%" in txt


def test_render_comparison_handles_no_specs():
    """Connector-like part with no parseable specs still renders."""
    new = {"name": "WeirdConn", "description": "Some connector thing"}
    cands = [
        {
            "name": "OtherConn",
            "category": "Connector",
            "description": "A different connector",
            "tier": "other",
        }
    ]
    txt = render_comparison(new, cands)
    assert "NEW:" in txt
    assert "EXISTING" in txt
