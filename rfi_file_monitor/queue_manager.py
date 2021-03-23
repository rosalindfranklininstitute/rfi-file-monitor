from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject

from typing import OrderedDict as OrderedDictType
from typing import Final, List, Union, Sequence, Optional
from collections import OrderedDict
from threading import RLock
import logging
import os
from time import time
from dataclasses import dataclass, astuple as dc_astuple

from .file import FileStatus, File
from .job import Job
from .utils.exceptions import AlreadyRunning, NotYetRunning
from .utils.widgetparams import WidgetParams

logger = logging.getLogger(__name__)


class QueueManager(WidgetParams, Gtk.Grid):
    MAX_JOBS = (
        len(getattr(os, "sched_getaffinity")(0))
        if hasattr(os, "sched_getaffinity")
        else os.cpu_count()
    )

    NAME = "Queue Manager"

    def __init__(self, appwindow):
        self._appwindow = appwindow
        self._running = False
        self._files_dict_lock = RLock()
        self._files_dict: OrderedDictType[str, File] = OrderedDict()
        self._jobs_list: Final[List[Job]] = list()
        self._njobs_running: int = 0

        kwargs = dict(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
            border_width=5,
            row_spacing=5,
        )
        Gtk.Grid.__init__(self, **kwargs)
        WidgetParams.__init__(self)

        self.options_child_row_counter = 0

        # Promote created files to saved after # seconds
        created_status_promotion_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(
            created_status_promotion_grid,
            0,
            self.options_child_row_counter,
            1,
            1,
        )
        self.options_child_row_counter += 1
        created_status_promotion_checkbutton = self.register_widget(
            Gtk.CheckButton(
                label="Promote files from 'Created' to 'Saved' after",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "created_status_promotion_active",
            desensitized=True,
        )
        created_status_promotion_grid.attach(
            created_status_promotion_checkbutton, 0, 0, 1, 1
        )
        created_status_promotion_spinbutton = self.register_widget(
            Gtk.SpinButton(
                adjustment=Gtk.Adjustment(
                    lower=1, upper=3600, value=5, page_size=0, step_increment=1
                ),
                value=5,
                update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
                numeric=True,
                climb_rate=5,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "created_status_promotion_delay",
            desensitized=True,
        )
        created_status_promotion_grid.attach(
            created_status_promotion_spinbutton, 1, 0, 1, 1
        )
        created_status_promotion_grid.attach(
            Gtk.Label(label="seconds"), 2, 0, 1, 1
        )

        self._add_horizontal_separator()

        # Delay promoting saved files to queued for # seconds
        saved_status_promotion_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(
            saved_status_promotion_grid, 0, self.options_child_row_counter, 1, 1
        )
        self.options_child_row_counter += 1
        label = Gtk.Label(
            label="Delay promoting files from 'Saved' to 'Queued' for",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        saved_status_promotion_grid.attach(label, 0, 0, 1, 1)
        saved_status_promotion_spinbutton = self.register_widget(
            Gtk.SpinButton(
                adjustment=Gtk.Adjustment(
                    lower=2, upper=3600, value=5, page_size=0, step_increment=1
                ),
                value=5,
                update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
                numeric=True,
                climb_rate=5,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "saved_status_promotion_delay",
            desensitized=True,
        )
        saved_status_promotion_grid.attach(
            saved_status_promotion_spinbutton, 1, 0, 1, 1
        )
        saved_status_promotion_grid.attach(
            Gtk.Label(label="seconds"), 2, 0, 1, 1
        )

        self._add_horizontal_separator()

        # Set the max number of threads to be used for processing
        max_threads_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )
        self.attach(max_threads_grid, 0, self.options_child_row_counter, 1, 1)
        self.options_child_row_counter += 1
        max_threads_grid.attach(
            Gtk.Label(
                label="Maximum number of threads to use",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )

        max_threads_spinbutton = self.register_widget(
            Gtk.SpinButton(
                adjustment=Gtk.Adjustment(
                    lower=1,
                    upper=self.MAX_JOBS,
                    value=max(self.MAX_JOBS // 2, 1),
                    page_size=0,
                    step_increment=1,
                ),
                value=max(self.MAX_JOBS // 2, 1),
                update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
                numeric=True,
                climb_rate=1,
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "max_threads",
            desensitized=True,
        )
        max_threads_grid.attach(max_threads_spinbutton, 1, 0, 1, 1)

        self._add_horizontal_separator()

        # Remove from list after n minutes
        remove_from_list_status_promotion_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(
            remove_from_list_status_promotion_grid,
            0,
            self.options_child_row_counter,
            1,
            1,
        )
        self.options_child_row_counter += 1
        remove_from_list_status_promotion_checkbutton = self.register_widget(
            Gtk.CheckButton(
                label="Remove from table after",
                active=True,
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "remove_from_list_status_promotion_active",
            desensitized=True,
        )
        remove_from_list_status_promotion_grid.attach(
            remove_from_list_status_promotion_checkbutton, 0, 0, 1, 1
        )
        remove_from_list_status_promotion_spinbutton = self.register_widget(
            Gtk.SpinButton(
                adjustment=Gtk.Adjustment(
                    lower=1,
                    upper=60 * 24 * 7,
                    value=60,
                    page_size=0,
                    step_increment=1,
                ),
                value=60,
                update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
                numeric=True,
                climb_rate=5,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "remove_from_list_status_promotion_delay",
            desensitized=True,
        )
        remove_from_list_status_promotion_grid.attach(
            remove_from_list_status_promotion_spinbutton, 1, 0, 1, 1
        )
        remove_from_list_status_promotion_grid.attach(
            Gtk.Label(label="minutes"), 2, 0, 1, 1
        )

    def _add_horizontal_separator(self):
        self.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=True,
            ),
            0,
            self.options_child_row_counter,
            1,
            1,
        )
        self.options_child_row_counter += 1

    @GObject.Property(type=bool, default=False)
    def running(self):
        return self._running

    def _add_to_model(self, file: File):
        # add new entry to model
        outputrow = OutputRow(
            relative_filename=str(file.relative_filename),
            creation_timestamp=file.created,
            status=int(file.status),
            operation_name="All",
        )
        iter = self._appwindow._files_tree_model.append(
            parent=None, row=dc_astuple(outputrow)
        )
        _row_reference = Gtk.TreeRowReference.new(
            self._appwindow._files_tree_model,
            self._appwindow._files_tree_model.get_path(iter),
        )

        # create its children, one for each operation
        for _operation in self._appwindow._operations_box:
            outputrow = OutputRow(
                relative_filename="",
                creation_timestamp=0,
                status=int(FileStatus.QUEUED),
                operation_name=_operation.NAME,
            )
            self._appwindow._files_tree_model.append(
                parent=iter, row=dc_astuple(outputrow)
            )

        file.row_reference = _row_reference

    def add(self, file_or_files: Union[File, Sequence[File]]):
        """Add one or more new files to the queue. Call from the GUI thread!"""

        if not self._running:
            raise NotYetRunning(
                "The queue manager needs to be started before it can be stopped."
            )

        if isinstance(file_or_files, File):
            file_paths = [file_or_files]
        else:
            file_paths = list(file_or_files)

        with self._files_dict_lock:
            for _file in file_paths:
                if not isinstance(_file, File):
                    raise TypeError(f"{str(_file)} must be a File object")

                file_path = _file.filename

                if file_path in self._files_dict:
                    logger.info(
                        f"{file_path} has been recreated! Calling saved..."
                    )
                    self.saved(file_path)
                    continue

                if _file.status == FileStatus.CREATED:
                    logger.debug(f"New file {file_path} created")
                elif _file.status == FileStatus.SAVED:
                    logger.debug(f"Adding existing file {file_path}")
                    _file.saved = time()
                else:
                    raise NotImplementedError(
                        "Newly created files must have CREATED or SAVED as status!"
                    )

                self._add_to_model(_file)

                self._files_dict[file_path] = _file

    def saved(self, file_path: Union[str, Sequence[str]]):
        """Call when the engine detected that the file(s) have been saved (again).vMust be called from the GUI thread!"""

        if not self._running:
            raise NotYetRunning(
                "The queue manager needs to be started before it can be stopped."
            )

        if isinstance(file_path, str):
            file_paths = [file_path]
        else:
            file_paths = list(file_path)

        with self._files_dict_lock:
            for file_path in file_paths:
                try:
                    file = self._files_dict[file_path]
                except KeyError:
                    logger.warning(
                        f"{file_path} has not been created yet! Ignoring..."
                    )
                    continue

                if file.status == FileStatus.SAVED:
                    # looks like this file has been saved again!
                    # update saved timestamp
                    logger.debug(f"File {file_path} has been saved again")
                    file.saved = time()
                elif file.status == FileStatus.CREATED:
                    logger.debug(f"File {file_path} has been saved")
                    file.status = FileStatus.SAVED
                    file.saved = time()
                    path = file.row_reference.get_path()
                    self._appwindow._files_tree_model[path][2] = int(
                        FileStatus.SAVED
                    )
                elif file.status == FileStatus.QUEUED:
                    # file hasn't been processed yet, so it's safe to demote it to SAVED
                    logger.debug(
                        f"File {file_path} has been saved again while queued"
                    )
                    file.status = FileStatus.SAVED
                    path = file.row_reference.get_path()
                    self._appwindow._files_tree_model[path][2] = int(
                        FileStatus.SAVED
                    )
                elif file.status in (
                    FileStatus.RUNNING,
                    FileStatus.SUCCESS,
                    FileStatus.FAILURE,
                ):
                    # file is currently being processed or has been processed -> mark it for being requeued
                    logger.debug(
                        f"File {file_path} has been saved again while {str(file.status)}"
                    )
                    file.requeue = True
                elif file.status is FileStatus.REMOVED_FROM_LIST:
                    # file has already been removed from the list!!
                    logger.debug(
                        f"File {file_path} was removed from list but is now back!"
                    )
                    file.requeue = True
                    self._add_to_model(file)
                else:
                    logger.warning(
                        f"File {file_path} has been saved again after it was queued for processing!!"
                    )

    def start(self):
        if self._running:
            raise AlreadyRunning(
                "The queue manager is already running. It needs to be stopped before it may be restarted"
            )

        self._running = True
        self._timeout_id = GLib.timeout_add_seconds(
            1, self._files_dict_timeout_cb, priority=GLib.PRIORITY_DEFAULT
        )
        self.notify("running")

    def stop(self):
        if not self._running:
            raise NotYetRunning(
                "The queue manager needs to be started before it can be stopped."
            )

        GLib.source_remove(self._timeout_id)
        with self._files_dict_lock:
            self._files_dict.clear()
            self._njobs_running = 0
        for job in self._jobs_list:
            job.should_exit = True
        self._jobs_list.clear()

        self._running = False
        self.notify("running")

    def _files_dict_timeout_cb(self, *user_data):
        """
        This function runs every second, and will take action based on the status of all files in the dict
        It runs in the GUI thread, so GUI updates are allowed here.
        """
        # logger.debug(f"files_dict_timeout_cb enter: {self._njobs_running=} {self.params.max_threads=}")
        with self._files_dict_lock:
            status_counters = {
                FileStatus.CREATED: 0,
                FileStatus.SAVED: 0,
                FileStatus.QUEUED: 0,
                FileStatus.RUNNING: 0,
                FileStatus.SUCCESS: 0,
                FileStatus.FAILURE: 0,
                FileStatus.REMOVED_FROM_LIST: 0,
            }
            for _filename, _file in self._files_dict.items():
                # logger.debug(f"timeout_cb: {_filename} found as {str(_file.status)}")
                if _file.status == FileStatus.CREATED:
                    logger.debug(
                        f"files_dict_timeout_cb: {_filename} was CREATED"
                    )
                    if (
                        self.params.created_status_promotion_active
                        and (time() - _file.created)
                        > self.params.created_status_promotion_delay
                    ):
                        # promote to SAVED!
                        _file.status = FileStatus.SAVED
                        _file.saved = time()
                        path = _file.row_reference.get_path()
                        self._appwindow._files_tree_model[path][2] = int(
                            FileStatus.SAVED
                        )
                        logger.debug(
                            f"files_dict_timeout_cb: promoting {_filename} to SAVED"
                        )

                elif _file.status == FileStatus.SAVED:
                    if (
                        time() - _file.saved
                    ) > self.params.saved_status_promotion_delay:
                        # queue the job
                        logger.debug(
                            f"files_dict_timeout_cb: adding {_filename} to queue for future processing"
                        )
                        _file.status = FileStatus.QUEUED
                        path = _file.row_reference.get_path()
                        self._appwindow._files_tree_model[path][2] = int(
                            _file.status
                        )

                elif _file.status == FileStatus.QUEUED:
                    # logger.debug(f"files_dict_timeout_cb QUEUED: {self._njobs_running=} {self.params.max_threads=}")
                    if self._njobs_running < self.params.max_threads:
                        # try and launch a new job
                        logger.debug(
                            f"files_dict_timeout_cb: launching queued job for {_filename}"
                        )
                        job = Job(self, _file)
                        self._jobs_list.append(job)
                        job.start()
                        self._njobs_running += 1

                elif _file.requeue and _file.status in (
                    FileStatus.SUCCESS,
                    FileStatus.FAILURE,
                    FileStatus.REMOVED_FROM_LIST,
                ):
                    # demote to saved so it gets requeued
                    _file.requeue = False
                    _file.status = FileStatus.SAVED
                    _file.saved = time()
                    _file.succeeded = 0
                    _file.operation_metadata.clear()
                    path = _file.row_reference.get_path()
                    iter = self._appwindow._files_tree_model.get_iter(path)
                    self._appwindow._files_tree_model[iter][2] = int(
                        FileStatus.SAVED
                    )
                    self._appwindow._files_tree_model[iter][4] = 0.0
                    self._appwindow._files_tree_model[iter][5] = "0.0 %"
                    self._appwindow._files_tree_model[iter][6] = None
                    self._appwindow._files_tree_model[iter][7] = ""

                    for child in self._appwindow._files_tree_model[
                        iter
                    ].iterchildren():
                        child[2] = int(FileStatus.QUEUED)
                        child[4] = 0.0
                        child[5] = "0.0 %"
                        child[6] = None
                        child[7] = ""

                    logger.debug(
                        f"files_dict_timeout_cb: requeuing {_filename}"
                    )

                elif _file.status == FileStatus.SUCCESS:
                    if (
                        self.params.remove_from_list_status_promotion_active
                        and (
                            (time() - _file.succeeded)
                            > (
                                60
                                * self.params.remove_from_list_status_promotion_delay
                            )
                        )
                    ):

                        path = _file.row_reference.get_path()

                        # update status
                        _file.status = FileStatus.REMOVED_FROM_LIST
                        # remove from table
                        del self._appwindow._files_tree_model[path]

                status_counters[_file.status] += 1

            # update status bar
            self._appwindow._status_grid.get_child_at(
                0, 0
            ).props.label = f"Total: {len(self._files_dict)}"
            for _status, _counter in status_counters.items():
                self._appwindow._status_grid.get_child_at(
                    int(_status), 0
                ).props.label = f"{str(_status)}: {_counter}"

        return GLib.SOURCE_CONTINUE


@dataclass
class OutputRow:
    relative_filename: str
    creation_timestamp: float
    status: int
    operation_name: str
    operation_progress: float = 0.0
    operation_progress_str: str = "0.0 %"
    background_color: Optional[str] = None
    error_message: str = ""
