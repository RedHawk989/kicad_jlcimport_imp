"""KiCad ActionPlugin subclass for JLCImport-Imp."""

import os

import pcbnew
import wx

from .dialog import JLCImportImpDialog
from .kicad.version import detect_kicad_version_from_pcbnew


class JLCImportImpPlugin(pcbnew.ActionPlugin):
    _dialog = None

    def defaults(self):
        self.name = "JLCImport-Imp"
        self.category = "Import"
        self.description = "Import symbols, footprints, and 3D models from LCSC/EasyEDA"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

    @staticmethod
    def _clear_dialog():
        """Callback for the dialog to clear the singleton reference."""
        JLCImportImpPlugin._dialog = None

    def Run(self):
        if JLCImportImpPlugin._dialog is not None:
            JLCImportImpPlugin._dialog.Raise()
            return
        board = pcbnew.GetBoard()
        kicad_version = detect_kicad_version_from_pcbnew()
        parent = wx.FindWindowByName("PcbFrame") or wx.FindWindowByName("SchematicFrame")
        dlg = JLCImportImpDialog(parent, board, kicad_version=kicad_version, on_close=self._clear_dialog)
        JLCImportImpPlugin._dialog = dlg
        dlg.Show()
