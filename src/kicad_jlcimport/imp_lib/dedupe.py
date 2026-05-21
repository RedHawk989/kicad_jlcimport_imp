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

# Tokens of length >= 3 used for fuzzy "shared family" matching.  Excludes
# very common short strings.  The list of stop-tokens keeps it from matching
# every part on words like "smd" / "rohs".
_TOKEN_RE = re.compile(r"[A-Za-z0-9]{3,}")
_STOP_TOKENS = {
    "smd",
    "smt",
    "rohs",
    "mlcc",
    "the",
    "and",
    "with",
    "for",
    "esr",
    "led",
    "ipc",
    "lcsc",
    "yageo",
    "samsung",
    "murata",
    "tdk",
    "ti",
    "diodes",
    "incorporated",
    "vishay",
}


def _tokenize(text: str) -> set:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP_TOKENS}


# When the part's natural category is the key, also dedupe against these
# sibling categories (where equivalent parts often already live).
_RELATED = {
    "Capacitor_SMD": ("Basic_Capacitors_Resistors", "Extended_Capacitors_Resistors"),
    "Basic_Capacitors_Resistors": ("Extended_Capacitors_Resistors", "Capacitor_SMD"),
    "Extended_Capacitors_Resistors": ("Basic_Capacitors_Resistors", "Capacitor_SMD"),
}

# JLCPCB assembly tier inferred from the imp-kicad-lib category name.  Used to
# surface "a Basic-tier alternative exists" in the similar-parts popup so users
# don't accidentally import an Extended part when a same-spec Basic one is
# already in the shared library.
_BASIC_CATEGORIES = {"Basic_Capacitors_Resistors"}
_EXTENDED_CATEGORIES = {"Extended_Capacitors_Resistors", "Capacitor_SMD"}


def category_tier(category: str) -> str:
    """Return ``"basic"``, ``"extended"``, or ``"other"`` for an imp-kicad-lib category."""
    if category in _BASIC_CATEGORIES:
        return "basic"
    if category in _EXTENDED_CATEGORIES:
        return "extended"
    return "other"


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


def find_similar(
    imp_lib_path: str,
    category: str,
    new_description: str,
    part_name: str = "",
    value_tol: float = 0.01,
    max_results: int = 3,
    new_tier: str = "",
) -> list:
    """Return a list of NEAR matches in imp-kicad-lib.

    Looser than ``find_match``: tolerates differences in size, voltage,
    dielectric, tolerance, and value (within ``value_tol``, default 5 %).
    The target category and any sibling categories are searched.

    Returns a list of dicts::

        {"name": str, "category": str, "description": str, "diffs": [str, ...]}

    sorted by closeness (exact-name and LCSC matches first, then by value
    proximity).  Empty list if nothing is close.
    """
    new_spec = None
    for fn in (cap_specs, res_specs, ind_specs):
        new_spec = fn(new_description)
        if new_spec:
            break

    candidates: list = []

    # Exact name match anywhere (loud signal — sort to top)
    if part_name:
        for cat, sym_dir in _all_category_dirs(imp_lib_path):
            sym_path = os.path.join(sym_dir, f"{part_name}.kicad_sym")
            if os.path.isfile(sym_path):
                desc = _read_desc(sym_path)
                candidates.append(
                    {
                        "name": part_name,
                        "category": cat,
                        "description": desc,
                        "diffs": ["same part name"],
                        "tier": category_tier(cat),
                        "_rank": 0,
                    }
                )

    # LCSC code match anywhere
    lcsc_codes = set(_LCSC_RE.findall(part_name or "")) | set(_LCSC_RE.findall(new_description or ""))
    if lcsc_codes:
        for cat, sym_dir in _all_category_dirs(imp_lib_path):
            for _path, name, desc in _iter_symbols_in_dir(sym_dir):
                if any(c in (desc or "") or c in name for c in lcsc_codes):
                    if not any(c["name"] == name and c["category"] == cat for c in candidates):
                        candidates.append(
                            {
                                "name": name,
                                "category": cat,
                                "description": desc,
                                "diffs": ["same LCSC code"],
                                "tier": category_tier(cat),
                                "_rank": 1,
                            }
                        )

    # Decide which categories to scan for spec matches. When the natural
    # category is "to-be-organized" (or anything not in _RELATED), or the
    # caller passed no useful category, search ALL category dirs so the popup
    # still catches obvious near matches.
    if category in _RELATED:
        cats = [category] + list(_RELATED[category])
    elif category and category != "to-be-organized":
        cats = [category]
    else:
        cats = [c for c, _ in _all_category_dirs(imp_lib_path)]

    # Token-based fallback: only used when we couldn't parse a spec for the
    # new part (so spec matching can't catch identical parts). Without this
    # guard, importing a 22nF cap was surfacing dozens of unrelated caps that
    # merely shared the package size token.
    if not new_spec:
        new_tokens = _tokenize(part_name) | _tokenize(new_description)
        for cat in cats:
            sym_dir = os.path.join(imp_lib_path, "symbols", f"{cat}__C.kicad_symdir")
            for _path, name, desc in _iter_symbols_in_dir(sym_dir):
                if any(c["name"] == name and c["category"] == cat for c in candidates):
                    continue
                tokens = _tokenize(name) | _tokenize(desc)
                shared = new_tokens & tokens
                # Require at least 2 shared tokens to count as a meaningful
                # match — single-token overlaps (e.g. just "0402") are noise.
                if len(shared) < 2:
                    continue
                candidates.append(
                    {
                        "name": name,
                        "category": cat,
                        "description": desc,
                        "diffs": [f"shared tokens: {', '.join(sorted(shared))[:80]}"],
                        "tier": category_tier(cat),
                        "_rank": 10 + 1.0 / max(len(shared), 1),
                    }
                )

    if not new_spec:
        # Final cleanup + de-dup by (cat, name) preserving order
        seen = set()
        uniq = []
        for c in sorted(candidates, key=lambda x: x.get("_rank", 99)):
            key = (c["category"], c["name"])
            if key in seen:
                continue
            seen.add(key)
            c.pop("_rank", None)
            uniq.append(c)
        return uniq[:max_results]

    for cat, _path, name, desc in _iter_symbols(imp_lib_path, cats):
        diffs = _spec_diff(new_spec, desc)
        if diffs is None:
            continue
        value_dist, diff_strs = diffs
        if value_dist > value_tol:
            continue
        cand_tier = category_tier(cat)
        # When importing an Extended (or Other) part, surface Basic-tier
        # alternatives at the very top — they're cheaper to assemble at JLC.
        rank = 2 + value_dist
        if cand_tier == "basic" and new_tier in ("extended", "other", ""):
            rank = 0.5 + value_dist
            diff_strs = ["JLC Basic alternative", *diff_strs]
        candidates.append(
            {
                "name": name,
                "category": cat,
                "description": desc,
                "diffs": diff_strs,
                "tier": cand_tier,
                "_rank": rank,
            }
        )

    # De-dup by (category, name) keeping the best-ranked entry per pair.
    by_key: dict = {}
    for c in candidates:
        key = (c["category"], c["name"])
        if key not in by_key or c.get("_rank", 99) < by_key[key].get("_rank", 99):
            by_key[key] = c
    uniq = sorted(by_key.values(), key=lambda c: c.get("_rank", 99))
    for c in uniq:
        c.pop("_rank", None)
    return uniq[:max_results]


