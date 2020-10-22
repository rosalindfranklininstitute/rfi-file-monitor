from abc import ABC, abstractmethod, ABCMeta
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .utils import EXPAND_AND_FILL
from .engine import Engine

class EngineAdvancedSettingsMeta(ABCMeta, type(Gtk.Grid)):
    pass

class EngineAdvancedSettings(ABC, Gtk.Grid, metaclass=EngineAdvancedSettingsMeta):

    @abstractmethod
    def __init__(self, engine: Engine):
        kwargs = dict(
            **EXPAND_AND_FILL,
            border_width=5,
            row_spacing=5, column_spacing=5,
        )
        Gtk.Grid.__init__(self, **kwargs)
        self._engine : Engine = engine