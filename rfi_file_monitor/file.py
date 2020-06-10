from enum import auto, IntEnum, unique
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

@unique
class FileStatus(IntEnum):
    CREATED = auto()
    SAVED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    REMOVED_FROM_LIST = auto()

    def __str__(self):
        #pylint: disable=no-member
        return self.name.lower().capitalize().replace('_', ' ')

class File(GObject.GObject):
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