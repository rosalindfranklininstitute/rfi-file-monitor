import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk, GLib
from ..engine import Engine
from pathlib import Path
from ..utils.decorators import exported_filetype
import os
from ..utils.exceptions import AlreadyRunning, NotYetRunning
from ..file import SubFolder


@exported_filetype(filetype=SubFolder)
class DirectoryMonitorEngine(Engine):

    NAME = 'Directory Monitor Engine'

    def __init__(self, appwindow):
        super().__init__( appwindow)
        label = Gtk.Label(
            label='Top Directory',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False
        )
        self.attach(label, 0, 0, 1, 1)

        self._directory_chooser_button = self.register_widget(Gtk.FileChooserButton(
            title="Select a directory for monitoring",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            create_folders=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False), 'monitored_directory')
        self.attach(self._directory_chooser_button, 1, 0, 1, 1)
        self._directory_chooser_button.connect("selection-changed", self._directory_chooser_button_cb)



    def _directory_chooser_button_cb(self, button):
        # self.set_title(f"Monitoring: {self.params.monitored_directory}")
        if self.params.monitored_directory is None or \
                Path(self.params.monitored_directory).is_dir() is False:
            self._valid = False
        else:
            try:
                os.listdir(self.params.monitored_directory)
                self._valid = True
            except PermissionError:
                self._valid = False
        self.notify('valid')

    def start(self):
        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        self._running = True
        self.notify('running')

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        self._running = False
        self.notify('running')