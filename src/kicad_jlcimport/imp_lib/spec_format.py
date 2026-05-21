"""Structured spec extraction + side-by-side comparison rendering.

Given a part name and JLCPCB description, ``parse_spec_table`` returns the
component kind and an ordered list of ``(field, value)`` tuples.  Field sets
are kind-specific:

    Cap (C):       Value, Voltage, Dielectric, Tolerance, Size
    Resistor (R):  Value, Size, Tolerance, Power
    Inductor (L):  Value, Size, Current
    LED (D):       Color, Size
    Transistor:    Channel, Vds, Package
    Switch (SW):   Description (fallback)
    Connector (J): Pins, Pitch, Mount, Description
    Other:         Description fallback

``render_comparison`` lays out the new part and any number of candidates
side-by-side with ``✓`` / ``✗`` markers so users can scan differences.
"""

from __future__ import annotations

import re

from .specs import _format_pF, cap_specs, ind_specs, res_specs

DASH = "—"
CHECK = "✓"
CROSS = "✗"

# --- helpers -----------------------------------------------------------------

_TOL_PCT_RE = re.compile(r"±\s*(\d+(?:\.\d+)?)\s*%")
_TOL_LETTER = {"B": "±0.1%", "C": "±0.25%", "D": "±0.5%", "F": "±1%", "G": "±2%", "J": "±5%", "K": "±10%", "M": "±20%"}
_POWER_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:m?W)\b|\d+/\d+\s*W\b)", re.IGNORECASE)
_CURRENT_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:mA|A))\b", re.IGNORECASE)
_SIZE_RE = re.compile(r"\b(0201|0402|0603|0805|1206|1210|1608|1812|2010|2012|2512|3225|4030|1050|0606|0605)\b")
_PIN_COUNT_RE = re.compile(r"\b(\d+)\s*[Pp]in", re.IGNORECASE)
_PITCH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*pitch", re.IGNORECASE)
_VDS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*V(?:ds|DS)?\b")

# LED color hints embedded in common XL-/KT- series MPNs.
_LED_COLOR_CODES = {
    "UBC": "Blue",
    "UGC": "Green",
    "URC": "Red",
    "UOC": "Orange",
    "UWC": "White",
    "UYC": "Yellow",
    "UWPC": "White",
    "UBGC": "Blue-Green",
}
_LED_COLOR_WORDS = re.compile(r"\b(red|green|blue|white|amber|orange|yellow|infrared|uv|purple|pink)\b", re.IGNORECASE)


_MPN_TOL_AFTER_VALUE = re.compile(
    r"(?:X7R|X5R|X6S|X7S|X8R|C0G|NP0|NPO|Y5V|Z5U)\d{3}([A-Z])(?=\d|$|[^A-Z])",
    re.IGNORECASE,
)


def _extract_tolerance(text: str, mpn: str = "") -> str | None:
    m = _TOL_PCT_RE.search(text or "")
    if m:
        return f"±{m.group(1)}%"
    # IEC tolerance letter appears immediately after the dielectric + 3-digit
    # value code in cap MPNs (e.g. C0G101F500 → F → ±1%).
    if mpn:
        m2 = _MPN_TOL_AFTER_VALUE.search(mpn)
        if m2:
            letter = m2.group(1).upper()
            if letter in _TOL_LETTER:
                return _TOL_LETTER[letter]
    return None


def _extract_power(text: str) -> str | None:
    m = _POWER_RE.search(text or "")
    return m.group(1).replace(" ", "") if m else None


def _extract_current(text: str) -> str | None:
    m = _CURRENT_RE.search(text or "")
    return m.group(1).replace(" ", "") if m else None


def _extract_size(text: str, mpn: str = "") -> str | None:
    for src in (text or "", mpn or ""):
        m = _SIZE_RE.search(src)
        if m:
            return m.group(1)
    return None


def _extract_pin_count(text: str, mpn: str = "") -> str | None:
    for src in (text or "", mpn or ""):
        m = _PIN_COUNT_RE.search(src)
        if m:
            return m.group(1)
    return None


def _extract_pitch(text: str) -> str | None:
    m = _PITCH_RE.search(text or "")
    return f"{m.group(1)}mm" if m else None


def _extract_vds(text: str) -> str | None:
    m = _VDS_RE.search(text or "")
    return f"{m.group(1)}V" if m else None


def _detect_led_color(mpn: str, description: str) -> str | None:
    up = (mpn or "").upper()
    for code, color in sorted(_LED_COLOR_CODES.items(), key=lambda x: -len(x[0])):
        if code in up:
            return color
    m = _LED_COLOR_WORDS.search(description or "")
    return m.group(1).title() if m else None


def _format_voltage(v: float | None) -> str:
    if v is None:
        return DASH
    return f"{int(v) if v == int(v) else v}V"


# --- kind detection + spec table --------------------------------------------


def detect_kind(name: str, description: str) -> str:
    """Return a one-letter kind code: C/R/L/D/J/Q/SW/U/?."""
    desc = (description or "").lower()
    if cap_specs(description or "", mpn=name or ""):
        return "C"
    if res_specs(description or ""):
        return "R"
    if ind_specs(description or ""):
        return "L"
    if "led" in desc or "light emitting" in desc or _LED_COLOR_WORDS.search(desc):
        return "D"
    if any(t in desc for t in ("transistor", "mosfet", "n-channel", "p-channel", "fet", "bjt", "n-fet", "p-fet")):
        return "Q"
    if any(t in desc for t in ("tact switch", "tactile", "push button", "slide switch", "dip switch", "switch")):
        return "SW"
    if any(t in desc for t in ("connector", "header", "receptacle", "jack", "plug", "usb", "type-c", "socket")):
        return "J"
    return "U"


