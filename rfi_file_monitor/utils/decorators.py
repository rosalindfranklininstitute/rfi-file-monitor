from __future__ import annotations
from rfi_file_monitor.utils import ExitableThread

from gi.repository import Gio

from ..engine_advanced_settings import EngineAdvancedSettings
from ..engine import Engine
from ..utils.exceptions import SkippedOperation
from ..file import File, FileStatus
from ..files.regular_file import RegularFile, WeightedRegularFile
from ..files.directory import Directory
from ..operation import Operation

from typing import Type, Union, Sequence, Callable, Optional
import logging
import inspect
from pathlib import Path
import collections.abc
import functools
import threading
from time import sleep

logger = logging.getLogger(__name__)

_app = Gio.Application.get_default()


def with_pango_docs(filename: str):
    """Decorator for engines and operations, used to set the name of the file
    whose contents should be used to populate the associated Help dialog.
    Provide the basename of the file only, and make sure it is placed in a folder
    called `docs`, which must be a subfolder within the folder containing the engine or operation"""

    def _with_pango_docs(cls: Type[Union[Operation, Engine]]):
        if _app is None:
            return cls
        if not issubclass(cls, Operation) and not issubclass(cls, Engine):
            logger.error(
                f"with_pango_cos can only be used to decorate classes that extend Engine, Operation or QueueManager"
            )
            return cls
        try:
            module = inspect.getmodule(cls)
            if not module:
                raise Exception(f"module for class {cls.NAME} not found")
            contents = (
                Path(module.__file__)
                .parent.joinpath("docs", filename)
                .read_text()
            )
        except Exception:
            logger.exception(
                f"with_pango_docs: could not open {filename} for reading"
            )
        else:
            _app.pango_docs_map[cls] = contents
        return cls

    return _with_pango_docs


def with_advanced_settings(
    engine_advanced_settings: Type[EngineAdvancedSettings],
):
    """Decorator for Engine classes, to be used when some of their
    settings have been delegated to an advanced settings window
    OPTIONAL."""

    def _with_advanced_settings(cls: Type[Engine]):
        if _app is None:
            return cls
        if not issubclass(cls, Engine):
            logger.error(
                f"with_advanced_settings can only be used to decorate classes that extend Engine"
            )
            return cls
        _app.engines_advanced_settings_map[cls] = engine_advanced_settings
        return cls

    return _with_advanced_settings


# This may need to be changed later, if an engine can record multiple filetypes...
def exported_filetype(filetype: Type[File]):
    """Decorator for Engine classes that declares which filetype
    it will be looking out for. MANDATORY. Without this decorator,
    the engine cannot be tied to operations."""

    def _exported_filetype(cls: Type[Engine]):
        if _app is None:
            return cls
        if not issubclass(cls, Engine):
            logger.error(
                f"exported_filetype can only be used to decorate classes that extend Engine"
            )
            return cls
        _app.engines_exported_filetype_map[cls] = filetype
        return cls

    return _exported_filetype


def supported_filetypes(filetypes: Union[Type[File], Sequence[Type[File]]]):
    """Decorator for Operation classes that should be used to declare
    which filetype(s) it supports. OPTIONAL. If unused, then the operation
    will be assumed to support regular files only!"""

    def _supported_filetypes(cls: Type[Operation]):
        if _app is None:
            return cls
        if not issubclass(cls, Operation):
            logger.error(
                f"supported_filetypes can only be used to decorate classes that extend Operation"
            )
            return cls
        if isinstance(filetypes, collections.abc.Sequence):
            _filetypes = filetypes
        else:
            _filetypes = [filetypes]
        for filetype in _filetypes:
            if filetype in _app.filetypes_supported_operations_map:
                _app.filetypes_supported_operations_map[filetype].append(cls)
            else:
                _app.filetypes_supported_operations_map[filetype] = [cls]
        return cls

    return _supported_filetypes


# We are using filesize to determine weight in progressbar changes
# However, if the combined filesize is 0, then the file index will be used instead.
def add_directory_support(run: Callable[[Operation, File], Optional[str]]):
    @functools.wraps(run)
    def wrapper(self: Operation, file: File):
        current_thread = threading.current_thread()

        if isinstance(file, RegularFile):
            return run(self, file)
        elif isinstance(file, Directory):
            # get all files contained with Directory, as well as their sizes
            _path = Path(file.filename)
            _parent = _path.parent
            total_size = file.total_size
            size_seen = 0

            file.operation_metadata[self.index] = {}
            for file_index, (filename, size) in enumerate(file):
                # abort if job has been cancelled
                if (
                    isinstance(current_thread, ExitableThread)
                    and current_thread.should_exit
                ):
                    return str("Thread killed")

                if total_size == 0:
                    offset = file_index / len(file)
                    weight = 1 / len(file)
                else:
                    offset = size_seen / total_size
                    size_seen += size
                    weight = size / total_size

                _file = WeightedRegularFile(
                    filename,
                    Path(filename).relative_to(_parent),
                    0,
                    FileStatus.CREATED,
                    offset,
                    weight,
                )
                # reuse the row_reference to ensure the progress bars are updated
                _file.row_reference = file.row_reference

                # run the wrapped method, and do the usual exception and return value handling
                try:
                    rv = run(self, _file)
                    if rv:
                        return rv
                except SkippedOperation:
                    pass

                if self.index in _file.operation_metadata:
                    file.operation_metadata[self.index][
                        _file.filename
                    ] = _file.operation_metadata[self.index]
            return None
        else:
            raise NotImplementedError(f"{type(file)} is currently unsupported")

    return wrapper

def do_bulk_upload( process_existing_files: Callable[List]):
    @functools.wraps(process_existing_files)
    def wrapper(self: Engine, existing_files: List):
        no_files = sum(len(fs) for _, _, fs, in os.walk(*args))
        if no_files > 5000: # do not like this hard coded value but will put this in for performance testing
            chunked_input = [existing_files[i:i + 5000] for i in range(0, len(existing_files), 5000)]
            for rv in chunked_input:
                process_existing_files(self, rv)
                sleep(60) # calculate this based on the file weight?
    return wrapper
