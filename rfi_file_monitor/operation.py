from abc import ABC, abstractmethod, ABCMeta
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from typing import Final

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

    @property
    @abstractmethod
    def valid(self) -> bool:
        """
        This property reflects the state of the user-input for the operation.
        True means that the input is valid, and that this operation is allowed
        to proceed.
        """
        raise NotImplementedError

    @abstractmethod
    def set_sensitive(self, state: bool):
        """
        Use this method to disable those input widgets that should be inactive
        while monitoring (and processing) is active.
        Note that this overrides a Gtk.Widget method!
        """
        raise NotImplementedError