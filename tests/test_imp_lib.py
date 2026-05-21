"""Tests for the imp-kicad-lib integration package."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from kicad_jlcimport.imp_lib import api
from kicad_jlcimport.imp_lib.categorize import categorize, reference_for
from kicad_jlcimport.imp_lib.dedupe import find_match
from kicad_jlcimport.imp_lib.discovery import find_imp_lib
from kicad_jlcimport.imp_lib.formatter import (
    imp_lib_paths,
    label_for,
    reformat_footprint,
    reformat_symbol,
    write_imp_lib_files,
)
from kicad_jlcimport.imp_lib.specs import cap_specs, ind_specs, res_specs

# ---------- specs ----------


def test_cap_specs_basic():
    s = cap_specs("100nF ±10% 50V Ceramic Capacitor X7R 0402")
    assert s is not None
    assert s["kind"] == "C"
    assert s["value_pF"] == 100_000
    assert s["voltage"] == 50
    assert s["dielectric"] == "X7R"
    assert s["size"] == "0402"
    assert s["label"] == "100nF/50V/X7R"


def test_cap_specs_uf():
    s = cap_specs("10uF 25V X5R 0805 Ceramic Capacitor")
    assert s["value_pF"] == 10_000_000
    assert s["label"] == "10uF/25V/X5R"


def test_cap_specs_missing_returns_none():
    assert cap_specs("Not a capacitor description") is None


def test_cap_specs_npo_normalised_to_c0g():
    s = cap_specs("22pF 50V NP0 0402 Ceramic Capacitor")
    assert s["dielectric"] == "C0G"


def test_res_specs():
    s = res_specs("6.8kΩ 50V 62.5mW Thick Film Resistor ±1% 0402 Chip Resistor")
    assert s["kind"] == "R"
    assert s["value_ohm"] == 6_800
    assert s["size"] == "0402"
    assert s["label"] == "6.8k"


def test_res_specs_milliohm():
    s = res_specs("10mΩ 150V 250mW Thick Film Resistor 0805")
    assert s["value_ohm"] == 0.01
    assert s["size"] == "0805"


def test_ind_specs():
    s = ind_specs("3.9uH ±20% SMD,4030 Power Inductors")
    assert s["kind"] == "L"
    assert s["value_nH"] == 3_900
    assert s["label"] == "3.9uH"


# ---------- discovery ----------


def test_find_imp_lib_via_gitmodules(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    lib = tmp_path / "lib"
    (lib / "symbols").mkdir(parents=True)
    (lib / "footprints").mkdir()
    (lib / "packages3d").mkdir()
    (tmp_path / ".gitmodules").write_text(
        textwrap.dedent("""\
            [submodule "lib"]
              path = lib
              url = https://github.com/impossible-inc/imp-kicad-lib.git
        """)
    )
    found = find_imp_lib(str(project))
    assert found is not None
    assert os.path.samefile(found, str(lib))


def test_find_imp_lib_fallback(tmp_path: Path):
    lib = tmp_path / "lib"
    (lib / "symbols").mkdir(parents=True)
    (lib / "footprints").mkdir()
    (lib / "packages3d").mkdir()
    found = find_imp_lib(str(tmp_path / "nowhere"), fallback_path=str(lib))
    assert found is not None
    assert os.path.samefile(found, str(lib))


def test_find_imp_lib_returns_none_when_not_found(tmp_path: Path):
    assert find_imp_lib(str(tmp_path)) is None


def test_find_imp_lib_rejects_incomplete_fallback(tmp_path: Path):
    # No subdirectories: should be rejected
    assert find_imp_lib(str(tmp_path), fallback_path=str(tmp_path)) is None


# ---------- categorize ----------


@pytest.mark.parametrize(
    "name,desc,want",
    [
        ("CL05B104KB54PNC", "100nF ±10% 50V Ceramic Capacitor X7R 0402", "Basic_Capacitors_Resistors"),
        ("CC0805KRX7R8BB104", "100nF X7R 25V Ceramic Capacitor 0805", "Capacitor_SMD"),
        ("OCV220M1VTR-0606", "22uF 35V Polymer Capacitor", "Capacitor_SMD"),
        ("0402WGF1002TCE", "10kΩ ±1% 0402 Thick Film Resistor", "Basic_Capacitors_Resistors"),
        ("ANR4030T3R9M", "3.9uH ±20% SMD,4030 Power Inductor", "Inductor"),
        ("BLM18PG121SN1D", "120Ω@100MHz ferrite bead, 0402", "BEAD"),
        ("XL-1608UGC-04", "Green LED 0603", "LED"),
        ("TYPE-C-31-M-12", "USB Type-C connector", "Connector_USB"),
        ("AO3401A", "P-Channel 30V MOSFET", "Transistor_FET"),
        ("MysteryIC123", "Some random thing", "to-be-organized"),
    ],
)
def test_categorize(name, desc, want):
    assert categorize(name, desc) == want


def test_reference_for_known():
    assert reference_for("Capacitor_SMD") == "C"
    assert reference_for("Inductor") == "L"
    assert reference_for("LED") == "D"


# ---------- formatter ----------


SAMPLE_SYMBOL = """  (symbol "TEST_CAP"
    (pin_names (offset 1.016))
    (in_bom yes)
    (on_board yes)
    (property "Reference" "U" (at 0 7.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "TEST_CAP" (at 0 -7.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "JLCImport-Imp:TEST_CAP" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Description" "100nF 50V X7R 0402 Ceramic Capacitor" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (symbol "TEST_CAP_0_1"
      (polyline (pts (xy 0 0)) (stroke (width 0.254) (type solid)))
    )
  )"""


def test_reformat_symbol_sets_reference_and_annotation():
    out = reformat_symbol(
        SAMPLE_SYMBOL,
        part_name="TEST_CAP",
        category="Capacitor_SMD",
        description="100nF 50V X7R 0402 Ceramic Capacitor",
        fp_lib_name="Capacitor_SMD__C",
        fp_name="C_0402",
    )
    assert '(property "Reference" "C"' in out
    assert '(property "Footprint" "Capacitor_SMD__C:C_0402"' in out
    assert "TEST_CAP_1_1" in out
    assert "100nF/50V/X7R" in out
    # Value gets hidden
    assert "(hide yes)" in out


def test_reformat_footprint_rewrites_model_path():
    fp = '(footprint "X" (model "${KIPRJMOD}/JLCImport-Imp.3dshapes/X.wrl" (offset (xyz 0 0 0))))'
    out = reformat_footprint(fp, "Capacitor_SMD", "X")
    assert "../../packages3d/Capacitor_SMD__C.3dshapes/X.step" in out
    assert ".wrl" not in out


def test_label_for_cap():
    assert label_for("Capacitor_SMD", "100nF 50V X7R 0402 Ceramic") == "100nF/50V/X7R"


def test_label_for_res():
    assert label_for("Basic_Capacitors_Resistors", "10kΩ ±1% 0402 Resistor") == "10k"


def test_imp_lib_paths_categorized(tmp_path):
    paths = imp_lib_paths(str(tmp_path), "Capacitor_SMD")
    assert paths["sym_dir"].endswith("symbols/Capacitor_SMD__C.kicad_symdir")
    assert paths["fp_lib_name"] == "Capacitor_SMD__C"


def test_imp_lib_paths_unorganized(tmp_path):
    paths = imp_lib_paths(str(tmp_path), "to-be-organized")
    assert "to-be-organized" in paths["sym_dir"]


# ---------- dedupe ----------


def _seed_lib(root: Path, category: str, name: str, description: str):
    d = root / "symbols" / f"{category}__C.kicad_symdir"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.kicad_sym").write_text(
        f'(kicad_symbol_lib (symbol "{name}" (property "Description" "{description}" (at 0 0 0))))\n'
    )
    (root / "footprints" / f"{category}__C.pretty").mkdir(parents=True, exist_ok=True)
    (root / "packages3d" / f"{category}__C.3dshapes").mkdir(parents=True, exist_ok=True)


def test_find_match_caps_strict(tmp_path: Path):
    _seed_lib(tmp_path, "Capacitor_SMD", "EXISTING", "100nF 50V X7R 0402 Ceramic")
    m = find_match(str(tmp_path), "Capacitor_SMD", "100nF 50V X7R 0402 Ceramic")
    assert m and m["name"] == "EXISTING"


def test_find_match_caps_higher_voltage_existing(tmp_path: Path):
    _seed_lib(tmp_path, "Capacitor_SMD", "EXISTING", "100nF 50V X7R 0402 Ceramic")
    m = find_match(str(tmp_path), "Capacitor_SMD", "100nF 16V X7R 0402 Ceramic")
    assert m and m["name"] == "EXISTING"  # existing 50V ≥ new 16V


def test_find_match_caps_lower_voltage_existing_skipped(tmp_path: Path):
    _seed_lib(tmp_path, "Capacitor_SMD", "EXISTING", "100nF 16V X7R 0402 Ceramic")
    m = find_match(str(tmp_path), "Capacitor_SMD", "100nF 50V X7R 0402 Ceramic")
    assert m is None  # existing 16V too low for new 50V request


def test_find_match_caps_different_dielectric(tmp_path: Path):
    _seed_lib(tmp_path, "Capacitor_SMD", "EXISTING", "100nF 50V X5R 0402 Ceramic")
    m = find_match(str(tmp_path), "Capacitor_SMD", "100nF 50V X7R 0402 Ceramic")
    assert m is None


def test_find_match_resistor(tmp_path: Path):
    _seed_lib(tmp_path, "Basic_Capacitors_Resistors", "EX_R", "10kΩ ±1% 0402 Resistor")
    m = find_match(str(tmp_path), "Basic_Capacitors_Resistors", "10kΩ ±1% 0402 Resistor")
    assert m and m["name"] == "EX_R"


def test_find_match_no_existing(tmp_path: Path):
    (tmp_path / "symbols").mkdir()
    m = find_match(str(tmp_path), "Capacitor_SMD", "100nF 50V X7R 0402 Ceramic")
    assert m is None


# ---------- write + api ----------


def test_write_imp_lib_files(tmp_path: Path):
    written, paths = write_imp_lib_files(
        imp_lib=str(tmp_path),
        part_name="TEST_CAP",
        fp_name="C_0402",
        category="Capacitor_SMD",
        description="100nF 50V X7R 0402 Ceramic Capacitor",
        sym_content=SAMPLE_SYMBOL,
        fp_content='(footprint "X" (model "${KIPRJMOD}/JLCImport-Imp.3dshapes/X.wrl"))',
        step_src=None,
    )
    assert any(p.endswith(".kicad_sym") for p in written)
    assert any(p.endswith(".kicad_mod") for p in written)
    sym = Path(written[0]).read_text()
    assert "100nF/50V/X7R" in sym


def test_try_contribute_not_found(tmp_path: Path):
    res = api.try_contribute(
        lib_dir=str(tmp_path),
        lib_name="JLCImport-Imp",
        part_name="X",
        fp_name="X",
        description="",
        sym_content="",
        fp_content="",
        config={"imp_lib_enabled": True, "imp_lib_path": "", "imp_lib_dedupe": True, "imp_lib_auto_push": False},
        log=lambda _msg: None,
    )
    assert res["status"] == "not_found"


def test_try_contribute_disabled(tmp_path: Path):
    res = api.try_contribute(
        lib_dir=str(tmp_path),
        lib_name="JLCImport-Imp",
        part_name="X",
        fp_name="X",
        description="",
        sym_content="",
        fp_content="",
        config={"imp_lib_enabled": False},
        log=lambda _msg: None,
    )
    assert res["status"] == "disabled"


def test_try_contribute_added_then_duplicate(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    lib = tmp_path / "lib"
    for sub in ("symbols", "footprints", "packages3d"):
        (lib / sub).mkdir(parents=True)
    (tmp_path / ".gitmodules").write_text(
        '[submodule "lib"]\n  path = lib\n  url = https://github.com/impossible-inc/imp-kicad-lib.git\n'
    )
    cfg = {
        "imp_lib_enabled": True,
        "imp_lib_path": "",
        "imp_lib_dedupe": True,
        "imp_lib_auto_push": False,  # avoid touching git
    }
    res = api.try_contribute(
        lib_dir=str(project),
        lib_name="JLCImport-Imp",
        part_name="TEST_CAP",
        fp_name="C_0402",
        description="100nF 50V X7R 0402 Ceramic Capacitor",
        sym_content=SAMPLE_SYMBOL,
        fp_content='(footprint "X" (model "${KIPRJMOD}/JLCImport-Imp.3dshapes/X.wrl"))',
        config=cfg,
        log=lambda _msg: None,
    )
    assert res["status"] == "added"
    assert res["category"] == "Capacitor_SMD"

    # Second time should detect duplicate
    res2 = api.try_contribute(
        lib_dir=str(project),
        lib_name="JLCImport-Imp",
        part_name="TEST_CAP2",
        fp_name="C_0402b",
        description="100nF 50V X7R 0402 Ceramic Capacitor",
        sym_content=SAMPLE_SYMBOL,
        fp_content="",
        config=cfg,
        log=lambda _msg: None,
    )
    assert res2["status"] == "duplicate"
    assert res2["match"] == "TEST_CAP"
