"""Git add / commit / push helpers for the imp-kicad-lib checkout."""

from __future__ import annotations

import subprocess
from typing import Callable, List, Tuple


def _run(cmd: List[str], cwd: str) -> Tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def commit_and_push(
    imp_lib_path: str,
    relative_paths: List[str],
    message: str,
    push: bool = True,
    log: Callable[[str], None] = print,
) -> bool:
    """Stage given paths, create a commit, optionally push.

    Returns True if the commit (and push if requested) succeeded.  Push failures
    are surfaced via ``log`` but do not raise — the local commit is still made.
    """
    if not relative_paths:
        return False

    rc, out = _run(["git", "add", "--"] + relative_paths, imp_lib_path)
    if rc != 0:
        log(f"imp-kicad-lib: git add failed: {out}")
        return False

    rc, out = _run(["git", "diff", "--cached", "--quiet"], imp_lib_path)
    if rc == 0:
        log("imp-kicad-lib: nothing to commit (files already up to date)")
        return False

    rc, out = _run(["git", "commit", "-m", message], imp_lib_path)
    if rc != 0:
        log(f"imp-kicad-lib: git commit failed: {out}")
        return False
    log(f"imp-kicad-lib: committed — {message}")

    if push:
        rc, out = _run(["git", "push"], imp_lib_path)
        if rc != 0:
            log(f"imp-kicad-lib: git push failed (commit kept locally): {out.splitlines()[-1] if out else ''}")
            return False
        log("imp-kicad-lib: pushed to remote")
    return True
