import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

import logging

logger = logging.getLogger(__name__)


class ParamsWindow(Gtk.Window):
    def __init__(
        self, contents: Gtk.Widget, parent: Gtk.ApplicationWindow, title: str
    ):
        super().__init__(
            destroy_with_parent=True,
            transient_for=parent,
            #window_position=Gtk.WindowPosition.NONE,
            title=title,
        )
        self.set_child(contents)


    def do_delete_event(self, event):
        return self.hide_on_delete()
