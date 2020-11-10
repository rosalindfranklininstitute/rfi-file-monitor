import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import logging

from ..operation import Operation
from ..utils.decorators import with_pango_docs,supported_filetypes
from ..file import SubFolder, RegularFile

logger = logging.getLogger(__name__)


@supported_filetypes(filetypes=SubFolder)
class DummyFolderOperation(Operation):
    NAME = "Dummy Folder Operation"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            row_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)
        self._grid.attach(Gtk.Label(label='This is a dummy folder operation'), 0, 0, 1, 1)

    def preflight_check(self):
        metadata = dict(example='metadata')
        if metadata:
            self.appwindow.preflight_check_metadata[self.index] = metadata
    def run(self, file: SubFolder):

        logger.debug(f'Processing {file.filename}')
        return None