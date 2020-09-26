import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib

from ..operation import Operation, SkippedOperation
from ..file import File
from ..utils import get_md5

import logging
import tempfile
import os
from pathlib import Path
from threading import current_thread

logger = logging.getLogger(__name__)

class LocalCopierOperation(Operation):
    NAME = 'Local Copier'


    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._cancellable = Gio.Cancellable()
        grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(grid)

        # boxes are needed for
        # destination folder
        # that's it??
        # a button to force creation of the destination folder is not necessary,
        # as we use a filechooserdialog to select it, and create it from there if necessary.

        label = Gtk.Label(
            label='Destination',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        grid.attach(label, 0, 0, 1, 1)

        directory_chooser_button = self.register_widget(Gtk.FileChooserButton(
            title="Select a directory to copy monitored files to",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            create_folders=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False), 'destination_directory')
        grid.attach(directory_chooser_button, 1, 0, 1, 1)

    def preflight_check(self):
        logger.debug(f'Try copying a test file to the destination folder {self.params.destination_directory}')

        # ensure destination is not None
        if self.params.destination_directory is None:
            raise ValueError('Destination folder cannot be empty')

        # destination directory cannot be monitored directory!!
        if Path(self.params.destination_directory).samefile(self.appwindow.params.monitored_directory):
            raise ValueError('Destination folder cannot be the same as the monitored directory')

        # when using recursive monitoring, the destination directory cannot be a subdirectory of the monitored directory
        if self.appwindow.params.monitor_recursively:
            try:
                Path(self.params.destination_directory).resolve().relative_to(Path(self.appwindow.params.monitored_directory))
            except ValueError:
                pass
            else:
                raise ValueError('The destination directory cannot be a subdirectory of the monitored directory when monitoring recursively.')

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(os.urandom(1024))
            tmpfile = f.name
        try:
            gtmpfile = Gio.File.new_for_path(tmpfile)
            destination_file = str(Path(self.params.destination_directory, Path(tmpfile).name))
            gdestination_file = Gio.File.new_for_path(destination_file)
            gtmpfile.copy(gdestination_file, Gio.FileCopyFlags.NONE)
        except GLib.Error:
            logger.exception(f'Error copying {tmpfile} to {self.params.destination_directory}')
            raise
        else:
            # delete copied file
            os.unlink(destination_file)
        finally:
            # remove temporary file
            os.unlink(tmpfile)

    def run(self, file: File):

        try:
            gsource_file = Gio.File.new_for_path(file.filename)
            destination_file = Path(self.params.destination_directory, *file.relative_filename.parts)

            # skip if the file has been copied already
            if destination_file.exists() and \
                Path(file.filename).stat().st_size == destination_file.stat().st_size:
                # calculate checksums
                local_md5 = get_md5(file.filename)
                copy_md5 = get_md5(destination_file)

                if local_md5 == copy_md5:
                    raise SkippedOperation('File has been copied already')

            # make parent directories if necessary
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            gdestination_file = Gio.File.new_for_path(str(destination_file))
            gsource_file.copy(gdestination_file, Gio.FileCopyFlags.NONE, file.cancellable, LocalCopyProgressPercentage(file, self))
        except SkippedOperation:
            raise
        except Exception as e:
            logger.exception(f'LocalCopierOperation.run exception')
            return str(e)
        else:
            # add destination path to metadata
            file.operation_metadata[self.index] = {'local copy path': destination_file}
            logger.debug(f"{file.operation_metadata[self.index]=}")
        return None

class LocalCopyProgressPercentage():
    def __init__(self, file: File, operation: Operation):
        self._file = file
        self._last_percentage = 0
        self._operation = operation

    def __call__(self, current_num_bytes, total_num_bytes):
        thread = current_thread()
        if thread.should_exit:
            self._file.cancellable.cancel()
            return
        percentage = (current_num_bytes / total_num_bytes) * 100
        if int(percentage) > self._last_percentage:
            self._last_percentage = int(percentage)
            self._file.update_progressbar(self._operation.index, self._last_percentage)

        
