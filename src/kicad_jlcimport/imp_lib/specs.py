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


def cap_specs(description: str, mpn: str = "") -> dict | None:
    """Parse a capacitor description (with optional MPN fallback).

    Returns dict with keys ``value_pF``, ``voltage``, ``dielectric``, ``size``,
    ``label``.  Tries the description first (explicit ``100nF``/``50V``/``X7R``),
    then falls back to parsing the IEC-encoded cap MPN convention
    (``…0402 C0G 101 F 500…`` → 100pF 50V C0G 0402) when any field is missing.
    """
    # Pass 1: explicit fields in the description text
    m_v = _CAP_VALUE_RE.search(description)
    m_volt = _VOLT_RE.search(description)
    m_d = _DIELECTRIC_RE.search(description)
    m_s = _SIZE_RE.search(description)

    value_pF = None
    voltage = None
    dielectric = None
    size = ""
    val_label = ""

    if m_v:
        value = float(m_v.group(1))
        unit = _normalise_cap_unit(m_v.group(2))
        value_pF = _normalise_value_pF(value, unit)
        val_label = f"{m_v.group(1)}{unit}"
    if m_volt:
        voltage = float(m_volt.group(1))
    if m_d:
        dielectric = _normalise_dielectric(m_d.group(1))
    if m_s:
        size = m_s.group(1)

    # Pass 2: fall back to MPN parsing for any missing field
    if mpn and (value_pF is None or voltage is None or dielectric is None or not size):
        mpn_spec = _cap_specs_from_mpn(mpn)
        if mpn_spec:
            if value_pF is None:
                value_pF = mpn_spec.get("value_pF")
                val_label = mpn_spec.get("label_value", val_label)
            if voltage is None:
                voltage = mpn_spec.get("voltage")
            if dielectric is None:
                dielectric = mpn_spec.get("dielectric")
            if not size:
                size = mpn_spec.get("size", "") or ""

    if value_pF is None or voltage is None or dielectric is None:
        return None
    if not val_label:
        val_label = _format_pF(value_pF)
    return {
        "kind": "C",
        "value_pF": value_pF,
        "voltage": voltage,
        "dielectric": dielectric,
        "size": size,
        "label": f"{val_label}/{int(voltage) if voltage == int(voltage) else voltage}V/{dielectric}",
    }


def _format_pF(value_pF: float) -> str:
    """Pick a human-readable capacitance unit from a pF value."""
    if value_pF >= 1_000_000:
        v = value_pF / 1_000_000
        return f"{v:g}uF"
    if value_pF >= 1_000:
        v = value_pF / 1_000
        return f"{v:g}nF"
    return f"{value_pF:g}pF"


# IEC 60062 three-digit cap code: 2-digit mantissa × 10^exponent, in pF.
# e.g. "101" = 10*10^1 pF = 100pF; "104" = 10*10^4 pF = 100nF; "475" = 47*10^5 pF = 4.7uF
_CAP_MPN_CODE_RE = re.compile(
    r"(0201|0402|0603|0805|1206|1210|1812|2010|2512)"  # size
    r".*?"
    r"(X7R|X5R|X6S|X7S|X8R|C0G|NP0|NPO|Y5V|Z5U)"  # dielectric
    r".*?"
    r"(\d{3})"  # 3-digit value code
    r"(?:[A-Z])?"  # optional tolerance letter
    r"(\d{2,3}|\dR\d)?",  # optional 2-3 char voltage code
    re.IGNORECASE,
)


def _decode_voltage_code(code: str) -> float | None:
    """Decode an IEC cap voltage code (e.g. '500' = 50V, '101' = 100V, '6R3' = 6.3V)."""
    if not code:
        return None
    s = code.upper()
    if "R" in s:
        # Decimal point form: 6R3 -> 6.3
        try:
            return float(s.replace("R", "."))
        except ValueError:
            return None
    if len(s) == 3 and s.isdigit():
        # IEC: first two digits × 10^third digit (in volts here, not pF)
        try:
            return int(s[:2]) * (10 ** int(s[2]))
        except ValueError:
            return None
    if s.isdigit():
        return float(s)
    return None


def _cap_specs_from_mpn(mpn: str) -> dict | None:
    """Parse size / dielectric / value / voltage from a cap MPN.

    Conservative: returns None if size + dielectric + value code aren't all
    present in the expected order.  Voltage is optional.
    """
    m = _CAP_MPN_CODE_RE.search(mpn or "")
    if not m:
        return None
    size = m.group(1)
    dielectric = _normalise_dielectric(m.group(2))
    code = m.group(3)
    try:
        value_pF = int(code[:2]) * (10 ** int(code[2]))
    except (ValueError, IndexError):
        return None
    voltage = _decode_voltage_code(m.group(4) or "")
    return {
        "size": size,
        "dielectric": dielectric,
        "value_pF": float(value_pF),
        "voltage": voltage,
        "label_value": _format_pF(value_pF),
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
