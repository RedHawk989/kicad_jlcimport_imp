"""Extract structured specs (value/voltage/dielectric/size) from a part Description."""

from __future__ import annotations

import re

_CAP_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(pF|nF|uF|µF|μF)", re.IGNORECASE)
_RES_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mΩ|kΩ|MΩ|Ω)")
_IND_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(nH|uH|µH|μH|mH)", re.IGNORECASE)
_VOLT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*V\b")
_DIELECTRIC_RE = re.compile(r"\b(X7R|X5R|X6S|X7S|X8R|C0G|NP0|NPO|Y5V|Z5U)\b", re.IGNORECASE)
_SIZE_RE = re.compile(r"\b(0201|0402|0603|0805|1206|1210|1812|2010|2512|3225|4030|1050|0606|0605)\b")


def _normalise_cap_unit(unit: str) -> str:
    u = unit.replace("µ", "u").replace("μ", "u")
    return u  # pF, nF, uF


def _normalise_dielectric(d: str) -> str:
    d = d.upper()
    return "C0G" if d in ("NP0", "NPO") else d


def _normalise_value_pF(value: float, unit: str) -> float:
    """Express a capacitance in picofarads for comparison."""
    u = _normalise_cap_unit(unit).lower()
    if u == "pf":
        return value
    if u == "nf":
        return value * 1_000
    if u == "uf":
        return value * 1_000_000
    return value


def _normalise_value_ohm(value: float, unit: str) -> float:
    if unit == "mΩ":
        return value / 1_000
    if unit == "kΩ":
        return value * 1_000
    if unit == "MΩ":
        return value * 1_000_000
    return value


def _normalise_value_nH(value: float, unit: str) -> float:
    u = unit.replace("µ", "u").replace("μ", "u").lower()
    if u == "nh":
        return value
    if u == "uh":
        return value * 1_000
    if u == "mh":
        return value * 1_000_000
    return value


def cap_specs(description: str) -> dict | None:
    """Parse a capacitor description. Returns dict with keys: value_pF, voltage, dielectric, size, label."""
    m_v = _CAP_VALUE_RE.search(description)
    m_volt = _VOLT_RE.search(description)
    m_d = _DIELECTRIC_RE.search(description)
    m_s = _SIZE_RE.search(description)
    if not (m_v and m_volt and m_d):
        return None
    value = float(m_v.group(1))
    unit = _normalise_cap_unit(m_v.group(2))
    voltage = float(m_volt.group(1))
    dielectric = _normalise_dielectric(m_d.group(1))
    size = m_s.group(1) if m_s else ""
    val_str = f"{m_v.group(1)}{unit}"
    return {
        "kind": "C",
        "value_pF": _normalise_value_pF(value, unit),
        "voltage": voltage,
        "dielectric": dielectric,
        "size": size,
        "label": f"{val_str}/{int(voltage) if voltage == int(voltage) else voltage}V/{dielectric}",
    }


def res_specs(description: str) -> dict | None:
    m_v = _RES_VALUE_RE.search(description)
    m_s = _SIZE_RE.search(description)
    if not m_v:
        return None
    value = float(m_v.group(1))
    unit = m_v.group(2)
    label = f"{m_v.group(1)}{unit.replace('kΩ', 'k').replace('MΩ', 'M')}"
    return {
        "kind": "R",
        "value_ohm": _normalise_value_ohm(value, unit),
        "size": m_s.group(1) if m_s else "",
        "label": label,
    }


def ind_specs(description: str) -> dict | None:
    m_v = _IND_VALUE_RE.search(description)
    m_s = _SIZE_RE.search(description)
    if not m_v:
        return None
    value = float(m_v.group(1))
    unit = m_v.group(2).replace("µ", "u").replace("μ", "u")
    return {
        "kind": "L",
        "value_nH": _normalise_value_nH(value, unit),
        "size": m_s.group(1) if m_s else "",
        "label": f"{m_v.group(1)}{unit}",
    }
