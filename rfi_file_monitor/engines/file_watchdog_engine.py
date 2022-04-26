from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ..utils import match_path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from ..engine import Engine, EngineThread
from ..utils import (
    LongTaskWindow,
    get_file_creation_timestamp,
    _get_common_patterns,
)
from ..file import FileStatus
from ..files.regular_file import RegularFile
from ..utils.decorators import (
    exported_filetype,
    with_advanced_settings,
    with_pango_docs,
    do_bulk_upload,
)
from .file_watchdog_engine_advanced_settings import (
    FileWatchdogEngineAdvancedSettings,
)

from typing import List
from pathlib import Path, PurePath
import logging
import os

logger = logging.getLogger(__name__)

ERROR_MSG = "Ensure that the selected directory is readable and that any provided patterns do not conflict"


@with_pango_docs(filename="file_watchdog_engine.pango")
@with_advanced_settings(
    engine_advanced_settings=FileWatchdogEngineAdvancedSettings
)
@exported_filetype(filetype=RegularFile)
class FileWatchdogEngine(Engine):

    NAME = "Files Monitor"

    def __init__(self, appwindow):
        super().__init__(appwindow, FileWatchdogEngineThread, ERROR_MSG)

        label = Gtk.Label(
            label="Monitored Directory",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        self.attach(label, 0, 0, 1, 1)

        self._directory_chooser_button = self.register_widget(
            Gtk.FileChooserButton(
                title="Select a directory for monitoring",
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                create_folders=True,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.FILL,
                hexpand=True,
                vexpand=False,
            ),
            "monitored_directory",
        )
        self.attach(self._directory_chooser_button, 1, 0, 1, 1)
        self._directory_chooser_button.connect(
            "selection-changed", self._directory_chooser_button_cb
        )

        self._monitor: Observer = None

    def _directory_chooser_button_cb(self, button):
        if (
            self.params.monitored_directory is None
            or Path(self.params.monitored_directory).is_dir() is False
        ):
            self._valid = False
        else:
            try:
                os.listdir(self.params.monitored_directory)
                self._valid = True
            except Exception:
                self._valid = False

        self.notify("valid")


# add our ExitableThread methods to Watchdog's Observer class to ensure it can be used as an EngineThread
class FileWatchdogEngineThread(Observer):
    def __init__(self, engine: FileWatchdogEngine, task_window: LongTaskWindow):
        super().__init__()
        self._should_exit: bool = False
        self._engine: Engine = engine
        self.params = engine.params
        self._task_window = task_window
        app = engine.appwindow.props.application
        self._included_patterns = app.get_allowed_file_patterns(
            self.params.allowed_patterns
        )
        self._excluded_patterns = app.get_ignored_file_patterns(
            self.params.ignore_patterns
        )

        self.schedule(
            event_handler=EventHandler(engine),
            path=engine.params.monitored_directory,
            recursive=engine.params.monitor_recursively,
        )

    @property
    def should_exit(self):
        return self._should_exit

    @should_exit.setter
    def should_exit(self, value: bool):
        self._should_exit = value
        if self._should_exit:
            self.stop()

    def _search_for_existing_files(self, directory: Path) -> List[RegularFile]:
        rv: List[RegularFile] = list()
        path_tree = os.walk(directory)
        for root, dirs, files in path_tree:
            for fname in files:
                if not Path(fname).is_symlink() and match_path(
                    Path(fname),
                    included_patterns=self._included_patterns,
                    excluded_patterns=self._excluded_patterns,
                    case_sensitive=False,
                ):
                    file_path = Path(os.path.join(root, fname))
                    relative_file_path = file_path.relative_to(
                        self.params.monitored_directory
                    )
                    _file = RegularFile(
                        str(file_path),
                        relative_file_path,
                        get_file_creation_timestamp(file_path),
                        FileStatus.SAVED,
                    )
                    rv.append(_file)
        GLib.idle_add(
            self._engine._appwindow._queue_manager.get_total_files_in_path,
            len(rv),
            priority=GLib.PRIORITY_DEFAULT_IDLE,
        )

        return rv

    @do_bulk_upload
    def process_existing_files(self, existing_files):
        try:
            GLib.idle_add(
                self._engine._appwindow._queue_manager.add,
                existing_files,
                priority=GLib.PRIORITY_DEFAULT_IDLE,
            )
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                e,
                priority=GLib.PRIORITY_HIGH,
            )
        GLib.idle_add(
            self._engine.kill_task_window,
            self._task_window,
            priority=GLib.PRIORITY_HIGH,
        )
        return

    def run(self):
        # confirm patterns are valid
        if bool(
            common_patterns := _get_common_patterns(
                self._included_patterns, self._excluded_patterns, False
            )
        ):
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                f"Common patterns {common_patterns} detected!",
                priority=GLib.PRIORITY_HIGH,
            )
            return

        # check for existing files if necessary
        if self.params.process_existing_files:
            GLib.idle_add(
                self._task_window.set_text,
                "<b>Processing existing files...</b>",
            )

            existing_files = self._search_for_existing_files(
                Path(self.params.monitored_directory)
            )
            self.process_existing_files(existing_files)
            return

        # if we get here, things should be working.
        # close task_window
        GLib.idle_add(
            self._engine.kill_task_window,
            self._task_window,
            priority=GLib.PRIORITY_HIGH,
        )

        # kick off watchdog's run method
        super().run()

    def on_thread_stop(self):
        super().on_thread_stop()
        self._engine.cleanup()


EngineThread.register(FileWatchdogEngineThread)


class EventHandler(PatternMatchingEventHandler):
    def __init__(self, engine: FileWatchdogEngine):
        self._engine = engine
        self.params = engine.params
        app = engine.appwindow.props.application
        included_patterns = app.get_allowed_file_patterns(
            self.params.allowed_patterns
        )
        ignore_patterns = app.get_ignored_file_patterns(
            self.params.ignore_patterns
        )
        super().__init__(
            patterns=included_patterns,
            ignore_patterns=ignore_patterns,
            ignore_directories=True,
        )

    def on_created(self, event):
        file_path = event.src_path
        logger.info(f"Monitor found {file_path} for event type CREATED")
        relative_file_path = PurePath(
            os.path.relpath(file_path, self.params.monitored_directory)
        )
        if (
            self._engine.props.running
            and self._engine._appwindow._queue_manager.props.running
        ):
            creation_timestamp = get_file_creation_timestamp(file_path)
            if creation_timestamp:
                _file = RegularFile(
                    file_path,
                    relative_file_path,
                    creation_timestamp,
                    FileStatus.CREATED,
                )
            else:
                logger.info(f"File Not found, {file_path} has been skipped")
                return None
            GLib.idle_add(
                self._engine._appwindow._queue_manager.add,
                _file,
                priority=GLib.PRIORITY_HIGH,
            )

    def on_modified(self, event):
        file_path = event.src_path
        logger.info(f"Monitor found {file_path} for event type MODIFIED")
        if (
            self._engine.props.running
            and self._engine._appwindow._queue_manager.props.running
        ):
            GLib.idle_add(
                self._engine._appwindow._queue_manager.saved,
                file_path,
                priority=GLib.PRIORITY_HIGH,
            )
