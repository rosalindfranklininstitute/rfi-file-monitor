from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from ..utils import match_path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from ..engine import Engine
from ..utils import LongTaskWindow, get_patterns_from_string, get_file_creation_timestamp, DEFAULT_IGNORE_PATTERNS
from ..file import FileStatus, RegularFile
from ..utils.exceptions import AlreadyRunning, NotYetRunning
from ..utils.decorators import exported_filetype, with_advanced_settings, with_pango_docs
from .file_watchdog_engine_advanced_settings import FileWatchdogEngineAdvancedSettings

from threading import Thread
from typing import List, Final
from pathlib import Path, PurePath, PurePosixPath
import logging
import os

logger = logging.getLogger(__name__)

@with_pango_docs(filename='file_watchdog_engine.pango')
@with_advanced_settings(engine_advanced_settings=FileWatchdogEngineAdvancedSettings)
@exported_filetype(filetype=RegularFile)
class FileWatchdogEngine(Engine):

    NAME = 'Files Monitor'

    def __init__(self, appwindow):
        super().__init__(appwindow)

        label = Gtk.Label(
            label='Monitored Directory',
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

        self._monitor : Final[Observer] = None

    def _directory_chooser_button_cb(self, button):
        if self.params.monitored_directory is None or \
            Path(self.params.monitored_directory).is_dir() is False:
            self._valid = False
        else:
            try:
                os.listdir(self.params.monitored_directory)
                self._valid = True
            except Exception:
                self._valid = False
        logger.debug(f'_directory_chooser_button_cb: {self._valid}')
        self.notify('valid')

    def _start_watchdog(self):
        self._monitor = Observer()
        self._monitor.schedule(EventHandler(self), self.params.monitored_directory, recursive=self.params.monitor_recursively)
        self._monitor.start()

        self._running = True
        self.notify('running')

    def start(self):
        # start the engine
        # this assumes that the preflight check has been completed successfully!
        # start by looking for existing files, if requested.

        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        if self.params.process_existing_files:
            # pop up a long task window
            # spawn a thread for this to avoid GUI freezes
            task_window = LongTaskWindow(self._appwindow)
            task_window.set_text("<b>Checking for existing files</b>")
            task_window.show()
            watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
            task_window.get_window().set_cursor(watch_cursor)

            ProcessExistingFilesThread(self, task_window).start()
        else:
            self._start_watchdog()

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        self._monitor.stop()
        self._monitor = None
        self._running = False
        self.notify('running')


    def _process_existing_files_thread_cb(self, task_window: LongTaskWindow, existing_files: List[RegularFile]):
        self._appwindow._queue_manager.add(existing_files)

        # destroy task window
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        self._start_watchdog()

        return GLib.SOURCE_REMOVE

class ProcessExistingFilesThread(Thread):
    def __init__(self, engine: FileWatchdogEngine, task_window: LongTaskWindow):
        super().__init__()
        self._engine = engine
        self._task_window = task_window
        self._included_patterns = get_patterns_from_string(self._engine.params.allowed_patterns)
        self._excluded_patterns = get_patterns_from_string(self._engine.params.ignore_patterns, defaults=DEFAULT_IGNORE_PATTERNS)

    def _search_for_existing_files(self, directory: Path) -> List[RegularFile]:
        rv: List[RegularFile] = list()
        for child in directory.iterdir():
            if child.is_file() \
                and not child.is_symlink() \
                and match_path(PurePosixPath(child), included_patterns=self._included_patterns, excluded_patterns=self._excluded_patterns,
                               case_sensitive=False):
                
                file_path = directory.joinpath(child)
                relative_file_path = file_path.relative_to(self._engine.params.monitored_directory)
                _file = RegularFile(str(file_path), relative_file_path, get_file_creation_timestamp(file_path), FileStatus.SAVED)
                rv.append(_file)
            elif self._engine.params.monitor_recursively and child.is_dir() and not child.is_symlink():
                rv.extend(self._search_for_existing_files(directory.joinpath(child)))
        return rv
    
    def run(self):
        existing_files = self._search_for_existing_files(Path(self._engine.params.monitored_directory))
        GLib.idle_add(self._engine._process_existing_files_thread_cb, self._task_window, existing_files, priority=GLib.PRIORITY_DEFAULT_IDLE)


class EventHandler(PatternMatchingEventHandler):
    def __init__(self, engine: FileWatchdogEngine):
        self._engine = engine 
        included_patterns = get_patterns_from_string(self._engine.params.allowed_patterns)
        ignore_patterns =  get_patterns_from_string(self._engine.params.ignore_patterns, defaults=DEFAULT_IGNORE_PATTERNS)
        super().__init__(patterns=included_patterns, ignore_patterns=ignore_patterns, ignore_directories=True)
        
    def on_created(self, event):
        file_path = event.src_path
        logger.debug(f"Monitor found {file_path} for event type CREATED")
        relative_file_path = PurePath(os.path.relpath(file_path, self._engine.params.monitored_directory))
        if self._engine.props.running and \
            self._engine._appwindow._queue_manager.props.running:
            creation_timestamp = get_file_creation_timestamp(file_path)
            if creation_timestamp:
                _file = RegularFile(file_path, relative_file_path, creation_timestamp, FileStatus.CREATED)
            else:
                logger.debug(f"File Not found, {file_path} has been skipped")
                return None
            GLib.idle_add(self._engine._appwindow._queue_manager.add, _file, priority=GLib.PRIORITY_HIGH)

    def on_modified(self, event):
        file_path = event.src_path
        logger.debug(f"Monitor found {file_path} for event type MODIFIED")
        if self._engine.props.running and \
            self._engine._appwindow._queue_manager.props.running:
            GLib.idle_add(self._engine._appwindow._queue_manager.saved, file_path, priority=GLib.PRIORITY_HIGH)

