import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..engine_advanced_settings import EngineAdvancedSettings
from ..engine import Engine
from ..utils import PATTERN_PLACEHOLDER_TEXT

class AWSS3BucketEngineAdvancedSettings(EngineAdvancedSettings):

    def __init__(self, engine: Engine):
        super().__init__(engine)

        self._row_counter = 0

        # Specify allowed file patterns
        allowed_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )

        self.attach(allowed_patterns_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1
        allowed_patterns_grid.attach(Gtk.Label(
                label='Allowed filename patterns',
                halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
                hexpand=False, vexpand=False,
            ),
            0, 0, 1, 1,
        )
        self._allowed_patterns_entry = engine.register_widget(Gtk.Entry(placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
        ), 'allowed_patterns')
        allowed_patterns_grid.attach(self._allowed_patterns_entry, 1, 0, 1, 1)

        self._add_horizontal_separator()

        # Specify ignored file patterns
        ignore_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )

        self.attach(ignore_patterns_grid, 0, self._row_counter, 1, 2)
        self._row_counter += 1
        ignore_patterns_grid.attach(Gtk.Label(
            label='Ignored filename patterns',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,

        ),
            0, 0, 1, 1,
        )
        self._ignored_patterns_entry = engine.register_widget(Gtk.Entry(placeholder_text=PATTERN_PLACEHOLDER_TEXT,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'ignore_patterns')
        ignore_patterns_grid.attach(self._ignored_patterns_entry, 1, 0, 1, 1)

    def _add_horizontal_separator(self):
        self.attach(Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=True,
            ),
            0, self._row_counter, 1, 1
        )
        self._row_counter += 1