import gi
from gi.repository import Gio, GLib

from typing import Callable, Optional

def add_action_entries(
    map: Gio.ActionMap,
    action: str,
    callback: Callable[[Gio.ActionMap, Gio.SimpleAction, GLib.Variant], None],
    param: Optional[str] = None) -> None:

    action = Gio.SimpleAction.new(action, GLib.VariantType.new(param) if param else None)
    action.connect("activate", callback)
    map.add_action(action)