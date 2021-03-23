import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..engine_advanced_settings import EngineAdvancedSettings
from ..engine import Engine
from ..utils import PATTERN_PLACEHOLDER_TEXT


class DirectoryWatchdogEngineAdvancedSettings(EngineAdvancedSettings):
    def __init__(self, engine: Engine):
        super().__init__(engine)

        self._row_counter = 0

        # Process existing directories in monitored directory
        self._process_existing_directories_checkbutton = engine.register_widget(
            Gtk.CheckButton(
                label="Process existing directories in target directory",
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
                active=False,
            ),
            "process_existing_directories",
        )
        self.attach(
            self._process_existing_directories_checkbutton,
            0,
            self._row_counter,
            1,
            1,
        )
        self._row_counter += 1

        self._add_horizontal_separator()

        # Specify allowed file patterns
        allowed_file_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(allowed_file_patterns_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1
        allowed_file_patterns_grid.attach(
            Gtk.Label(
                label="Allowed filename patterns",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        self._allowed_file_patterns_entry = engine.register_widget(
            Gtk.Entry(
                placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "allowed_file_patterns",
        )
        allowed_file_patterns_grid.attach(
            self._allowed_file_patterns_entry, 1, 0, 1, 1
        )

        self._add_horizontal_separator()

        # Specify ignored file patterns
        ignore_file_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(ignore_file_patterns_grid, 0, self._row_counter, 1, 2)
        self._row_counter += 1
        ignore_file_patterns_grid.attach(
            Gtk.Label(
                label="Ignored filename patterns",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        self._ignored_file_patterns_entry = engine.register_widget(
            Gtk.Entry(
                placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "ignore_file_patterns",
        )
        ignore_file_patterns_grid.attach(
            self._ignored_file_patterns_entry, 1, 0, 1, 1
        )

        self._add_horizontal_separator()

        # Specify allowed directory patterns
        allowed_directory_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(allowed_directory_patterns_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1
        allowed_directory_patterns_grid.attach(
            Gtk.Label(
                label="Allowed directory patterns",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        self._allowed_directory_patterns_entry = engine.register_widget(
            Gtk.Entry(
                placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "allowed_directory_patterns",
        )
        allowed_directory_patterns_grid.attach(
            self._allowed_directory_patterns_entry, 1, 0, 1, 1
        )

        self._add_horizontal_separator()

        # Specify ignored directory patterns
        ignore_directory_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )

        self.attach(ignore_directory_patterns_grid, 0, self._row_counter, 1, 2)
        self._row_counter += 1
        ignore_directory_patterns_grid.attach(
            Gtk.Label(
                label="Ignored directory patterns",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        self._ignored_directory_patterns_entry = engine.register_widget(
            Gtk.Entry(
                placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "ignore_directory_patterns",
        )
        ignore_directory_patterns_grid.attach(
            self._ignored_directory_patterns_entry, 1, 0, 1, 1
        )

    def _add_horizontal_separator(self):
        self.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=True,
            ),
            0,
            self._row_counter,
            1,
            1,
        )
        self._row_counter += 1
