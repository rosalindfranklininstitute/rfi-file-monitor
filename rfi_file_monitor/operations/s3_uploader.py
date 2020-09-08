import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import boto3
import botocore

from ..operation import Operation
from ..file import File
from ..job import Job

import os
import logging
import tempfile
from pathlib import PurePosixPath
from threading import current_thread, Lock
import urllib
from typing import Sequence

logger = logging.getLogger(__name__)

# useful info from help(boto3.session.Session.client)

ALLOWED_BUCKET_ACL_OPTIONS = (
    'ACL',
    'AccessControlPolicy',
    'GrantFullControl',
    'GrantRead',
    'GrantReadACP',
    'GrantWrite',
    'GrantWriteACP',
)

ALLOWED_OBJECT_ACL_OPTIONS = (
    'ACL',
    'AccessControlPolicy',
    'GrantFullControl',
    'GrantRead',
    'GrantReadACP',
    'GrantWrite',
    'GrantWriteACP',
    'RequestPayer',
    'VersionID',
)

class S3UploaderOperation(Operation):
    NAME = "S3 Uploader"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)

        # we need boxes for at least:
        # * hostname (+ allow disabling security)
        # * bucket name (+ allow creating it)
        # * access
        # * secret

        # Endpoint
        self._grid.attach(Gtk.Label(
            label="Endpoint",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            text="https://s3.amazonaws.com",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'hostname')
        self._grid.attach(widget, 1, 0, 1, 1)
        widget = self.register_widget(Gtk.CheckButton(
            active=True, label="Verify SSL Certificates",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 'hostname_ssl_verify')
        self._grid.attach(widget, 2, 0, 1, 1)

        # Access key
        self._grid.attach(Gtk.Label(
            label="Access Key",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'access_key')
        self._grid.attach(widget, 1, 1, 2, 1)

        # Secret key
        self._grid.attach(Gtk.Label(
            label="Secret Key", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 2, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            visibility=False,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'secret_key', exportable=False)
        self._grid.attach(widget, 1, 2, 2, 1)

        # Bucket name
        self._grid.attach(Gtk.Label(
            label="Bucket Name", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 3, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'bucket_name')
        self._grid.attach(widget, 1, 3, 1, 1)
        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Create bucket if necessary",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 'force_bucket_creation')
        self._grid.attach(widget, 2, 3, 1, 1)

    def _get_dict_tagset(self, tagtype: str):
        for metadata_dict in reversed(self.appwindow.preflight_check_metadata.values()):
            if tagtype in metadata_dict:
                tags = metadata_dict[tagtype]
                tagset = [dict(Key=_key, Value=_value) for _key, _value in tags.items()]
                return dict(TagSet=tagset)
        return None

    def _get_dict_acl_options(self, resource: str, allow_list: Sequence[str]):
        for metadata_dict in reversed(self.appwindow.preflight_check_metadata.values()):
            if resource in metadata_dict:
                options = metadata_dict[resource]
                for option in options:
                    if option not in allow_list:
                        raise ValueError(f'{option} is not permitted in {resource}')
                return options
        return dict()


    def preflight_check(self):
        self._client_options = dict()
        self._client_options['endpoint_url'] = self.params.hostname
        self._client_options['verify'] = self.params.hostname_ssl_verify
        self._client_options['aws_access_key_id'] = self.params.access_key
        self._client_options['aws_secret_access_key'] = self.params.secret_key

        # bucket creation options
        self._bucket_acl_options = self._get_dict_acl_options('bucket_acl_options', ALLOWED_BUCKET_ACL_OPTIONS)
        # object creation options
        self._object_acl_options = self._get_dict_acl_options('object_acl_options', ALLOWED_OBJECT_ACL_OPTIONS)

        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_tagging
        self._bucket_tags = self._get_dict_tagset('bucket_tags')
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        self._object_tags = self._get_dict_tagset('object_tags')

        # open connection (things can definitely go wrong here!)
        self._s3_client = boto3.client('s3', **self._client_options)

        # check if the bucket exists
        # taken from https://stackoverflow.com/a/47565719
        try:
            logger.debug(f"Checking if bucket {self.params.bucket_name} exists")
            self._s3_client.head_bucket(Bucket=self.params.bucket_name)
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                logger.info(f"Bucket {self.params.bucket_name} exists but is not accessible")
                raise
            elif error_code == 404:
                logger.info(f"Bucket {self.params.bucket_name} does not exist")
                if self.params.force_bucket_creation:
                    logger.info(f"Trying to create bucket {self.params.bucket_name}")
                    self._s3_client.create_bucket(Bucket=self.params.bucket_name)
                    if self._bucket_tags:
                        self._s3_client.put_bucket_tagging(Bucket=self.params.bucket_name, Tagging=self._bucket_tags)
                    if self._bucket_acl_options:
                        self._s3_client.put_bucket_acl(Bucket=self.params.bucket_name, **self._bucket_acl_options)
                else:
                    raise
            else:
                raise
        else:
            # try uploading a simple object
            logger.debug(f"Try uploading a test file to {self.params.bucket_name}")
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(os.urandom(1024)) # 1 kB
                tmpfile = f.name
            try:
                self._s3_client.upload_file(
                    Filename=tmpfile,
                    Bucket=self.params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    Config = boto3.s3.transfer.TransferConfig(max_concurrency=1),
                    )
                if self._object_tags:
                    self._s3_client.put_object_tagging(
                        Bucket=self.params.bucket_name,
                        Key=os.path.basename(tmpfile),
                        Tagging=self._object_tags
                    )
                if self._object_acl_options:
                    self._s3_client.put_object_acl(
                        Bucket=self.params.bucket_name,
                        Key=os.path.basename(tmpfile),
                        **self._object_acl_options,
                    )
            except:
                raise
            else:
                # if successful, remove it
                # delete tags first!
                if self._object_tags:
                    self._s3_client.delete_object_tagging(
                        Bucket=self.params.bucket_name,
                        Key=os.path.basename(tmpfile),
                        )
                
                self._s3_client.delete_object(\
                    Bucket=self.params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    )
            finally:
                os.unlink(tmpfile)

    def run(self, file: File):
        thread = current_thread()

        try:
            #TODO: do not allow overwriting existing keys in bucket??
            key = str(PurePosixPath(*file.relative_filename.parts))
            self._s3_client.upload_file( \
                Filename=file.filename,\
                Bucket=self.params.bucket_name,
                Key=key,
                Config = boto3.s3.transfer.TransferConfig(max_concurrency=1),
                Callback = S3ProgressPercentage(file, thread, self),
                )
            if self._object_tags:
                self._s3_client.put_object_tagging(
                    Bucket=self.params.bucket_name,
                    Key=key,
                    Tagging=self._object_tags,
                    )
            if self._object_acl_options:
                self._s3_client.put_object_acl(
                    Bucket=self.params.bucket_name,
                    Key=key,
                    **self._object_acl_options,
                )
        except Exception as e:
            logger.exception(f'S3UploaderOperation.run exception')
            return str(e)
        else:
            #add object URL to metadata
            parsed_url = urllib.parse.urlparse(self._client_options['endpoint_url'])
            file.operation_metadata[self.index] = {'s3 object url':
                f'{parsed_url.scheme}://{self.params.bucket_name}.{parsed_url.netloc}/{urllib.parse.quote(key)}'}
            logger.info(f"S3 upload complete from {file._filename} to {self.params.bucket_name}")
            logger.debug(f"{file.operation_metadata[self.index]=}")
        return None

# taken from https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
class S3ProgressPercentage(object):

    def __init__(self, file: File, thread: Job, operation: Operation):
        self._file = file
        self._filename = file._filename
        self._size = float(os.path.getsize(self._filename))
        self._seen_so_far = 0
        self._last_percentage = 0
        self._lock = Lock() # not sure this is necessary since we are using just one thread
        self._thread = thread
        self._operation = operation

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            if int(percentage) > self._last_percentage:
                self._last_percentage = int(percentage)
                self._file.update_progressbar(self._operation.index, self._last_percentage)
