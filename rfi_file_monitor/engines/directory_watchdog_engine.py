from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, DirCreatedEvent, FileCreatedEvent, FileModifiedEvent

from ..engine import Engine
from ..file import Directory, FileStatus
from ..utils import get_file_creation_timestamp
from ..utils.decorators import exported_filetype
from ..utils.exceptions import AlreadyRunning, NotYetRunning

import logging
from typing import Final, List
from pathlib import Path, PurePath
import os

logger = logging.getLogger(__name__)

@exported_filetype(filetype=Directory)
class DirectoryWatchdogEngine(Engine):

    NAME = 'Directories Monitor'

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
        self._monitor.schedule(EventHandler(self), self.params.monitored_directory, recursive=True)
        self._monitor.start()

        self._running = True
        self.notify('running')

    def start(self):
        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        self._start_watchdog()

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        self._monitor.stop()
        self._monitor = None
        self._running = False
        self.notify('running')

class EventHandler(PatternMatchingEventHandler):
    def __init__(self, engine: DirectoryWatchdogEngine):
        self._engine = engine 
        super().__init__(ignore_directories=False)
        #included_patterns = get_patterns_from_string(self._engine.params.allowed_patterns)
        #ignore_patterns =  get_patterns_from_string(self._engine.params.ignore_patterns, defaults=IGNORE_PATTERNS)
        #super().__init__(patterns=included_patterns, ignore_patterns=ignore_patterns, ignore_directories=True)

        self._empty_directories : List[Directory] = []

    def on_created(self, event):
        path = event.src_path
        logger.debug(f"Monitor found {path} for event type CREATED")
        path_object : PurePath = PurePath(path)
        rel_path = path_object.relative_to(self._engine.params.monitored_directory)

        if isinstance(event, DirCreatedEvent):
            # if this happens directly within the monitored directory,
            # add path to the internal list
            # else if path is already in self._empty_directories that contains this, do nothing
            # else send a saved event for path, even though it may not exist in the queue!

            if len(rel_path.parts) > 1 and \
                rel_path.parts[0] not in self._empty_directories and \
                self._engine.props.running and \
                self._engine._appwindow._queue_manager.props.running:

                GLib.idle_add(self._engine._appwindow._queue_manager.saved, path, priority=GLib.PRIORITY_HIGH)

            elif rel_path.parts[0] not in self._empty_directories:
                logger.debug(f'New directory {rel_path.parts[0]} was created')
                self._empty_directories.append(rel_path.parts[0])
            
        elif isinstance(event, FileCreatedEvent):
            # if the corresponding toplevel directory is in the internal array, it's time to send it to the queue
            # else, this should trigger a saved change of the corresponding Directory instance.
            # ignore if this file is put directly in the monitored directory
            if len(rel_path.parts) == 1:
                logger.debug(f'Ignoring file in monitored directory {path}')
                return

            if rel_path.parts[0] in self._empty_directories:
                self._empty_directories.remove(rel_path.parts[0])
                new_path = os.path.join(self._engine.params.monitored_directory, rel_path.parts[0])
                creation_timestamp = get_file_creation_timestamp(new_path)
                if creation_timestamp:
                    _dir = Directory(new_path, PurePath(rel_path.parts[0]), creation_timestamp, FileStatus.CREATED)
                else:
                    logger.debug(f"File Not found, {path} has been skipped")
                    return 
                GLib.idle_add(self._engine._appwindow._queue_manager.add, _dir, priority=GLib.PRIORITY_HIGH)

            elif self._engine.props.running and \
                self._engine._appwindow._queue_manager.props.running:

                new_path = os.path.join(self._engine.params.monitored_directory, rel_path.parts[0])
                GLib.idle_add(self._engine._appwindow._queue_manager.saved, new_path, priority=GLib.PRIORITY_HIGH)

            
        else:
            raise NotImplementedError(f'Unknown event type {str(event)} in on_created')

    def on_modified(self, event):
        path = event.src_path
        logger.debug(f"Monitor found {path} for event type MODIFIED")
        path_object : PurePath = PurePath(path)
        rel_path = path_object.relative_to(self._engine.params.monitored_directory)

        if isinstance(event, FileModifiedEvent):
            # this should trigger a saved change of the corresponding Directory instance.
            # ignore if this file is put directly in the monitored directory
            if len(rel_path.parts) == 1:
                logger.debug(f'Ignoring file in monitored directory {path}')
                return

            elif self._engine.props.running and \
                self._engine._appwindow._queue_manager.props.running:
                new_path = os.path.join(self._engine.params.monitored_directory, rel_path.parts[0])
                GLib.idle_add(self._engine._appwindow._queue_manager.saved, new_path, priority=GLib.PRIORITY_HIGH)
