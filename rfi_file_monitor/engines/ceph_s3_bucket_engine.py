from __future__ import annotations
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
import boto3
from botocore.client import Config
import pika

import logging
import urllib
import ssl
from pathlib import Path
import time
import json

from .base_s3_bucket_engine import BaseS3BucketEngine, BaseS3BucketEngineThread
from .ceph_s3_bucket_engine_advanced_settings import (
    CephS3BucketEngineAdvancedSettings,
)
from ..file import S3Object
from ..utils.decorators import (
    exported_filetype,
    with_advanced_settings,
    with_pango_docs,
)
from ..utils import get_random_string

logger = logging.getLogger(__name__)

ABORT_MESSAGE = "Ensure you are using valid credentials and bucket name, and that a push-endpoint has been properly configured in Advanced Settings."


@exported_filetype(filetype=S3Object)
@with_advanced_settings(
    engine_advanced_settings=CephS3BucketEngineAdvancedSettings
)
@with_pango_docs(filename="ceph_s3_bucket_engine.pango")
class CephS3BucketEngine(BaseS3BucketEngine):

    NAME = "Ceph S3 Bucket Monitor"

    def __init__(self, appwindow):
        super().__init__(appwindow, CephS3BucketEngineThread, ABORT_MESSAGE)

        # Needs:
        # 1. endpoint
        # 2. bucket name
        # 3. access key
        # 4. secret key

        # the rest of the config goes into advanced
        # add endpoint
        self.attach(
            Gtk.Label(
                label="Ceph Endpoint",
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
        self._ceph_endpoint_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "ceph_endpoint",
        )
        self.attach(self._ceph_endpoint_entry, 1, 0, 1, 1)

        # add bucket name -> this bucket must already exist!!!
        self.attach(
            Gtk.Label(
                label="Bucket Name",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
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
        self.attach(self._bucket_name_entry, 3, 0, 1, 1)

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

        self.attach(
            Gtk.Label(
                label="<b>Please use Advanced Settings to configure the push-endpoint</b>",
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
                xalign=0.5,
                use_markup=True,
            ),
            0,
            2,
            4,
            1,
        )

        # connect signal handlers to determine validity
        self._ceph_endpoint_entry.connect("changed", self._s3_entry_changed_cb)
        self._access_key_entry.connect("changed", self._s3_entry_changed_cb)
        self._secret_key_entry.connect("changed", self._s3_entry_changed_cb)
        self._bucket_name_entry.connect("changed", self._s3_entry_changed_cb)

    def _s3_entry_changed_cb(self, entry):
        # todo: implement better bucket name validation
        if (
            self.params.ceph_endpoint.startswith("https://")
            and self.params.bucket_name
            and self.params.access_key
            and self.params.secret_key
        ):
            self._valid = True
        else:
            self._valid = False

        self.notify("valid")

    def _get_client_options(self) -> dict:
        rv = super()._get_client_options()
        rv["endpoint_url"] = self._get_params().ceph_endpoint
        return rv

    def cleanup(self):
        # delete notification config
        try:
            self.s3_client.delete_bucket_notification_configuration(
                Bucket=self._get_params().bucket_name
            )
        except Exception as e:
            logger.exception(
                f"Could not restore bucket notification config: {str(e)}"
            )

        # remove topic
        if hasattr(self, "topic_arn"):
            try:
                self.sns_client.delete_topic(TopicArn=self.topic_arn)
            except Exception as e:
                logger.exception(
                    f"Could not remove topic {self.topic_arn}: {str(e)}"
                )

        super().cleanup()


class CephS3BucketEngineThread(BaseS3BucketEngineThread):
    def get_full_name(self, key):
        return f"{self.params.ceph_endpoint}/{self.params.bucket_name}/{key}"

    def run(self):
        self._client_options = self._engine._get_client_options()

        if not self.get_region_name(""):
            return

        # set up proper s3 client
        self._engine.s3_client = boto3.client("s3", **self._client_options)

        # set up sns client
        self._engine.sns_client = boto3.client(
            "sns", **self._client_options, config=Config(signature_version="s3")
        )

        try:
            # get current bucket notifications
            # response = self._engine.s3_client.get_bucket_notification_configuration(
            #    Bucket=self.params.bucket_name,
            # )

            # self._engine.old_bucket_notification_config = {configs: response.get(configs, []) for configs in AVAILABLE_CONFIGURATIONS}

            GLib.idle_add(
                self._task_window.set_text,
                "<b>Configuring bucket notifications...</b>",
            )
            self._engine.s3_client.delete_bucket_notification_configuration(
                Bucket=self.params.bucket_name,
            )

            if not self.params.rabbitmq_vhost.startswith("/"):
                raise ValueError("RabbitMQ vhost must start with a /")
            elif self.params.rabbitmq_vhost == "/":
                vhost = ""
            else:
                vhost = self.params.rabbitmq_vhost

            endpoint_args = (
                f"push-endpoint=amqp://{self.params.rabbitmq_username}:"
                + f"{self.params.rabbitmq_password}@{self.params.rabbitmq_hostname}:"
                + f"{int(self.params.rabbitmq_producer_port)}{vhost}&"
                + f"amqp-exchange={self.params.rabbitmq_exchange}&"
                + f"amqp-ack-level=broker"
            )
            attributes = {
                nvp[0]: nvp[1]
                for nvp in urllib.parse.parse_qsl(
                    endpoint_args, keep_blank_values=True
                )
            }

            topic_name = f"rfi-file-monitor-ceph.{get_random_string(8)}"

            resp = self._engine.sns_client.create_topic(
                Name=topic_name, Attributes=attributes
            )
            self._engine.topic_arn = resp["TopicArn"]

            topic_conf_list = [
                {
                    "TopicArn": self._engine.topic_arn,
                    "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],
                    "Id": "another-one-bites-the-dust",
                },
            ]

            self._engine.s3_client.put_bucket_notification_configuration(
                Bucket=self.params.bucket_name,
                NotificationConfiguration={
                    "TopicConfigurations": topic_conf_list
                },
            )

            # test connection to rabbitmq
            GLib.idle_add(
                self._task_window.set_text, "<b>Testing AMQP server...</b>"
            )
            if self.params.rabbitmq_consumer_use_ssl:
                ssl_context = ssl.create_default_context()
                if (
                    self.params.rabbitmq_ca_certificate
                    and (
                        ca_cert := Path(self.params.rabbitmq_ca_certificate)
                    ).exists()
                ):
                    ssl_context.load_verify_locations(cafile=ca_cert)
                ssl_options = pika.SSLOptions(ssl_context)
            else:
                ssl_options = None
            credentials = pika.credentials.PlainCredentials(
                self.params.rabbitmq_username, self.params.rabbitmq_password
            )
            connection_params = pika.ConnectionParameters(
                host=self.params.rabbitmq_hostname,
                port=int(self.params.rabbitmq_consumer_port),
                virtual_host=self.params.rabbitmq_vhost,
                credentials=credentials,
                ssl_options=ssl_options,
            )

            with pika.BlockingConnection(connection_params) as connection:
                with connection.channel() as channel:
                    channel.exchange_declare(
                        exchange=self.params.rabbitmq_exchange,
                        exchange_type="topic",
                        durable=True,
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

        # sleep 1 second
        time.sleep(1)

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
        try:
            with pika.BlockingConnection(connection_params) as connection:
                with connection.channel() as channel:
                    channel.exchange_declare(
                        exchange=self.params.rabbitmq_exchange,
                        exchange_type="topic",
                        durable=True,
                    )
                    result = channel.queue_declare("", exclusive=True)
                    queue_name = result.method.queue
                    channel.queue_bind(
                        exchange=self.params.rabbitmq_exchange,
                        queue=queue_name,
                        routing_key=topic_name,
                    )

                    while True:
                        if self._should_exit:
                            self._engine.cleanup()
                            return

                        method_frame, _, _body = channel.basic_get(queue_name)
                        if method_frame:
                            body = json.loads(_body)
                            channel.basic_ack(method_frame.delivery_tag)
                            # we are going to assume 1 record per message
                            try:
                                record = body["Records"][0]
                                event_name: str = record["eventName"]
                            except Exception as e:
                                logger.info(
                                    f"Ignoring {_body=} because of {str(e)}"
                                )
                                continue

                            if "ObjectCreated" in event_name:
                                # new file created!
                                s3_info = record["s3"]
                                if not self.process_new_file(s3_info):
                                    continue
                        else:
                            time.sleep(1)
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort, None, e, priority=GLib.PRIORITY_HIGH
            )
            return
