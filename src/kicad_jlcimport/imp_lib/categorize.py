"""Map a part to the appropriate imp-kicad-lib category directory.

Returns a directory base name (no ``__C`` suffix).  Parts that cannot be
confidently placed go to ``to-be-organized``.
"""

from __future__ import annotations

import re

KNOWN_CATEGORIES = {
    "Capacitor_SMD",
    "Capacitor_THT",
    "Basic_Capacitors_Resistors",
    "Extended_Capacitors_Resistors",
    "Inductor",
    "BEAD",
    "LED",
    "Diode",
    "Transistor_FET",
    "Transistor_BJT",
    "Switch",
    "Connector_USB",
    "Connector",
    "MUX",
    "Memory_Flash",
    "Oscillator",
    "LDO",
    "Regulator_Linear",
    "Motor_Driver",
    "Sensor_Motion",
}


def _looks_like(words: list, desc: str) -> bool:
    d = desc.lower()
    return any(w in d for w in words)


def categorize(part_name: str, description: str = "", easyeda_category: str = "") -> str:
    """Pick the best imp-kicad-lib category for the part.

    Returns the directory base name (without ``__C`` suffix), e.g. ``Capacitor_SMD``.
    """
    name = part_name or ""
    desc = (description or "").lower()
    cat = (easyeda_category or "").lower()

    # Polymer / tantalum caps go to Capacitor_SMD too
    if _looks_like(["polymer", "tantalum"], desc):
        return "Capacitor_SMD"

    # Bead before inductor
    if "ferrite bead" in desc or re.search(r"\bbead\b", desc):
        return "BEAD"

    # Ceramic / MLCC
    if "capacitor" in desc or "ceramic" in desc or re.search(r"\b(pF|nF|uF|µF)\b", description):
        # Heuristic: small Basic ceramics from canonical series go to the Basic dir
        if re.match(r"^(0402CG|CL05[BC]|CL05A105|CL05A225)", name):
            return "Basic_Capacitors_Resistors"
        return "Capacitor_SMD"

    if "resistor" in desc or re.search(r"(mΩ|kΩ|MΩ|\bΩ\b)", description):
        return "Basic_Capacitors_Resistors"

    if "inductor" in desc or re.search(r"\b(nH|uH|µH|mH)\b", description):
        return "Inductor"

    if (
        "led" in cat
        or "light emitting" in desc
        or "led" in name.lower().split("_")[0:1]
        or re.match(r"^(XL-|KT-|0603(W|White|Red))", name)
    ):
        return "LED"

    if _looks_like(["n-channel", "p-channel", "mosfet"], desc):
        return "Transistor_FET"

    if _looks_like(["npn", "pnp"], desc) and "transistor" in desc:
        return "Transistor_BJT"

    if _looks_like(["tact switch", "tactile", "push button", "slide switch"], desc):
        return "Switch"

    if _looks_like(["usb", "type-c", "type c"], desc):
        return "Connector_USB"

    if "connector" in desc:
        return "Connector"

    if "crystal" in desc or "oscillator" in desc:
        return "Oscillator"

    if "ldo" in desc or "linear regulator" in desc or "low-dropout" in desc:
        return "LDO"

    return "to-be-organized"


def reference_for(category: str) -> str | None:
    """Return the schematic reference designator for a given category, if known."""
    return {
        "Capacitor_SMD": "C",
        "Capacitor_THT": "C",
        "Basic_Capacitors_Resistors": None,  # depends on part — set by formatter
        "Extended_Capacitors_Resistors": None,
        "Inductor": "L",
        "BEAD": "FB",
        "LED": "D",
        "Diode": "D",
        "Transistor_FET": "Q",
        "Transistor_BJT": "Q",
        "Switch": "SW",
        "Connector_USB": "J",
        "Connector": "J",
        "MUX": "U",
        "Memory_Flash": "U",
        "Oscillator": "Y",
        "LDO": "U",
        "Regulator_Linear": "U",
        "Motor_Driver": "U",
        "Sensor_Motion": "U",
    }.get(category)
