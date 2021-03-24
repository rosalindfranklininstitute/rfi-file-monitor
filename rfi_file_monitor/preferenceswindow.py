from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject
import yaml

from typing import Dict, Any, Final
import logging

from .preferences import (
    Preference,
    BooleanPreference,
    ListPreference,
    DictPreference,
    StringPreference,
    Preferences,
)
from rfi_file_monitor.utils import EXPAND_AND_FILL, PREFERENCES_CONFIG_FILE

logger = logging.getLogger(__name__)


class PreferenceValueCellRenderer(Gtk.CellRenderer):
    @GObject.Property(type=str)
    def key(self) -> str:
        return self._key

    @key.setter
    def key(self, value: str):
        self._key = value
        self._set_renderer(value)

    def __init__(
        self,
        window: PreferencesWindow,
        settings: Dict[Preference, Any],
        list_store: Gtk.ListStore,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._settings = settings
        self._list_store = list_store
        # self._key: str = ""
        self._window: PreferencesWindow = window
        self._renderer: Gtk.CellRenderer = None

        # our renderers
        self._toggle_renderer = Gtk.CellRendererToggle(
            activatable=True, radio=False
        )
        self._combo_renderer = Gtk.CellRendererCombo(has_entry=False)
        self._text_renderer = Gtk.CellRendererText(editable=True)

        # our combo models
        self._combo_models: Final[Dict[Preference, Gtk.ListStore]] = dict()

        # connect signal handlers
        self._toggle_renderer.connect("toggled", self._toggle_cb)
        self._combo_renderer.connect("changed", self._changed_cb)
        self._text_renderer.connect("edited", self._edited_cb)

    def _get_key_from_model(self, path: str) -> str:
        return self._list_store[path][0]

    def _edited_cb(self, combo: Gtk.CellRendererText, path: str, new_text: str):
        key: str = self._get_key_from_model(path)
        pref: Preference = self._get_pref_for_key(key)
        self._settings[pref] = new_text

        # update config file
        self._window._update_config_file()

    def _changed_cb(
        self, combo: Gtk.CellRendererCombo, path: str, new_iter: Gtk.TreeIter
    ):
        key: str = self._get_key_from_model(path)
        pref: Preference = self._get_pref_for_key(key)
        store = self._combo_models[pref]

        new_value = store[new_iter][0]
        self._settings[pref] = new_value

        # update config file
        self._window._update_config_file()

    def _toggle_cb(self, renderer: Gtk.CellRendererToggle, path: str):
        key: str = self._get_key_from_model(path)
        pref: Preference = self._get_pref_for_key(key)
        self._settings[pref] = not self._settings[pref]

        # update config file
        self._window._update_config_file()

    def _get_pref_for_key(self, key) -> Preference:
        # given a key, get the corresponding Preference class
        for _pref in self._settings:
            if _pref.key == key:
                return _pref
        raise Exception(f"pref not found for key {key}")

    def _set_renderer(self, key: str):
        pref: Preference = self._get_pref_for_key(key)

        if isinstance(pref, BooleanPreference):
            self._renderer = self._toggle_renderer
            # the mode has to be set for both self and child!!!
            self.props.mode = Gtk.CellRendererMode.ACTIVATABLE
            self._renderer.props.mode = Gtk.CellRendererMode.ACTIVATABLE
            self._renderer.props.active = self._settings[pref]
            self._renderer.props.activatable = True
        elif isinstance(pref, ListPreference) or isinstance(
            pref, DictPreference
        ):
            self._renderer = self._combo_renderer
            self.props.mode = Gtk.CellRendererMode.EDITABLE
            current_value = self._settings[pref]

            if pref not in self._combo_models:
                # create new model
                store = Gtk.ListStore(str)
                for _val in pref.values:
                    store.append([_val])
                self._combo_models[pref] = store
            else:
                store = self._combo_models[pref]

            self._renderer.props.model = store
            self._renderer.props.text = current_value
            self._renderer.props.text_column = 0
            self._renderer.props.editable = True
            self._renderer.props.mode = Gtk.CellRendererMode.EDITABLE
        elif isinstance(pref, StringPreference):
            self._renderer = self._text_renderer
            self.props.mode = Gtk.CellRendererMode.EDITABLE
            current_value = self._settings[pref]
            self._renderer.props.mode = Gtk.CellRendererMode.EDITABLE
            self._renderer.props.editable = True
            self._renderer.props.text = current_value
        else:
            raise NotImplementedError

    # these methods define how the renderer should do its drawing.
    # we just need to redirect it to the appropriate child renderer.
    def do_activate(
        self, event, widget, path, background_area, cell_area, flags
    ):
        return type(self._renderer).do_activate(
            self._renderer,
            event,
            widget,
            path,
            background_area,
            cell_area,
            flags,
        )

    def do_get_aligned_area(self, widget, flags, cell_area):
        return type(self._renderer).do_get_aligned_area(
            self._renderer, widget, flags, cell_area
        )

    def do_get_preferred_height(self, widget):
        return type(self._renderer).do_get_preferred_height(
            self._renderer, widget
        )

    def do_get_preferred_height_for_width(self, widget, width):
        return type(self._renderer).do_get_preferred_height_for_width(
            self._renderer, widget, width
        )

    def do_get_preferred_width(self, widget):
        return type(self._renderer).do_get_preferred_width(
            self._renderer, widget
        )

    def do_get_preferred_width_for_height(self, widget, height):
        return type(self._renderer).do_get_preferred_width_for_height(
            self._renderer, widget, height
        )

    def do_get_request_mode(self):
        return type(self._renderer).do_get_request_mode(self._renderer)

    def do_get_size(self, widget, cell_area):
        return type(self._renderer).do_get_size(
            self._renderer, widget, cell_area
        )

    def do_render(self, cr, widget, background_area, cell_area, flags):
        type(self._renderer).do_render(
            self._renderer, cr, widget, background_area, cell_area, flags
        )

    def do_start_editing(
        self, event, widget, path, background_area, cell_area, flags
    ):
        return type(self._renderer).do_start_editing(
            self._renderer,
            event,
            widget,
            path,
            background_area,
            cell_area,
            flags,
        )


class PreferencesWindow(Gtk.Window):
    def __init__(self, prefs: Preferences, *args, **kwargs):
        logger.debug("Creating new PreferencesWindow")
        super().__init__(*args, **kwargs)

        self.set_default_size(500, 500)
        self._prefs: Preferences = prefs

        grid = Gtk.Grid(**EXPAND_AND_FILL)
        self.add(grid)

        nb = Gtk.Notebook(**EXPAND_AND_FILL)
        grid.attach(nb, 0, 0, 1, 1)

        # Settings
        config_page = Gtk.Grid(
            **EXPAND_AND_FILL, border_width=5, row_spacing=5, column_spacing=5
        )
        nb.append_page(config_page, Gtk.Label("Settings"))

        frame_child = Gtk.Label(
            label="<b>Settings specific to this machine, usable by operations and engines</b>",
            use_markup=True,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        frame = Gtk.Frame(
            height_request=50,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.START,
            hexpand=True,
            vexpand=False,
        )
        frame.add(frame_child)
        config_page.attach(frame, 0, 0, 1, 1)

        store = Gtk.ListStore(str, str)
        for _pref in self._prefs.settings:
            store.append([_pref.key, _pref.description])

        sw = Gtk.ScrolledWindow(
            **EXPAND_AND_FILL, shadow_type=Gtk.ShadowType.IN
        )
        tv = Gtk.TreeView(model=store, tooltip_column=1, **EXPAND_AND_FILL)
        sw.add(tv)
        config_page.attach(sw, 0, 1, 1, 1)

        key_renderer = Gtk.CellRendererText()
        value_renderer = PreferenceValueCellRenderer(
            window=self, settings=self._prefs.settings, list_store=store
        )

        key_column = Gtk.TreeViewColumn("Key", key_renderer, text=0)
        value_column = Gtk.TreeViewColumn("Value", value_renderer, key=0)

        tv.append_column(key_column)
        tv.append_column(value_column)

        # Operations
        operations_page = Gtk.Grid(
            **EXPAND_AND_FILL, border_width=5, row_spacing=5, column_spacing=5
        )
        nb.append_page(operations_page, Gtk.Label("Operations"))

        frame_child = Gtk.Label(
            label="<b>Use this table to select which operations will be available.</b>",
            use_markup=True,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        frame = Gtk.Frame(
            height_request=50,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.START,
            hexpand=True,
            vexpand=False,
        )
        frame.add(frame_child)
        operations_page.attach(frame, 0, 0, 1, 1)

        self._operations_store = Gtk.ListStore(str, bool, object)
        for _op, _value in self._prefs.operations.items():
            self._operations_store.append([_op.NAME, _value, _op])

        sw = Gtk.ScrolledWindow(
            **EXPAND_AND_FILL, shadow_type=Gtk.ShadowType.IN
        )
        tv = Gtk.TreeView(model=self._operations_store, **EXPAND_AND_FILL)
        sw.add(tv)
        operations_page.attach(sw, 0, 1, 1, 1)

        key_renderer = Gtk.CellRendererText()
        value_renderer = Gtk.CellRendererToggle()
        value_renderer.connect("toggled", self._operation_toggled)

        key_column = Gtk.TreeViewColumn("Operation Name", key_renderer, text=0)
        value_column = Gtk.TreeViewColumn("Enabled", value_renderer, active=1)

        tv.append_column(key_column)
        tv.append_column(value_column)

        # Engines
        engines_page = Gtk.Grid(
            **EXPAND_AND_FILL, border_width=5, row_spacing=5, column_spacing=5
        )
        nb.append_page(engines_page, Gtk.Label("Engines"))

        frame_child = Gtk.Label(
            label="<b>Use this table to select which engines will be available.</b>",
            use_markup=True,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        frame = Gtk.Frame(
            height_request=50,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.START,
            hexpand=True,
            vexpand=False,
        )
        frame.add(frame_child)
        engines_page.attach(frame, 0, 0, 1, 1)

        self._engines_store = Gtk.ListStore(str, bool, object)
        for _engine, _value in self._prefs.engines.items():
            self._engines_store.append([_engine.NAME, _value, _engine])

        sw = Gtk.ScrolledWindow(
            **EXPAND_AND_FILL, shadow_type=Gtk.ShadowType.IN
        )
        tv = Gtk.TreeView(model=self._engines_store, **EXPAND_AND_FILL)
        sw.add(tv)
        engines_page.attach(sw, 0, 1, 1, 1)

        key_renderer = Gtk.CellRendererText()
        value_renderer = Gtk.CellRendererToggle()
        value_renderer.connect("toggled", self._engine_toggled)

        key_column = Gtk.TreeViewColumn("Engine Name", key_renderer, text=0)
        value_column = Gtk.TreeViewColumn("Enabled", value_renderer, active=1)

        tv.append_column(key_column)
        tv.append_column(value_column)

        grid.show_all()

    def _operation_toggled(self, renderer: Gtk.CellRendererToggle, path: str):
        count_toggled = 0
        for _toggled in self._operations_store:
            if _toggled[1] is True:
                count_toggled += 1
        if count_toggled == 1 and self._operations_store[path][1] is True:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"At least 1 operation must be selected!",
            )
            dialog.run()
            dialog.destroy()
            return
        self._operations_store[path][1] = not self._operations_store[path][1]
        self._prefs.operations[
            self._operations_store[path][2]
        ] = self._operations_store[path][1]

        self._update_config_file()

    def _engine_toggled(self, renderer: Gtk.CellRendererToggle, path: str):
        count_toggled = 0
        for _toggled in self._engines_store:
            if _toggled[1] is True:
                count_toggled += 1
        if count_toggled == 1 and self._engines_store[path][1] is True:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"At least 1 engine must be selected!",
            )
            dialog.run()
            dialog.destroy()
            return
        self._engines_store[path][1] = not self._engines_store[path][1]
        self._prefs.engines[self._engines_store[path][2]] = self._engines_store[
            path
        ][1]

        self._update_config_file()

    def _update_config_file(self):
        # write prefs into dictionary format
        yaml_dict = dict(settings={}, operations={}, engines={})

        for _pref, _value in self._prefs.settings.items():
            yaml_dict["settings"][_pref.key] = _value

        for _op, _value in self._prefs.operations.items():
            yaml_dict["operations"][_op.NAME] = _value

        for _engine, _value in self._prefs.engines.items():
            yaml_dict["engines"][_engine.NAME] = _value

        try:
            # ensure parent directories of preferences file have been created
            PREFERENCES_CONFIG_FILE.parent.mkdir(
                mode=0o700, parents=True, exist_ok=True
            )

            # open for writing
            with PREFERENCES_CONFIG_FILE.open("w") as f:
                logger.debug(
                    f"Writing preferences to {str(PREFERENCES_CONFIG_FILE)}"
                )
                yaml.safe_dump(data=yaml_dict, stream=f)
        except Exception:
            logger.exception(
                f"Could not write to {str(PREFERENCES_CONFIG_FILE)}"
            )
