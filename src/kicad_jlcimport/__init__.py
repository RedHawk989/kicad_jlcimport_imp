"""JLCImport-Imp - KiCad 8/9/10 LCSC Component Import Plugin."""

try:
    import pcbnew  # noqa: F401
except ImportError:
    pass  # pcbnew not available (running outside KiCad)
else:
    try:
        from .plugin import JLCImportImpPlugin

        JLCImportImpPlugin().register()
    except Exception:
        import traceback

        traceback.print_exc()
