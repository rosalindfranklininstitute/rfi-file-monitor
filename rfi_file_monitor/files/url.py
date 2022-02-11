import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio
from ..file import File

class URL(File):
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: int,
        status: FileStatus,
    ):

        super().__init__(
            filename,
            relative_filename,
            created,
            status,
        )
