from __future__ import annotations

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk, Gtk
import boto3
import botocore

from ..engine import Engine
from ..file import S3Object, FileStatus
from ..operations.s3_uploader import AWS_S3_ENGINE_IGNORE_ME
from ..utils import ExitableThread, LongTaskWindow, match_path, get_patterns_from_string
from ..utils.exceptions import AlreadyRunning, NotYetRunning

from typing import Optional, Type
import logging
from pathlib import PurePosixPath
import urllib.parse
import traceback

logger = logging.getLogger(__name__)

AVAILABLE_CONFIGURATIONS = (
    'LambdaFunctionConfigurations',
    'TopicConfigurations',
    'QueueConfigurations'
)

class BaseS3BucketEngineThread(ExitableThread):
    def __init__(self, engine: BaseS3BucketEngine, task_window: LongTaskWindow):
        super().__init__()
        self._engine : BaseS3BucketEngine = engine
        self._task_window = task_window
        self._client_options: dict = {}

        # prepare patterns
        self._included_patterns = get_patterns_from_string(self._engine.params.allowed_patterns)
        self._excluded_patterns = get_patterns_from_string(self._engine.params.ignore_patterns, defaults=[])

    def get_full_name(self, key) -> str:
        raise NotImplementedError

    def get_region_name(self, default_region: str) -> bool:
        # set up temporary s3 client
        temp_s3_client = boto3.client('s3', **self._client_options)

        # first confirm that the bucket exists and that we can read it
        try:
            logger.debug(f"Checking if bucket {self._engine.params.bucket_name} exists")
            temp_s3_client.head_bucket(Bucket=self._engine.params.bucket_name)
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return False

        # next try to get the region the bucket is located in
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_bucket_location
        try:
            logger.debug(f'Getting {self._engine.params.bucket_name} location')
            response = temp_s3_client.get_bucket_location(Bucket=self._engine.params.bucket_name)
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return False
        
        self._client_options['region_name'] = response['LocationConstraint'] if response['LocationConstraint'] else default_region

        return True

    def process_new_file(self, s3_info: dict):
        object_info = s3_info['object']
        key = urllib.parse.unquote_plus(object_info['key'])
        if 'eTag' in object_info: # AWS
            etag = object_info['eTag']
        elif 'etag' in object_info: # Ceph
            etag = object_info['etag']
        else:
            logger.warning(f'no etag found for {key}')
            etag = ''
        size = object_info['size']

        if not match_path( PurePosixPath(key),
            included_patterns=self._included_patterns,
            excluded_patterns=self._excluded_patterns,
            case_sensitive=False):
            return False

        # ensure that this is not an S3Uploader testfile!
        try:
            response = self._engine.s3_client.head_object(
                Bucket=self._engine.params.bucket_name,
                Key=key,
            )
        except botocore.exceptions.ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.debug(f"{key} does not exist in {self._engine.params.bucket_name}")
            else:
                logger.exception(f'head_object failure for {key} in {self._engine.params.bucket_name}')
            return False

        if 'Metadata' in response and AWS_S3_ENGINE_IGNORE_ME in response['Metadata']:
            # this is a testfile -> ignore!
            return False

        full_path = self.get_full_name(object_info['key'])
        relative_path = PurePosixPath(key)
        created = response['LastModified'].timestamp()

        if self._engine.props.running and \
            self._engine._appwindow._queue_manager.props.running:
            _file = S3Object(
                full_path,
                relative_path,
                created,
                FileStatus.SAVED,
                self._engine.params.bucket_name,
                etag,
                size,
                self._client_options['region_name'],
                )
            GLib.idle_add(self._engine._appwindow._queue_manager.add, _file, priority=GLib.PRIORITY_HIGH)
        return True

    def process_existing_files(self) -> bool:
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

                    full_path = self.get_full_name(quoted_key)
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
    def __init__(self, appwindow, engine_thread_class: Type[BaseS3BucketEngineThread], abort_message: str):
        super().__init__(appwindow)

        self._engine_thread_class = engine_thread_class
        self._abort_message = abort_message

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
        
    def _abort(self, task_window: Optional[LongTaskWindow], e: Exception):
        if task_window:
            # destroy task window
            task_window.get_window().set_cursor(None)
            task_window.destroy()

        # display dialog with error message
        traceback.print_exc()
        logger.debug(''.join(traceback.format_tb(e.__traceback__)))
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(),
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text=f"Could not start {self.NAME}",
                secondary_text=str(e) + f'\n\n{self._abort_message}')
        dialog.run()
        dialog.destroy()

        return GLib.SOURCE_REMOVE

