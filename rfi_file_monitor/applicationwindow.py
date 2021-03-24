from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib, Gdk
import yaml

from typing import Final, Dict, Any, List, Optional
import logging
from fnmatch import fnmatch
from time import ctime
from threading import Thread, current_thread
import inspect
import collections.abc
import traceback

from .utils import PATTERN_PLACEHOLDER_TEXT, MONITOR_YAML_VERSION
from .utils.paramswindow import ParamsWindow
from .utils import (
    add_action_entries,
    EXPAND_AND_FILL,
    LongTaskWindow,
    class_in_object_iterable,
)
from .file import FileStatus, File
from .queue_manager import QueueManager
from .engine import Engine
from .operation import Operation
from .preferences import Preferences

logger = logging.getLogger(__name__)


class ApplicationWindow(Gtk.ApplicationWindow):

    ENGINE_ADVANCED_SETTINGS_WINDOW_ATTR = "advanced settings window"

    def __init__(self, force_all=False, **kwargs):
        logger.debug("Calling ApplicationWindow __init__")
        Gtk.ApplicationWindow.__init__(self, **kwargs)

        self._prefs: Preferences = self.get_property(
            "application"
        ).get_preferences()

        self._preflight_check_metadata: Final[
            Dict[int, Dict[str, Any]]
        ] = dict()
        self._yaml_file: str = None

        self.set_default_size(1000, 1000)

        action_entries = (
            ("save", self.on_save),
            ("save-as", self.on_save_as),
            ("close", self.on_close),
            ("minimize", self.on_minimize),
            ("play", self.on_play),
            ("stop", self.on_stop),
            ("add-operation", self.on_add_operation),
            ("queue-manager", self.on_open_queue_manager),
            ("help-queue-manager", self.on_open_queue_manager_help),
            (
                "status-filter-created",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.CREATED,
            ),
            (
                "status-filter-saved",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.SAVED,
            ),
            (
                "status-filter-queued",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.QUEUED,
            ),
            (
                "status-filter-running",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.RUNNING,
            ),
            (
                "status-filter-success",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.SUCCESS,
            ),
            (
                "status-filter-failure",
                self.on_status_filter,
                None,
                GLib.Variant.new_boolean(True),
                FileStatus.FAILURE,
            ),
        )

        # This doesn't work, which is kind of uncool
        # self.add_action_entries(action_entries)
        for action_entry in action_entries:
            add_action_entries(self, *action_entry)

        self.set_border_width(10)
        main_grid = Gtk.Grid(row_spacing=10, **EXPAND_AND_FILL)
        self.add(main_grid)

        controls_frame = Gtk.Frame(
            label="File Monitor Controls",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=False,
        )
        main_grid.attach(controls_frame, 0, 0, 1, 1)

        controls_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=False,
        )

        controls_grid_basic = Gtk.Grid(
            **EXPAND_AND_FILL, border_width=10, column_spacing=5, row_spacing=5
        )
        controls_frame.add(controls_grid)
        controls_grid.attach(controls_grid_basic, 0, 0, 1, 1)
        monitor_play_button = Gtk.Button(
            action_name="win.play",
            image=Gtk.Image(
                icon_name="media-playback-start", icon_size=Gtk.IconSize.DIALOG
            ),
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.END,
            hexpand=False,
            vexpand=False,
        )
        controls_grid_basic.attach(monitor_play_button, 0, 0, 1, 1)
        monitor_stop_button = Gtk.Button(
            action_name="win.stop",
            image=Gtk.Image(
                icon_name="media-playback-stop", icon_size=Gtk.IconSize.DIALOG
            ),
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.START,
            hexpand=False,
            vexpand=False,
        )
        controls_grid_basic.attach(monitor_stop_button, 0, 1, 1, 1)

        # turn the buttons off for now
        # play will become active when operations have been added
        self.lookup_action("play").set_enabled(False)
        self.lookup_action("stop").set_enabled(False)

        # add the notebook with the engines
        self._engines_notebook = Gtk.Notebook(
            **EXPAND_AND_FILL,
            scrollable=True,
        )
        controls_grid_basic.attach(self._engines_notebook, 1, 0, 6, 2)

        self._engines: List[Engine] = list()

        for engine_cls in self.get_property(
            "application"
        ).known_engines.values():
            if not (self._prefs.engines[engine_cls] or force_all):
                continue
            engine = engine_cls(appwindow=self)
            engine_grid = Gtk.Grid(
                **EXPAND_AND_FILL, row_spacing=5, border_width=5
            )
            engine_grid.attach(engine, 0, 0, 1, 1)
            buttons_grid = Gtk.Grid(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
                column_spacing=5,
            )
            # add button and dialog for advanced settings if necessary
            if (
                engine_cls
                in self.get_property(
                    "application"
                ).engines_advanced_settings_map
            ):
                engine_advanced_settings = self.get_property(
                    "application"
                ).engines_advanced_settings_map[type(engine)](engine)
                title = f"{engine.NAME} Advanced Settings"
                dialog = ParamsWindow(engine_advanced_settings, self, title)
                setattr(
                    engine, self.ENGINE_ADVANCED_SETTINGS_WINDOW_ATTR, dialog
                )

                advanced_settings_button = Gtk.Button(
                    label="Advanced Settings",
                    halign=Gtk.Align.CENTER,
                    valign=Gtk.Align.CENTER,
                    hexpand=True,
                    vexpand=False,
                )
                buttons_grid.attach(
                    advanced_settings_button, len(buttons_grid), 0, 1, 1
                )
                advanced_settings_button.connect(
                    "clicked",
                    self._engine_advanced_settings_button_clicked_cb,
                    engine,
                )
            if engine_cls in self.get_property("application").pango_docs_map:
                help_button = Gtk.Button(
                    label="Help",
                    halign=Gtk.Align.CENTER,
                    valign=Gtk.Align.CENTER,
                    hexpand=True,
                    vexpand=False,
                )
                buttons_grid.attach(help_button, len(buttons_grid), 0, 1, 1)
                help_button.connect(
                    "clicked", self._engine_help_button_clicked_cb, engine
                )

            # fix layout a bit. Buttons should be grouped and centered
            if (buttons_grid_len := len(buttons_grid)) :
                engine_grid.attach(buttons_grid, 0, 1, 1, 1)
                if buttons_grid_len >= 2:
                    # apparently the children of the grid are listed in LIFO order
                    list(buttons_grid)[0].props.halign = Gtk.Align.START
                    list(buttons_grid)[-1].props.halign = Gtk.Align.END
                if buttons_grid_len >= 3:
                    for widget in list(buttons_grid)[1:-1]:
                        widget.props.hexpand = False
            else:
                del buttons_grid
            self._engines_notebook.append_page(
                engine_grid, Gtk.Label(label=engine_cls.NAME)
            )
            self._engines.append(engine)

        # ensure first engine is active
        self._active_engine: Engine = self._engines[0]
        self._active_engine_valid_handler_id = self._active_engine.connect(
            "notify::valid", self._engine_valid_changed_cb
        )
        self._engines_notebook.props.page = 0
        self._engines_notebook.connect("switch-page", self._switch_page_cb)

        # Add support for adding and removing operations
        controls_grid_basic.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=True,
            ),
            0,
            2,
            7,
            1,
        )

        controls_grid_basic.attach(
            Gtk.Label(
                label="<b>Add operation: </b>",
                use_markup=True,
                halign=Gtk.Align.END,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            3,
            2,
            1,
        )

        self._controls_operations_model = Gtk.ListStore(str, object)
        self._controls_operations_combo = Gtk.ComboBox(
            model=self._controls_operations_model,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )

        renderer = Gtk.CellRendererText()
        self._controls_operations_combo.pack_start(renderer, True)
        self._controls_operations_combo.add_attribute(renderer, "text", 0)
        controls_grid_basic.attach(self._controls_operations_combo, 2, 3, 2, 1)

        add_operation_button = Gtk.Button(
            label="Add",
            action_name="win.add-operation",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        controls_grid_basic.attach(add_operation_button, 4, 3, 2, 1)

        self._repopulate_available_operations()

        if len(self._controls_operations_model) > 0:
            self._controls_operations_combo.set_active(0)
        else:
            self.lookup_action("add-operation").set_enabled(False)
            self._controls_operations_combo.set_sensitive(False)

        paned = Gtk.Paned(
            wide_handle=True,
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        main_grid.attach(paned, 0, 1, 1, 1)

        operations_frame = Gtk.Frame(
            label="List of Operations",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        paned.pack1(operations_frame, resize=True, shrink=False)
        operations_scrolled_window = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        operations_frame.add(operations_scrolled_window)
        self._operations_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        operations_scrolled_window.add(self._operations_box)

        output_frame = Gtk.Frame(
            label="Processing Queue",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        paned.pack2(output_frame, resize=True, shrink=False)

        self._files_tree_model = Gtk.TreeStore(
            str,  # filename, relative to monitored directory
            float,  # epoch time
            int,  # status as code
            str,  # operation name
            float,  # operation progress
            str,  # operation progress as string
            str,  # background color
            str,  # error message
        )

        self._files_tree_model_filter = Gtk.TreeModelFilter(
            child_model=self._files_tree_model
        )
        self._files_tree_model_filter.set_visible_func(
            self._files_tree_model_visible_func
        )

        output_grid = Gtk.Grid(**EXPAND_AND_FILL, row_spacing=2, border_width=2)

        filters_grid = Gtk.Grid(
            border_width=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_spacing=5,
        )
        output_grid.attach(filters_grid, 0, 0, 1, 1)

        label = Gtk.Label(
            label="Queue Filters:",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        filters_grid.attach(label, 0, 0, 1, 1)
        state_filters_button = Gtk.Button(
            label="Status",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        filters_grid.attach(state_filters_button, 1, 0, 1, 1)

        state_filter_popover = Gtk.Popover.new_from_model(
            state_filters_button,
            self.get_property("application").filter_popover_menu,
        )
        state_filters_button.connect(
            "clicked", self._state_filters_button_clicked, state_filter_popover
        )

        label = Gtk.Label(
            label="Name:",
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        filters_grid.attach(label, 2, 0, 1, 1)
        self._name_filter_entry = Gtk.Entry(
            placeholder_text=PATTERN_PLACEHOLDER_TEXT,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        filters_grid.attach(self._name_filter_entry, 3, 0, 1, 1)
        self._name_filter_entry.connect(
            "changed", self._name_filter_entry_changed
        )

        queue_manager_button = Gtk.Button(
            label="Queue Manager",
            action_name="win.queue-manager",
            halign=Gtk.Align.END,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        filters_grid.attach(queue_manager_button, 4, 0, 1, 1)
        self._queue_manager = QueueManager(self)
        self._queue_manager_window = ParamsWindow(
            self._queue_manager, self, "Queue Manager"
        )

        help_queue_manager_button = Gtk.Button(
            label="Help",
            action_name="win.help-queue-manager",
            halign=Gtk.Align.END,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        filters_grid.attach(help_queue_manager_button, 5, 0, 1, 1)

        files_frame = Gtk.Frame(border_width=5)
        files_scrolled_window = Gtk.ScrolledWindow(**EXPAND_AND_FILL)
        files_frame.add(files_scrolled_window)
        output_grid.attach(files_frame, 0, 1, 1, 1)
        output_frame.add(output_grid)

        files_tree_view = Gtk.TreeView(
            model=self._files_tree_model_filter, border_width=5
        )
        files_scrolled_window.add(files_tree_view)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(
            "Filename", renderer, text=0, cell_background=6
        )
        files_tree_view.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Created", renderer, cell_background=6)
        column.set_cell_data_func(
            renderer, self._time_cell_data_func, func_data=dict(column=1)
        )
        files_tree_view.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Status", renderer, cell_background=6)
        column.set_cell_data_func(
            renderer, self._status_cell_data_func, func_data=dict(column=2)
        )
        files_tree_view.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(
            "Operation", renderer, text=3, cell_background=6
        )
        files_tree_view.append_column(column)

        renderer = Gtk.CellRendererProgress()
        column = Gtk.TreeViewColumn(
            "Progress", renderer, value=4, text=5, cell_background=6
        )
        files_tree_view.append_column(column)

        files_tree_view.set_tooltip_column(column=7)

        # add status bar
        self._status_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            column_homogeneous=True,
            column_spacing=5,
        )
        output_grid.attach(self._status_grid, 0, 2, 1, 1)
        statuses = (
            "Total",
            "Created",
            "Saved",
            "Queued",
            "Running",
            "Success",
            "Failure",
            "Removed from list",
        )
        for _index, _status in enumerate(statuses):
            self._status_grid.attach(
                Gtk.Label(label=f"{_status}: 0"), _index, 0, 1, 1
            )

        # connect delete-event signal handler
        self.connect("delete-event", self._delete_event_cb)

    def _delete_event_dialog_timeout(self, dialog):
        if self._active_engine.props.running:
            return GLib.SOURCE_CONTINUE

        dialog.response(Gtk.ResponseType.CLOSE)

        return GLib.SOURCE_REMOVE

    def _delete_event_killer(self, engine, _):
        if engine.props.running is False:
            self.destroy()

    def _delete_event_cb(self, window, event):
        logger.debug(f"Enterng _delete_event_cb")

        # If nothing is running, just close it down
        if (
            not self._active_engine.props.running
            and not self._queue_manager.get_property("running")
        ):
            return False

        # else, pop up a dialog asking for confirmation
        dialog = Gtk.MessageDialog(
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_type=Gtk.MessageType.QUESTION,
            text="The monitor engine is still running!",
            secondary_text="Are you sure you want to close this window?",
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
        )

        source_id = GLib.timeout_add_seconds(
            1, self._delete_event_dialog_timeout, dialog
        )
        rv = dialog.run()
        dialog.destroy()
        GLib.source_remove(source_id)

        if rv in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            return True
        elif rv in (Gtk.ResponseType.OK, Gtk.ResponseType.CLOSE):
            if (
                self._active_engine.props.running
                and self._queue_manager.get_property("running")
            ):
                # hookup signal to active_engine running property
                self._queue_manager.connect(
                    "notify::running", self._delete_event_killer
                )
                # stop it manually
                self._active_engine.stop()
                return True
            return False

    def _switch_page_cb(self, notebook, page, page_num):
        logger.debug(f"_switch_page_cb: {page_num=}")
        self._active_engine.disconnect(self._active_engine_valid_handler_id)
        self._active_engine = self._engines[page_num]
        self._repopulate_available_operations()
        self._update_monitor_switch_sensitivity()
        self._active_engine_valid_handler_id = self._active_engine.connect(
            "notify::valid", self._engine_valid_changed_cb
        )

    def _repopulate_available_operations(self):
        # get active engine
        filetype_cls = self.get_property(
            "application"
        ).engines_exported_filetype_map[type(self._active_engine)]
        operation_cls_list = []

        for _cls in filetype_cls.__mro__:
            if _cls is File:
                break
            for _op in self.get_property(
                "application"
            ).filetypes_supported_operations_map[_cls]:
                if self._prefs.operations[_op]:
                    operation_cls_list.append(_op)

        operation_cls_list.sort(key=lambda operation: operation.NAME)

        self._controls_operations_model.clear()
        for _class in operation_cls_list:
            self._controls_operations_model.append([_class.NAME, _class])

        if len(self._controls_operations_model):
            self._controls_operations_combo.props.active = 0
            self.lookup_action("add-operation").set_enabled(True)
            self._controls_operations_combo.set_sensitive(True)
        else:
            self.lookup_action("add-operation").set_enabled(False)
            self._controls_operations_combo.set_sensitive(False)

    def _update_monitor_switch_sensitivity(self):
        logger.debug("_update_monitor_switch_sensitivity")
        if len(self._operations_box) == 0:
            self.lookup_action("play").set_enabled(False)
            self._engines_notebook.props.show_tabs = True
        else:
            self._engines_notebook.props.show_tabs = False
            if self._active_engine.props.valid:
                self.lookup_action("play").set_enabled(True)
            else:
                self.lookup_action("play").set_enabled(False)

    def _files_tree_model_visible_func(self, model, iter, data):
        # Children should always be shown when the parent is visible
        if model.iter_parent(iter) is not None:
            return True

        status = FileStatus(model[iter][2])

        if status not in (
            FileStatus.CREATED,
            FileStatus.SAVED,
            FileStatus.QUEUED,
            FileStatus.RUNNING,
            FileStatus.SUCCESS,
            FileStatus.FAILURE,
        ):
            return False

        try:
            status_filter = self.get_action_state(
                f"status-filter-{status.name.lower()}"
            ).get_boolean()
        except AttributeError:
            logger.exception(f"{status=}")
            status_filter = False

        if status_filter is False:
            return False

        pattern = self._name_filter_entry.get_text().strip()

        if not pattern:
            return True
        return fnmatch(model[iter][0], pattern)

    def _engine_advanced_settings_button_clicked_cb(self, button, engine):
        # To avoid problems with the params, we have to reuse the window
        # So when it is closed, it is hidden instead of destroyed.
        dialog = getattr(engine, self.ENGINE_ADVANCED_SETTINGS_WINDOW_ATTR)
        dialog.present()

    def _engine_help_button_clicked_cb(self, button, engine):
        # Reuse window for all engines
        dialog = self.get_property("application").help_window
        dialog.props.transient_for = self
        dialog.select_item(type(engine))
        dialog.present()

    def on_open_queue_manager(self, action, param):
        self._queue_manager_window.present()

    def on_open_queue_manager_help(self, action, param):
        dialog = self.get_property("application").help_window
        dialog.props.transient_for = self
        dialog.select_item(QueueManager)
        dialog.present()

    def on_add_operation(self, action, param):
        logger.debug("Clicked on_add_operation")

        _class = self._controls_operations_combo.get_model()[
            self._controls_operations_combo.get_active_iter()
        ][1]
        new_operation = _class(appwindow=self)
        new_operation.index = len(self._operations_box)
        self._operations_box.pack_start(new_operation, False, False, 0)
        new_operation.show_all()
        self._update_monitor_switch_sensitivity()

    def _remove_operation(self, op_to_remove: Operation):
        self._operations_box.remove(op_to_remove)
        self._operations_box.resize_children()

        self._update_monitor_switch_sensitivity()

        if len(self._operations_box) == 0:
            return

        for op in self._operations_box:
            if op.index > op_to_remove.index:
                op.index = (
                    op.index - 1
                )  # reordering all the indices of the ops.

    def _state_filters_button_clicked(self, button, popover):
        popover.show_all()
        popover.popup()

    def _name_filter_entry_changed(self, entry):
        self._files_tree_model_filter.refilter()

    def _time_cell_data_func(
        self, tree_column, cell, tree_model: Gtk.TreeStore, iter, func_data
    ):
        # we currently dont write a timestamp for the individual operations
        if tree_model.iter_parent(iter) is not None:
            cell.set_property("text", "")
            return
        epoch = tree_model.get_value(iter, func_data["column"])
        date_string = ctime(epoch)
        cell.set_property("text", date_string)

    def _status_cell_data_func(
        self, tree_column, cell, tree_model, iter, func_data
    ):
        status = tree_model.get_value(iter, func_data["column"])
        status_string = str(FileStatus(status))
        cell.set_property("text", status_string)

    def on_minimize(self, action, param):
        self.iconify()

    def on_close(self, action, param):
        self.close()

    def on_status_filter(self, action, param, arg):
        logger.debug(f"{action.get_state()=} for {str(arg)}")
        # invert state!
        action.set_state(
            GLib.Variant.new_boolean(not action.get_state().get_boolean())
        )
        self._files_tree_model_filter.refilter()

    def on_play(self, action, param):
        self.lookup_action("play").set_enabled(False)
        task_window = LongTaskWindow(self)
        task_window.set_text("<b>Running preflight check</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(
            Gdk.Display.get_default(), Gdk.CursorType.WATCH
        )
        task_window.get_window().set_cursor(watch_cursor)

        # Cleanup tree model
        self._files_tree_model.clear()
        PreflightCheckThread(self, task_window).start()

    def on_stop(self, action, param):
        self.lookup_action("stop").set_enabled(False)

        self._active_engine.stop()

    def _preflight_check_cb(
        self, task_window: LongTaskWindow, exception_msgs: Optional[List[str]]
    ):
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        if exception_msgs:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text="Operation configuration error(s) found",
                secondary_text="\n".join(exception_msgs),
            )
            dialog.run()
            dialog.destroy()
            self.lookup_action("play").set_enabled(True)
            return

        # Launch the queue manager and the engine
        self._active_engine.set_sensitive(False)
        self._queue_manager.set_sensitive(False)

        for operation in self._operations_box:
            operation.set_sensitive(False)

        self._queue_manager_running_changed_handler_id = (
            self._queue_manager.connect(
                "notify::running", self._queue_manager_running_changed
            )
        )
        self._active_engine_running_changed_handler_id = (
            self._active_engine.connect(
                "notify::running", self._active_engine_running_changed
            )
        )
        self._queue_manager.start()

    def _queue_manager_running_changed(self, queue_manager, param):
        logger.debug(
            f"Calling _queue_manager_running_changed from {current_thread()} with value {queue_manager.props.running}"
        )
        if queue_manager.props.running:
            self._active_engine.start()
        else:
            # at this point everything should have stopped, except for Jobs that still need to finish and cannot be killed
            self._active_engine.set_sensitive(True)
            self._queue_manager.set_sensitive(True)

            for operation in self._operations_box:
                operation.set_sensitive(True)

            self._active_engine.disconnect(
                self._active_engine_running_changed_handler_id
            )
            self._queue_manager.disconnect(
                self._queue_manager_running_changed_handler_id
            )
            del self._active_engine_running_changed_handler_id
            del self._queue_manager_running_changed_handler_id
            self.lookup_action("play").set_enabled(True)

    def _active_engine_running_changed(self, active_engine, param):
        logger.debug(
            f"Calling _active_engine_running_changed from {current_thread()} with value {active_engine.props.running}"
        )
        if active_engine.props.running:
            # at this point things should really be running.
            self.lookup_action("stop").set_enabled(True)
            self.get_property(
                "application"
            ).google_analytics_context.send_event(
                "RUN-ENGINE", active_engine.NAME
            )
        else:
            self.lookup_action("stop").set_enabled(False)
            self._queue_manager.stop()

    def _engine_valid_changed_cb(self, engine, param):
        logger.debug(f"calling _engine_valid_changed_cb")
        self._update_monitor_switch_sensitivity()

    def _write_to_yaml(self):
        yaml_dict = dict(
            version=MONITOR_YAML_VERSION,
            active_engine=self._active_engine.NAME,
            queue_manager=self._queue_manager.exportable_params,
            operations=[
                dict(name=op.NAME, params=op.exportable_params)
                for op in self._operations_box
            ],
            engines=[
                dict(name=engine.NAME, params=engine.exportable_params)
                for engine in self._engines
            ],
        )
        logger.debug(f"{yaml.safe_dump(yaml_dict)=}")
        with open(self._yaml_file, "w") as f:
            yaml.safe_dump(yaml_dict, f)

    def on_save(self, action, param):
        if self._yaml_file is None:
            self.on_save_as(action, param)
        try:
            self._write_to_yaml()
            logger.info(f"{self._yaml_file} has been updated")
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"Could not write to {self._yaml_file}",
                secondary_text=str(e),
            )
            dialog.run()
            dialog.destroy()

    def on_save_as(self, action, param):
        # open a file chooser dialog
        dialog = Gtk.FileChooserNative(
            modal=True,
            title="Save monitor configuration to YAML file",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        filter = Gtk.FileFilter()
        filter.add_pattern("*.yml")
        filter.add_pattern("*.yaml")
        filter.set_name("YAML file")
        dialog.add_filter(filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self._yaml_file = dialog.get_filename()
            dialog.destroy()
            # ensure filename ends in .yaml or .yml
            if not self._yaml_file.endswith(
                ".yml"
            ) and not self._yaml_file.endswith(".yaml"):
                self._yaml_file += ".yml"
            try:
                self._write_to_yaml()
                logger.info(f"{self._yaml_file} has been written to")
            except Exception as e:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE,
                    text=f"Could not write to {self._yaml_file}",
                    secondary_text=str(e),
                )
                dialog.run()
                dialog.destroy()
        else:
            dialog.destroy()

    def load_from_yaml_dict(self, yaml_dict: dict):

        # active_engine
        active_engine = yaml_dict["active_engine"]
        queue_manager = yaml_dict["queue_manager"]
        operations = yaml_dict["operations"]
        engines = yaml_dict["engines"]

        for engine in engines:
            # find corresponding engine in appwindow
            engine_match = next(
                e for e in self._engines if e.NAME == engine["name"]
            )
            engine_match.update_from_dict(engine["params"])
            if active_engine == engine_match.NAME:
                active_engine_index = self._engines.index(engine_match)
                break
        else:
            logger.error(
                f"Active engine {active_engine} not found in list of engines"
            )
            return

        self._queue_manager.update_from_dict(queue_manager)

        # add the operations
        if isinstance(operations, collections.abc.Sequence):
            for op in operations:
                for _class in self.get_property(
                    "application"
                ).known_operations.values():
                    if op["name"] == _class.NAME:
                        new_operation = _class(appwindow=self)
                        new_operation.index = len(self._operations_box)
                        self._operations_box.pack_start(
                            new_operation, False, False, 0
                        )
                        new_operation.update_from_dict(op["params"])
                        new_operation.show_all()
                        break
                else:
                    logger.error(
                        f"load_from_yaml_dict: no match found for operation {op['name']}"
                    )

        self._engines_notebook.set_current_page(active_engine_index)
        self._update_monitor_switch_sensitivity()

    @property
    def preflight_check_metadata(self) -> dict:
        return self._preflight_check_metadata

    @property
    def queue_manager(self) -> QueueManager:
        return self._queue_manager

    @property
    def active_engine(self) -> Engine:
        return self._active_engine


class PreflightCheckThread(Thread):
    def __init__(
        self, appwindow: ApplicationWindow, task_window: LongTaskWindow
    ):
        super().__init__()
        self._appwindow = appwindow
        self._task_window = task_window

    def run(self):
        exception_msgs = []
        self._appwindow._preflight_check_metadata.clear()

        for index, operation in enumerate(self._appwindow._operations_box):
            if index > 0 and hasattr(operation, "PREREQUISITES"):
                preceding_ops = self._appwindow._operations_box.get_children()[
                    0:index
                ]
                preceding_ops_str = map(lambda op: op.NAME, preceding_ops)
                for prerequisite in getattr(operation, "PREREQUISITES"):
                    if (
                        inspect.isclass(prerequisite)
                        and issubclass(prerequisite, Operation)
                        and not class_in_object_iterable(
                            preceding_ops, prerequisite
                        )
                    ):

                        exception_msgs.append(
                            f"* {prerequisite.NAME} must precede {operation.NAME}"
                        )
                        break
                    elif (
                        isinstance(prerequisite, str)
                        and prerequisite not in preceding_ops_str
                    ):

                        exception_msgs.append(
                            f"* {prerequisite} must precede {operation.NAME}"
                        )
                        break
            elif hasattr(operation, "PREREQUISITES"):
                prereq = ", ".join(
                    map(
                        lambda x: x if isinstance(x, str) else x.NAME,
                        getattr(operation, "PREREQUISITES"),
                    )
                )
                exception_msgs.append(
                    f"* Operation {operation.NAME} must be proceded by {prereq}"
                )

            try:
                operation.preflight_check()
            except Exception as e:
                logger.debug(
                    f"Exception caught from {operation.NAME}: {traceback.format_exc()}"
                )
                exception_msgs.append(f"* {operation.NAME}: " + str(e))

        if exception_msgs:
            for operation in self._appwindow._operations_box:
                operation.postflight_cleanup()

            GLib.idle_add(
                self._appwindow._preflight_check_cb,
                self._task_window,
                exception_msgs,
                priority=GLib.PRIORITY_DEFAULT_IDLE,
            )
            return

        GLib.idle_add(
            self._appwindow._preflight_check_cb,
            self._task_window,
            None,
            priority=GLib.PRIORITY_DEFAULT_IDLE,
        )
