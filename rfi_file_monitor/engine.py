from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GObject, Gdk, GLib

from abc import ABC, abstractmethod, ABCMeta
from typing import Optional, Type, Union
import traceback
import logging

from .utils import ExitableThread, LongTaskWindow
from .utils.exceptions import AlreadyRunning, NotYetRunning
from .utils.widgetparams import WidgetParams


logger = logging.getLogger(__name__)

class EngineThread(ABC, ExitableThread):
    def __init__(self, engine: Engine, task_window: LongTaskWindow):
        super().__init__()
        self._engine : Engine = engine
        self._task_window = task_window


class EngineMeta(ABCMeta, Gtk.Grid.__class__):
    pass

class Engine(ABC, WidgetParams, Gtk.Grid, metaclass=EngineMeta):
    @abstractmethod
    def __init__(self, appwindow, engine_thread_class: Type[EngineThread], abort_message: str):
        self._appwindow = appwindow
        self._engine_thread_class = engine_thread_class
        self._abort_message = abort_message
    
        kwargs = dict(
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True,
            row_spacing=5, column_spacing=5,
            border_width=5,
        )
        Gtk.Grid.__init__(self, **kwargs)
        WidgetParams.__init__(self)

        self._running = False
        self._valid = False

    @property
    @classmethod
    @abstractmethod
    def NAME(cls) -> str:
        """
        A descriptive short name for the engine
        """
        raise NotImplementedError

    @GObject.Property(type=bool, default=False)
    def running(self):
        return self._running

    @GObject.Property(type=bool, default=False)
    def valid(self):
        return self._valid

    @property
    def appwindow(self):
        return self._appwindow

    def start(self):
        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        # pop up a long task window
        # spawn a thread for this to avoid GUI freezes
        task_window = LongTaskWindow(self._appwindow)
        task_window.set_text(f"<b>Launching {self.NAME}</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
        task_window.get_window().set_cursor(watch_cursor)

        self._thread = self._engine_thread_class(self, task_window)
        self._thread.start()

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        task_window = LongTaskWindow(self._appwindow)
        task_window.set_text(f"<b>Stopping {self.NAME}</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
        task_window.get_window().set_cursor(watch_cursor)

        self._running_changed_handler_id = self.connect('notify::running', self._running_changed_cb, task_window)                

        # if the thread is sleeping, it will be killed at the next iteration
        self._thread.should_exit = True

    def _running_changed_cb(self, _self, param, task_window):
        self.disconnect(self._running_changed_handler_id)
        if not self._running:
            task_window.get_window().set_cursor(None)
            task_window.destroy()

    def kill_task_window(self, task_window: LongTaskWindow):
        # destroy task window
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        self._running = True
        self.notify('running')

        return GLib.SOURCE_REMOVE
        
    def abort(self, task_window: Optional[LongTaskWindow], e: Union[Exception, str]):
        if task_window:
            # destroy task window
            task_window.get_window().set_cursor(None)
            task_window.destroy()

        # display dialog with error message
        if isinstance(e, Exception):
            traceback.print_exc()
            logger.debug(''.join(traceback.format_tb(e.__traceback__)))
        elif isinstance(e, str):
            logger.debug(e)
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(),
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text=f"Could not start {self.NAME}",
                secondary_text=str(e) + f'\n\n{self._abort_message}')
        dialog.run()
        dialog.destroy()

        return GLib.SOURCE_REMOVE
    
    def cleanup(self):
        GLib.idle_add(self._stop_running)

    def _stop_running(self):
        self._running = False
        self.notify('running')

        return GLib.SOURCE_REMOVE