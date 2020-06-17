from enum import auto, IntEnum, unique
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GLib

import logging

@unique
class FileStatus(IntEnum):
    CREATED = auto()
    SAVED = auto()
    QUEUED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    REMOVED_FROM_LIST = auto()

    def __str__(self):
        #pylint: disable=no-member
        return self.name.lower().capitalize().replace('_', ' ')

class File(GObject.GObject):
    filename = GObject.Property(type=str, flags = GObject.ParamFlags.READWRITE) # filename
    created = GObject.Property(type=int, flags = GObject.ParamFlags.READWRITE) # created timestamp
    status = GObject.Property(type=int, flags = GObject.ParamFlags.READWRITE, default=FileStatus.CREATED) # status
    row_reference = GObject.Property(type=Gtk.TreeRowReference, flags=GObject.ParamFlags.READWRITE, default=None)
    #operation_data = GObject.Property(type=list, flags = GObject.ParamFlags.READWRITE) # operation data


    @GObject.Property(type=object)
    def operation_data(self):
        return self._operation_data

    @operation_data.setter
    def operation_data(self, value):
        print("Calling operation_data setter")
        self._operation_data = value

    def __init__(self, *args, **kwargs):
        GObject.GObject.__init__(self, *args, **kwargs)

    def _update_progressbar_worker_cb(self, index: int, value: float):
        #logging.debug(f"_update_progressbar_worker_cb: {index=} {value=}")
        if not self.props.row_reference.valid():
            logging.warning(f"_update_progressbar_worker_cb: {self.props.filename} is invalid!")
            return GLib.SOURCE_REMOVE

        model = self.props.row_reference.get_model()
        path = self.props.row_reference.get_path()
        parent_iter = model.get_iter(path)
        n_children = model.iter_n_children(parent_iter)

        cumul_value = (index * 100.0 + value) / n_children
        model[parent_iter][4] = cumul_value
        model[parent_iter][5] = f"{cumul_value:.1f} %"

        child_iter = model.iter_nth_child(parent_iter, index)
        model[child_iter][4] = value
        model[child_iter][5] = f"{value:.1f} %"
        
        return GLib.SOURCE_REMOVE

    def _update_status_worker_cb(self, index: int, status: FileStatus):
        if not self.props.row_reference.valid():
            logging.warning(f"_update_status_worker_cb: {self.props.filename} is invalid!")
            return GLib.SOURCE_REMOVE

        model = self.props.row_reference.get_model()
        path = self.props.row_reference.get_path()

        if index == -1: # parent
            self.props.status = int(status)
            model[path][2] = self.props.status
        else:
            parent_iter = model.get_iter(path)
            child_iter = model.iter_nth_child(parent_iter, index)
            model[child_iter][2] = int(status)
        
        return GLib.SOURCE_REMOVE

    def update_status(self, index: int, status: FileStatus):
        """
        When an operation has finished, update the status of the corresponding
        entry in the treemodel.
        An index of -1 refers to the parent entry, 0 or higher refers to a child.
        """
        GLib.idle_add(self._update_status_worker_cb, index, status)

    def update_progressbar(self, index: int, value: float):
        """
        This method will update the progressbar of the current operation,
        defined by index, as well as the global one.
        value must be between 0 and 100.

        Try not to use this function too often, as it may slow the GUI
        down considerably. I recommend to use it only when value is a whole number
        """
        GLib.idle_add(self._update_progressbar_worker_cb, index, value)



if __name__ == "__main__":
    print(str(FileStatus.REMOVED_FROM_LIST))
    print(FileStatus.REMOVED_FROM_LIST)
    print(int(FileStatus.REMOVED_FROM_LIST))

    my_file = File(created=1000, operation_data=list())
    my_file.connect("notify::created", lambda obj, gparamstring: print(f"New created: {obj.created}"))
    my_file.connect("notify::operation-data", lambda obj, gparamstring: print(f"New operation_data: {obj.operation_data}"))
    print(f"{my_file.props.created=}")
    print(f"{my_file.props.status=}")
    my_file.created = 500
    print(f"{my_file.props.operation_data=}")
    my_file.operation_data = [1, 2, 3]
    #my_file.operation_data[1] = 4
    my_file.operation_data = "sjalalala"
    #print(my_file.props.operation_data.__gtype__)