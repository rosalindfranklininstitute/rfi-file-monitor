from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import boto3
import boto3.s3.transfer
import botocore

from ..file import AbstractS3Object
from ..operation import Operation
from ..utils.decorators import supported_filetypes, with_pango_docs
from ..utils import get_random_string
from ..utils.exceptions import SkippedOperation
from ..utils.s3 import calculate_etag, TransferConfig, S3ProgressPercentage

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@supported_filetypes(filetypes=[AbstractS3Object])
@with_pango_docs(filename='s3_downloader.pango')
class S3DownloaderOperation(Operation):

    NAME = 'S3 Downloader'

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)

        # We are going to use the client from the engine
        # We only need to specify a directory where to save the files locally
        label = Gtk.Label(
            label='Download Destination',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        self._grid.attach(label, 0, 0, 1, 1)

        self._directory_chooser_button = self.register_widget(Gtk.FileChooserButton(
            title="Select the directory to write to",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            create_folders=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False), 'download_destination')
        self._grid.attach(self._directory_chooser_button, 1, 0, 1, 1)

    def preflight_check(self):

        # to check:
        # 1. Does the engine export the S3 client?
        # 2. Can we list the bucket?
        # 3. Is the destination writable?

        # write random file into destination folder
        temp_filename = Path(self.params.download_destination, get_random_string(6) + '.dat')
        temp_filename.write_text('delete me')
        temp_filename.unlink()

    def run(self, file: AbstractS3Object):
        
        s3_client = self.appwindow.active_engine.s3_client
        bucket_name = self.appwindow.active_engine.params.bucket_name

        # Check if file already exists in the destination folder
        destination = Path(self.params.download_destination, *file.relative_filename.parts)

        # get size and etag
        response = s3_client.head_object(
            Bucket=bucket_name,
            Key=file.key,
        )
        key_size = int(response['ContentLength'])

        if destination.exists():
            if destination.stat().st_size == key_size:
                remote_etag = response['ETag'][1:-1] # get rid of those extra quotes
                # note: for this to work with objects that were initially
                # uploaded with multipart uploads,
                # then the upload must have used the same TransferConfig as used in S3UploaderOperation
                local_etag = calculate_etag(destination)
                if remote_etag == local_etag:
                    # attach metadata
                    raise SkippedOperation('File has been downloaded already')
        else:
            # ensure the parent directories exist
            destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            s3_client.download_file(
                Bucket=bucket_name,
                Key=file.key,
                Filename=str(destination),
                Config=TransferConfig,
                Callback=S3ProgressPercentage(file, destination, self.index, float(key_size)),
            )
        except Exception as e:
            logger.exception(f'S3UploaderOperation.run exception')
            return f'Could not download {str(destination)}: {str(e)}'

        return None
