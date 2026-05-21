"""Remove a part from imp-kicad-lib across all category directories."""

from __future__ import annotations

import os
from typing import Callable

from .discovery import find_imp_lib
from .gitops import commit_and_push


def _scan(imp_lib: str, subdir: str, ext: str, part_name: str):
    """Yield (category, absolute_path) for every file `<part_name><ext>` under
    `imp_lib/<subdir>/<Cat>__C<suffix>/`."""
    root = os.path.join(imp_lib, subdir)
    if not os.path.isdir(root):
        return
    for d in os.listdir(root):
        sub = os.path.join(root, d)
        if not os.path.isdir(sub):
            continue
        target = os.path.join(sub, f"{part_name}{ext}")
        if os.path.isfile(target):
            yield d, target


def find_part(imp_lib: str, part_name: str) -> dict:
    """Return all files that would be removed for ``part_name``."""
    return {
        "symbols": [(d, p) for d, p in _scan(imp_lib, "symbols", ".kicad_sym", part_name)],
        "footprints": [(d, p) for d, p in _scan(imp_lib, "footprints", ".kicad_mod", part_name)],
        "models": [(d, p) for d, p in _scan(imp_lib, "packages3d", ".step", part_name)],
    }


def remove_part(
    *,
    imp_lib_path: str = "",
    part_name: str,
    config: dict | None = None,
    log: Callable[[str], None] = print,
    auto_push: bool = True,
) -> dict:
    """Remove all symbol/footprint/3D model files matching ``part_name`` from
    imp-kicad-lib, commit, and (optionally) push.

    Returns ``{"status": "removed"|"not_found"|"not_detected"|"error",
                "removed_paths": [...], "imp_lib": path|None}``.
    """
    config = config or {}
    imp_lib = imp_lib_path or find_imp_lib(os.getcwd(), fallback_path=config.get("imp_lib_path", ""))
    if not imp_lib:
        log("imp-kicad-lib: not detected — cannot remove")
        return {"status": "not_detected", "removed_paths": [], "imp_lib": None}

    found = find_part(imp_lib, part_name)
    total = len(found["symbols"]) + len(found["footprints"]) + len(found["models"])
    if total == 0:
        log(f"imp-kicad-lib: no files found for '{part_name}'")
        return {"status": "not_found", "removed_paths": [], "imp_lib": imp_lib}

    removed = []
    for kind in ("symbols", "footprints", "models"):
        for _d, path in found[kind]:
            try:
                os.remove(path)
                rel = os.path.relpath(path, imp_lib)
                removed.append(rel)
                log(f"imp-kicad-lib: removed {rel}")
            except OSError as exc:
                log(f"imp-kicad-lib: failed to remove {path}: {exc}")

    if not removed:
        return {"status": "error", "removed_paths": [], "imp_lib": imp_lib}

    if auto_push:
        commit_and_push(
            imp_lib_path=imp_lib,
            relative_paths=removed,
            message=f"Remove {part_name} via JLCImport-Imp plugin",
            push=True,
            log=log,
        )
    return {"status": "removed", "removed_paths": removed, "imp_lib": imp_lib}
