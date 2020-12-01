from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk
from tenacity.retry import retry_base
from requests.adapters import HTTPAdapter

from typing import Callable, Optional, Final, Any, Dict, List, Iterable
import logging
from pathlib import Path
import hashlib
import os
import platform
from threading import Thread
import time
import string
import random

from .exceptions import SkippedOperation

# bump this number when the yaml layout changes!
MONITOR_YAML_VERSION = 2

EXPAND_AND_FILL: Final[Dict[str, Any]] = dict(hexpand=True, vexpand=True, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL)

PREFERENCES_CONFIG_FILE = Path(GLib.get_user_config_dir(), 'rfi-file-monitor', 'prefs.yml')

PATTERN_PLACEHOLDER_TEXT = 'e.g *.txt, *.csv or *temp* or *log*'

DEFAULT_TIMEOUT = 5 # seconds

DEFAULT_IGNORE_PATTERNS = ('*.swp', '*.swx', )

logger = logging.getLogger(__name__)

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)

# had to write my own retry condition class to support:
# 1. retry if an exception was thrown that was not a SkippedOperation
# 2. retry if a value was returned that is not None
# see https://github.com/jd/tenacity/issues/255
class monitor_retry_condition(retry_base):
    def __init__(self):
        self._value_predicate = lambda value: value is not None
        self._exception_predicate = lambda e: not isinstance(e, SkippedOperation)

    def __call__(self, retry_state):
        if retry_state.outcome.failed:
            return self._exception_predicate(retry_state.outcome.exception())
        else:
            return self._value_predicate(retry_state.outcome.result())

def query_metadata(metadata: Dict[int, Dict[str, Any]], key: str, full_dict=False) -> Any:
    '''
    Reverse iterates through the metadata until the key is found.
    When successful, returns the matching dictionary value.
    If full_dict is True, then the whole dict that the key belongs to is returned.
    Upon failure, None is returned.
    '''
    if metadata is None:
        return None
    for metadata_dict in reversed(metadata.values()):
        if key in metadata_dict:
            if full_dict:
                return metadata_dict
            else:
                return metadata_dict[key]
    return None

def add_action_entries(
    map: Gio.ActionMap,
    action: str,
    callback: Callable[[Gio.ActionMap, Gio.SimpleAction, GLib.Variant], None],
    param: Optional[str] = None,
    state: Optional[GLib.Variant] = None,
    callback_arg: Optional[Any] = None) -> None:

    if state:
        action = Gio.SimpleAction.new_stateful(action, GLib.VariantType.new(param) if param else None, state)
    else:
        action = Gio.SimpleAction.new(action, GLib.VariantType.new(param) if param else None)
    
    if callback_arg:
        action.connect("activate", callback, callback_arg)
    else:
        action.connect("activate", callback)

    map.add_action(action)

def class_in_object_iterable(iterable: Iterable, klass) -> bool:
    for _iter in iterable:
        if isinstance(_iter, klass):
            return True
    return False

def get_patterns_from_string(input: str, defaults: Optional[List[str]]=None) -> List[str]:
    if defaults is None:
        if input or  input.strip():
            return list(map(lambda x: x.strip(), input.split(',')))
        else:
            return ['*']
    else:
        if input or input.strip():
             return list(map(lambda x: x.strip(), input.split(','))) + defaults
        else:
            return defaults

def get_md5(fname: os.PathLike) -> str:
    # taken from https://stackoverflow.com/a/3431838
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_file_creation_timestamp(file_path: os.PathLike):
    # get creation time, or something similar...
    # https://stackoverflow.com/a/39501288
    if platform.system() == 'Windows':
        try:
            creation_timestamp = os.stat(file_path).st_ctime
        except FileNotFoundError:
            time.sleep(1)
            try:
                creation_timestamp = os.stat(file_path).st_ctime
            except FileNotFoundError:
                creation_timestamp = None
    else:
        try:
            # this should work on macOS
            creation_timestamp = os.stat(file_path).st_birthtime
        except AttributeError:
            creation_timestamp = os.stat(file_path).st_mtime
    return creation_timestamp

def get_random_string(length: int):
    letters = string.ascii_letters
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


class LongTaskWindow(Gtk.Window):
    def __init__(self, parent_window: Optional[Gtk.Window] = None, *args, **kwargs):
        kwargs.update(dict(
            transient_for=parent_window,
		    window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
		    modal=True,
    		default_width=250,
		    default_height=100,
    		type=Gtk.WindowType.TOPLEVEL,
		    destroy_with_parent=True,
    		decorated=False,
		    border_width=5
        ))
        Gtk.Window.__init__(self, *args, **kwargs)
        main_grid = Gtk.Grid(column_spacing=10, row_spacing=10, **EXPAND_AND_FILL)
        self._label = Gtk.Label(wrap=True, **EXPAND_AND_FILL)
        main_grid.attach(self._label, 0, 0, 1, 1)
        label = Gtk.Label(label="This may take a while...", )
        main_grid.attach(label, 0, 1, 1, 1)
        self.add(main_grid)
        self.connect("delete-event", Gtk.true)
        main_grid.show_all()

    def set_text(self, text: str):
        self._label.set_markup(text)

class ExitableThread(Thread):
    
    def __init__(self):
        super().__init__()
        self._should_exit: Final[bool] = False

    @property
    def should_exit(self):
        return self._should_exit
    
    @should_exit.setter
    def should_exit(self, value: bool):
        self._should_exit = value