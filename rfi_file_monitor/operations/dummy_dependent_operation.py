import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import logging
from ..operation import Operation
from .dummy_operation import DummyOperation
from ..utils.decorators import with_pango_docs, supported_filetypes, add_directory_support
from ..file import File, RegularFile, AWSS3Object, URL, Directory

logger = logging.getLogger(__name__)
@with_pango_docs(filename='dependent_dummy_operation.pango')
@supported_filetypes(filetypes=[RegularFile, Directory])
class DependentDummyOperation(Operation):

    NAME = "Dependent Dummy Operation"
    PREREQUISITES = (DummyOperation,)
    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            row_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)
        self._grid.attach(Gtk.Label(label='This is a dummy dependent operation'), 0, 0, 1, 1)

        widget = Gtk.CheckButton(
            active=False, label="Process Directory Operational Metadata",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(widget, 0, 8, 2, 1)
        widget.connect('toggled', self.on_checked)

    def on_checked(self,widget):
        self.process_dir_metadata = True

    def preflight_check(self):
        pass

    def run(self, file):
         if self.process_dir_metadata:
            if isinstance(file, Directory):
                if file.operation_metadata:
                    for i in file.operation_metadata.values():
                        for k,v in i.items():
                            logger.info(f"****  {k} : {v}")
                else:
                    logger.info("**** no directory info")