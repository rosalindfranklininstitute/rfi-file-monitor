import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..engine import Engine
from ..file import RegularFile, FileStatus
from ..utils.exceptions import AlreadyRunning, NotYetRunning
from ..utils.decorators import exported_filetype, with_pango_docs
from ..utils import ExitableThread

import logging
from tempfile import TemporaryDirectory
from pathlib import Path, PurePath
import os
from time import sleep, time

logger = logging.getLogger(__name__)

SIZE_UNITS = {
    'B': 1,
    'KB': 1000,
    'MB': 1000000,
    'GB': 1000000000,
}

@with_pango_docs(filename='temporary_file_engine.pango')
@exported_filetype(filetype=RegularFile)
class TemporaryFileEngine(Engine):

    NAME = 'Temporary File Generator'

    def __init__(self, appwindow):
        super().__init__(appwindow)

        # Set filesize
        filesize_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )
        self.attach(filesize_grid, 0, 0, 1, 1)
        label = Gtk.Label(
            label='Filesize: ',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        filesize_grid.attach(label, 1, 0, 1, 1)
        filesize_number_spinbutton = self.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=1,
                upper=1024,
                value=10,
                page_size=0,
                step_increment=1),
            value=10,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=5,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'filesize_number', desensitized=True)
        filesize_grid.attach(filesize_number_spinbutton, 2, 0, 1, 1)
        filesize_unit_combobox = Gtk.ComboBoxText(
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        for unit in SIZE_UNITS:
            filesize_unit_combobox.append_text(unit)
        filesize_unit_combobox.set_active(0)
        self.register_widget(filesize_unit_combobox, 'filesize_unit', desensitized=True)
        filesize_grid.attach(filesize_unit_combobox, 3, 0, 1, 1)

        # Add horizontal separator
        separator = Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self.attach(separator, 0, 1, 3, 1)

        # set time between files being created
        time_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )
        self.attach(time_grid, 0, 2, 1, 1)
        label = Gtk.Label(
            label='Time between file creation events: ',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        time_grid.attach(label, 1, 0, 1, 1)
        time_number_spinbutton = self.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=1,
                upper=3600*24,
                value=5,
                page_size=0,
                step_increment=1),
            value=5,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=5,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'creation_delay', desensitized=True)
        time_grid.attach(time_number_spinbutton, 2, 0, 1, 1)

        # Add vertical separator
        separator = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.FILL,
            hexpand=False, vexpand=True,
        )
        self.attach(separator, 1, 0, 1, 3)

        # start index
        start_index_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )
        self.attach(start_index_grid, 2, 0, 1, 1)
        label = Gtk.Label(
            label='Start index: ',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        start_index_grid.attach(label, 0, 0, 1, 1)
        start_index_spinbutton = self.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=0,
                upper=10000,
                value=0,
                page_size=0,
                step_increment=1),
            value=0,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=5,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'start_index', desensitized=False)
        start_index_grid.attach(start_index_spinbutton, 1, 0, 1, 1)

        # prefix
        prefix_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )
        self.attach(prefix_grid, 2, 2, 1, 1)
        label = Gtk.Label(
            label='File prefix: ',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        prefix_grid.attach(label, 0, 0, 1, 1)
        self._prefix_entry = self.register_widget(Gtk.Entry(
            text='test_',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 'file_prefix', desensitized=False)
        prefix_grid.attach(self._prefix_entry, 1, 0, 1, 1)

        # this starts out as valid
        self._valid = True

    def _file_prefix_entry_changed_cb(self, entry):
        if self.params.file_prefix:
            self._valid = True
        else:
            self._valid = False

        self.notify('valid')

    def start(self):
        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        self._tempdir = TemporaryDirectory()
        self._thread = FileGeneratorThread(self)
        self._thread.start()
        self._running = True
        self.notify('running')

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        # if the thread is sleeping, it will be killed at the next iteration
        self._thread.should_exit = True

        self._tempdir.cleanup()

        self._running = False
        self.notify('running')


class FileGeneratorThread(ExitableThread):

    SUFFIX = '.dat'

    def __init__(self, engine: TemporaryFileEngine):
        super().__init__()
        self._engine = engine

    def run(self):
        index = int(self._engine.params.start_index)
        while 1:
            if self.should_exit:
                logger.info('Killing FileGeneratorThread')
                return
            basename = f"{self._engine.params.file_prefix}{index}{self.SUFFIX}"
            path = Path(self._engine._tempdir.name, basename)
            path.write_bytes(os.urandom(int(self._engine.params.filesize_number * SIZE_UNITS[self._engine.params.filesize_unit])))
            logger.debug(f'Writing {str(path)}')
            index = index + 1
            if self._engine.props.running and \
                self._engine._appwindow._queue_manager.props.running:
                _file = RegularFile(str(path), PurePath(basename), time(), FileStatus.CREATED)
                GLib.idle_add(self._engine._appwindow._queue_manager.add, _file, priority=GLib.PRIORITY_HIGH)
            sleep(self._engine.params.creation_delay)
            
            



        