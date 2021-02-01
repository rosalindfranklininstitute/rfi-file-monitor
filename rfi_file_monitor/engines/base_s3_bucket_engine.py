from __future__ import annotations

import gi
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gdk

from ..engine import Engine
from ..file import S3Object, FileStatus
from ..utils import ExitableThread, LongTaskWindow, match_path
from ..utils.exceptions import AlreadyRunning, NotYetRunning

from typing import Type
import logging
from pathlib import PurePosixPath
import urllib.parse

logger = logging.getLogger(__name__)

class BaseS3BucketEngineThread(ExitableThread):
    def __init__(self, engine: BaseS3BucketEngine, task_window: LongTaskWindow):
        super().__init__()
        self._engine : BaseS3BucketEngine = engine
        self._task_window = task_window

    def process_existing_files(self):
        try:
            paginator = self._engine.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=self._engine.params.bucket_name)

            existing_files = []

            for page in page_iterator:
                logger.debug(f"{page}")
                if page['KeyCount'] == 0:
                    continue
                for _object in page['Contents']:
                    key = _object['Key']

                    if not match_path(PurePosixPath(key),
                        included_patterns=self._included_patterns,
                        excluded_patterns=self._excluded_patterns,
                        case_sensitive=False):
                        continue

                    last_modified = _object['LastModified']
                    size = _object['Size']
                    etag = _object['ETag'][1:-1] # get rid of those weird quotes
                    quoted_key = urllib.parse.quote_plus(key)

                    full_path = f"https://{self._engine.params.bucket_name}.s3.{self._client_options['region_name']}.amazonaws.com/{quoted_key}"
                    relative_path = PurePosixPath(key)
                    created = last_modified.timestamp()

                    _file = S3Object(
                        full_path,
                        relative_path,
                        created,
                        FileStatus.SAVED,
                        self._engine.params.bucket_name,
                        etag,
                        size,
                        self._client_options['region_name'])
                    
                    existing_files.append(_file)
            if existing_files:
                GLib.idle_add(self._engine._appwindow._queue_manager.add, existing_files, priority=GLib.PRIORITY_HIGH)
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return False

        return True

class BaseS3BucketEngine(Engine):
    def __init__(self, appwindow, engine_thread_class: Type[BaseS3BucketEngineThread]):
        super().__init__(appwindow)

        self._engine_thread_class = engine_thread_class

    def start(self):
        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        # pop up a long task window
        # spawn a thread for this to avoid GUI freezes
        task_window = LongTaskWindow(self._appwindow)
        task_window.set_text(f"<b>Launching {self.NAME}</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
        task_window.get_window().set_cursor(watch_cursor)

        self._thread = self._engine_thread_class(self, task_window)
        self._thread.start()

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        task_window = LongTaskWindow(self._appwindow)
        task_window.set_text(f"<b>Stopping {self.NAME}</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
        task_window.get_window().set_cursor(watch_cursor)

        self._running_changed_handler_id = self.connect('notify::running', self._running_changed_cb, task_window)                

        # if the thread is sleeping, it will be killed at the next iteration
        self._thread.should_exit = True

    def _running_changed_cb(self, _self, param, task_window):
        self.disconnect(self._running_changed_handler_id)
        if not self._running:
            task_window.get_window().set_cursor(None)
            task_window.destroy()

    def _get_client_options(self) -> dict:
        client_options = dict()
        client_options['aws_access_key_id'] = self.params.access_key
        client_options['aws_secret_access_key'] = self.params.secret_key
        return client_options

    def _kill_task_window(self, task_window: LongTaskWindow):
        # destroy task window
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        self._running = True
        self.notify('running')

        return GLib.SOURCE_REMOVE
