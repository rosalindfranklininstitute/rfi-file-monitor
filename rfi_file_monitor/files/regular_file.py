import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib
from ..file import File, FileStatus
from pathlib import PurePath


class RegularFile(File):
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: int,
        status: FileStatus,
    ):

        super().__init__(
            filename,
            relative_filename,
            created,
            status,
        )


class WeightedRegularFile(RegularFile):
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: int,
        status: FileStatus,
        offset: float,  # fractional
        weight: float,  # fractional
    ):

        super().__init__(
            filename,
            relative_filename,
            created,
            status,
        )

        self._offset = offset
        self._weight = weight

    def update_progressbar(self, index: int, value: float):
        new_value = 100.0 * self._offset + value * self._weight
        GLib.idle_add(self._update_progressbar_worker_cb, index, new_value)
