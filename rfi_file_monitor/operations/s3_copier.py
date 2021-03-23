from __future__ import annotations

import boto3
import botocore

from ..utils.decorators import supported_filetypes, with_pango_docs
from ..utils.exceptions import SkippedOperation
from ..utils.s3 import S3ProgressPercentage, TransferConfig
from ..file import S3Object
from .s3_uploader import S3UploaderOperation, ALLOWED_OBJECT_ACL_OPTIONS

import logging

logger = logging.getLogger(__name__)


@supported_filetypes(filetypes=S3Object)
@with_pango_docs(filename="s3_copier.pango")
class S3CopierOperation(S3UploaderOperation):

    NAME = "S3 Copier"

    def run(self, file: S3Object):
        # prepare our clients
        s3_origin_client = self.appwindow.active_engine.s3_client
        bucket_origin_name = (
            self.appwindow.active_engine._get_params().bucket_name
        )

        client_destination_options = self._get_client_options(self.params)
        s3_destination_client = boto3.client("s3", **client_destination_options)

        # object creation options
        object_acl_options = self._get_dict_acl_options(
            self.appwindow.preflight_check_metadata,
            "object_acl_options",
            ALLOWED_OBJECT_ACL_OPTIONS,
        )
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object_tagging
        object_tags = self._get_dict_tagset(
            self.appwindow.preflight_check_metadata, "object_tags"
        )

        # Check if file already exists in the destination bucket
        try:
            response_destination = s3_destination_client.head_object(
                Bucket=self.params.bucket_name,
                Key=file.key,
            )
        except botocore.exceptions.ClientError as e:
            # key not found, which is fine
            if int(e.response["Error"]["Code"]) != 404:
                return str(e)
        else:
            # compare etags
            remote_etag = response_destination["ETag"][1:-1]
            if remote_etag == file.etag:
                # attach metadata
                self._attach_metadata(
                    file,
                    client_destination_options["endpoint_url"],
                    file.key,
                    self.params,
                    self.index,
                )
                raise SkippedOperation(
                    "File has been copied already to the destination bucket"
                )

        try:
            s3_destination_client.copy(
                CopySource={"Bucket": bucket_origin_name, "Key": file.key},
                Bucket=self.params.bucket_name,
                Key=file.key,
                SourceClient=s3_origin_client,
                Callback=S3ProgressPercentage(
                    file, file.filename, self.index, float(file.size)
                ),
                Config=TransferConfig,
            )
            if object_tags:
                s3_destination_client.put_object_tagging(
                    Bucket=self.params.bucket_name,
                    Key=file.key,
                    Tagging=object_tags,
                )
            if object_acl_options:
                s3_destination_client.put_object_acl(
                    Bucket=self.params.bucket_name,
                    Key=file.key,
                    **object_acl_options,
                )
        except Exception as e:
            logger.exception(f"S3UploaderOperation.run exception")
            return str(e)
        else:
            # add object URL to metadata
            self._attach_metadata(
                file,
                client_destination_options["endpoint_url"],
                file.key,
                self.params,
                self.index,
            )
        return None
