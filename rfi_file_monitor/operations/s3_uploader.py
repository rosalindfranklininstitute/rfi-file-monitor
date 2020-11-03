import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import boto3
import boto3.s3.transfer
import botocore
from munch import Munch

from ..operation import Operation
from ..utils.exceptions import SkippedOperation
from ..file import File
from ..job import Job
from ..utils import query_metadata
from ..utils.decorators import with_pango_docs

import os
import logging
import tempfile
import hashlib
from pathlib import PurePosixPath, Path
from threading import current_thread, Lock
import urllib
from typing import Sequence, Dict, Any

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

KB = 1024
MB = KB * KB
TransferConfig = boto3.s3.transfer.TransferConfig(max_concurrency=1, multipart_chunksize=8*MB, multipart_threshold=8*MB)

@with_pango_docs(filename='s3_uploader.pango')
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

    @classmethod
    def _calculate_etag(cls, file: File):
        # taken from https://stackoverflow.com/a/52300584
        with Path(file.filename).open('rb') as f:
            md5hash = hashlib.md5()
            filesize = 0
            block_count = 0
            md5string = b''
            for block in iter(lambda: f.read(TransferConfig.multipart_chunksize), b''):
                md5hash = hashlib.md5()
                md5hash.update(block)
                md5string += md5hash.digest()
                filesize += len(block)
                block_count += 1

        if filesize > TransferConfig.multipart_threshold:
            md5hash = hashlib.md5()
            md5hash.update(md5string)
            md5hash = md5hash.hexdigest() + "-" + str(block_count)
        else:
            md5hash = md5hash.hexdigest()

        return md5hash

    @classmethod
    def _get_dict_tagset(cls, preflight_check_metadata: Dict[int, Dict[str, Any]], tagtype: str) -> dict:
        tags = query_metadata(preflight_check_metadata, tagtype)
        if tags is None:
            return None
        tagset = [dict(Key=_key, Value=_value) for _key, _value in tags.items()]
        return dict(TagSet=tagset)

    @classmethod
    def _get_dict_acl_options(cls, preflight_check_metadata: Dict[int, Dict[str, Any]], resource: str, allow_list: Sequence[str]) -> dict:
        options = query_metadata(preflight_check_metadata, resource)
        if options is None:
            return None
        for option in options:
            if option not in allow_list:
                raise ValueError(f'{option} is not permitted in {resource}')
        return options

    @classmethod
    def _get_client_options(cls, params: Munch) -> dict:
        client_options = dict()
        client_options['endpoint_url'] = params.hostname
        client_options['verify'] = params.hostname_ssl_verify
        client_options['aws_access_key_id'] = params.access_key
        client_options['aws_secret_access_key'] = params.secret_key
        return client_options

    @classmethod
    def _preflight_check(cls, preflight_check_metadata: Dict[int, Dict[str, Any]], params: Munch):
        client_options = cls._get_client_options(params)

        # bucket creation options
        bucket_acl_options = cls._get_dict_acl_options(preflight_check_metadata, 'bucket_acl_options', ALLOWED_BUCKET_ACL_OPTIONS)
        # object creation options
        object_acl_options = cls._get_dict_acl_options(preflight_check_metadata, 'object_acl_options', ALLOWED_OBJECT_ACL_OPTIONS)

        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_tagging
        bucket_tags = cls._get_dict_tagset(preflight_check_metadata, 'bucket_tags')
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        object_tags = cls._get_dict_tagset(preflight_check_metadata, 'object_tags')

        # open connection
        s3_client = boto3.client('s3', **client_options)

        # check if the bucket exists
        # taken from https://stackoverflow.com/a/47565719
        try:
            logger.debug(f"Checking if bucket {params.bucket_name} exists")

            s3_client.head_bucket(Bucket=params.bucket_name)
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 403:
                logger.info(f"Bucket {params.bucket_name} exists but is not accessible")
                raise
            elif error_code == 404:
                logger.info(f"Bucket {params.bucket_name} does not exist")
                if params.force_bucket_creation:
                    logger.info(f"Trying to create bucket {params.bucket_name}")
                    s3_client.create_bucket(Bucket=params.bucket_name)
                    if bucket_tags:
                        s3_client.put_bucket_tagging(Bucket=params.bucket_name, Tagging=bucket_tags)
                    if bucket_acl_options:
                        s3_client.put_bucket_acl(Bucket=params.bucket_name, **bucket_acl_options)
                else:
                    raise
            else:
                raise
        # try uploading a simple object
        logger.debug(f"Try uploading a test file to {params.bucket_name}")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(os.urandom(1024)) # 1 kB
            tmpfile = f.name
        try:
            s3_client.upload_file(
                Filename=tmpfile,
                Bucket=params.bucket_name,
                Key=os.path.basename(tmpfile),
                Config=TransferConfig,
                )
            if object_tags:
                s3_client.put_object_tagging(
                    Bucket=params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    Tagging=object_tags
                )
            if object_acl_options:
                s3_client.put_object_acl(
                    Bucket=params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    **object_acl_options,
                )
        except:
            raise
        else:
            # if successful, remove it
            # delete tags first!
            if object_tags:
                s3_client.delete_object_tagging(
                    Bucket=params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    )
                
            s3_client.delete_object(
                Bucket=params.bucket_name,
                Key=os.path.basename(tmpfile),
                )
        finally:
            os.unlink(tmpfile)

    def preflight_check(self):
        self._preflight_check(self.appwindow.preflight_check_metadata, self.params)

    @classmethod
    def _attach_metadata(cls, file: File, endpoint_url: str, key: str, params: Munch, operation_index:int):
        parsed_url = urllib.parse.urlparse(endpoint_url)
        file.operation_metadata[operation_index] = {'s3 object url':
            f'{parsed_url.scheme}://{params.bucket_name}.{parsed_url.netloc}/{urllib.parse.quote(key)}'}
        logger.info(f"S3 upload complete from {file.filename} to {params.bucket_name}")
        logger.debug(f"{file.operation_metadata[operation_index]=}")

    @classmethod
    def _run(cls, file: File, preflight_check_metadata: Dict[int, Dict[str, Any]], params: Munch, operation_index:int):
        thread = current_thread()
        client_options = cls._get_client_options(params)
        s3_client = boto3.client('s3', **client_options)

        # object creation options
        object_acl_options = cls._get_dict_acl_options(preflight_check_metadata, 'object_acl_options', ALLOWED_OBJECT_ACL_OPTIONS)
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        object_tags = cls._get_dict_tagset(preflight_check_metadata, 'object_tags')

        key = str(PurePosixPath(*file.relative_filename.parts))

        # Check if file already exists and is identical
        # Inspired by: https://stackoverflow.com/questions/6591047/etag-definition-changed-in-amazon-s3
        try:
            response = s3_client.head_object(
                Bucket=params.bucket_name,
                Key=key,
            )
        except botocore.exceptions.ClientError as e:
            # key not found, which is fine
            if int(e.response['Error']['Code']) != 404:
                return str(e)
        else:
            if Path(file.filename).stat().st_size == int(response['ContentLength']):
                remote_etag = response['ETag'][1:-1] # get rid of those extra quotes
                local_etag = cls._calculate_etag(file)
                if remote_etag == local_etag:
                    # attach metadata
                    cls._attach_metadata(file, client_options['endpoint_url'], key, params, operation_index)
                    raise SkippedOperation('File has been uploaded already')

        try:
            s3_client.upload_file( \
                Filename=file.filename,\
                Bucket=params.bucket_name,
                Key=key,
                Config=TransferConfig,
                Callback=S3ProgressPercentage(file, thread, operation_index),
                )
            if object_tags:
                s3_client.put_object_tagging(
                    Bucket=params.bucket_name,
                    Key=key,
                    Tagging=object_tags,
                    )
            if object_acl_options:
                s3_client.put_object_acl(
                    Bucket=params.bucket_name,
                    Key=key,
                    **object_acl_options,
                )
        except Exception as e:
            logger.exception(f'S3UploaderOperation.run exception')
            del s3_client
            del client_options
            return str(e)
        else:
            #add object URL to metadata
            cls._attach_metadata(file, client_options['endpoint_url'], key, params, operation_index)
            del s3_client
            del client_options
        return None

    def run(self, file: File):
        return self._run(file, self.appwindow.preflight_check_metadata, self.params, self.index)


# taken from https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
class S3ProgressPercentage(object):

    def __init__(self, file: File, thread: Job, operation_index: int):
        self._file = file
        self._filename = file._filename
        self._size = float(os.path.getsize(self._filename))
        self._seen_so_far = 0
        self._last_percentage = 0
        self._lock = Lock() # not sure this is necessary since we are using just one thread
        self._thread = thread
        self._operation_index = operation_index

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            if int(percentage) > self._last_percentage:
                self._last_percentage = int(percentage)
                self._file.update_progressbar(self._operation_index, self._last_percentage)
