import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..operation import Operation
from ..file import File

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

class DropboxUploaderOperation(Operation):
    NAME = "Dropbox Uploader"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)