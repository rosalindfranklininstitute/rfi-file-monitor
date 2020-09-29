import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import dropbox

from ..operation import Operation, SkippedOperation
from ..applicationwindow import ApplicationWindow
from ..file import File

import logging
import os
import tempfile
import string
import random
from pathlib import PurePosixPath
import hashlib

logger = logging.getLogger(__name__)


# taken from https://github.com/dropbox/dropbox-api-content-hasher/blob/master/python/dropbox_content_hasher.py
class DropboxContentHasher(object):
    """
    Computes a hash using the same algorithm that the Dropbox API uses for the
    the "content_hash" metadata field.
    The digest() method returns a raw binary representation of the hash.  The
    hexdigest() convenience method returns a hexadecimal-encoded version, which
    is what the "content_hash" metadata field uses.
    This class has the same interface as the hashers in the standard 'hashlib'
    package.
    Example:
        hasher = DropboxContentHasher()
        with open('some-file', 'rb') as f:
            while True:
                chunk = f.read(1024)  # or whatever chunk size you want
                if len(chunk) == 0:
                    break
                hasher.update(chunk)
        print(hasher.hexdigest())
    """

    BLOCK_SIZE = 4 * 1024 * 1024

    def __init__(self):
        self._overall_hasher = hashlib.sha256()
        self._block_hasher = hashlib.sha256()
        self._block_pos = 0

        self.digest_size = self._overall_hasher.digest_size

    def update(self, new_data):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest()")

        new_data_pos = 0
        while new_data_pos < len(new_data):
            if self._block_pos == self.BLOCK_SIZE:
                self._overall_hasher.update(self._block_hasher.digest())
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0

            space_in_block = self.BLOCK_SIZE - self._block_pos
            part = new_data[new_data_pos:(new_data_pos+space_in_block)]
            self._block_hasher.update(part)

            self._block_pos += len(part)
            new_data_pos += len(part)

    def _finish(self):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest() or hexdigest()")

        if self._block_pos > 0:
            self._overall_hasher.update(self._block_hasher.digest())
            self._block_hasher = None
        h = self._overall_hasher
        self._overall_hasher = None  # Make sure we can't use this object anymore.
        return h

    def digest(self):
        return self._finish().digest()

    def hexdigest(self):
        return self._finish().hexdigest()

class DropboxUploaderOperation(Operation):
    NAME = "Dropbox Uploader"

    SESSION = dropbox.create_session(max_connections=ApplicationWindow.MAX_JOBS)
    APP_KEY = 'l9wed9kx1tq965c'
    CHUNK_SIZE = 1024 * 1024 # 1MB

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)

        # In the initial version, use only access-key and folder name
        self._grid.attach(Gtk.Label(
            label="Destination folder",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'destination_folder')
        self._grid.attach(widget, 1, 0, 1, 1)

        self._grid.attach(Gtk.Label(
            label="Access key",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'access_key')
        self._grid.attach(widget, 1, 1, 1, 1)

    @classmethod
    def _get_random_string(cls, length):
        # Random string with the combination of lower and upper case
        letters = string.ascii_letters
        result_str = ''.join(random.choice(letters) for i in range(length))
        return result_str

    def preflight_check(self):
        if not self.params.destination_folder:
            raise Exception('Destination folder cannot be an empty string')

        self._dropbox = dropbox.Dropbox(oauth2_access_token=self.params.access_key, session=self.SESSION, app_key=self.APP_KEY)
        echo_user = self._dropbox.check_user('test-user')
        logger.debug(f'{echo_user=}')
        account_info = self._dropbox.users_get_current_account()
        logger.debug(f'{account_info=}')
        space_usage = self._dropbox.users_get_space_usage()
        logger.debug(f'{space_usage=}')

        # create folder and upload test file
        self._base_folder = f'/{self.params.destination_folder}'
        try:
            self._dropbox.files_create_folder_v2(self._base_folder)
        except dropbox.exceptions.ApiError:
            # an exception is thrown if the directory already exists
            pass
        test_filename = f'{self._base_folder}/test-file-{self._get_random_string(6)}.txt'
        self._dropbox.files_upload(b'Dummy contents', path=test_filename)

        # delete file
        self._dropbox.files_delete_v2(test_filename)

    def run(self, file: File):
        # check first if file already exists
        # if it does, then first get its size
        # if the size matches, calculate checksum.
        # if checksums match, SKIP
        # else: remove file and upload new version

        dbx_filename = str(PurePosixPath(self._base_folder, *file.relative_filename.parts))
        size = os.path.getsize(file.filename)

        try:
            metadata = self._dropbox.files_get_metadata(dbx_filename)
        except dropbox.exceptions.ApiError:
            pass
        else:
            if size == metadata.size:
                # calculate content hash of local file
                hasher = DropboxContentHasher()
                with open(file.filename, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if len(chunk) == 0:
                            break
                        hasher.update(chunk)
                if hasher.hexdigest() == metadata.content_hash:
                    raise SkippedOperation('File has already been uploaded to Dropbox')
                else:
                    # delete remote file
                    self._dropbox.files_delete_v2(dbx_filename)
            else:
                # delete remote file
                self._dropbox.files_delete_v2(dbx_filename)
        
        # the following was inspired by Maestral
        if size <= self.CHUNK_SIZE:
            # upload small file
            with open(file.filename, 'rb') as f:
                self._dropbox.files_upload(f.read(), dbx_filename)
        else:
            # upload large file
            with open(file.filename, 'rb') as f:
                session_start = self._dropbox.files_upload_session_start(f.read(self.CHUNK_SIZE))
                uploaded = f.tell()

                cursor = dropbox.files.UploadSessionCursor(
                    session_id=session_start.session_id,
                    offset=uploaded
                )
                commit = dropbox.files.CommitInfo(
                    path=dbx_filename)

                while True:
                    try:
                        if size - f.tell() <= self.CHUNK_SIZE:
                            md = self._dropbox.files_upload_session_finish(
                                f.read(self.CHUNK_SIZE),
                                cursor,
                                commit
                            )

                        else:
                            self._dropbox.files_upload_session_append_v2(
                                f.read(self.CHUNK_SIZE),
                                cursor
                            )
                            md = None

                        # housekeeping
                        uploaded = f.tell()

                        # upload progressbar
                        file.update_progressbar(self.index, 100*uploaded/size)

                        if md:
                            break
                        else:
                            cursor.offset = uploaded

                    except dropbox.exceptions.DropboxException as exc:
                        error = getattr(exc, 'error', None)
                        if (isinstance(error, dropbox.files.UploadSessionFinishError)
                                and error.is_lookup_failed()):
                            session_lookup_error = error.get_lookup_failed()
                        elif isinstance(error, dropbox.files.UploadSessionLookupError):
                            session_lookup_error = error
                        else:
                            return str(exc)

                        if session_lookup_error.is_incorrect_offset():
                            o = session_lookup_error.get_incorrect_offset().correct_offset
                            # reset position in file
                            f.seek(o)
                            cursor.offset = f.tell()
                        else:
                            return str(exc)
                            

        return None
