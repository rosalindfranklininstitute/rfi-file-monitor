import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio


from enum import auto, IntEnum, unique
import logging
from pathlib import PurePath, PurePosixPath, Path
from typing import Final, Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
from time import time


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
    SKIPPED = auto()

    def __str__(self):
        # pylint: disable=no-member
        return self.name.lower().capitalize().replace("_", " ")


class File(ABC):
    @abstractmethod
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: float,
        status: FileStatus,
    ):

        self._filename = filename
        self._relative_filename = relative_filename
        self._created: Final[float] = created
        self._status = status
        self._row_reference: Gtk.TreeRowReference = None
        self._operation_metadata: Final[Dict[int, Dict[str, Any]]] = dict()
        self._cancellable = Gio.Cancellable()
        self._saved: float = 0
        self._requeue: bool = False
        self._succeeded: float = 0

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
    def created(self) -> float:
        return self._created

    @property
    def saved(self) -> float:
        return self._saved

    @saved.setter
    def saved(self, value: int):
        self._saved = value

    @property
    def succeeded(self) -> float:
        return self._succeeded

    @succeeded.setter
    def succeeded(self, value: int):
        self._succeeded = value

    @property
    def status(self) -> FileStatus:
        return self._status

    @status.setter
    def status(self, value: FileStatus):
        self._status = value

    @property
    def requeue(self) -> bool:
        return self._requeue

    @requeue.setter
    def requeue(self, value: bool):
        self._requeue = value

    @property
    def row_reference(self) -> Gtk.TreeRowReference:
        return self._row_reference

    @row_reference.setter
    def row_reference(self, value: Gtk.TreeRowReference):
        self._row_reference = value

    def __str__(self):
        return f"{type(self).__name__}: {self._filename} -> {str(self._status)}"

    def _update_progressbar_worker_cb(self, index: int, value: float):
        if not self.row_reference.valid():
            logger.warning(
                f"_update_progressbar_worker_cb: {self.filename} is invalid!"
            )
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

    def _update_status_worker_cb(self, index: int, status: FileStatus, message):
        if not self.row_reference.valid():
            logger.warning(
                f"_update_status_worker_cb: {self.filename} is invalid!"
            )
            return GLib.SOURCE_REMOVE

        model = self.row_reference.get_model()
        path = self.row_reference.get_path()
        iter = model.get_iter(path)

        if index == -1:  # parent
            self.status = status
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
        elif status == FileStatus.FAILURE:
            model[iter][6] = "red"
            model[iter][7] = GLib.markup_escape_text(message)
        elif status == FileStatus.SKIPPED:
            model[iter][6] = "grey"
            model[iter][7] = GLib.markup_escape_text(message)

        return GLib.SOURCE_REMOVE

    def update_status(
        self, index: int, status: FileStatus, message: Optional[str] = None
    ):
        """
        When an operation has finished, update the status of the corresponding
        entry in the treemodel.
        An index of -1 refers to the parent entry, 0 or higher refers to a child.
        """
        GLib.idle_add(self._update_status_worker_cb, index, status, message)

    def update_progressbar(self, index: int, value: float):
        """
        This method will update the progressbar of the current operation,
        defined by index, as well as the global one.
        value must be between 0 and 100.

        Try not to use this function too often, as it may slow the GUI
        down considerably. I recommend to use it only when value is a whole number
        """
        GLib.idle_add(self._update_progressbar_worker_cb, index, value)
