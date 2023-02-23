from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gio, Gtk, GdkPixbuf
import yaml
from munch import Munch

import importlib.resources
import platform
import webbrowser
import logging
from typing import Dict, Type, Union, List, Optional
import importlib.metadata
from pathlib import Path

from .version import __version__
# from .utils import (
#     add_action_entries,
#     PREFERENCES_CONFIG_FILE,
#     MONITOR_YAML_VERSION,
# )
from .preferences import (
     Preferences,
#     AllowedFilePatternsPreference,
#     IgnoredFilePatternsPreference,
)
# from .preferenceswindow import PreferencesWindow
# from .files.regular_file import RegularFile
# from .file import File
# from .utils.helpwindow import HelpWindow
# from .utils.googleanalytics import GoogleAnalyticsContext
from .applicationwindow import ApplicationWindow
# from .engine import Engine
# from .engine_advanced_settings import EngineAdvancedSettings
# from .operation import Operation
# from .queue_manager import QueueManager


logger = logging.getLogger(__name__)


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="uk.ac.rfi.ai.file-monitor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            **kwargs,
        )
        GLib.set_application_name("RFI File Monitor")

    @property
    def known_operations(self):
        return self._known_operations

    # @property
    # def known_engines(self):
    #     return self._known_engines
    #
    # @property
    # def help_window(self):
    #     return self._help_window
    #
    # @property
    # def engines_advanced_settings_map(self):
    #     return self._engines_advanced_settings_map
    #
    # @property
    # def engines_exported_filetype_map(self):
    #     return self._engines_exported_filetype_map
    #
    # @property
    # def filetypes_supported_operations_map(
    #     self,
    # ) -> Dict[Type[File], List[Type[Operation]]]:
    #     return self._filetypes_supported_operations_map
    #
    # @property
    # def pango_docs_map(self):
    #     return self._pango_docs_map
    #
    # @property
    # def google_analytics_context(self):
    #     return self._google_analytics_context
    #
    # def do_shutdown(self):
    #     Gtk.Application.do_shutdown(self)
    #
    #     self._google_analytics_context.consumer_thread.should_exit = True
    #
    def do_startup(self):
        Gtk.Application.do_startup(self)
    #
        # this may need to be checked on other platforms as well
        if platform.system() == "Darwin":
            appmenus_str = importlib.resources.read_text(
                "rfi_file_monitor.data", "menus-appmenu.ui"
            )
            builder = Gtk.Builder.new_from_string(appmenus_str, -1)
            self.set_app_menu(builder.get_object("app-menu"))

        commonmenus_str = importlib.resources.read_text(
            "rfi_file_monitor.data", "menus-common.ui"
        )
        builder = Gtk.Builder.new_from_string(commonmenus_str, -1)
        self.set_menubar(builder.get_object("menubar"))
    #
        # get file filter menu
        popover_filter_menu_str = importlib.resources.read_text(
            "rfi_file_monitor.data", "filter-popover.ui"
        )
        builder = Gtk.Builder.new_from_string(popover_filter_menu_str, -1)
        self.filter_popover_menu = builder.get_object("filter-popover-menu")
    #
    #     action_entries = (
    #         ("about", self.on_about),
    #         ("quit", self.on_quit),
    #         ("open", self.on_open),
    #         ("new", lambda *_: self.do_activate()),
    #         ("help-url", self.on_help_url, "s"),
    #         ("preferences", self.on_preferences),
    #     )
    #
    #     # This doesn't work, which is kind of uncool
    #     # self.add_action_entries(action_entries)
    #     for action_entry in action_entries:
    #         add_action_entries(self, *action_entry)
    #
    #     # add accelerators
    #     accelerators = (
    #         ("app.quit", ("<Primary>Q",)),
    #         ("app.new", ("<Primary>N",)),
    #         ("app.open", ("<Primary>O",)),
    #         ("win.save", ("<Primary>S",)),
    #         ("win.save-as", ("<Primary><Shift>S",)),
    #         ("win.close", ("<Primary>W",)),
    #     )
    #
    #     for accel in accelerators:
    #         self.set_accels_for_action(accel[0], accel[1])
    #
    #     self._engines_advanced_settings_map: Dict[
    #         Type[Engine], Type[EngineAdvancedSettings]
    #     ] = dict()
    #
    #     self._engines_exported_filetype_map: Dict[
    #         Type[Engine], Type[File]
    #     ] = dict()
    #
    #     self._filetypes_supported_operations_map: Dict[
    #         Type[File], List[Type[Operation]]
    #     ] = dict()
    #
    #     self._pango_docs_map: Dict[
    #         Type[Union[Engine, QueueManager, Operation]], str
    #     ] = dict()
    #
    #     # add queue manager docs manually
    #     try:
    #         contents = (
    #             Path(__file__)
    #             .parent.joinpath("docs", "queue_manager.pango")
    #             .read_text()
    #         )
    #     except Exception:
    #         logger.exception(
    #             f"with_pango_docs: could not open queue_manager.pango for reading"
    #         )
    #     else:
    #         self._pango_docs_map[QueueManager] = contents
    #
    # #     # get info from entry points
    #     self._known_operations = {
    #         e.name: e.load()
    #         for e in importlib.metadata.entry_points()[
    #             "rfi_file_monitor.operations"
    #         ]
    #     }
    #
    #     self._update_supported_filetypes()
    #
    #     self._known_engines = {
    #         e.name: e.load()
    #         for e in importlib.metadata.entry_points()[
    #             "rfi_file_monitor.engines"
    #         ]
    #     }
    #
    #     # add our help window, which will be shared by all appwindows
    #     self._help_window = HelpWindow(self._pango_docs_map)
    #
    #     # populate dict with preferences found in entry points
    #     self._prefs = Preferences(Munch(), Munch(), Munch())
    #     if "rfi_file_monitor.preferences" in importlib.metadata.entry_points():
    #         for e in importlib.metadata.entry_points()[
    #             "rfi_file_monitor.preferences"
    #         ]:
    #             _pref = e.load()
    #             self._prefs.settings[_pref] = _pref.default
    #
    #     for _op in self._known_operations.values():
    #         self._prefs.operations[_op] = not bool(getattr(_op, "DEBUG", False))
    #
    #     for _engine in self._known_engines.values():
    #         self._prefs.engines[_engine] = not bool(
    #             getattr(_engine, "DEBUG", False)
    #         )
    #
    #     # now, open preferences file and update the prefs dictionary
    #     try:
    #         with PREFERENCES_CONFIG_FILE.open("r") as f:
    #             stored_prefs = yaml.safe_load(f)
    #     except FileNotFoundError:
    #         pass
    #     else:
    #         if stored_prefs and isinstance(stored_prefs, dict):
    #             # to maintain compatibility with older versions, first look for settings dict
    #             if (
    #                 "settings" in stored_prefs
    #                 and stored_prefs["settings"] is not None
    #                 and isinstance(stored_prefs["settings"], dict)
    #             ):
    #                 for _key, _value in stored_prefs["settings"].items():
    #                     for _pref in self._prefs.settings:
    #                         if _pref.key == _key:
    #                             self._prefs.settings[_pref] = _value
    #                             break
    #                     else:
    #                         logger.warning(
    #                             f"Could not find a corresponding Preference class for key {_key} from preferences file"
    #                         )
    #             else:
    #                 for _key, _value in stored_prefs.items():
    #                     for _pref in self._prefs.settings:
    #                         if _pref.key == _key:
    #                             self._prefs.settings[_pref] = _value
    #                             break
    #                     else:
    #                         logger.warning(
    #                             f"Could not find a corresponding Preference class for key {_key} from preferences file"
    #                         )
    #
    #             if (
    #                 "operations" in stored_prefs
    #                 and stored_prefs["operations"] is not None
    #                 and isinstance(stored_prefs["operations"], dict)
    #             ):
    #                 for _key, _value in stored_prefs["operations"].items():
    #                     for _pref in self._prefs.operations:
    #                         if _pref.NAME == _key:
    #                             self._prefs.operations[_pref] = _value
    #                             break
    #                     else:
    #                         logger.warning(
    #                             f"Could not find a corresponding Operation class for key {_key} from preferences file"
    #                         )
    #
    #             if (
    #                 "engines" in stored_prefs
    #                 and stored_prefs["engines"] is not None
    #                 and isinstance(stored_prefs["engines"], dict)
    #             ):
    #                 for _key, _value in stored_prefs["engines"].items():
    #                     for _pref in self._prefs.engines:
    #                         if _pref.NAME == _key:
    #                             self._prefs.engines[_pref] = _value
    #                             break
    #                     else:
    #                         logger.warning(
    #                             f"Could not find a corresponding Engine class for key {_key} from preferences file"
    #                         )
    #
    #     # acquire google analytics context
    #     self._google_analytics_context = GoogleAnalyticsContext(
    #         endpoint="https://www.google-analytics.com/collect",
    #         tracking_id="UA-184737687-1",
    #         application_name="RFI-File-Monitor",
    #         application_version=__version__,
    #         config_file=Path(
    #             GLib.get_user_config_dir(), "rfi-file-monitor", "ga.conf"
    #         ),
    #     )
    #
    #     # send event to Google Analytics
    #     self._google_analytics_context.send_event(
    #         "LAUNCH",
    #         "Monitor-{}-Python-{}-{}".format(
    #             __version__, platform.python_version(), platform.platform()
    #         ),
    #         None,
    #     )
    #
    # def _update_supported_filetypes(self):
    #     # this will update filetypes_supported_operations_map
    #     # with operations that were not decorated.
    #     # We will assume they support RegularFile only
    #     decorated_operations = list()
    #     for operations in self._filetypes_supported_operations_map.values():
    #         decorated_operations.extend(operations)
    #     decorated_operations = set(decorated_operations)
    #
    #     undecorated_operations = set(
    #         self._known_operations.values()
    #     ).difference(decorated_operations)
    #
    #     if RegularFile in self._filetypes_supported_operations_map:
    #         self._filetypes_supported_operations_map[RegularFile].extend(
    #             undecorated_operations
    #         )
    #     else:
    #         self._filetypes_supported_operations_map[RegularFile] = list(
    #             undecorated_operations
    #         )
    #
    #     for operations in self._filetypes_supported_operations_map.values():
    #         operations.sort(key=lambda operation: operation.NAME)
    #
    def get_preferences(self) -> Preferences:
        return self._prefs
    #
    # @classmethod
    # def _split_patterns(cls, patterns: Optional[str]) -> List[str]:
    #     if patterns and patterns.split():
    #         return list(map(lambda x: x.strip(), patterns.split(",")))
    #     return []
    #
    # def get_allowed_file_patterns(
    #     self, extra_patterns: Optional[str] = None
    # ) -> List[str]:
    #     global_allowed_patterns: str = self._prefs.settings[
    #         AllowedFilePatternsPreference
    #     ]
    #     patterns = self._split_patterns(global_allowed_patterns)
    #     patterns.extend(self._split_patterns(extra_patterns))
    #
    #     # if no patterns were found, match everything!
    #     if not patterns:
    #         return ["*"]
    #     return patterns
    #
    # def get_ignored_file_patterns(
    #     self, extra_patterns: Optional[str] = None
    # ) -> List[str]:
    #     global_ignored_patterns: str = self._prefs.settings[
    #         IgnoredFilePatternsPreference
    #     ]
    #     patterns = self._split_patterns(global_ignored_patterns)
    #     patterns.extend(self._split_patterns(extra_patterns))
    #     return patterns
    #
    # def on_open(self, action, param):
    #     # fire up file chooser dialog
    #     active_window = self.get_active_window()
    #     dialog = Gtk.FileChooserNative(
    #         modal=True,
    #         title="Open monitor configuration YAML file",
    #         transient_for=active_window,
    #         action=Gtk.FileChooserAction.OPEN,
    #     )
    #     filter = Gtk.FileFilter()
    #     filter.add_pattern("*.yml")
    #     filter.add_pattern("*.yaml")
    #     filter.set_name("YAML file")
    #     dialog.add_filter(filter)
    #
    #     if dialog.run() == Gtk.ResponseType.ACCEPT:
    #         yaml_file = dialog.get_filename()
    #         dialog.destroy()
    #         try:
    #             with open(yaml_file, "r") as f:
    #                 yaml_dict = yaml.safe_load(f)
    #             if (
    #                 "version" not in yaml_dict
    #                 or yaml_dict["version"] != MONITOR_YAML_VERSION
    #             ):
    #                 raise Exception(
    #                     f"The YAML file {yaml_file} is not compatible with this version of the RFI-File-Monitor"
    #                 )
    #             if (
    #                 "active_engine" not in yaml_dict
    #                 or "queue_manager" not in yaml_dict
    #                 or "operations" not in yaml_dict
    #                 or "engines" not in yaml_dict
    #             ):
    #                 raise Exception(
    #                     f"The YAML file {yaml_file} is incomplete and cannot be loaded"
    #                 )
    #         except Exception as e:
    #             dialog = Gtk.MessageDialog(
    #                 transient_for=active_window,
    #                 modal=True,
    #                 destroy_with_parent=True,
    #                 message_type=Gtk.MessageType.ERROR,
    #                 buttons=Gtk.ButtonsType.CLOSE,
    #                 text=f"Could not load {yaml_file}",
    #                 secondary_text=str(e),
    #             )
    #             dialog.run()
    #             dialog.destroy()
    #         else:
    #             window = ApplicationWindow(
    #                 application=self,
    #                 type=Gtk.WindowType.TOPLEVEL,
    #                 force_all=True,
    #             )
    #             window.show_all()
    #             window.load_from_yaml_dict(yaml_dict)
    #     else:
    #         dialog.destroy()
    #
    def do_activate(self):
        window = ApplicationWindow(
            application=self,
            title="RFI-File-Monitor",
            #type=Gtk.Window.TOPLEVEL,
        )
        window.present()
    #
    # def on_about(self, action, param):
    #
    #     with importlib.resources.path(
    #         "rfi_file_monitor.data", "RFI-logo-transparent.png"
    #     ) as f:
    #         logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(
    #             str(f), 300, -1, True
    #         )
    #
    #     about_dialog = Gtk.AboutDialog(
    #         transient_for=self.get_active_window(),
    #         modal=True,
    #         authors=["Tom Schoonjans"],
    #         logo=logo,
    #         version=__version__,
    #     )
    #     about_dialog.present()
    #
    # def on_quit(self, action, param):
    #     windows = filter(
    #         lambda window: isinstance(window, ApplicationWindow),
    #         self.get_windows(),
    #     )
    #
    #     for index, window in enumerate(windows):
    #         if window.active_engine.props.running:
    #             window.close()
    #         else:
    #             self.remove_window(window)
    #
    # def on_help_url(self, action, param):
    #     webbrowser.open_new_tab(param.get_string())
    #
    # def on_preferences(self, action, param):
    #     window = PreferencesWindow(
    #         self._prefs,
    #         modal=False,
    #         transient_for=self.get_active_window(),
    #         window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
    #         type=Gtk.WindowType.TOPLEVEL,
    #         destroy_with_parent=True,
    #         border_width=5,
    #     )
    #     window.present()
