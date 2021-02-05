from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk, GdkPixbuf
import yaml

import importlib.resources
import platform
import webbrowser
import logging
from typing import Any, Dict, Type, Union, List
import importlib.metadata
from pathlib import Path

from .version import __version__
from .utils import add_action_entries, PREFERENCES_CONFIG_FILE, MONITOR_YAML_VERSION 
from .preferences import Preference
from .preferenceswindow import PreferencesWindow
from .file import RegularFile, File
from .utils.helpwindow import HelpWindow
from .utils.googleanalytics import GoogleAnalyticsContext
from .applicationwindow import ApplicationWindow
from .engine import Engine
from .engine_advanced_settings import EngineAdvancedSettings
from .operation import Operation
from .queue_manager import QueueManager


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

    @property
    def known_operations(self):
        return self._known_operations

    @property
    def known_engines(self):
        return self._known_engines

    @property
    def help_window(self):
        return self._help_window

    @property
    def engines_advanced_settings_map(self):
        return self._engines_advanced_settings_map

    @property
    def engines_exported_filetype_map(self):
        return self._engines_exported_filetype_map

    @property
    def filetypes_supported_operations_map(self):
        return self._filetypes_supported_operations_map

    @property
    def pango_docs_map(self):
        return self._pango_docs_map

    @property
    def google_analytics_context(self):
        return self._google_analytics_context

    def do_shutdown(self):
        logger.debug('Calling do_shutdown')
        Gtk.Application.do_shutdown(self)

        self._google_analytics_context.consumer_thread.should_exit = True

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

        # get file filter menu
        popover_filter_menu_str = importlib.resources.read_text('rfi_file_monitor.data', 'filter-popover.ui')
        builder = Gtk.Builder.new_from_string(popover_filter_menu_str, -1)
        self.filter_popover_menu = builder.get_object("filter-popover-menu")

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
        self._prefs: Dict[Preference, Any] = dict()
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
            for _key, _value in stored_prefs.items():
                for _pref in self._prefs:
                    if _pref.key == _key:
                        self._prefs[_pref] = _value
                        break
                else:
                    logger.warning(f'Could not find a corresponding Preference class for key {_key} from preferences file')

        logger.debug(f'{self._prefs=}')


        self._engines_advanced_settings_map : Dict[Type[Engine], Type[EngineAdvancedSettings]] = dict()

        self._engines_exported_filetype_map : Dict[Type[Engine], Type[File]] = dict()

        self._filetypes_supported_operations_map : Dict[Type[File], List[Type[Operation]]] = dict()

        self._pango_docs_map : Dict[Type[Union[Engine, QueueManager, Operation]], str] = dict()

        # add queue manager docs manually
        try:
            contents = Path(__file__).parent.joinpath('docs', 'queue_manager.pango').read_text()
        except Exception:
            logger.exception(f'with_pango_docs: could not open queue_manager.pango for reading')
        else:
            self._pango_docs_map[QueueManager] = contents

        # get info from entry points
        self._known_operations = {
            e.name: e.load() for e in importlib.metadata.entry_points()['rfi_file_monitor.operations']
        }

        self._update_supported_filetypes()

        for _name in self._known_operations:
            logger.debug(f"Operation found: {_name}")
        
        self._known_engines = {
            e.name: e.load() for e in importlib.metadata.entry_points()['rfi_file_monitor.engines']
        }
        
        for _name in self._known_engines:
            logger.debug(f"Engine found: {_name}")

        # add our help window, which will be shared by all appwindows
        self._help_window = HelpWindow(self._pango_docs_map)

        # acquire google analytics context
        self._google_analytics_context = GoogleAnalyticsContext(
            endpoint="https://www.google-analytics.com/collect",
            tracking_id="UA-184737687-1",
            application_name="RFI-File-Monitor",
            application_version=__version__,
            config_file=Path(GLib.get_user_config_dir(), 'rfi-file-monitor', 'ga.conf'),
        )

        # send event to Google Analytics
        self._google_analytics_context.send_event('LAUNCH', 'Monitor-{}-Python-{}-{}'.format(__version__, platform.python_version(), platform.platform()), None)

    def _update_supported_filetypes(self):
        # this will update filetypes_supported_operations_map 
        # with operations that were not decorated.
        # We will assume they support RegularFile only
        decorated_operations = list()
        for operations in self._filetypes_supported_operations_map.values():
            decorated_operations.extend(operations)
        decorated_operations = set(decorated_operations)
        
        undecorated_operations = set(self._known_operations.values()).difference(decorated_operations)

        if RegularFile in self._filetypes_supported_operations_map:
            self._filetypes_supported_operations_map[RegularFile].extend(undecorated_operations)
        else:
            self._filetypes_supported_operations_map[RegularFile] = list(undecorated_operations)

        for operations in self._filetypes_supported_operations_map.values():
            operations.sort(key=lambda operation: operation.NAME)


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
                if 'version' not in yaml_dict or yaml_dict['version'] != MONITOR_YAML_VERSION:
                    raise Exception(f"The YAML file {yaml_file} is not compatible with this version of the RFI-File-Monitor")
                if 'active_engine' not in yaml_dict or 'queue_manager' not in yaml_dict or 'operations' not in yaml_dict or 'engines' not in yaml_dict:
                    raise Exception(f'The YAML file {yaml_file} is incomplete and cannot be loaded')
            except Exception as e:
                dialog = Gtk.MessageDialog(transient_for=active_window,
                    modal=True, destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE, text=f"Could not load {yaml_file}",
                    secondary_text=str(e))
                dialog.run()
                dialog.destroy()
            else:
                window = ApplicationWindow(application=self, type=Gtk.WindowType.TOPLEVEL)
                window.show_all()
                window.load_from_yaml_dict(yaml_dict)
        else:
            dialog.destroy()

    def do_activate(self):
        window = ApplicationWindow(application=self, title="RFI-File-Monitor", type=Gtk.WindowType.TOPLEVEL)
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
            version=__version__,
            )
        about_dialog.present()

    def on_quit(self, action, param):
        windows = filter(lambda window: isinstance(window, ApplicationWindow), self.get_windows())

        for index, window in enumerate(windows):
            logger.debug(f'Closing Window {index}')
            if window.active_engine.props.running:
                window.close()
            else:
                self.remove_window(window)

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
