from threading import current_thread
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..operation import Operation
from ..file import Directory
from ..utils import ExitableThread, get_random_string
from ..utils.decorators import supported_filetypes, with_pango_docs
from ..utils.exceptions import SkippedOperation

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Tuple
import tarfile
import zipfile
from pathlib import Path
import os.path


logger = logging.getLogger(__name__)


@dataclass
class Compressor:
    opener: Callable
    mode: str
    adder: str  # 'add' (tar) or 'write' (zip)
    suffix: str
    opener_args: Dict[str, Any] = field(default_factory=dict)


COMPRESSORS: Dict[str, Compressor] = {
    "TAR + GZIP": Compressor(tarfile.open, "w:gz", "add", ".tar.gz"),
    "TAR + BZIP2": Compressor(tarfile.open, "w:bz2", "add", ".tar.bz2"),
    "TAR + LZMA": Compressor(tarfile.open, "w:xz", "add", ".tar.xz"),
    "TAR": Compressor(tarfile.open, "w", "add", ".tar"),
    "ZIP": Compressor(
        zipfile.ZipFile,
        "w",
        "write",
        ".zip",
        opener_args=dict(compression=zipfile.ZIP_DEFLATED),
    ),
}


@supported_filetypes(filetypes=Directory)
@with_pango_docs(filename="directory_compressor.pango")
class DirectoryCompressorOperation(Operation):

    NAME = "Directory Compressor"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        grid = Gtk.Grid(
            border_width=5,
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.add(grid)

        # boxes are needed for
        # destination folder
        # compression type

        label = Gtk.Label(
            label="Destination",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        grid.attach(label, 0, 0, 1, 1)

        directory_chooser_button = self.register_widget(
            Gtk.FileChooserButton(
                title="Select a directory to copy compressed files to",
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                create_folders=True,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "destination_directory",
        )
        grid.attach(directory_chooser_button, 1, 0, 1, 1)

        grid.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            0,
            1,
            2,
            1,
        )

        label = Gtk.Label(
            label="Compression Type",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        grid.attach(label, 0, 2, 1, 1)

        compression_type_combo_box = self.register_widget(
            Gtk.ComboBoxText(
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "compression_type",
        )

        grid.attach(compression_type_combo_box, 1, 2, 1, 1)
        for compression_type in COMPRESSORS:
            compression_type_combo_box.append_text(compression_type)
        compression_type_combo_box.set_active(0)

    def preflight_check(self):
        # ensure destination is not None
        if self.params.destination_directory is None:
            raise ValueError("Destination folder cannot be empty")

        # ensure we are not writing into the monitored directory
        from ..engines.directory_watchdog_engine import DirectoryWatchdogEngine

        if not isinstance(
            self.appwindow.active_engine, DirectoryWatchdogEngine
        ):
            raise ValueError(
                "DirectoryCompressor currently only works with DirectoryWatchdog engines!"
            )

        self._monitored_directory = (
            self.appwindow.active_engine._get_params().monitored_directory
        )

        if Path(self.params.destination_directory).samefile(
            self._monitored_directory
        ):
            raise ValueError(
                "Destination folder cannot be the same as the monitored directory"
            )

        try:
            Path(self.params.destination_directory).resolve().relative_to(
                Path(self._monitored_directory)
            )
        except ValueError:
            pass
        else:
            raise ValueError(
                "The destination directory cannot be a subdirectory of the monitored directory."
            )

        # ensure the destination is writable
        tempfile = Path(
            self.params.destination_directory, get_random_string(10)
        )
        try:
            with tempfile.open("w") as f:
                f.write("teststring")
        except Exception as e:
            raise ValueError(f"Cannot write to destination folder: {str(e)}")
        else:
            tempfile.unlink(missing_ok=True)

    def _check_existing_zipfile(
        self, _zipfile: Path, file_list: List[Tuple[str, int]]
    ):
        if not _zipfile.exists() or not zipfile.is_zipfile(_zipfile):
            return

        with zipfile.ZipFile(_zipfile) as f:
            zipped_files = dict(
                zip(
                    map(
                        lambda x: os.path.join(self._monitored_directory, x),
                        f.namelist(),
                    ),
                    f.infolist(),
                )
            )

        if len(zipped_files) != len(file_list):
            return

        for _filename, _size in file_list:
            if _filename not in zipped_files:
                return
            zipped_file = zipped_files[_filename]
            if _size != zipped_file.file_size:
                return
            elif os.stat(_filename).st_mtime > _zipfile.stat().st_mtime:
                return

        raise SkippedOperation("Zipfile contents are equal to directory")

    def _check_existing_tarfile(
        self, _tarfile: Path, file_list: List[Tuple[str, int]]
    ):
        if not _tarfile.exists() or not tarfile.is_tarfile(_tarfile):
            return

        with tarfile.open(_tarfile) as f:
            zipped_files = dict(
                zip(
                    map(
                        lambda x: os.path.join(self._monitored_directory, x),
                        f.getnames(),
                    ),
                    f.getmembers(),
                )
            )

        if len(zipped_files) != len(file_list):
            return

        for _filename, _size in file_list:
            if _filename not in zipped_files:
                return
            zipped_file = zipped_files[_filename]
            if _size != zipped_file.size:
                return
            elif os.stat(_filename).st_mtime > zipped_file.mtime:
                return

        raise SkippedOperation("Tarball contents are equal to directory")

    def run(self, dir: Directory):  # type: ignore[override]

        compressor = COMPRESSORS[self.params.compression_type]

        destination_filename = Path(
            self.params.destination_directory, dir.relative_filename.name
        ).with_suffix(compressor.suffix)

        our_thread = current_thread()

        total_size = dir.total_size
        file_list = list(dir)
        number_of_files = len(dir)
        size_seen = 0

        if "tar" in compressor.suffix:
            self._check_existing_tarfile(destination_filename, file_list)
        elif "zip" in compressor.suffix:
            self._check_existing_zipfile(destination_filename, file_list)

        with compressor.opener(
            destination_filename, compressor.mode, **compressor.opener_args
        ) as f:
            for _file_index, (_file, _size) in enumerate(dir):
                if (
                    isinstance(our_thread, ExitableThread)
                    and our_thread.should_exit
                ):
                    return "Job aborted"
                arcname = os.path.relpath(_file, self._monitored_directory)
                getattr(f, compressor.adder)(_file, arcname)

                if total_size == 0:
                    dir.update_progressbar(
                        self.index, 100.0 * (_file_index + 1) / number_of_files
                    )
                else:
                    size_seen += _size
                    dir.update_progressbar(
                        self.index, 100.0 * size_seen / total_size
                    )
