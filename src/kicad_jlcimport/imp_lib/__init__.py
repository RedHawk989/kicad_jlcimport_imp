"""Integration with the imp-kicad-lib shared component library.

When enabled (the default) and an `imp-kicad-lib` checkout is discoverable
either as a git submodule of the active KiCad project or via a configured
fallback path, freshly-imported parts are:

1. Checked against the existing library for same-spec duplicates.
   Strict matches block the import and report the existing part name.
2. Categorised (Capacitor_SMD__C, Basic_Capacitors_Resistors__C, Inductor__C,
   LED__C, Transistor_FET__C, Connector_USB__C, Switch__C, or to-be-organized).
3. Reformatted to match the library's conventions: correct Reference,
   Description property, hidden Value on passives, purple ``_1_1`` text
   annotation (e.g. ``100nF/50V/X7R``), Footprint property prefixed with
   ``<Category>__C:``.
4. Written into the library's per-symbol layout
   (``symbols/<Cat>__C.kicad_symdir/<part>.kicad_sym`` etc.).
5. Optionally git-committed and pushed.
"""

from .api import try_contribute
from .categorize import categorize
from .dedupe import find_similar
from .discovery import find_imp_lib
from .gitops import pull_latest
from .remove import find_part, remove_part

__all__ = [
    "try_contribute",
    "remove_part",
    "find_part",
    "find_similar",
    "find_imp_lib",
    "categorize",
    "pull_latest",
]
