import threading
from typing import Final

from .file import File, FileStatus

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

class Job(threading.Thread):
    def __init__(self, appwindow, file: File):
        super().__init__()
        self._appwindow = appwindow 
        self._file = file
        self._should_exit: Final[bool] = False

    def run(self):
        # update status to running
        self._file.update_status(-1, FileStatus.RUNNING)

        # If operation.run() returns None, then it was considered a success.
        #Otherwise a string is returned with an error message
        rv = None

        for index, operation in enumerate(self._appwindow._operations_box):
            self._file.update_status(index, FileStatus.RUNNING)

            if not self._should_exit and \
                rv is None and \
                (rv := operation.run(self._file)) == None:
                # update operation status to success
                self._file.update_status(index, FileStatus.SUCCESS)
            else:
                # update operation status to failed
                self._file.update_status(index, FileStatus.FAILURE)

        # update global operation status
        if rv is None:
            # update job status to success
            self._file.update_status(-1, FileStatus.SUCCESS)
        else:
            # update job status to failed
            self._file.update_status(-1, FileStatus.FAILURE)

        self._appwindow._njobs_running -= 1

        return

    @property
    def should_exit(self):
        return self._should_exit
    
    @should_exit.setter
    def should_exit(self, value: bool):
        self._should_exit = value

