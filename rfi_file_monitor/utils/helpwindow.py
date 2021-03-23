import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

import logging
from typing import Dict, Final, Type, Union

from . import EXPAND_AND_FILL
from ..engine import Engine
from ..operation import Operation
from ..queue_manager import QueueManager

logger = logging.getLogger(__name__)


class HelpWindow(Gtk.Window):
    def __init__(
        self,
        contents_raw: Final[
            Dict[Type[Union[Engine, QueueManager, Operation]], str]
        ],
    ):
        super().__init__(
            destroy_with_parent=True,
            window_position=Gtk.WindowPosition.NONE,
            border_width=5,
            title="Help",
        )
        self.set_default_size(600, 600)

        grid = Gtk.Grid(**EXPAND_AND_FILL, row_spacing=5, column_spacing=5)
        self.add(grid)

        self._search_entry = Gtk.SearchEntry(
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        self._search_entry.connect("changed", self._search_entry_changed_cb)
        grid.attach(self._search_entry, 0, 0, 1, 1)

        list_sw = Gtk.ScrolledWindow(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=False,
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            shadow_type=Gtk.ShadowType.IN,
        )
        grid.attach(list_sw, 0, 1, 1, 1)

        self._list_box = Gtk.ListBox(
            **EXPAND_AND_FILL,
            activate_on_single_click=False,
        )

        list_sw.add(self._list_box)

        # prepare contents
        contents = list()

        # engines
        engines = list(
            sorted(
                filter(
                    lambda widgetclass: issubclass(widgetclass, Engine),
                    contents_raw,
                ),
                key=lambda engine: engine.NAME,
            )
        )
        for engine in engines:
            engine.section = "Engines"
        contents.extend(engines)

        # operations
        operations = list(
            sorted(
                filter(
                    lambda widgetclass: issubclass(widgetclass, Operation),
                    contents_raw,
                ),
                key=lambda operation: operation.NAME,
            )
        )
        for operation in operations:
            operation.section = "Operations"
        contents.extend(operations)

        # others
        others = list(
            sorted(
                filter(
                    lambda widgetclass: not issubclass(widgetclass, Engine)
                    and not issubclass(widgetclass, Operation),
                    contents_raw,
                ),
                key=lambda other: other.NAME,
            )
        )
        for other in others:
            other.section = "Miscellaneous"
        contents.extend(others)

        self._rows = dict()

        self._list_box.set_header_func(self._list_box_header_func)
        self._list_box.set_filter_func(self._list_box_filter_func)

        for widgetclass in contents:
            label = Gtk.Label(
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
                margin=6,
                label=f"{widgetclass.NAME}",
            )
            self._list_box.insert(label, -1)

            row = label.get_parent()
            row.set_activatable(False)

            self._rows[widgetclass] = row

            row.section = widgetclass.section
            row.label = contents_raw[widgetclass]

        self._list_box.connect("row-selected", self._row_selected_cb)

        label_sw = Gtk.ScrolledWindow(
            **EXPAND_AND_FILL,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            shadow_type=Gtk.ShadowType.IN,
        )
        self._contents_label = Gtk.Label(
            **EXPAND_AND_FILL,
            wrap=True,
            use_markup=True,
            selectable=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
            yalign=0,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5,
        )
        label_sw.add(self._contents_label)
        grid.attach(label_sw, 1, 0, 1, 2)

        self._list_box.invalidate_headers()

        grid.show_all()

    def _search_entry_changed_cb(self, entry):
        self._list_box.invalidate_filter()

    def _list_box_filter_func(self, row):
        search_string = self._search_entry.get_text().strip()

        if not search_string:
            return True

        return search_string.lower() in row.get_child().props.label.lower()

    def _list_box_header_func(self, row, before):
        header = row.get_header()

        if not header and (before is None or before.section != row.section):
            title = f"<b>{row.section}</b>"

            header = Gtk.Label(
                label=title,
                use_markup=True,
                halign=Gtk.Align.START,
                margin_top=12,
                margin_start=6,
                margin_end=6,
                margin_bottom=6,
            )
            header.show()

            row.set_header(header)

    def _row_selected_cb(self, list_box, row):
        self._contents_label.props.label = row.label

    def select_item(self, klass: Type[Union[Engine, QueueManager, Operation]]):
        self._list_box.select_row(self._rows[klass])

    def do_delete_event(self, event):
        return self.hide_on_delete()
