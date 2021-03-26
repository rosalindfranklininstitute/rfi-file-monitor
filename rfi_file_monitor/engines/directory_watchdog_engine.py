from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ..utils import match_path, _get_common_patterns
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    DirCreatedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
)

from .directory_watchdog_engine_advanced_settings import (
    DirectoryWatchdogEngineAdvancedSettings,
)
from ..engine import Engine, EngineThread
from ..file import Directory, FileStatus
from ..utils import (
    get_file_creation_timestamp,
    LongTaskWindow,
    get_patterns_from_string,
)
from ..utils.decorators import (
    exported_filetype,
    with_advanced_settings,
    with_pango_docs,
)

import logging
from typing import List
from pathlib import Path, PurePath
import os

logger = logging.getLogger(__name__)

ERROR_MSG = "Ensure that the selected directory is readable and that any provided patterns do not conflict"


@with_pango_docs(filename="directory_watchdog_engine.pango")
@with_advanced_settings(
    engine_advanced_settings=DirectoryWatchdogEngineAdvancedSettings
)
@exported_filetype(filetype=Directory)
class DirectoryWatchdogEngine(Engine):

    NAME = "Directories Monitor"

    def __init__(self, appwindow):
        super().__init__(appwindow, DirectoryWatchdogEngineThread, ERROR_MSG)

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
class DirectoryWatchdogEngineThread(Observer):
    def __init__(
        self, engine: DirectoryWatchdogEngine, task_window: LongTaskWindow
    ):
        super().__init__()
        self._engine = engine
        self._task_window = task_window
        app = engine.appwindow.props.application
        self._included_file_patterns = app.get_allowed_file_patterns(
            self.params.allowed_file_patterns
        )
        self._excluded_file_patterns = app.get_ignored_file_patterns(
            self.params.ignore_file_patterns
        )
        self._included_directory_patterns = get_patterns_from_string(
            self.params.allowed_directory_patterns
        )
        self._excluded_directory_patterns = get_patterns_from_string(
            self.params.ignore_directory_patterns, defaults=[]
        )

        self.schedule(
            event_handler=EventHandler(engine),
            path=engine.params.monitored_directory,
            recursive=True,
        )

    @property
    def should_exit(self):
        return self._should_exit

    @should_exit.setter
    def should_exit(self, value: bool):
        self._should_exit = value
        if self._should_exit:
            self.stop()

    def _search_for_existing_files(self, directory: Path) -> int:
        rv: int = 0
        for child in directory.iterdir():
            if (
                child.is_file()
                and not child.is_symlink()
                and match_path(
                    child,
                    included_patterns=self._included_file_patterns,
                    excluded_patterns=self._excluded_file_patterns,
                    case_sensitive=False,
                )
            ):

                rv += 1
            elif child.is_dir() and not child.is_symlink():
                rv += self._search_for_existing_files(directory.joinpath(child))
        return rv

    def _dir_filter(self, child: Path) -> bool:
        return (
            child.is_dir()
            and not child.is_symlink()
            and match_path(
                child,
                included_patterns=self._included_directory_patterns,
                excluded_patterns=self._excluded_directory_patterns,
                case_sensitive=False,
            )
            and (self._search_for_existing_files(child) > 0)
        )

    def _search_for_existing_directories(
        self, directory: Path
    ) -> List[Directory]:
        rv: List[Directory] = list()
        dirs = filter(self._dir_filter, directory.iterdir())

        for _dir in dirs:
            rv.append(
                Directory(
                    str(_dir),
                    PurePath(_dir.name),
                    get_file_creation_timestamp(_dir),
                    FileStatus.SAVED,
                    self._included_file_patterns,
                    self._excluded_file_patterns,
                )
            )
        return rv

    def run(self):
        # confirm patterns are valid
        if bool(
            common_file_patterns := _get_common_patterns(
                self._included_file_patterns,
                self._excluded_file_patterns,
                False,
            )
        ):
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                f"Common file patterns {common_file_patterns} detected!",
                priority=GLib.PRIORITY_HIGH,
            )
            return

        if bool(
            common_directory_patterns := _get_common_patterns(
                self._included_directory_patterns,
                self._excluded_directory_patterns,
                False,
            )
        ):
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                f"Common directory patterns {common_directory_patterns} detected!",
                priority=GLib.PRIORITY_HIGH,
            )
            return

        if self.params.process_existing_directories:
            GLib.idle_add(
                self._task_window.set_text,
                "<b>Processing existing directories...</b>",
            )
            try:
                existing_directories = self._search_for_existing_directories(
                    Path(self.params.monitored_directory)
                )
                GLib.idle_add(
                    self._engine._appwindow._queue_manager.add,
                    existing_directories,
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


EngineThread.register(DirectoryWatchdogEngineThread)


class EventHandler(FileSystemEventHandler):
    def __init__(self, engine: DirectoryWatchdogEngine):
        self._engine = engine
        app = engine.appwindow.props.application
        self._included_file_patterns = app.get_allowed_file_patterns(
            self.params.allowed_file_patterns
        )
        self._excluded_file_patterns = app.get_ignored_file_patterns(
            self.params.ignore_file_patterns
        )
        self._included_directory_patterns = get_patterns_from_string(
            self.params.allowed_directory_patterns
        )
        self._excluded_directory_patterns = get_patterns_from_string(
            self.params.ignore_directory_patterns, defaults=[]
        )
        super().__init__()

        self._empty_directories: List[Directory] = []

    def dispatch(self, event):

        paths = []
        if hasattr(event, "dest_path"):
            paths.append(os.fsdecode(event.dest_path))
        if event.src_path:
            paths.append(os.fsdecode(event.src_path))

        for path in paths:
            _path = Path(path)
            if (
                _path.is_dir()
                and match_path(
                    _path,
                    included_patterns=self._included_directory_patterns,
                    excluded_patterns=self._excluded_directory_patterns,
                    case_sensitive=False,
                )
            ) or (
                match_path(
                    _path,
                    included_patterns=self._included_file_patterns,
                    excluded_patterns=self._excluded_file_patterns,
                    case_sensitive=False,
                )
            ):

                super().dispatch(event)

    def on_created(self, event):
        path = event.src_path
        logger.info(f"Monitor found {path} for event type CREATED")
        path_object: PurePath = PurePath(path)
        rel_path = path_object.relative_to(self.params.monitored_directory)

        if isinstance(event, DirCreatedEvent):
            # if this happens directly within the monitored directory,
            # add path to the internal list
            # else if path is already in self._empty_directories that contains this, do nothing
            # else send a saved event for path, even though it may not exist in the queue!

            if (
                len(rel_path.parts) > 1
                and rel_path.parts[0] not in self._empty_directories
                and self._engine.props.running
                and self._engine._appwindow._queue_manager.props.running
            ):

                GLib.idle_add(
                    self._engine._appwindow._queue_manager.saved,
                    path,
                    priority=GLib.PRIORITY_HIGH,
                )

            elif rel_path.parts[0] not in self._empty_directories:
                logger.info(f"New directory {rel_path.parts[0]} was created")
                self._empty_directories.append(rel_path.parts[0])

        elif isinstance(event, FileCreatedEvent):
            # if the corresponding toplevel directory is in the internal array, it's time to send it to the queue
            # else, this should trigger a saved change of the corresponding Directory instance.
            # ignore if this file is put directly in the monitored directory
            if len(rel_path.parts) == 1:
                logger.info(f"Ignoring file in monitored directory {path}")
                return

            if rel_path.parts[0] in self._empty_directories:
                self._empty_directories.remove(rel_path.parts[0])
                new_path = os.path.join(
                    self.params.monitored_directory, rel_path.parts[0]
                )
                creation_timestamp = get_file_creation_timestamp(new_path)
                if creation_timestamp:
                    _dir = Directory(
                        new_path,
                        PurePath(rel_path.parts[0]),
                        creation_timestamp,
                        FileStatus.CREATED,
                        self._included_file_patterns,
                        self._excluded_file_patterns,
                    )
                else:
                    logger.info(f"File Not found, {path} has been skipped")
                    return
                GLib.idle_add(
                    self._engine._appwindow._queue_manager.add,
                    _dir,
                    priority=GLib.PRIORITY_HIGH,
                )

            elif (
                self._engine.props.running
                and self._engine._appwindow._queue_manager.props.running
            ):

                new_path = os.path.join(
                    self.params.monitored_directory, rel_path.parts[0]
                )
                GLib.idle_add(
                    self._engine._appwindow._queue_manager.saved,
                    new_path,
                    priority=GLib.PRIORITY_HIGH,
                )

        else:
            raise NotImplementedError(
                f"Unknown event type {str(event)} in on_created"
            )

    def on_modified(self, event):
        path = event.src_path
        logger.info(f"Monitor found {path} for event type MODIFIED")
        path_object: PurePath = PurePath(path)
        rel_path = path_object.relative_to(self.params.monitored_directory)

        if isinstance(event, FileModifiedEvent):
            # this should trigger a saved change of the corresponding Directory instance.
            # ignore if this file is put directly in the monitored directory
            if len(rel_path.parts) == 1:
                logger.info(f"Ignoring file in monitored directory {path}")
                return

            elif (
                self._engine.props.running
                and self._engine._appwindow._queue_manager.props.running
            ):
                new_path = os.path.join(
                    self.params.monitored_directory, rel_path.parts[0]
                )
                GLib.idle_add(
                    self._engine._appwindow._queue_manager.saved,
                    new_path,
                    priority=GLib.PRIORITY_HIGH,
                )
