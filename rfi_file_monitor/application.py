import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk

import pkg_resources
import platform
import webbrowser

from .applicationwindow import ApplicationWindow
from .utils import add_action_entries

class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="uk.ac.rfi.ai.file-monitor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            **kwargs
        )
        GLib.set_application_name("RFI File Monitor")

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # this may need to be checked on other platforms as well
        if platform.system() == 'Darwin':
            appmenus_str = pkg_resources.resource_string('rfi_file_monitor', 'data/menus-appmenu.ui').decode("utf-8")
            builder = Gtk.Builder.new_from_string(appmenus_str, -1)
            self.set_app_menu(builder.get_object("app-menu"))

        commonmenus_str = pkg_resources.resource_string('rfi_file_monitor', 'data/menus-common.ui').decode("utf-8")
        builder = Gtk.Builder.new_from_string(commonmenus_str, -1)
        self.set_menubar(builder.get_object("menubar"))

        action_entries = (
            ("about", self.on_about),
            ("quit", self.on_quit),
            ("new", lambda *_: self.do_activate()),
            ("help-url", self.on_help_url, "s")
        )

        # This doesn't work, which is kind of uncool
        # self.add_action_entries(action_entries)
        for action_entry in action_entries:
            add_action_entries(self, *action_entry)

        # add accelerators
        accelerators = (
            ("app.quit", ("<Primary>Q", )),
            ("app.new", ("<Primary>N", )),
            ("win.close", ("<Primary>W", )),
        )

        for accel in accelerators:
            self.set_accels_for_action(accel[0], accel[1])

    def do_activate(self):
        window = ApplicationWindow(application=self, title="Unknown Folder", type=Gtk.WindowType.TOPLEVEL)
        window.show_all()

    def on_about(self, action, param):
        about_dialog = Gtk.AboutDialog(transient_for=self.get_active_window(), modal=True)
        about_dialog.present()

    def on_quit(self, action, param):
        self.quit()

    def on_help_url(self, action, param):
        webbrowser.open_new_tab(param.get_string())