def parse_spec_table(name: str, description: str, kind: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(kind, [(field, value), ...])`` for a part.

    Always includes every field the kind defines, using ``"—"`` when unknown,
    so columns line up across the new part and every candidate.
    """
    name = name or ""
    description = description or ""
    if kind is None:
        kind = detect_kind(name, description)

    if kind == "C":
        s = cap_specs(description, mpn=name)
        tol = _extract_tolerance(description, name) or DASH
        if s:
            return kind, [
                ("Value", _format_pF(s["value_pF"])),
                ("Voltage", _format_voltage(s.get("voltage"))),
                ("Dielectric", s["dielectric"]),
                ("Tolerance", tol),
                ("Size", s["size"] or _extract_size(description, name) or DASH),
            ]
        return kind, [
            ("Value", DASH),
            ("Voltage", DASH),
            ("Dielectric", DASH),
            ("Tolerance", tol),
            ("Size", _extract_size(description, name) or DASH),
        ]

    if kind == "R":
        s = res_specs(description)
        tol = _extract_tolerance(description, name) or DASH
        pwr = _extract_power(description) or DASH
        if s:
            return kind, [
                ("Value", s["label"]),
                ("Size", s["size"] or _extract_size(description, name) or DASH),
                ("Tolerance", tol),
                ("Power", pwr),
            ]
        return kind, [
            ("Value", DASH),
            ("Size", _extract_size(description, name) or DASH),
            ("Tolerance", tol),
            ("Power", pwr),
        ]

    if kind == "L":
        s = ind_specs(description)
        cur = _extract_current(description) or DASH
        if s:
            return kind, [
                ("Value", s["label"]),
                ("Size", s["size"] or _extract_size(description, name) or DASH),
                ("Current", cur),
            ]
        return kind, [
            ("Value", DASH),
            ("Size", _extract_size(description, name) or DASH),
            ("Current", cur),
        ]

    if kind == "D":
        return kind, [
            ("Color", _detect_led_color(name, description) or DASH),
            ("Size", _extract_size(description, name) or DASH),
        ]

    if kind == "Q":
        chan = DASH
        d = description.lower()
        if "n-channel" in d or "n-fet" in d or "nmos" in d:
            chan = "N-channel"
        elif "p-channel" in d or "p-fet" in d or "pmos" in d:
            chan = "P-channel"
        elif "npn" in d:
            chan = "NPN"
        elif "pnp" in d:
            chan = "PNP"
        return kind, [
            ("Channel", chan),
            ("Vds", _extract_vds(description) or DASH),
        ]

    if kind == "J":
        return kind, [
            ("Pins", _extract_pin_count(description, name) or DASH),
            ("Pitch", _extract_pitch(description) or DASH),
        ]

    # Fallback: description-only row
    desc_short = (description or DASH)[:80]
    return kind, [("Description", desc_short)]


# --- rendering ---------------------------------------------------------------


def render_comparison(
    new_part: dict,
    candidates: list,
    new_tier: str = "",
) -> str:
    """Render a text block comparing ``new_part`` to each candidate.

    ``new_part`` must have ``name``, ``description``.  Each candidate must
    have ``name``, ``category``, ``description``, and optional ``tier``,
    ``diffs``.

    Output is a single multi-line string suitable for ``wx.MessageDialog``.
    Each field row shows the new value, the candidate's value, and a
    ``✓`` / ``✗`` marker.
    """
    kind, new_rows = parse_spec_table(new_part.get("name", ""), new_part.get("description", ""))
    new_field_map = dict(new_rows)
    fields = [f for f, _ in new_rows]
    field_width = max(len(f) for f in fields) if fields else 0
    val_width = max((len(str(v)) for v in new_field_map.values()), default=4)
    val_width = max(val_width, 6)

    def _badge(tier: str) -> str:
        if tier == "basic":
            return " [JLC Basic]"
        if tier == "extended":
            return " [JLC Extended]"
        return ""

    new_badge = _badge(new_tier)
    out: list = [f"NEW: {new_part.get('name', '')}{new_badge}"]
    if new_part.get("description"):
        out.append(f"     {new_part['description'][:90]}")
    out.append("")

    has_basic_alt = any(c.get("tier") == "basic" for c in candidates) and new_tier != "basic"
    if has_basic_alt:
        out.append(
            "⚠ A JLC Basic-tier alternative already exists in imp-kicad-lib — "
            "Basic parts are cheaper to assemble at JLCPCB than Extended ones."
        )
        out.append("")

    for c in candidates:
        cand_badge = _badge(c.get("tier", ""))
        basic_marker = "  ⚠ Basic alternative" if c.get("tier") == "basic" and new_tier != "basic" else ""
        out.append(f"EXISTING ({c.get('category', '')}__C : {c.get('name', '')}){cand_badge}{basic_marker}")
        if c.get("description"):
            out.append(f"     {c['description'][:90]}")
        _, cand_rows = parse_spec_table(c.get("name", ""), c.get("description", ""), kind=kind)
        cand_map = dict(cand_rows)
        for field in fields:
            new_val = new_field_map.get(field, DASH)
            cand_val = cand_map.get(field, DASH)
            marker = CHECK if str(new_val) == str(cand_val) and new_val != DASH else CROSS
            if new_val == DASH and cand_val == DASH:
                marker = " "  # both unknown — no judgement
            out.append(
                f"     {field.ljust(field_width)} : "
                f"{str(new_val).ljust(val_width)} vs  {str(cand_val).ljust(val_width)} {marker}"
            )
        out.append("")

    return "\n".join(out)
