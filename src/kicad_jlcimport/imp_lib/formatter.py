"""Reshape generated KiCad files to match imp-kicad-lib conventions.

The plugin generates a symbol as a single s-expression block (the body of a
``(symbol "...")`` form, without the outer ``(kicad_symbol_lib ...)`` wrapper).
For imp-kicad-lib we:

* wrap each symbol in its own ``.kicad_sym`` file inside the category's
  ``.kicad_symdir`` directory
* fix the Reference designator based on the category
* hide the Value property and annotate with a purple ``_1_1`` text label
* rewrite the Footprint property prefix to ``<Cat>__C:``
* rewrite the .kicad_mod ``(model ...)`` paths to the relative
  ``../../packages3d/<Cat>__C.3dshapes/<part>.step`` form
"""

from __future__ import annotations

import os
import re
from typing import Tuple

from .categorize import reference_for
from .specs import cap_specs, ind_specs, res_specs

ANNOT_COLOR = "163 59 255 1"

_PROP_REF_RE = re.compile(r'\(property\s+"Reference"\s+"[^"]*"')
_PROP_FOOTPRINT_RE = re.compile(r'\(property\s+"Footprint"\s+"[^"]*"')
_PROP_VALUE_RE = re.compile(r'\(property\s+"Value"\s+"([^"]*)"([^)]*)\)', re.DOTALL)
_MODEL_RE = re.compile(r'\(model\s+"[^"]+"')


def label_for(category: str, description: str) -> str | None:
    """Return the schematic value label for a part (e.g. ``100nF/50V/X7R``)."""
    if category in ("Capacitor_SMD", "Capacitor_THT"):
        spec = cap_specs(description)
        return spec["label"] if spec else None
    if category in ("Basic_Capacitors_Resistors", "Extended_Capacitors_Resistors"):
        if re.search(r"\b(pF|nF|uF|µF)\b", description):
            spec = cap_specs(description)
            return spec["label"] if spec else None
        spec = res_specs(description)
        return spec["label"] if spec else None
    if category == "Inductor":
        spec = ind_specs(description)
        return spec["label"] if spec else None
    return None


def _ref_for(category: str, description: str) -> str:
    ref = reference_for(category)
    if ref:
        return ref
    # Basic/Extended mixed — decide from description
    if re.search(r"\b(pF|nF|uF|µF)\b", description):
        return "C"
    return "R"


def reformat_symbol(
    sym_content: str,
    part_name: str,
    category: str,
    description: str,
    fp_lib_name: str,
    fp_name: str,
) -> str:
    """Rewrite a symbol body (the ``(symbol "...")`` block) to match imp-kicad-lib style.

    ``sym_content`` may be either a bare symbol block or a full ``(kicad_symbol_lib ...)``
    file; the returned text is always a full ``(kicad_symbol_lib ...)`` file containing
    the single symbol.
    """
    body = _extract_symbol_block(sym_content, part_name)
    if body is None:
        body = sym_content

    ref = _ref_for(category, description)
    body = _PROP_REF_RE.sub(f'(property "Reference" "{ref}"', body, count=1)
    body = _PROP_FOOTPRINT_RE.sub(f'(property "Footprint" "{fp_lib_name}:{fp_name}"', body, count=1)

    # Hide the Value property for passives so the annotation drives the display
    if ref in ("R", "C", "L"):
        body = _hide_value(body)

    # Inject _1_1 annotation
    label = label_for(category, description)
    if label:
        body = _inject_annotation(body, part_name, label, ref)

    return (
        "(kicad_symbol_lib\n"
        "\t(version 20251024)\n"
        '\t(generator "kicad_jlcimport_imp")\n'
        '\t(generator_version "10.0")\n' + body + "\n)\n"
    )


def reformat_footprint(
    fp_content: str,
    category: str,
    part_name: str,
) -> str:
    """Rewrite the ``(model "...")`` 3D paths to the imp-kicad-lib relative layout."""
    new_dir = f"../../packages3d/{category}__C.3dshapes"

    def repl(m: re.Match) -> str:
        old = m.group(0)
        mfn = re.search(r'/([^/"]+)\.(wrl|step)"', old)
        if not mfn:
            return old
        base = mfn.group(1)
        return f'(model "{new_dir}/{base}.step"'

    return _MODEL_RE.sub(repl, fp_content)


