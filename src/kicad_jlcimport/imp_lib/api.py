"""Public entrypoint called by the importer once base files are written."""

from __future__ import annotations

import os
from typing import Callable

from .categorize import categorize
from .dedupe import find_match
from .discovery import find_imp_lib
from .formatter import write_imp_lib_files
from .gitops import commit_and_push


def try_contribute(
    *,
    lib_dir: str,
    lib_name: str,
    part_name: str,
    fp_name: str,
    description: str,
    sym_content: str,
    fp_content: str,
    config: dict,
    log: Callable[[str], None] = print,
    easyeda_category: str = "",
    force_overwrite: bool = False,
    lcsc_code: str = "",
) -> dict | None:
    """Try to contribute the just-imported part to imp-kicad-lib.

    Returns a result dict on success::

        {"status": "added"|"duplicate"|"disabled"|"not_found",
         "imp_lib": path or None,
         "category": str or None,
         "match": existing part name when status=="duplicate"}

    The function never raises — all failures are logged and reported via ``status``.
    """
    if not config.get("imp_lib_enabled", True):
        return {"status": "disabled", "imp_lib": None, "category": None, "match": None}

    imp_lib = find_imp_lib(lib_dir, fallback_path=config.get("imp_lib_path", ""))
    if not imp_lib:
        return {"status": "not_found", "imp_lib": None, "category": None, "match": None}
    log(f"imp-kicad-lib: detected at {imp_lib}")

    category = categorize(part_name, description, easyeda_category)
    log(f"imp-kicad-lib: auto-category = {category}__C")

    if force_overwrite:
        log("imp-kicad-lib: force-overwrite requested — bypassing dedupe check")
    elif config.get("imp_lib_dedupe", True):
        log(f"imp-kicad-lib: checking {category}__C and related categories for similar parts...")
        match = find_match(imp_lib, category, description, part_name=part_name, lcsc_code=lcsc_code)
        if match:
            existing_cat = match.get("category", category)
            reason = match.get("reason", "equivalent")
            log(
                f"imp-kicad-lib: SKIPPED — {reason}: {match['name']} ({match['spec']}) "
                f"already exists in {existing_cat}__C"
            )
            return {
                "status": "duplicate",
                "imp_lib": imp_lib,
                "category": category,
                "match": match["name"],
            }
        log("imp-kicad-lib: no similar part found — will contribute as new part")
    else:
        log("imp-kicad-lib: dedupe disabled — skipping similarity check")

    # Locate the source STEP file that was written by the importer
    step_src = os.path.join(lib_dir, f"{lib_name}.3dshapes", f"{fp_name}.step")
    if not os.path.isfile(step_src):
        step_src = None

    written, _paths = write_imp_lib_files(
        imp_lib=imp_lib,
        part_name=part_name,
        fp_name=fp_name,
        category=category,
        description=description,
        sym_content=sym_content,
        fp_content=fp_content,
        step_src=step_src,
    )
    rel_written = [os.path.relpath(p, imp_lib) for p in written]
    log(f"imp-kicad-lib: wrote {len(rel_written)} file(s) to {category}__C")

    if config.get("imp_lib_auto_push", True):
        commit_and_push(
            imp_lib_path=imp_lib,
            relative_paths=rel_written,
            message=f"Add {part_name} via JLCImport-Imp plugin",
            push=True,
            log=log,
        )
    return {
        "status": "added",
        "imp_lib": imp_lib,
        "category": category,
        "match": None,
    }
