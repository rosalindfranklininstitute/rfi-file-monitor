import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk
from munch import Munch, munchify

from typing import Callable, Optional, Final, Any, Dict, final, List
import logging
from pathlib import Path

EXPAND_AND_FILL: Final[Dict[str, Any]] = dict(hexpand=True, vexpand=True, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL)

PREFERENCES_CONFIG_FILE = Path(GLib.get_user_config_dir(), 'rfi-file-monitor', 'prefs.yml')

logger = logging.getLogger(__name__)

def add_action_entries(
    map: Gio.ActionMap,
    action: str,
    callback: Callable[[Gio.ActionMap, Gio.SimpleAction, GLib.Variant], None],
    param: Optional[str] = None) -> None:

    action = Gio.SimpleAction.new(action, GLib.VariantType.new(param) if param else None)
    action.connect("activate", callback)
    map.add_action(action)

class WidgetParams:
    """
    Inheriting from this class
    """
    #pylint: disable=unsubscriptable-object
    def __init__(self, *args, **kwargs):
        logger.debug('Calling WidgetParams __init__')
        super().__init__()
        self._params: Final[Munch[str, Any]] = Munch()
        self._signal_ids: Final[Munch[str, int]] = Munch()
        self._widgets: Final[Munch[str, Gtk.Widget]] = Munch()
        self._exportable_params: Final[List[str]] = list()

    @final
    def _entry_changed_cb(self, entry: Gtk.Entry, param_name: str):
        #pylint: disable=used-before-assignment
        self._params[param_name] = tmp if (tmp := entry.get_text().strip()) != "" else entry.get_placeholder_text()

    @final
    def _checkbutton_toggled_cb(self, checkbutton: Gtk.CheckButton, param_name: str):
        self._params[param_name] = checkbutton.get_active()

    @final
    def _filechooserbutton_selection_changed_cb(self, filechooserbutton: Gtk.FileChooserButton, param_name: str):
        self._params[param_name] = filechooserbutton.get_filename()

    @final
    def _spinbutton_value_changed_cb(self, spinbutton: Gtk.SpinButton, param_name: str):
        self._params[param_name] = spinbutton.get_value()

    @final
    def _combobox_changed_cb(self,combobox: Gtk.ComboBoxText, param_name: str):
        self._params[param_name] = combobox.get_active_text()

    @final
    def register_widget(self, widget: Gtk.Widget, param_name: str, exportable: bool = True):

        if param_name in self._params:
            raise ValueError("register_widget cannot overwrite existing parameters!")

        if isinstance(widget, Gtk.SpinButton):
            self._params[param_name] = widget.get_value()
            self._signal_ids[param_name] = widget.connect("value-changed", self._spinbutton_value_changed_cb, param_name)
        elif isinstance(widget, Gtk.CheckButton):
            self._params[param_name] = widget.get_active()
            self._signal_ids[param_name] = widget.connect("toggled", self._checkbutton_toggled_cb, param_name)
        elif isinstance(widget, Gtk.FileChooserButton):
            self._params[param_name] = widget.get_filename()
            self._signal_ids[param_name] = widget.connect("selection-changed", self._filechooserbutton_selection_changed_cb, param_name)
        elif isinstance(widget, Gtk.Entry):
            #pylint: disable=used-before-assignment
            self._params[param_name] = tmp if (tmp := widget.get_text().strip()) != "" else widget.get_placeholder_text()
            self._signal_ids[param_name] = widget.connect("changed", self._entry_changed_cb, param_name)
        elif isinstance(widget, Gtk.ComboBoxText):
            self._params[param_name] = widget.get_active_text()
            self._signal_ids[param_name] =widget.connect('changed', self._combobox_changed_cb, param_name)
        else:
            raise NotImplementedError(f"register_widget: no support for {type(widget).__name__}")

        self._widgets[param_name] = widget
        if exportable:
            self._exportable_params.append(param_name)

        logger.debug(f'Registered {param_name} with value {self._params[param_name]} of type {type(self._params[param_name])}')

        return widget

    def update_from_dict(self, yaml_dict: dict):
        for param_name, value in yaml_dict.items():
            if param_name not in self._params:
                logger.warning(f'update_from_dict: {param_name} not found in widget params!')
                continue
        
            widget = self._widgets[param_name]

            with widget.handler_block(self._signal_ids[param_name]):
                self._params[param_name] = value
        
                if isinstance(widget, Gtk.SpinButton):
                    widget.set_value(value)
                elif isinstance(widget, Gtk.CheckButton):
                    widget.set_active(value)
                elif isinstance(widget, Gtk.FileChooserButton):
                    if value is None or not Path(value).exists:
                        continue
                    widget.set_filename(value)
                elif isinstance(widget, Gtk.Entry):
                    if widget.get_placeholder_text() == value:
                        widget.set_text("")
                    else:
                        widget.set_text(value)
                elif isinstance(widget, Gtk.ComboBoxText):
                    for row in widget.get_model():
                        if row[0] == value:
                            widget.set_active_iter(row.iter)
                            break
                else:
                    raise NotImplementedError(f"update_from_dict: no support for {type(widget).__name__}")

    @property
    def params(self) -> Munch:
        """
        A Munch dict containing the parameters that will be used by run
        """
        return self._params

    @property
    def exportable_params(self) -> Munch:
        """
        A Munch dict containing those parameters that have been considered safe for exporting.
        This will typically exclude widgets meant to hold passwords and other secrets.
        """
        return munchify({param: self._params[param] for param in self._exportable_params})


    @property
    def widgets(self) -> Munch:
        """
        A Munch dict containing the registered widgets
        """
        return self._widgets

class LongTaskWindow(Gtk.Window):
    def __init__(self, parent_window: Optional[Gtk.Window] = None, *args, **kwargs):
        kwargs.update(dict(
            transient_for=parent_window,
		    window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
		    modal=True,
    		default_width=200,
		    default_height=50,
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
