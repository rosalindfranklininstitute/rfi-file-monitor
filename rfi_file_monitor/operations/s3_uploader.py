from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import boto3
import botocore
from munch import Munch
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_log,
    after_log,
    before_sleep_log,
)

from ..operation import Operation
from ..utils.exceptions import SkippedOperation
from ..file import File, RegularFile, Directory
from ..utils import query_metadata, monitor_retry_condition
from ..utils.decorators import (
    with_pango_docs,
    supported_filetypes,
    add_directory_support,
)
from ..utils.s3 import S3ProgressPercentage, TransferConfig, calculate_etag

import os
import logging
import tempfile
from pathlib import PurePosixPath, Path
import urllib
from typing import Sequence, Dict, Any, Optional

logger = logging.getLogger(__name__)

# useful info from help(boto3.session.Session.client)

ALLOWED_BUCKET_ACL_OPTIONS = (
    "ACL",
    "AccessControlPolicy",
    "GrantFullControl",
    "GrantRead",
    "GrantReadACP",
    "GrantWrite",
    "GrantWriteACP",
)

ALLOWED_OBJECT_ACL_OPTIONS = (
    "ACL",
    "AccessControlPolicy",
    "GrantFullControl",
    "GrantRead",
    "GrantReadACP",
    "GrantWrite",
    "GrantWriteACP",
    "RequestPayer",
    "VersionID",
)

AWS_S3_ENGINE_IGNORE_ME = "rfi-file-monitor-ignore-me"


