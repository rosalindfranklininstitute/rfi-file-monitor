import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import logging

logger = logging.getLogger(__name__)

class ParamsWindow(Gtk.Window):

    def __init__(self, contents: Gtk.Grid, parent: Gtk.ApplicationWindow, title: str):
        super().__init__(
            destroy_with_parent=True,
            transient_for=parent,
            window_position=Gtk.WindowPosition.NONE,
            border_width=5,
            title=title)
        self.add(contents)
        contents.show_all()
    
    def do_delete_event(self, event):
        return self.hide_on_delete()

