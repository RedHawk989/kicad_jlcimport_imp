"""Locate the imp-kicad-lib checkout for the active project."""

from __future__ import annotations

import configparser
import os


def _scan_gitmodules(start_dir: str) -> str | None:
    """Walk up from ``start_dir`` looking for a .gitmodules entry whose URL
    points at imp-kicad-lib. Returns the absolute path of the submodule
    checkout, or None.
    """
    cur = os.path.abspath(start_dir or os.getcwd())
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        gm_path = os.path.join(cur, ".gitmodules")
        if os.path.isfile(gm_path):
            cp = configparser.ConfigParser()
            try:
                cp.read(gm_path, encoding="utf-8")
            except (configparser.Error, OSError):
                pass
            else:
                for section in cp.sections():
                    url = cp.get(section, "url", fallback="")
                    path = cp.get(section, "path", fallback="")
                    if "imp-kicad-lib" in url.lower() and path:
                        candidate = os.path.normpath(os.path.join(cur, path))
                        if _looks_like_imp_lib(candidate):
                            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _looks_like_imp_lib(path: str) -> bool:
    """Sanity check that the directory contains the expected layout."""
    if not os.path.isdir(path):
        return False
    return all(os.path.isdir(os.path.join(path, sub)) for sub in ("symbols", "footprints", "packages3d"))


def find_imp_lib(start_dir: str, fallback_path: str = "") -> str | None:
    """Return the absolute path to imp-kicad-lib, or None if not discoverable.

    Search order:
        1. Walk up from ``start_dir`` for a .gitmodules entry referencing imp-kicad-lib.
        2. ``fallback_path`` if provided and it looks like the expected layout.
    """
    found = _scan_gitmodules(start_dir)
    if found:
        return found
    if fallback_path:
        expanded = os.path.expanduser(fallback_path)
        if _looks_like_imp_lib(expanded):
            return os.path.abspath(expanded)
    return None
