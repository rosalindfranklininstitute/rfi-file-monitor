import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio
from ..file import File, FileStatus
from pathlib import PurePath, PurePosixPath


class S3Object(File):
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: int,
        status: FileStatus,
        bucket_name: str,
        etag: str,
        size: int,
        region_name: str = "",
    ):

        super().__init__(
            filename,
            relative_filename,
            created,
            status,
        )
        self._bucket_name = bucket_name
        self._etag = etag
        self._size = size
        self._key = str(PurePosixPath(*self._relative_filename.parts))
        self._region_name = region_name

    @property
    def bucket_name(self):
        return self._bucket_name

    @property
    def etag(self):
        return self._etag

    @property
    def key(self):
        return self._key

    @property
    def size(self):
        return self._size

    @property
    def region_name(self):
        return self._region_name