def _read_desc(sym_path: str) -> str:
    try:
        with open(sym_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    m = _DESC_RE.search(text)
    return m.group(1) if m else ""


def _spec_diff(new_spec: dict, existing_desc: str):
    """Return (value_distance, [diff strings]) for an existing description, or None.

    value_distance is 0 if values match exactly, larger as they diverge.
    """
    kind = new_spec["kind"]
    if kind == "C":
        existing = cap_specs(existing_desc)
        if not existing:
            return None
        diffs = []
        v_new, v_old = new_spec["value_pF"], existing["value_pF"]
        dist = abs(v_new - v_old) / max(v_new, 1)
        if dist > 0.005:
            diffs.append(f"value {new_spec['label'].split('/')[0]} vs {existing['label'].split('/')[0]}")
        if existing["voltage"] != new_spec["voltage"]:
            diffs.append(f"{int(new_spec['voltage'])}V vs {int(existing['voltage'])}V")
        if existing["dielectric"] != new_spec["dielectric"]:
            diffs.append(f"{new_spec['dielectric']} vs {existing['dielectric']}")
        if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
            diffs.append(f"size {new_spec['size']} vs {existing['size']}")
        if not diffs:
            diffs = ["exact same spec"]
        return dist, diffs
    if kind == "R":
        existing = res_specs(existing_desc)
        if not existing:
            return None
        diffs = []
        v_new, v_old = new_spec["value_ohm"], existing["value_ohm"]
        dist = abs(v_new - v_old) / max(v_new, 1e-6)
        if dist > 0.005:
            diffs.append(f"value {new_spec['label']} vs {existing['label']}")
        if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
            diffs.append(f"size {new_spec['size']} vs {existing['size']}")
        if not diffs:
            diffs = ["exact same spec"]
        return dist, diffs
    if kind == "L":
        existing = ind_specs(existing_desc)
        if not existing:
            return None
        diffs = []
        v_new, v_old = new_spec["value_nH"], existing["value_nH"]
        dist = abs(v_new - v_old) / max(v_new, 1e-6)
        if dist > 0.005:
            diffs.append(f"value {new_spec['label']} vs {existing['label']}")
        if existing["size"] and new_spec["size"] and existing["size"] != new_spec["size"]:
            diffs.append(f"size {new_spec['size']} vs {existing['size']}")
        if not diffs:
            diffs = ["exact same spec"]
        return dist, diffs
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
