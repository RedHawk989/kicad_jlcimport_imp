"""Detect functionally-identical parts already present in imp-kicad-lib.

Match precedence:
    1. Exact part name match anywhere in imp-kicad-lib (any category).
    2. Same LCSC C-number anywhere in imp-kicad-lib.
    3. Same-spec match within the target category and any cross-related
       category (caps also check Basic_Capacitors_Resistors and
       Extended_Capacitors_Resistors; resistors check Basic + Extended).

Same-spec means: same value (within 0.5%), same size if both specify one,
same dielectric for caps, and existing voltage >= new voltage.  If specs
can't be parsed from either side, that branch is skipped.
"""

from __future__ import annotations

import os
import re

from .specs import cap_specs, ind_specs, res_specs

_DESC_RE = re.compile(r'\(property\s+"Description"\s+"([^"]*)"')
_NAME_RE = re.compile(r'\(symbol\s+"([^"]+)"')
_LCSC_RE = re.compile(r"\bC\d{4,}\b")

# When the part's natural category is the key, also dedupe against these
# sibling categories (where equivalent parts often already live).
_RELATED = {
    "Capacitor_SMD": ("Basic_Capacitors_Resistors", "Extended_Capacitors_Resistors"),
    "Basic_Capacitors_Resistors": ("Extended_Capacitors_Resistors", "Capacitor_SMD"),
    "Extended_Capacitors_Resistors": ("Basic_Capacitors_Resistors", "Capacitor_SMD"),
}


def _all_category_dirs(imp_lib_path: str) -> list:
    sym_root = os.path.join(imp_lib_path, "symbols")
    if not os.path.isdir(sym_root):
        return []
    out = []
    for d in os.listdir(sym_root):
        if d.endswith(".kicad_symdir"):
            out.append((d[: -len(".kicad_symdir")], os.path.join(sym_root, d)))
    return out


def _iter_symbols_in_dir(sym_dir: str):
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


def _iter_symbols(imp_lib_path: str, categories: list):
    for cat in categories:
        sym_dir = os.path.join(imp_lib_path, "symbols", f"{cat}__C.kicad_symdir")
        for path, name, desc in _iter_symbols_in_dir(sym_dir):
            yield cat, path, name, desc


def _find_by_name(imp_lib_path: str, part_name: str):
    target = part_name.lower()
    for cat, _path in _all_category_dirs(imp_lib_path):
        sym_path = os.path.join(_path, f"{part_name}.kicad_sym")
        if os.path.isfile(sym_path):
            return cat, part_name
        # case-insensitive fallback
        for fname in os.listdir(_path):
            if fname.lower() == f"{target}.kicad_sym":
                return cat, fname[: -len(".kicad_sym")]
    return None


def _find_by_lcsc(imp_lib_path: str, lcsc_code: str):
    for cat, sym_dir in _all_category_dirs(imp_lib_path):
        for _path, name, desc in _iter_symbols_in_dir(sym_dir):
            if lcsc_code in (desc or "") or lcsc_code in name:
                return cat, name
    return None


def find_match(
    imp_lib_path: str,
    category: str,
    new_description: str,
    part_name: str = "",
) -> dict | None:
    """Look for a same-spec or exact-identity match.

    Returns ``{"name": existing_name, "category": cat, "spec": label, "reason": str}``
    or ``None``.
    """
    # 1) exact part-name match anywhere in the lib
    if part_name:
        hit = _find_by_name(imp_lib_path, part_name)
        if hit:
            cat, name = hit
            return {"name": name, "category": cat, "spec": name, "reason": "same part name"}

    # 2) LCSC C-number identity
    lcsc_codes = set(_LCSC_RE.findall(part_name)) | set(_LCSC_RE.findall(new_description or ""))
    for code in lcsc_codes:
        hit = _find_by_lcsc(imp_lib_path, code)
        if hit:
            cat, name = hit
            return {"name": name, "category": cat, "spec": code, "reason": f"same LCSC code {code}"}

    # 3) parse new part specs
    new_spec = None
    for fn in (cap_specs, res_specs, ind_specs):
        new_spec = fn(new_description)
        if new_spec:
            break
    if not new_spec:
        return None

    # search the target category plus any siblings
    cats = [category] + list(_RELATED.get(category, ()))
    for cat, _path, name, desc in _iter_symbols(imp_lib_path, cats):
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
            return {"name": name, "category": cat, "spec": existing["label"], "reason": "same C spec"}
        if new_spec["kind"] == "R":
            existing = res_specs(desc)
            if not existing:
                continue
            if abs(existing["value_ohm"] - new_spec["value_ohm"]) / max(new_spec["value_ohm"], 1e-6) > 0.005:
                continue
            if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
                continue
            return {"name": name, "category": cat, "spec": existing["label"], "reason": "same R spec"}
        if new_spec["kind"] == "L":
            existing = ind_specs(desc)
            if not existing:
                continue
            if abs(existing["value_nH"] - new_spec["value_nH"]) / max(new_spec["value_nH"], 1e-6) > 0.005:
                continue
            if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
                continue
            return {"name": name, "category": cat, "spec": existing["label"], "reason": "same L spec"}
    return None
