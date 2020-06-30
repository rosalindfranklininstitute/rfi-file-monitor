from abc import ABC, abstractmethod, ABCMeta
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from munch import Munch

from typing import Final, Union, final

from .file import File

#
# This is my attempt at extending Gtk.Frame with
# abstract methods to turn it into an abstract class.
# Though this seems to be done properly, classes derived from
# the Operation abstract class do not appear to cause errors
# at runtime if abstract methods were not implemented.
# So, the errors that are produced and bring the app down are
# NotImplementedError exceptions...
#
class OperationMeta(ABCMeta, type(Gtk.Frame)):
    pass

class Operation(ABC, Gtk.Frame, metaclass=OperationMeta):

    @abstractmethod
    def __init__(self, *args, **kwargs):
        kwargs.update(dict(
            #label=f"Operation {index}: {self.NAME}",
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=True,
            border_width=5,
        ))
        Gtk.Frame.__init__(self, *args, **kwargs)
        self._index: Final[int] = 0
        self._params: Final[Munch[str, Union[str, bool]]] = Munch()
        self._signal_ids: Final[Munch[str, int]] = Munch()
        self._widgets: Final[Munch[str, Gtk.Widget]] = Munch()

    def set_sensitive(self, sensitive: bool):
        for widget in self._widgets.values():
            widget.set_sensitive(sensitive)

    @final
    def _entry_changed_cb(self, entry: Gtk.Entry, param_name: str):
        #pylint: disable=used-before-assignment
        self._params[param_name] = tmp if (tmp := entry.get_text().strip()) != "" else entry.get_placeholder_text()

    @final
    def _checkbutton_toggled_cb(self, checkbutton: Gtk.CheckButton, param_name: str):
        self._params[param_name] = checkbutton.get_active()

    @final
    def register_widget(self, widget: Gtk.Widget, param_name: str):
        if isinstance(widget, Gtk.Entry):
            #pylint: disable=used-before-assignment
            self._params[param_name] = tmp if (tmp := widget.get_text().strip()) != "" else widget.get_placeholder_text()
            self._signal_ids[param_name] = widget.connect("changed", self._entry_changed_cb, param_name)
        elif isinstance(widget, Gtk.CheckButton):
            self._params[param_name] = widget.get_active()
            self._signal_ids[param_name] = widget.connect("toggled", self._checkbutton_toggled_cb, param_name)
        else:
            raise NotImplementedError(f"register_widget: no support for {type(widget).__name__}")

        self._widgets[param_name] = widget

        return widget

    @property
    def params(self) -> Munch:
        """
        A Munch dict containing the parameters that will be used by run
        """
        return self._params

    @property
    def index(self) -> int:
        """
        The position of the operation in the list of operations in the applicationwindow
        """
        return self._index

    @index.setter
    def index(self, value: int):
        self._index = value
        self.props.label = f"Operation {self._index + 1}: {self.NAME}"

    @property
    @classmethod
    @abstractmethod
    def NAME(cls) -> str:
        """
        A descriptive short name for the operation,
        that will show up in the list of available operations,
        and will be used in the title of this frame.
        """
        raise NotImplementedError

    @abstractmethod
    def run(self, file: File):
        """
        This method will process File and execute the operation.
        Since this will be done in a worker-thread, you cannot directly
        call any methods that update the GUI.

        """
        raise NotImplementedError

    def preflight_check(self):
        """
        This method will be used to check that all widgets have valid information,
        and should also be used to extract that information into variables that
        can be used in the run() method, meaning that no Gtk calls will need to be made
        when calling run() afterwards.
        Feel free to use it also for initializing other stuff, such as opening connections.
        
        If something goes wrong during this method, an exception will be raised.
        """
        return

    def postflight_cleanup(self):
        """
        Use this method to do some cleanup, usually things that were done in preflight_cleanup().
        """
        return

    