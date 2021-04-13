from abc import ABC, abstractmethod, ABCMeta
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .file import File
from .utils.widgetparams import WidgetParams


#
# This is my attempt at extending Gtk.Frame with
# abstract methods to turn it into an abstract class.
# Though this seems to be done properly, classes derived from
# the Operation abstract class do not appear to cause errors
# at runtime if abstract methods were not implemented.
# So, the errors that are produced and bring the app down are
# NotImplementedError exceptions...
#
class OperationMeta(ABCMeta, Gtk.Frame.__class__):
    pass


class Operation(ABC, Gtk.Frame, WidgetParams, metaclass=OperationMeta):
    @abstractmethod
    def __init__(self, *args, **kwargs):
        self._appwindow = kwargs.pop("appwindow")
        self._index: int = 0

        self._label = Gtk.Label(
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
            label=f"Operation without index: {self.NAME}",
        )

        label_grid = Gtk.Grid(
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
            column_spacing=5,
            border_width=5,
        )
        label_grid.attach(self._label, 0, 0, 1, 1)

        # add delete button
        delete_button = Gtk.Button(
            image=Gtk.Image(
                icon_name="edit-delete-symbolic",
                icon_size=Gtk.IconSize.SMALL_TOOLBAR,
            ),
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            hexpand=False,
            vexpand=False,
        )
        label_grid.attach(delete_button, 1, 0, 1, 1)

        delete_button.connect("clicked", self._delete_clicked_cb)

        if (
            type(self)
            in self._appwindow.get_property("application").pango_docs_map
        ):
            help_button = Gtk.Button(
                image=Gtk.Image(
                    icon_name="dialog-question-symbolic",
                    icon_size=Gtk.IconSize.SMALL_TOOLBAR,
                ),
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            )
            label_grid.attach(help_button, 2, 0, 1, 1)

            help_button.connect("clicked", self._help_clicked_cb)

        kwargs.update(
            dict(
                label_widget=label_grid,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.FILL,
                hexpand=True,
                vexpand=True,
                border_width=5,
                label_xalign=0.5,
            )
        )
        Gtk.Frame.__init__(self, *args, **kwargs)
        WidgetParams.__init__(self)

    def _delete_clicked_cb(self, button):
        self._appwindow._remove_operation(self)

    def _help_clicked_cb(self, button):
        dialog = self._appwindow.get_property("application").help_window
        dialog.props.transient_for = self._appwindow
        dialog.select_item(type(self))
        dialog.present()

    @property
    def appwindow(self):
        """
        Returns the ApplicationWindow instance this operation is a part of
        """
        return self._appwindow

    @property
    def index(self) -> int:
        """
        The position of the operation in the list of operations in the applicationwindow
        """
        return self._index

    @index.setter
    def index(self, value: int):
        self._index = value
        self._label.props.label = f"Operation {self._index + 1}: {self.NAME}"

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

    def preflight_cleanup(self, success: bool):
        """
        Use this method to do some cleanup after the preflight_check.
        The value of success is determined by the global outcome of the
        preflight_check, not just the current operation.
        """
        return

    def destroy_operation(self):
        """
        use this method to remove widgets from the GUI and widget registry
        """
        return
