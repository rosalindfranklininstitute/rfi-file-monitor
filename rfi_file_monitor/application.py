import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk, GdkPixbuf
import yaml

import importlib.resources
import platform
import webbrowser
import logging
from typing import Any, Final, Dict
import importlib.metadata

from .applicationwindow import ApplicationWindow
from rfi_file_monitor.utils import add_action_entries, PREFERENCES_CONFIG_FILE
from .preferences import Preference
from .preferenceswindow import PreferencesWindow

logger = logging.getLogger(__name__)

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
            appmenus_str = importlib.resources.read_text('rfi_file_monitor.data', 'menus-appmenu.ui')
            builder = Gtk.Builder.new_from_string(appmenus_str, -1)
            self.set_app_menu(builder.get_object("app-menu"))

        commonmenus_str = importlib.resources.read_text('rfi_file_monitor.data', 'menus-common.ui')
        builder = Gtk.Builder.new_from_string(commonmenus_str, -1)
        self.set_menubar(builder.get_object("menubar"))

        action_entries = (
            ("about", self.on_about),
            ("quit", self.on_quit),
            ("open", self.on_open),
            ("new", lambda *_: self.do_activate()),
            ("help-url", self.on_help_url, "s"),
            ("preferences", self.on_preferences)
        )

        # This doesn't work, which is kind of uncool
        # self.add_action_entries(action_entries)
        for action_entry in action_entries:
            add_action_entries(self, *action_entry)

        # add accelerators
        accelerators = (
            ("app.quit", ("<Primary>Q", )),
            ("app.new", ("<Primary>N", )),
            ("app.open", ("<Primary>O", )),
            ("win.save", ("<Primary>S", )),
            ("win.save-as", ("<Primary><Shift>S", )),
            ("win.close", ("<Primary>W", )),
        )

        for accel in accelerators:
            self.set_accels_for_action(accel[0], accel[1])
        
        # populate dict with preferences found in entry points
        self._prefs: Final[Dict[Preference, Any]] = dict()
        if 'rfi_file_monitor.preferences' in importlib.metadata.entry_points():
            for e in importlib.metadata.entry_points()['rfi_file_monitor.preferences']:
                _pref = e.load()
                self._prefs[_pref] = _pref.default

        # now, open preferences file and update the prefs dictionary
        try:
            with PREFERENCES_CONFIG_FILE.open('r') as f:
                stored_prefs = yaml.safe_load(f)
        except FileNotFoundError:
            pass
        else:
            logger.debug(f'Reading preferences from {str(PREFERENCES_CONFIG_FILE)}')
            for _pref in self._prefs:
                for _key, _value in stored_prefs.items():
                    if _pref.key == _key:
                        self._prefs[_pref] = _value
                        break
                else:
                    logger.warning(f'Could not find a corresponding Preference class for key {_key} from preferences file')

        logger.debug(f'{self._prefs=}')

    def get_preferences(self) -> Dict[Preference, Any]:
        return self._prefs

    def on_open(self, action, param):
        # fire up file chooser dialog
        active_window = self.get_active_window()
        dialog = Gtk.FileChooserNative(
            modal=True, title='Open monitor configuration YAML file',
            transient_for=active_window, action=Gtk.FileChooserAction.OPEN)
        filter = Gtk.FileFilter()
        filter.add_pattern('*.yml')
        filter.add_pattern('*.yaml')
        filter.set_name('YAML file')
        dialog.add_filter(filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            yaml_file = dialog.get_filename()
            dialog.destroy()
            try:
                with open(yaml_file, 'r') as f:
                    yaml_dict = yaml.safe_load(f)
                logger.debug(f"Open: {yaml_dict=}")
                if 'configuration' not in yaml_dict or 'operations' not in yaml_dict:
                    raise Exception("Valid YAML files must contain a dict with keys configuration and operations")
            except Exception as e:
                dialog = Gtk.MessageDialog(transient_for=self,
                    modal=True, destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE, text=f"Could not load {yaml_file}",
                    secondary_text=str(e))
                dialog.run()
                dialog.destroy()
            else:
                window = ApplicationWindow(application=self, type=Gtk.WindowType.TOPLEVEL)
                window.load_from_yaml_dict(yaml_dict)
                window.show_all()
        else:
            dialog.destroy()

    def do_activate(self):
        window = ApplicationWindow(application=self, title="Unknown Folder", type=Gtk.WindowType.TOPLEVEL)
        window.show_all()

    def on_about(self, action, param):

        with importlib.resources.path('rfi_file_monitor.data', 'RFI-logo-transparent.png') as f:
            logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(f),
                300,
                -1,
                True)

        about_dialog = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            authors=["Tom Schoonjans"],
            logo=logo,
            version="0.1.3",
            )
        about_dialog.present()

    def on_quit(self, action, param):
        self.quit()

    def on_help_url(self, action, param):
        webbrowser.open_new_tab(param.get_string())

    def on_preferences(self, action, param):
        window = PreferencesWindow(
            self._prefs,
            modal=False,
            transient_for=self.get_active_window(),
		    window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
            type=Gtk.WindowType.TOPLEVEL,
		    destroy_with_parent=True,
            border_width=5,
            )
        window.present()
