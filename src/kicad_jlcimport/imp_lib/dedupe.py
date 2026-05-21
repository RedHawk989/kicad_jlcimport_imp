"""Detect functionally-identical parts already present in imp-kicad-lib.

A *strict same-spec* match means: same capacitance + voltage + dielectric + size
for a cap, same resistance + size for a resistor, same inductance + size for
an inductor.  This is conservative: if any of those fields are missing from
the existing or new description, the function returns None (no match) and the
plugin proceeds with the import.
"""

from __future__ import annotations

import os
import re

from .specs import cap_specs, ind_specs, res_specs

_DESC_RE = re.compile(r'\(property\s+"Description"\s+"([^"]*)"')
_NAME_RE = re.compile(r'\(symbol\s+"([^"]+)"')


def _iter_symbols(imp_lib_path: str, category: str):
    """Yield (path, name, description) for every symbol in the given category dir."""
    sym_dir = os.path.join(imp_lib_path, "symbols", f"{category}__C.kicad_symdir")
    if not os.path.isdir(sym_dir):
        return
    for fname in os.listdir(sym_dir):
        if not fname.endswith(".kicad_sym"):
            continue
        path = os.path.join(sym_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        name_match = None
        for m in _NAME_RE.finditer(text):
            n = m.group(1)
            if not re.search(r"_\d+_\d+$", n):
                name_match = n
                break
        if not name_match:
            continue
        desc_match = _DESC_RE.search(text)
        desc = desc_match.group(1) if desc_match else ""
        yield path, name_match, desc


def find_match(
    imp_lib_path: str,
    category: str,
    new_description: str,
) -> dict | None:
    """Look for a same-spec match.  Returns ``{"name": existing_part_name, "spec": ...}`` or None.

    For caps the match must agree on value (within 0.5%), voltage (existing ≥ new),
    dielectric, and size if both have one.  For resistors / inductors: value (within 0.5%)
    and size if both have one.
    """
    parsers = (
        ("C", cap_specs),
        ("R", res_specs),
        ("L", ind_specs),
    )
    new_spec = None
    for _, fn in parsers:
        new_spec = fn(new_description)
        if new_spec:
            break
    if not new_spec:
        return None

    for _, name, desc in _iter_symbols(imp_lib_path, category):
        if new_spec["kind"] == "C":
            existing = cap_specs(desc)
            if not existing or existing["dielectric"] != new_spec["dielectric"]:
                continue
            if abs(existing["value_pF"] - new_spec["value_pF"]) / max(new_spec["value_pF"], 1) > 0.005:
                continue
            if existing["voltage"] < new_spec["voltage"]:
                continue
            if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
                continue
            return {"name": name, "spec": existing["label"]}
        if new_spec["kind"] == "R":
            existing = res_specs(desc)
            if not existing:
                continue
            if abs(existing["value_ohm"] - new_spec["value_ohm"]) / max(new_spec["value_ohm"], 1e-6) > 0.005:
                continue
            if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
                continue
            return {"name": name, "spec": existing["label"]}
        if new_spec["kind"] == "L":
            existing = ind_specs(desc)
            if not existing:
                continue
            if abs(existing["value_nH"] - new_spec["value_nH"]) / max(new_spec["value_nH"], 1e-6) > 0.005:
                continue
            if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
                continue
            return {"name": name, "spec": existing["label"]}
    return None
