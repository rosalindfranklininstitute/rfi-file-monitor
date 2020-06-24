import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk
import boto3
import botocore

#pylint: disable=relative-beyond-top-level
from ..operation import Operation
from ..file import File
from ..job import Job

import logging
import os
import tempfile
from pathlib import PurePosixPath
from threading import current_thread, Lock
import traceback
import sys
import urllib

# useful info from help(boto3.session.Session.client)

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
        self._hostname_entry = Gtk.Entry(
            placeholder_text="https://s3.amazonaws.com",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(self._hostname_entry, 1, 0, 1, 1)
        self._hostname_ssl_verify_check_button = Gtk.CheckButton(
            active=True, label="Verify SSL Certificates",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        self._grid.attach(self._hostname_ssl_verify_check_button, 2, 0, 1, 1)

        # Access key
        self._grid.attach(Gtk.Label(
            label="Access Key",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        self._access_key_entry = Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(self._access_key_entry, 1, 1, 2, 1)

        # Secret key
        self._grid.attach(Gtk.Label(
            label="Secret Key", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 2, 1, 1)
        self._secret_key_entry = Gtk.Entry(
            visibility=False,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(self._secret_key_entry, 1, 2, 2, 1)

        # Bucket name
        self._grid.attach(Gtk.Label(
            label="Bucket Name", 
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 3, 1, 1)
        self._bucket_name_entry = Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(self._bucket_name_entry, 1, 3, 1, 1)
        self._force_bucket_creation_check_button = Gtk.CheckButton(
            active=False, label="Create bucket if necessary",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        self._grid.attach(self._force_bucket_creation_check_button, 2, 3, 1, 1)

    def preflight_check(self):
        self._client_options = dict()
        self._client_options['endpoint_url'] = tmp if (tmp := self._hostname_entry.get_text().strip()) != "" else self._hostname_entry.get_placeholder_text()
        self._client_options['verify'] = self._hostname_ssl_verify_check_button.get_active()
        self._client_options['aws_access_key_id'] = tmp if (tmp := self._access_key_entry.get_text().strip()) != "" else None
        self._client_options['aws_secret_access_key'] = tmp if (tmp := self._secret_key_entry.get_text().strip()) != "" else None
        logging.debug(f'{self._client_options=}')

        self._bucket_name = self._bucket_name_entry.get_text().strip()
        self._force_bucket_creation = self._force_bucket_creation_check_button.get_active()

        # open connection (things can definitely go wrong here!)
        self._s3_client = boto3.client('s3', **self._client_options)

        # check if the bucket exists
        # taken from https://stackoverflow.com/a/47565719
        try:
            logging.debug(f"Checking if bucket {self._bucket_name} exists")
            self._s3_client.head_bucket(Bucket=self._bucket_name)
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                logging.info(f"Bucket {self._bucket_name} exists but is not accessible")
                raise
            elif error_code == 404:
                logging.info(f"Bucket {self._bucket_name} does not exist")
                if self._force_bucket_creation:
                    logging.info(f"Trying to create bucket {self._bucket_name}")
                    self._s3_client.create_bucket(Bucket=self._bucket_name)
                else:
                    raise
            else:
                raise
        else:
            # try uploading a simple object
            logging.debug(f"Try uploading a test file to {self._bucket_name}")
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(os.urandom(1024)) # 1 kB
                tmpfile = f.name
            try:
                self._s3_client.upload_file(tmpfile, self._bucket_name, os.path.basename(tmpfile))
            except:
                raise
            else:
                # if successful, remove it
                self._s3_client.delete_object(Bucket=self._bucket_name, Key=os.path.basename(tmpfile))
            finally:
                os.unlink(tmpfile)

    def run(self, file: File):
        thread = current_thread()

        try:
            #TODO: do not allow overwriting existing keys in bucket??
            key = str(PurePosixPath(*file._relative_filename.parts))
            self._s3_client.upload_file( \
                file._filename,\
                self._bucket_name,
                key,
                ExtraArgs = None, # TODO: add support for ACL??
                Config = boto3.s3.transfer.TransferConfig(max_concurrency=1),
                Callback = S3ProgressPercentage(file, thread, self)
                )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return str(e)
        else:
            #add object URL to metadata
            parsed_url = urllib.parse.urlparse(self._client_options['endpoint_url'])
            file.operation_metadata[self.index] = {'s3 object url':
                f'{parsed_url.scheme}://{self._bucket_name}.{parsed_url.netloc}/{urllib.parse.quote(key)}'}
            logging.info(f"S3 upload complete from {file._filename} to {self._bucket_name}")
            logging.debug(f"{file.operation_metadata[self.index]=}")
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
                self._file.update_progressbar(self._operation.index, percentage)
