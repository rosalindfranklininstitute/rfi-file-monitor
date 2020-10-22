from abc import ABC, abstractmethod, ABCMeta
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

from .utils.widgetparams import WidgetParams

class EngineMeta(ABCMeta, type(Gtk.Grid)):
    pass

class Engine(ABC, WidgetParams, Gtk.Grid, metaclass=EngineMeta):

    @abstractmethod
    def __init__(self, appwindow):
        self._appwindow = appwindow
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

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    @GObject.Property(type=bool, default=False)
    def valid(self):
        return self._valid