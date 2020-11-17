import threading
from typing import Final
import logging

from .file import File, FileStatus
from .operation import SkippedOperation

from tenacity import RetryError

logger = logging.getLogger(__name__)

class Job(threading.Thread):

    SKIPPED_MESSAGE = "A preceding operation has been skipped"
    ERROR_MESSAGE = "Operation not started due to previous error"

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
        # this will contain the first error message we run into,
        # and will be used as tooltip for the parent row
        global_rv = None

        for index, operation in enumerate(self._appwindow._operations_box):
            self._file.update_status(index, FileStatus.RUNNING)

            if self._should_exit:
                rv = "Monitoring aborted"
            elif rv is None:
                try:
                    rv = operation.run(self._file)
                except SkippedOperation as e:
                    rv = e
                except RetryError as e:
                    # happens when the run method is wrapped with tenacity.retry
                    # and we ran out of retries
                    rv = str(e.last_attempt.result())
                except Exception as e:
                    # exceptions caught here indicate a programming error,
                    # as exceptions should be caught during run, and if necessary,
                    # run should appropriate error message instead of None
                    # The only reason to catch it here is to avoid it taking the app down...
                    rv = str(e)
                    logger.exception(f"run() exception caught: {rv}!")
            else:
                # If we get here then an error was returned in a previous operation already
                rv = self.ERROR_MESSAGE

            if rv is None:
                # update operation status to success
                self._file.update_status(index, FileStatus.SUCCESS)
            elif isinstance(rv, SkippedOperation):
                # update operation status to skipped
                self._file.update_status(index, FileStatus.SKIPPED, str(rv))
                # reset rv to None to ensure the other operations are run
                rv = None
            else:
                # update operation status to failed
                self._file.update_status(index, FileStatus.FAILURE, rv)
                if global_rv is None:
                    global_rv = rv

        # update global operation status
        if global_rv is None:
            # update job status to success
            self._file.update_status(-1, FileStatus.SUCCESS)
        else:
            # update job status to failed
            self._file.update_status(-1, FileStatus.FAILURE, global_rv)

        # when the thread should exit, don't even bother decreasing njobs_running,
        # as it will should be set to 0 regardless, and you may end up with negative
        # njobs_running otherwise...
        if not self._should_exit:
            self._appwindow._njobs_running -= 1

        return

    @property
    def should_exit(self):
        return self._should_exit
    
    @should_exit.setter
    def should_exit(self, value: bool):
        self._should_exit = value

