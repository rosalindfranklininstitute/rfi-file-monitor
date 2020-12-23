import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib, Gdk
import boto3
import botocore
from ..utils import match_path

import string
import random
import time
from pathlib import PurePosixPath
import json
from copy import deepcopy
import urllib.parse
from typing import Optional
import logging

from ..engine import Engine
from .aws_s3_bucket_engine_advanced_settings import AWSS3BucketEngineAdvancedSettings
from ..file import AWSS3Object, FileStatus
from ..utils.decorators import exported_filetype, with_advanced_settings, with_pango_docs
from ..utils.exceptions import AlreadyRunning, NotYetRunning
from ..utils import ExitableThread, LongTaskWindow, get_patterns_from_string
from ..operations.s3_uploader import AWS_S3_ENGINE_IGNORE_ME

logger = logging.getLogger(__name__)

AVAILABLE_CONFIGURATIONS = (
    'LambdaFunctionConfigurations',
    'TopicConfigurations',
    'QueueConfigurations'
)

@exported_filetype(filetype=AWSS3Object)
@with_advanced_settings(engine_advanced_settings=AWSS3BucketEngineAdvancedSettings)
@with_pango_docs(filename='aws_s3_bucket_engine.pango')
class AWSS3BucketEngine(Engine):

    NAME = 'AWS S3 Bucket Monitor'

    def __init__(self, appwindow):
        super().__init__(appwindow)

        # Needs:
        # 1. region
        # 2. bucket name
        # 3. access key
        # 4. secret key

        # add bucket name -> this bucket must already exist!!!
        self.attach(Gtk.Label(
            label="Bucket Name", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        self._bucket_name_entry = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'bucket_name')
        self.attach(self._bucket_name_entry, 1, 0, 1, 1)

        # Process existing files in monitored directory
        process_existing_files_switch = self.register_widget(Gtk.Switch(
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
            active=False), 'process_existing_files')
        self.attach(process_existing_files_switch, 2, 0, 1, 1)
        self.attach(Gtk.Label(
            label='Process existing files in bucket',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 3, 0, 1, 1)

        # Access key
        self.attach(Gtk.Label(
            label="Access Key",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        self._access_key_entry = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'access_key')
        self.attach(self._access_key_entry, 1, 1, 1, 1)

        # Secret key
        self.attach(Gtk.Label(
            label="Secret Key", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 2, 1, 1, 1)
        self._secret_key_entry = self.register_widget(Gtk.Entry(
            visibility=False,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'secret_key', exportable=False)
        self.attach(self._secret_key_entry, 3, 1, 1, 1)

        # connect signal handlers to determine validity 
        self._access_key_entry.connect('changed', self._s3_entry_changed_cb)
        self._secret_key_entry.connect('changed', self._s3_entry_changed_cb)
        self._bucket_name_entry.connect('changed', self._s3_entry_changed_cb)

    def _s3_entry_changed_cb(self, entry):
        # todo: implement better bucket name validation
        if self.params.bucket_name and \
            self.params.access_key and \
            self.params.secret_key:
            self._valid = True
        else:
            self._valid = False

        logger.debug(f'_s3_entry_changed_cb: {self._valid}')

        self.notify('valid')

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

        self._thread = AWSS3BucketEngineThread(self, task_window)
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

    def _confirm_bucket_exists(self, client):
        try:
            logger.debug(f"Checking if bucket {self.params.bucket_name} exists")

            client.head_bucket(Bucket=self.params.bucket_name)
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                logger.info(f"Bucket {self.params.bucket_name} exists but is not accessible")
                return False
            elif error_code == 404:
                logger.info(f"Bucket {self.params.bucket_name} does not exist")
                return False
            else:
                logger.info(f"Accessing bucket {self.params.bucket_name} returned code {error_code}")
                return False
        return True
    
    def _kill_task_window(self, task_window: LongTaskWindow):
        # destroy task window
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        self._running = True
        self.notify('running')

        return GLib.SOURCE_REMOVE

    def _cleanup(self):
        #pylint: disable=no-member
        logger.debug('Running cleanup!')

        # we are going to do this 'ask for forgiveness, not permission'-style

        # restore old bucket notifications
        if hasattr(self, 'old_bucket_notification_config'):
            try:
                self.s3_client.put_bucket_notification_configuration(
                    Bucket=self.params.bucket_name,
                    NotificationConfiguration=self.old_bucket_notification_config
                )
                logger.debug(f'Successfully restored bucket notification config')
            except Exception as e:
                logger.debug(f'Could not restore bucket notification config: {str(e)}')

        # delete SQS queue
        if hasattr(self, 'queue_url'):
            try:
                self.sqs_client.delete_queue(QueueUrl=self.queue_url)
                logger.debug(f'Successfully deleted SQS queue {self.queue_url}')
            except Exception as e:
                logger.debug(f'Could not delete SQS queue {self.queue_url}: {str(e)}')
                GLib.idle_add(self._abort, None, e)
    
        # delete SQS DLQ
        if hasattr(self, 'dlq_url'):
            try:
                self.sqs_client.delete_queue(QueueUrl=self.dlq_url)
                logger.debug(f'Successfully deleted SQS queue {self.dlq_url}')
            except Exception as e:
                logger.debug(f'Could not delete SQS queue {self.dlq_url}: {str(e)}')

        GLib.idle_add(self._stop_running)

    def _stop_running(self):
        self._running = False
        self.notify('running')

        return GLib.SOURCE_REMOVE

    def _abort(self, task_window: Optional[LongTaskWindow], e: Exception):
        if task_window:
            # destroy task window
            task_window.get_window().set_cursor(None)
            task_window.destroy()

        # display dialog with error message
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(),
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text=f"Could not start {self.NAME}",
                secondary_text=str(e) + '\n\nEnsure you are using valid credentials and bucket name, and that an appropriate policy is attached to the user or role.')
        dialog.run()
        dialog.destroy()

        return GLib.SOURCE_REMOVE

class AWSS3BucketEngineThread(ExitableThread):
    def __init__(self, engine: AWSS3BucketEngine, task_window: LongTaskWindow):
        super().__init__()
        self._engine : AWSS3BucketEngine = engine
        self._task_window = task_window

    def run(self):
        client_options = self._engine._get_client_options()

        # set up temporary s3 client
        temp_s3_client = boto3.client('s3', **client_options)

        # first confirm that the bucket exists and that we can read it
        try:
            logger.debug(f"Checking if bucket {self._engine.params.bucket_name} exists")
            temp_s3_client.head_bucket(Bucket=self._engine.params.bucket_name)
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # next try to get the region the bucket is located in
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_bucket_location
        try:
            logger.debug(f'Getting {self._engine.params.bucket_name} location')
            response = temp_s3_client.get_bucket_location(Bucket=self._engine.params.bucket_name)
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return
        
        client_options['region_name'] = response['LocationConstraint'] if response['LocationConstraint'] else 'us-east-1'

        # set up proper s3 client
        self._engine.s3_client = boto3.client('s3', **client_options)

        # set up sqs client
        self._engine.sqs_client = boto3.client('sqs', **client_options)

        # create queue
        self._engine.queue_name = 'rfi-file-monitor-s3-bucket-engine-' + ''.join(random.choice(string.ascii_lowercase) for i in range(6))
        try:
            self._engine.queue_url = self._engine.sqs_client.create_queue(QueueName=self._engine.queue_name)['QueueUrl']
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # create dead-letter-queue
        self._engine.dlq_name = self._engine.queue_name + '-dlq'
        try:
            self._engine.dlq_url = self._engine.sqs_client.create_queue(QueueName=self._engine.dlq_name)['QueueUrl']
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # sleep 1 second to make sure the queue is available
        time.sleep(1)

        try:
            # get queue ARN
            self._engine.queue_arn = self._engine.sqs_client.get_queue_attributes(QueueUrl=self._engine.queue_url, AttributeNames=['QueueArn'])['Attributes']['QueueArn']
        
            # get dlq ARN
            self._engine.dlq_arn = self._engine.sqs_client.get_queue_attributes(QueueUrl=self._engine.dlq_url, AttributeNames=['QueueArn'])['Attributes']['QueueArn']
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # set queue policy
        sqs_policy = {
            "Version": "2012-10-17",
            "Id": "example-ID",
            "Statement": [
                {
                    "Sid": "RFI-File-Monitor-SQS-ID",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS":"*"  
                    },
                    "Action": [
                        "SQS:SendMessage"
                    ],
                    "Resource": self._engine.queue_arn,
                    "Condition": {
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:s3:*:*:{self._engine.params.bucket_name}"
                        },
                    }
                }
            ]
        }

        try:
            self._engine.sqs_client.set_queue_attributes(
                QueueUrl=self._engine.queue_url,
                Attributes={
                    'Policy': json.dumps(sqs_policy)
                }
            )
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # set dlq policy
        redrive_policy = {
            'deadLetterTargetArn': self._engine.dlq_arn,
            'maxReceiveCount': '10'
        }

        try:
            self._engine.sqs_client.set_queue_attributes(
                QueueUrl=self._engine.queue_url,
                Attributes={
                    'RedrivePolicy': json.dumps(redrive_policy)
                }
            )
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        try:
            # get current bucket notifications
            response = self._engine.s3_client.get_bucket_notification_configuration(
                Bucket=self._engine.params.bucket_name,
            )

            self._engine.old_bucket_notification_config = {configs: response.get(configs, []) for configs in AVAILABLE_CONFIGURATIONS}

            logger.debug(f'{self._engine.old_bucket_notification_config=}')

            new_bucket_notification_config = deepcopy(self._engine.old_bucket_notification_config)

            sqs_notification = {
                'QueueArn': self._engine.queue_arn,
                'Events': [
                    's3:ObjectCreated:*',
                    's3:ObjectRemoved:*',
                    's3:ObjectRestore:*'
                ]
            }

            new_bucket_notification_config['QueueConfigurations'].append(sqs_notification)

            # set bucket notifications
            self._engine.s3_client.put_bucket_notification_configuration(
                Bucket=self._engine.params.bucket_name,
                NotificationConfiguration=new_bucket_notification_config
            )
        except Exception as e:
            self._engine._cleanup()
            GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
            return

        # prepare patterns
        included_patterns = get_patterns_from_string(self._engine.params.allowed_patterns)
        excluded_patterns = get_patterns_from_string(self._engine.params.ignore_patterns, defaults=[])

        # if required, add existing files to queue
        if self._engine.params.process_existing_files:
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

                        if not match_path( PurePosixPath(key),
                            included_patterns=included_patterns,
                            excluded_patterns=excluded_patterns):
                            continue

                        last_modified = _object['LastModified']
                        size = _object['Size']
                        etag = _object['ETag'][1:-1] # get rid of those weird quotes
                        quoted_key = urllib.parse.quote_plus(key)

                        full_path = f"https://{self._engine.params.bucket_name}.s3.{client_options['region_name']}.amazonaws.com/{quoted_key}"
                        relative_path = PurePosixPath(key)
                        created = last_modified.timestamp()

                        _file = AWSS3Object(
                            full_path,
                            relative_path,
                            created,
                            FileStatus.SAVED,
                            self._engine.params.bucket_name,
                            etag,
                            size,
                            client_options['region_name'])
                    
                        existing_files.append(_file)
                if existing_files:
                    GLib.idle_add(self._engine._appwindow._queue_manager.add, existing_files, priority=GLib.PRIORITY_HIGH)
            except Exception as e:
                self._engine._cleanup()
                GLib.idle_add(self._engine._abort, self._task_window, e, priority=GLib.PRIORITY_HIGH)
                return


        # if we get here, things should be working.
        # close task_window
        GLib.idle_add(self._engine._kill_task_window, self._task_window, priority=GLib.PRIORITY_HIGH)

        # start the big while loop and start consuming incoming messages
        while True:

            if self._should_exit:
                logger.info('Killing S3BucketEngineThread')

                self._engine._cleanup()
                return

            try:
                resp = self._engine.sqs_client.receive_message(
                    QueueUrl=self._engine.queue_url,
                    AttributeNames=['All'],
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=10,
                )
            except Exception as e:
                self._engine._cleanup()
                GLib.idle_add(self._engine._abort, None, e, priority=GLib.PRIORITY_HIGH)
                return

            if 'Messages' not in resp:
                logger.debug('No messages found')
                continue

            # This is where we are supposed to start parsing, and add the files to the queue manager
            logger.debug(f"{resp['Messages']=}")

            for message in resp['Messages']:
                body = json.loads(message['Body'])
                # we are going to assume 1 record per message
                try:
                    record = body['Records'][0]
                    event_name = record['eventName']
                except Exception as e:
                    logger.debug(f'Ignoring {message=} because of {str(e)}')
                    continue

                if event_name.startswith('ObjectCreated'):
                    # new file created!
                    s3_info = record['s3']
                    object_info = s3_info['object']
                    key = urllib.parse.unquote_plus(object_info['key'])
                    etag = object_info['eTag']
                    size = object_info['size']

                    if not match_path( PurePosixPath(key),
                        included_patterns=included_patterns,
                        excluded_patterns=excluded_patterns):
                        continue

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
                        continue

                    if 'Metadata' in response and AWS_S3_ENGINE_IGNORE_ME in response['Metadata']:
                        # this is a testfile -> ignore!
                        continue

                    full_path = f"https://{self._engine.params.bucket_name}.s3.{client_options['region_name']}.amazonaws.com/{object_info['key']}"
                    relative_path = PurePosixPath(key)
                    created = response['LastModified'].timestamp()

                    if self._engine.props.running and \
                        self._engine._appwindow._queue_manager.props.running:
                        _file = AWSS3Object(
                            full_path,
                            relative_path,
                            created,
                            FileStatus.SAVED,
                            self._engine.params.bucket_name,
                            etag,
                            size,
                            client_options['region_name'],
                            )
                        GLib.idle_add(self._engine._appwindow._queue_manager.add, _file, priority=GLib.PRIORITY_HIGH)

            # delete messages from the queue
            entries = [
                {'Id': msg['MessageId'], 'ReceiptHandle': msg['ReceiptHandle']}
                for msg in resp['Messages']
            ]

            try:
                resp = self._engine.sqs_client.delete_message_batch(
                    QueueUrl=self._engine.queue_url, Entries=entries
                )
            except Exception as e:
                self._engine._cleanup()
                GLib.idle_add(self._engine._abort, None, e, priority=GLib.PRIORITY_HIGH)
                return

            if len(resp['Successful']) != len(entries):
                logger.warn(f"Failed to delete messages: entries={entries!r} resp={resp!r}")
