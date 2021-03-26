from __future__ import annotations
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
import boto3

import string
import random
import time
import json
from copy import deepcopy
import logging

from .aws_s3_bucket_engine_advanced_settings import (
    AWSS3BucketEngineAdvancedSettings,
)
from .base_s3_bucket_engine import (
    BaseS3BucketEngine,
    BaseS3BucketEngineThread,
    AVAILABLE_CONFIGURATIONS,
)
from ..file import S3Object
from ..utils.decorators import (
    exported_filetype,
    with_advanced_settings,
    with_pango_docs,
)

logger = logging.getLogger(__name__)

ABORT_MESSAGE = "Ensure you are using valid credentials and bucket name, and that an appropriate policy is attached to the user or role."


@exported_filetype(filetype=S3Object)
@with_advanced_settings(
    engine_advanced_settings=AWSS3BucketEngineAdvancedSettings
)
@with_pango_docs(filename="aws_s3_bucket_engine.pango")
class AWSS3BucketEngine(BaseS3BucketEngine):

    NAME = "AWS S3 Bucket Monitor"

    def __init__(self, appwindow):
        super().__init__(appwindow, AWSS3BucketEngineThread, ABORT_MESSAGE)

        # Needs:
        # 1. region
        # 2. bucket name
        # 3. access key
        # 4. secret key

        # add bucket name -> this bucket must already exist!!!
        self.attach(
            Gtk.Label(
                label="Bucket Name",
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
        self._bucket_name_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "bucket_name",
        )
        self.attach(self._bucket_name_entry, 1, 0, 1, 1)

        # Process existing files in monitored directory
        process_existing_files_switch = self.register_widget(
            Gtk.Switch(
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
                active=False,
            ),
            "process_existing_files",
        )
        self.attach(process_existing_files_switch, 2, 0, 1, 1)
        self.attach(
            Gtk.Label(
                label="Process existing files in bucket",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            3,
            0,
            1,
            1,
        )

        # Access key
        self.attach(
            Gtk.Label(
                label="Access Key",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            1,
            1,
            1,
        )
        self._access_key_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "access_key",
        )
        self.attach(self._access_key_entry, 1, 1, 1, 1)

        # Secret key
        self.attach(
            Gtk.Label(
                label="Secret Key",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            1,
            1,
            1,
        )
        self._secret_key_entry = self.register_widget(
            Gtk.Entry(
                visibility=False,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "secret_key",
            exportable=False,
        )
        self.attach(self._secret_key_entry, 3, 1, 1, 1)

        # connect signal handlers to determine validity
        self._access_key_entry.connect("changed", self._s3_entry_changed_cb)
        self._secret_key_entry.connect("changed", self._s3_entry_changed_cb)
        self._bucket_name_entry.connect("changed", self._s3_entry_changed_cb)

    def _s3_entry_changed_cb(self, entry):
        # todo: implement better bucket name validation
        if (
            self.params.bucket_name
            and self.params.access_key
            and self.params.secret_key
        ):
            self._valid = True
        else:
            self._valid = False

        self.notify("valid")

    def cleanup(self):
        # pylint: disable=no-member
        # we are going to do this 'ask for forgiveness, not permission'-style

        # restore old bucket notifications
        if hasattr(self, "old_bucket_notification_config"):
            try:
                self.s3_client.put_bucket_notification_configuration(
                    Bucket=self.params.bucket_name,
                    NotificationConfiguration=self.old_bucket_notification_config,
                )
            except Exception as e:
                logger.exception(
                    f"Could not restore bucket notification config: {str(e)}"
                )

        # delete SQS queue
        if hasattr(self, "queue_url"):
            try:
                self.sqs_client.delete_queue(QueueUrl=self.queue_url)
            except Exception as e:
                logger.exception(
                    f"Could not delete SQS queue {self.queue_url}: {str(e)}"
                )

        # delete SQS DLQ
        if hasattr(self, "dlq_url"):
            try:
                self.sqs_client.delete_queue(QueueUrl=self.dlq_url)
            except Exception as e:
                logger.exception(
                    f"Could not delete SQS queue {self.dlq_url}: {str(e)}"
                )

        super().cleanup()


class AWSS3BucketEngineThread(BaseS3BucketEngineThread):
    def get_full_name(self, key):
        return f"https://{self.params.bucket_name}.s3.{self._client_options['region_name']}.amazonaws.com/{key}"

    def run(self):
        self._client_options = self._engine._get_client_options()

        if not self.get_region_name("us-east-1"):
            return

        # set up proper s3 client
        self._engine.s3_client = boto3.client("s3", **self._client_options)

        # set up sqs client
        self._engine.sqs_client = boto3.client("sqs", **self._client_options)

        # create queue
        self._engine.queue_name = (
            "rfi-file-monitor-s3-bucket-engine-"
            + "".join(random.choice(string.ascii_lowercase) for i in range(6))
        )
        GLib.idle_add(
            self._task_window.set_text, "<b>Creating SQS queues...</b>"
        )
        try:
            self._engine.queue_url = self._engine.sqs_client.create_queue(
                QueueName=self._engine.queue_name
            )["QueueUrl"]
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                e,
                priority=GLib.PRIORITY_HIGH,
            )
            return

        # create dead-letter-queue
        self._engine.dlq_name = self._engine.queue_name + "-dlq"
        try:
            self._engine.dlq_url = self._engine.sqs_client.create_queue(
                QueueName=self._engine.dlq_name
            )["QueueUrl"]
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                e,
                priority=GLib.PRIORITY_HIGH,
            )
            return

        # sleep 1 second to make sure the queue is available
        time.sleep(1)

        try:
            # get queue ARN
            self._engine.queue_arn = (
                self._engine.sqs_client.get_queue_attributes(
                    QueueUrl=self._engine.queue_url, AttributeNames=["QueueArn"]
                )["Attributes"]["QueueArn"]
            )

            # get dlq ARN
            self._engine.dlq_arn = self._engine.sqs_client.get_queue_attributes(
                QueueUrl=self._engine.dlq_url, AttributeNames=["QueueArn"]
            )["Attributes"]["QueueArn"]
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                e,
                priority=GLib.PRIORITY_HIGH,
            )
            return

        # set queue policy
        sqs_policy = {
            "Version": "2012-10-17",
            "Id": "example-ID",
            "Statement": [
                {
                    "Sid": "RFI-File-Monitor-SQS-ID",
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["SQS:SendMessage"],
                    "Resource": self._engine.queue_arn,
                    "Condition": {
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:s3:*:*:{self.params.bucket_name}"
                        },
                    },
                }
            ],
        }

        try:
            self._engine.sqs_client.set_queue_attributes(
                QueueUrl=self._engine.queue_url,
                Attributes={"Policy": json.dumps(sqs_policy)},
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

        # set dlq policy
        redrive_policy = {
            "deadLetterTargetArn": self._engine.dlq_arn,
            "maxReceiveCount": "10",
        }

        try:
            self._engine.sqs_client.set_queue_attributes(
                QueueUrl=self._engine.queue_url,
                Attributes={"RedrivePolicy": json.dumps(redrive_policy)},
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

        GLib.idle_add(
            self._task_window.set_text,
            "<b>Configuring bucket notifications...</b>",
        )
        try:
            # get current bucket notifications
            response = (
                self._engine.s3_client.get_bucket_notification_configuration(
                    Bucket=self.params.bucket_name,
                )
            )

            self._engine.old_bucket_notification_config = {
                configs: response.get(configs, [])
                for configs in AVAILABLE_CONFIGURATIONS
            }

            new_bucket_notification_config = deepcopy(
                self._engine.old_bucket_notification_config
            )

            sqs_notification = {
                "QueueArn": self._engine.queue_arn,
                "Events": [
                    "s3:ObjectCreated:*",
                    "s3:ObjectRemoved:*",
                    "s3:ObjectRestore:*",
                ],
            }

            new_bucket_notification_config["QueueConfigurations"].append(
                sqs_notification
            )

            # set bucket notifications
            self._engine.s3_client.put_bucket_notification_configuration(
                Bucket=self.params.bucket_name,
                NotificationConfiguration=new_bucket_notification_config,
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

        # if required, add existing files to queue
        if (
            self.params.process_existing_files
            and not self.process_existing_files()
        ):
            return

        # if we get here, things should be working.
        # close task_window
        GLib.idle_add(
            self._engine.kill_task_window,
            self._task_window,
            priority=GLib.PRIORITY_HIGH,
        )

        # start the big while loop and start consuming incoming messages
        while True:

            if self._should_exit:
                self._engine.cleanup()
                return

            try:
                resp = self._engine.sqs_client.receive_message(
                    QueueUrl=self._engine.queue_url,
                    AttributeNames=["All"],
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=10,
                )
            except Exception as e:
                self._engine.cleanup()
                GLib.idle_add(
                    self._engine.abort, None, e, priority=GLib.PRIORITY_HIGH
                )
                return

            if "Messages" not in resp:
                continue

            for message in resp["Messages"]:
                body = json.loads(message["Body"])
                # we are going to assume 1 record per message
                try:
                    record = body["Records"][0]
                    event_name = record["eventName"]
                except Exception as e:
                    logger.info(f"Ignoring {message=} because of {str(e)}")
                    continue

                if event_name.startswith("ObjectCreated"):
                    # new file created!
                    s3_info = record["s3"]
                    if not self.process_new_file(s3_info):
                        continue

            # delete messages from the queue
            entries = [
                {"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]}
                for msg in resp["Messages"]
            ]

            try:
                resp = self._engine.sqs_client.delete_message_batch(
                    QueueUrl=self._engine.queue_url, Entries=entries
                )
            except Exception as e:
                self._engine.cleanup()
                GLib.idle_add(
                    self._engine.abort, None, e, priority=GLib.PRIORITY_HIGH
                )
                return

            if len(resp["Successful"]) != len(entries):
                logger.warn(
                    f"Failed to delete messages: entries={entries!r} resp={resp!r}"
                )
