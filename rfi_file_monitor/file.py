from enum import auto, IntEnum, unique
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio

import logging
from pathlib import PurePath
from typing import Final, Dict, Any

logger = logging.getLogger(__name__)

@unique
class FileStatus(IntEnum):
    CREATED = auto()
    SAVED = auto()
    QUEUED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    REMOVED_FROM_LIST = auto()

    def __str__(self):
        #pylint: disable=no-member
        return self.name.lower().capitalize().replace('_', ' ')

class File:
    def __init__(self, \
        filename: str, \
        relative_filename: PurePath, \
        created: int, \
        status: FileStatus, \
        row_reference: Gtk.TreeRowReference):

        self._filename = filename
        self._relative_filename = relative_filename
        self._created = created
        self._status = status
        self._row_reference = row_reference
        self._operation_metadata : Final[Dict[int, Dict[str, Any]]] = dict()
        self._cancellable = Gio.Cancellable()
        self._saved : int = 0

    @property
    def cancellable(self) -> Gio.Cancellable:
        return self._cancellable

    @property
    def operation_metadata(self) -> Dict[int, Dict[str, Any]]:
        return self._operation_metadata

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def relative_filename(self) -> PurePath:
        return self._relative_filename

    @property
    def created(self) -> int:
        return self._created

    @property
    def saved(self) -> int:
        return self._saved

    @saved.setter
    def saved(self, value: int):
        self._saved = value

    @property
    def status(self) -> FileStatus:
        return self._status

    @status.setter
    def status(self, value: FileStatus):
        self._status = value

    @property
    def row_reference(self):
        return self._row_reference

    def _update_progressbar_worker_cb(self, index: int, value: float):
        #logger.debug(f"_update_progressbar_worker_cb: {index=} {value=}")
        if not self.row_reference.valid():
            logger.warning(f"_update_progressbar_worker_cb: {self.filename} is invalid!")
            return GLib.SOURCE_REMOVE

        model = self.row_reference.get_model()
        path = self.row_reference.get_path()
        parent_iter = model.get_iter(path)
        n_children = model.iter_n_children(parent_iter)

        cumul_value = (index * 100.0 + value) / n_children
        model[parent_iter][4] = cumul_value
        model[parent_iter][5] = f"{cumul_value:.1f} %"

        child_iter = model.iter_nth_child(parent_iter, index)
        model[child_iter][4] = value
        model[child_iter][5] = f"{value:.1f} %"
        
        return GLib.SOURCE_REMOVE

    def _update_status_worker_cb(self, index: int, status: FileStatus):
        if not self.row_reference.valid():
            logger.warning(f"_update_status_worker_cb: {self.filename} is invalid!")
            return GLib.SOURCE_REMOVE

        model = self.row_reference.get_model()
        path = self.row_reference.get_path()
        iter = model.get_iter(path)

        if index == -1: # parent
            self.status = int(status)
            iter = model.get_iter(path)
        else:
            iter = model.iter_nth_child(iter, index)

        model[iter][2] = int(status)
        
        # When the operation succeeds, ensure that the progressbars go
        # to 100 %, which is necessary when the operation doesnt
        # do any progress updated (which would be unfortunate!)
        if status == FileStatus.SUCCESS:
            model[iter][4] = 100.0
            model[iter][5] = "100.0 %"

        return GLib.SOURCE_REMOVE

    def update_status(self, index: int, status: FileStatus):
        """
        When an operation has finished, update the status of the corresponding
        entry in the treemodel.
        An index of -1 refers to the parent entry, 0 or higher refers to a child.
        """
        GLib.idle_add(self._update_status_worker_cb, index, status)

    def update_progressbar(self, index: int, value: float):
        """
        This method will update the progressbar of the current operation,
        defined by index, as well as the global one.
        value must be between 0 and 100.

        Try not to use this function too often, as it may slow the GUI
        down considerably. I recommend to use it only when value is a whole number
        """
        GLib.idle_add(self._update_progressbar_worker_cb, index, value)

