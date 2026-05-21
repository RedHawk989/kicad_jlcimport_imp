"""Live JLCPCB search for same-spec JLC Basic-tier alternatives.

When the user imports an Extended part, query JLCPCB's parts search filtered
to ``componentLibraryType=base`` for parts with the same parsed spec (cap
value+voltage+dielectric+size, resistor value+size, inductor value+size).
Any hit means the user could swap to a cheaper-to-assemble Basic part.

Network failures, parse failures, and empty results all return ``[]`` —
this is purely informational and must never block an import.
"""

from __future__ import annotations

from typing import Callable

from .specs import _format_pF, cap_specs, ind_specs, res_specs


def _cap_query(spec: dict) -> str:
    parts = [_format_pF(spec["value_pF"])]
    if spec.get("voltage"):
        v = spec["voltage"]
        parts.append(f"{int(v) if v == int(v) else v}V")
    if spec.get("dielectric"):
        parts.append(spec["dielectric"])
    if spec.get("size"):
        parts.append(spec["size"])
    return " ".join(parts)


def _passive_query(spec: dict) -> str:
    parts = [spec["label"].split("/")[0]]
    if spec.get("size"):
        parts.append(spec["size"])
    return " ".join(parts)


def _spec_matches(new_spec: dict, candidate_name: str, candidate_desc: str) -> bool:
    """Return True when the candidate parses to the same spec as ``new_spec``."""
    kind = new_spec["kind"]
    if kind == "C":
        s = cap_specs(candidate_desc, mpn=candidate_name)
        if not s:
            return False
        if abs(s["value_pF"] - new_spec["value_pF"]) / max(new_spec["value_pF"], 1) > 0.01:
            return False
        if new_spec.get("dielectric") and s.get("dielectric") and s["dielectric"] != new_spec["dielectric"]:
            return False
        if new_spec.get("voltage") and s.get("voltage") and s["voltage"] < new_spec["voltage"]:
            return False
        if new_spec.get("size") and s.get("size") and s["size"] != new_spec["size"]:
            return False
        return True
    if kind == "R":
        s = res_specs(candidate_desc)
        if not s:
            return False
        if abs(s["value_ohm"] - new_spec["value_ohm"]) / max(new_spec["value_ohm"], 1e-6) > 0.01:
            return False
        if new_spec.get("size") and s.get("size") and s["size"] != new_spec["size"]:
            return False
        return True
    if kind == "L":
        s = ind_specs(candidate_desc)
        if not s:
            return False
        if abs(s["value_nH"] - new_spec["value_nH"]) / max(new_spec["value_nH"], 1e-6) > 0.01:
            return False
        if new_spec.get("size") and s.get("size") and s["size"] != new_spec["size"]:
            return False
        return True
    return False


def find_jlc_basic_alternatives(
    new_description: str,
    part_name: str = "",
    max_results: int = 5,
    search_fn: Callable | None = None,
) -> list:
    """Return up to ``max_results`` JLC Basic parts matching the new part's spec.

    Each entry is the raw JLCPCB search-result dict (lcsc, name, description,
    package, price, stock, ...).  Empty list when nothing matches or the spec
    can't be parsed.
    """
    new_spec = cap_specs(new_description, mpn=part_name) or res_specs(new_description) or ind_specs(new_description)
    if not new_spec:
        return []

    kind = new_spec["kind"]
    if kind == "C":
        query = _cap_query(new_spec)
    elif kind in ("R", "L"):
        query = _passive_query(new_spec)
    else:
        return []

    if search_fn is None:
        try:
            from ..easyeda.api import search_components

            search_fn = search_components
        except ImportError:
            return []

    try:
        raw = search_fn(query, page_size=20, part_type="base")
    except Exception:  # noqa: BLE001 — network / API failures must not block import
        return []

    out = []
    for r in raw.get("results", []):
        if r.get("type") != "Basic":
            continue
        if _spec_matches(new_spec, r.get("name", "") or r.get("model", ""), r.get("description", "")):
            out.append(r)
            if len(out) >= max_results:
                break
    return out
