import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from pathlib import Path
from typing import Final, Any, List, final, Optional

from munch import Munch, munchify
import logging

logger = logging.getLogger(__name__)

class WidgetParams:
    """
    Inheriting from this class
    """
    #pylint: disable=unsubscriptable-object
    def __init__(self, params: Optional[Munch] = None):
        logger.debug('Calling WidgetParams __init__')
        if params:
            self._params = params
        else:
            self._params: Final[Munch[str, Any]] = Munch()
        
        self._signal_ids: Final[Munch[str, int]] = Munch()
        self._widgets: Final[Munch[str, Gtk.Widget]] = Munch()
        self._exportable_params: Final[List[str]] = list()
        self._desensitized_widgets: Final[List[Gtk.Widget]] = list()

    @final
    def set_sensitive(self, sensitive: bool):
        for widget in self.widgets.values():
            if widget not in self._desensitized_widgets:
                widget.set_sensitive(sensitive)

    @final
    def _entry_changed_cb(self, entry: Gtk.Entry, param_name: str):
        self._params[param_name] = entry.get_text().strip()

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
    def register_widget(self,
        widget: Gtk.Widget,
        param_name: str,
        exportable: bool = True,
        desensitized: bool = False):

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
            self._params[param_name] = widget.get_text().strip()
            self._signal_ids[param_name] = widget.connect("changed", self._entry_changed_cb, param_name)
        elif isinstance(widget, Gtk.ComboBoxText):
            self._params[param_name] = widget.get_active_text()
            self._signal_ids[param_name] =widget.connect('changed', self._combobox_changed_cb, param_name)
        else:
            raise NotImplementedError(f"register_widget: no support for {type(widget).__name__}")

        self._widgets[param_name] = widget

        if exportable:
            self._exportable_params.append(param_name)

        if desensitized:
            self._desensitized_widgets.append(widget)

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