def _extract_symbol_block(text: str, part_name: str) -> str | None:
    needle = f'(symbol "{part_name}"'
    start = text.find(needle)
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _hide_value(body: str) -> str:
    m = _PROP_VALUE_RE.search(body)
    if not m:
        return body
    inner = m.group(2)
    if "(hide yes)" in inner or "hide yes" in inner:
        return body
    # Insert (hide yes) just before the closing paren of the property
    full = m.group(0)
    new = full[:-1] + "\n\t\t(hide yes)\n\t)"
    return body[: m.start()] + new + body[m.end() :]


def _inject_annotation(body: str, part_name: str, label: str, ref: str) -> str:
    y_by_ref = {"C": 3.048, "R": 2.032, "L": 2.032, "D": 4.572, "Q": 6.604, "SW": 6.604, "FB": 2.032}
    y = y_by_ref.get(ref, 3.048)
    block = (
        f'\t\t(symbol "{part_name}_1_1"\n'
        f'\t\t\t(text "{label}"\n'
        f"\t\t\t\t(at 0 {y} 0)\n"
        f"\t\t\t\t(effects (font (size 1.27 1.27) (color {ANNOT_COLOR})))\n"
        f"\t\t\t)\n"
        f"\t\t)\n"
    )
    # Already has annotation?
    if f'(symbol "{part_name}_1_1"' in body:
        return body
    # Insert just before the final closing paren of the symbol body
    idx = body.rfind(")")
    if idx < 0:
        return body
    line_start = body.rfind("\n", 0, idx) + 1
    return body[:line_start] + block + body[line_start:]


def imp_lib_paths(imp_lib: str, category: str) -> dict:
    """Return the destination paths inside imp-kicad-lib for ``category``.

    All categories — including ``to-be-organized`` — use the standard
    ``symbols/<Cat>__C.kicad_symdir`` / ``footprints/<Cat>__C.pretty`` /
    ``packages3d/<Cat>__C.3dshapes`` layout so they are picked up by
    KiCad via the lib tables.
    """
    return {
        "sym_dir": os.path.join(imp_lib, "symbols", f"{category}__C.kicad_symdir"),
        "fp_dir": os.path.join(imp_lib, "footprints", f"{category}__C.pretty"),
        "models_dir": os.path.join(imp_lib, "packages3d", f"{category}__C.3dshapes"),
        "fp_lib_name": f"{category}__C",
    }


def write_imp_lib_files(
    imp_lib: str,
    part_name: str,
    fp_name: str,
    category: str,
    description: str,
    sym_content: str,
    fp_content: str,
    step_src: str | None,
) -> Tuple[list, dict]:
    """Materialise the formatted files into imp-kicad-lib. Returns (written_paths, paths_dict)."""
    paths = imp_lib_paths(imp_lib, category)
    for d in (paths["sym_dir"], paths["fp_dir"], paths["models_dir"]):
        os.makedirs(d, exist_ok=True)

    written = []

    # Symbol
    if sym_content:
        reformatted = reformat_symbol(
            sym_content,
            part_name,
            category,
            description,
            paths["fp_lib_name"],
            fp_name,
        )
        sym_path = os.path.join(paths["sym_dir"], f"{part_name}.kicad_sym")
        with open(sym_path, "w", encoding="utf-8") as f:
            f.write(reformatted)
        written.append(sym_path)

    # Footprint
    if fp_content:
        reformatted_fp = reformat_footprint(fp_content, category, part_name)
        fp_path = os.path.join(paths["fp_dir"], f"{fp_name}.kicad_mod")
        with open(fp_path, "w", encoding="utf-8") as f:
            f.write(reformatted_fp)
        written.append(fp_path)

    # 3D model (STEP only — imp-kicad-lib drops .wrl)
    if step_src and os.path.isfile(step_src):
        import shutil

        dest = os.path.join(paths["models_dir"], f"{fp_name}.step")
        shutil.copy2(step_src, dest)
        written.append(dest)

    return written, paths