@with_pango_docs(filename="s3_uploader.pango")
@supported_filetypes(filetypes=(RegularFile, Directory))
class S3UploaderOperation(Operation):
    NAME = "S3 Uploader"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.add(self._grid)

        # we need boxes for at least:
        # * hostname (+ allow disabling security)
        # * bucket name (+ allow creating it)
        # * access
        # * secret

        # Endpoint
        self._grid.attach(
            Gtk.Label(
                label="Endpoint",
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
        self._endpoint_entry = self.register_widget(
            Gtk.Entry(
                text="https://s3.amazonaws.com",
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "hostname",
        )
        self._grid.attach(self._endpoint_entry, 1, 0, 1, 1)
        widget = self.register_widget(
            Gtk.CheckButton(
                active=True,
                label="Verify SSL Certificates",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "hostname_ssl_verify",
        )
        self._grid.attach(widget, 2, 0, 1, 1)

        # Access key
        self._grid.attach(
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
        self._grid.attach(self._access_key_entry, 1, 1, 2, 1)

        # Secret key
        self._grid.attach(
            Gtk.Label(
                label="Secret Key",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            2,
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
        self._grid.attach(self._secret_key_entry, 1, 2, 2, 1)

        # Bucket name
        self._grid.attach(
            Gtk.Label(
                label="Bucket Name",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            3,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "bucket_name",
        )
        self._grid.attach(widget, 1, 3, 1, 1)
        widget = self.register_widget(
            Gtk.CheckButton(
                active=False,
                label="Create bucket if necessary",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "force_bucket_creation",
        )
        self._grid.attach(widget, 2, 3, 1, 1)

    @classmethod
    def _get_dict_tagset(
        cls, preflight_check_metadata: Dict[int, Dict[str, Any]], tagtype: str
    ) -> Optional[dict]:
        tags = query_metadata(preflight_check_metadata, tagtype)
        if tags is None:
            return None
        tagset = [dict(Key=_key, Value=_value) for _key, _value in tags.items()]
        return dict(TagSet=tagset)

    @classmethod
    def _get_dict_acl_options(
        cls,
        preflight_check_metadata: Dict[int, Dict[str, Any]],
        resource: str,
        allow_list: Sequence[str],
    ) -> Optional[dict]:
        options = query_metadata(preflight_check_metadata, resource)
        if options is None:
            return None
        for option in options:
            if option not in allow_list:
                raise ValueError(f"{option} is not permitted in {resource}")
        return options

    @classmethod
    def _get_dict_bucket_cors(
        cls, preflight_check_metadata: Dict[int, Dict[str, Any]]
    ) -> Optional[dict]:
        options = query_metadata(preflight_check_metadata, "bucket_cors")
        if options is None:
            return None
        if not isinstance(options, dict) or "CORSRules" not in options:
            raise ValueError(
                "bucket_cors does not contain a valid CORS configuration"
            )
        return options

    @classmethod
    def _get_client_options(cls, params: Munch) -> dict:
        client_options = dict()
        client_options["endpoint_url"] = params.hostname
        client_options["verify"] = params.hostname_ssl_verify
        client_options["aws_access_key_id"] = params.access_key
        client_options["aws_secret_access_key"] = params.secret_key
        return client_options

    @classmethod
    def _preflight_check(
        cls,
        preflight_check_metadata: Dict[int, Dict[str, Any]],
        self: S3UploaderOperation,
        params: Munch,
    ):
        # this variable will be used later on in preflight_cleanup
        self._bucket_created = False

        client_options = cls._get_client_options(params)

        # bucket creation options
        bucket_acl_options = cls._get_dict_acl_options(
            preflight_check_metadata,
            "bucket_acl_options",
            ALLOWED_BUCKET_ACL_OPTIONS,
        )
        # object creation options
        object_acl_options = cls._get_dict_acl_options(
            preflight_check_metadata,
            "object_acl_options",
            ALLOWED_OBJECT_ACL_OPTIONS,
        )

        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_tagging
        bucket_tags = cls._get_dict_tagset(
            preflight_check_metadata, "bucket_tags"
        )
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        object_tags = cls._get_dict_tagset(
            preflight_check_metadata, "object_tags"
        )

        # get CORS bucket configuration
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_cors
        bucket_cors = cls._get_dict_bucket_cors(preflight_check_metadata)

        # open connection
        s3_client = boto3.client("s3", **client_options)

        # check if the bucket exists
        # taken from https://stackoverflow.com/a/47565719
        try:
            s3_client.head_bucket(Bucket=params.bucket_name)
        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response["Error"]["Code"])
            if error_code == 403:
                raise
            elif error_code == 404:
                if params.force_bucket_creation:
                    s3_client.create_bucket(Bucket=params.bucket_name)
                    self._bucket_created = True
                    if bucket_tags:
                        s3_client.put_bucket_tagging(
                            Bucket=params.bucket_name, Tagging=bucket_tags
                        )
                    if bucket_acl_options:
                        s3_client.put_bucket_acl(
                            Bucket=params.bucket_name, **bucket_acl_options
                        )
                    if bucket_cors:
                        s3_client.put_bucket_cors(
                            Bucket=params.bucket_name,
                            CORSConfiguration=bucket_cors,
                        )
                else:
                    raise
            else:
                raise
        # try uploading a simple object
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(os.urandom(1024))  # 1 kB
            tmpfile = f.name
        try:
            s3_client.upload_file(
                Filename=tmpfile,
                Bucket=params.bucket_name,
                Key=os.path.basename(tmpfile),
                Config=TransferConfig,
                ExtraArgs={
                    "Metadata": {
                        AWS_S3_ENGINE_IGNORE_ME: "1",
                    }
                },
            )
            if object_tags:
                s3_client.put_object_tagging(
                    Bucket=params.bucket_name,
                    Key=os.path.basename(tmpfile),
                    Tagging=object_tags,
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
        self._preflight_check(
            self.appwindow.preflight_check_metadata, self, self.params
        )

    @classmethod
    def _attach_metadata(
        cls,
        file: File,
        endpoint_url: str,
        key: str,
        params: Munch,
        operation_index: int,
    ):
        parsed_url = urllib.parse.urlparse(endpoint_url)
        file.operation_metadata[operation_index] = {
            "s3 object url": f"{parsed_url.scheme}://{params.bucket_name}.{parsed_url.netloc}/{urllib.parse.quote(key)}"
        }

    @classmethod
    def _preflight_cleanup(
        cls, success: bool, self: S3UploaderOperation, params: Munch
    ):
        if not success and self._bucket_created:
            # preflight_check failed and a bucket was created: delete it!
            client_options = cls._get_client_options(params)

            # open connection
            s3_client = boto3.client("s3", **client_options)

            try:
                s3_client.delete_bucket(Bucket=params.bucket_name)
                logger.info(f"Bucket {params.bucket_name} successfully deleted")
            except Exception:
                logger.exception(f"Could not delete {params.bucket_name}")

            del s3_client
        return

    def preflight_cleanup(self, success: bool):
        self._preflight_cleanup(success, self, self.params)

    @classmethod
    @retry(
        retry=monitor_retry_condition(),
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
    )
    def _run(
        cls,
        file: File,
        preflight_check_metadata: Dict[int, Dict[str, Any]],
        params: Munch,
        operation_index: int,
    ):
        client_options = cls._get_client_options(params)
        s3_client = boto3.client("s3", **client_options)

        # object creation options
        object_acl_options = cls._get_dict_acl_options(
            preflight_check_metadata,
            "object_acl_options",
            ALLOWED_OBJECT_ACL_OPTIONS,
        )
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        object_tags = cls._get_dict_tagset(
            preflight_check_metadata, "object_tags"
        )

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
            if int(e.response["Error"]["Code"]) != 404:
                return str(e)
        else:
            if Path(file.filename).stat().st_size == int(
                response["ContentLength"]
            ):
                remote_etag = response["ETag"][
                    1:-1
                ]  # get rid of those extra quotes
                local_etag = calculate_etag(file.filename)
                if remote_etag == local_etag:
                    # attach metadata
                    cls._attach_metadata(
                        file,
                        client_options["endpoint_url"],
                        key,
                        params,
                        operation_index,
                    )
                    raise SkippedOperation("File has been uploaded already")

        try:
            s3_client.upload_file(
                Filename=file.filename,
                Bucket=params.bucket_name,
                Key=key,
                Config=TransferConfig,
                Callback=S3ProgressPercentage(
                    file, file.filename, operation_index
                ),
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
            logger.exception(f"S3UploaderOperation.run exception")
            del s3_client
            del client_options
            return str(e)
        else:
            # add object URL to metadata
            cls._attach_metadata(
                file,
                client_options["endpoint_url"],
                key,
                params,
                operation_index,
            )
            del s3_client
            del client_options
        return None

    @add_directory_support
    def run(self, file: File):
        return self._run(
            file,
            self.appwindow.preflight_check_metadata,
            self.params,
            self.index,
        )
