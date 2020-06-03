import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk

from .utils import add_action_entries

class ApplicationWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(1000, 1000)

        action_entries = (
            ("on_close", self.on_close),
            ("on_minimize", self.on_minimize),
        )

        # This doesn't work, which is kind of uncool
        # self.add_action_entries(action_entries)
        for action_entry in action_entries:
            add_action_entries(self, *action_entry)

        self.label = Gtk.Label(label="TEST", margin=30)
        self.add(self.label)
        self.label.show()
    
    def on_minimize(self, action, param):
        self.iconify()

    def on_close(self, action, param):
        self.destroy()
