import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk

from .utils import add_action_entries
import logging
from collections import OrderedDict
from threading import RLock
from time import time, ctime
from .file import FileStatus, File
from pathlib import PurePath
from typing import OrderedDict as OrderedDictType

class ApplicationWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._monitor: Gio.FileMonitor = None
        self._monitored_directory: str = None
        self._files_dict_lock = RLock()
        self._files_dict: OrderedDictType[str, File] = OrderedDict()

        self.set_default_size(1000, 1000)

        action_entries = (
            ("close", self.on_close),
            ("minimize", self.on_minimize),
        )

        # This doesn't work, which is kind of uncool
        # self.add_action_entries(action_entries)
        for action_entry in action_entries:
            add_action_entries(self, *action_entry)

        self.set_border_width(10)
        main_grid = Gtk.Grid(
            row_spacing=10,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True)
        self.add(main_grid)

        controls_frame = Gtk.Frame(label="File Monitor Controls",
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False)
        main_grid.attach(controls_frame, 0, 0, 1, 1)
        
        controls_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False,
            border_width=10, column_spacing=5, row_spacing=5)
        controls_frame.add(controls_grid)
        self._monitor_switch = Gtk.Switch(active=False,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False)
        controls_grid.attach(self._monitor_switch, 0, 0, 1, 1)
        self._monitor_switch.connect("notify::active", self.monitor_switch_cb)
        self._monitor_switch.set_sensitive(False)
        self._directory_chooser_button = Gtk.FileChooserButton(
            title="Select a directory for monitoring",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            create_folders=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False)
        controls_grid.attach(self._directory_chooser_button, 1, 0, 1, 1)
        self._directory_chooser_button.connect("selection-changed", self.directory_chooser_button_cb)

        paned = Gtk.Paned(wide_handle=True,
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True)
        main_grid.attach(paned, 0, 1, 1, 1)

        operations_frame = Gtk.Frame(
            label='List of Operations',
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True)
        paned.pack1(operations_frame, resize=True, shrink=False)
        
        output_frame = Gtk.Frame(
            label='Output',
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True)
        paned.pack2(output_frame, resize=True, shrink=False)
        
        self._files_tree_model = Gtk.TreeStore(
            str, # filename, relative to monitored directory
            int, # epoch time
            int, # status as code
            #str, # status as string
            str, # operation name
            float, # operation progress
        )

        files_scrolled_window = Gtk.ScrolledWindow(
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True)
        output_frame.add(files_scrolled_window)

        files_tree_view = Gtk.TreeView(self._files_tree_model)
        files_scrolled_window.add(files_tree_view)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Filename", renderer, text=0)
        files_tree_view.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Created", renderer)
        column.set_cell_data_func(renderer, self.time_cell_data_func, func_data=dict(column=1))
        files_tree_view.append_column(column)


    def time_cell_data_func(self, tree_column, cell, tree_model, iter, func_data):
        epoch = tree_model.get_value(iter, func_data['column'])
        date_string = ctime(epoch)
        logging.debug(f"time_cell_data_func: {date_string}")
        logging.debug(f"{type(cell)}=")
        cell.set_property('text', date_string)

    def monitor_switch_cb(self, button, active):
        self._directory_chooser_button.set_sensitive(not button.get_active())

        if button.get_active():
            # cleanup, launch the monitor
            self._files_tree_model.clear()
            self._timeout_id = GLib.timeout_add_seconds(1, self.files_dict_timeout_cb, priority=GLib.PRIORITY_DEFAULT)

            monitor_file = Gio.File.new_for_path(self._monitored_directory)
            self._monitor = monitor_file.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES)
            self._monitor.connect("changed", self.monitor_cb)
        else:
            # disable the monitor
            GLib.source_remove(self._timeout_id)
            with self._files_dict_lock:
                self._files_dict.clear()

    def monitor_cb(self, monitor, file, other_file, event_type):
        """
        This method is called whenever our monitored directory changed
        """
        file_path = file.get_path()
        logging.debug(f"Monitor found {file_path} for event type {event_type}")
        # file has been created -> add a new object to dict
        if event_type == Gio.FileMonitorEvent.CREATED:
            if (file_type := file.query_file_type(Gio.FileQueryInfoFlags.NONE)) == Gio.FileType.REGULAR:
                # regular file -> add to queue for processing
                with self._files_dict_lock:
                    if file_path in self._files_dict:
                        logging.warn("f{file_path} has been recreated! Ignoring...")
                    self._files_dict[file_path] = File(created=time())
            elif file_type == Gio.FileType.DIRECTORY:
                # directory -> add a new file monitor since this is not working recursively
                pass
        # file has been saved -> kick off pipeline
        # need to check that this hasnt happened before!
        elif event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            pass

    def directory_chooser_button_cb(self, button):
        if monitored_directory := button.get_filename():
            self._monitored_directory = monitored_directory
            self._monitor_switch.set_sensitive(True)
            self.set_title(f"Monitoring: {self._monitored_directory}")

    def on_minimize(self, action, param):
        self.iconify()

    def on_close(self, action, param):
        self.destroy()

    def files_dict_timeout_cb(self, *user_data):
        """
        This function runs every second, and will take action based on the status of all files in the dict
        """
        with self._files_dict_lock:
            for _filename, _file in self._files_dict.items():
                if _file.status == FileStatus.CREATED and _file.row_reference == None:
                    logging.debug(f"files_dict_timeout_cb: {_filename} was created")
                    # add new entry to model
                    iter = self._files_tree_model.append(parent=None, row=[
                        str(PurePath(_filename).relative_to(self._monitored_directory)),
                        _file.created,
                        _file.status,
                        "ignored",
                        0.0,
                    ])
                    _file.row_reference = Gtk.TreeRowReference.new(self._files_tree_model, self._files_tree_model.get_path(iter))
        return GLib.SOURCE_CONTINUE


