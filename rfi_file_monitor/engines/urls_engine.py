from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..engine import Engine, EngineThread
from ..file import URL, FileStatus
from ..utils.decorators import exported_filetype, with_pango_docs
from ..utils.exceptions import NotYetRunning

import logging
from urllib.parse import urlparse, unquote_plus
from pathlib import PurePosixPath
from time import time

logger = logging.getLogger(__name__)

ERROR_MSG = (
    "Ensure that the selected file contains valid http and/or https URLs"
)


@with_pango_docs(filename="urls_engine.pango")
@exported_filetype(filetype=URL)
class URLsEngine(Engine):

    NAME = "URLs from File Loader"

    def __init__(self, appwindow):
        super().__init__(appwindow, URLsEngineThread, ERROR_MSG)

        self.attach(Gtk.Label(label="File with URLs"), 0, 0, 1, 1)

        self._file_chooser_button = self.register_widget(
            Gtk.FileChooserButton(
                title="Select a file containing a list of URLs",
                action=Gtk.FileChooserAction.OPEN,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.FILL,
                hexpand=True,
                vexpand=False,
            ),
            "file_with_urls",
        )
        self.attach(self._file_chooser_button, 1, 0, 1, 1)
        self._file_chooser_button.connect(
            "selection-changed", self._file_chooser_button_cb
        )

    def _file_chooser_button_cb(self, button):
        if self.params.file_with_urls is None:
            self._valid = False
        else:
            try:
                with open(self.params.file_with_urls, "r"):
                    pass
                self._valid = True
            except Exception:
                self._valid = False
        logger.debug(f"_file_chooser_button_cb: {self._valid}")
        self.notify("valid")

    # override parent method, as the thread will have died by the time stop is clicked
    def stop(self):
        if not self._running:
            raise NotYetRunning(
                "The engine needs to be started before it can be stopped."
            )

        self.cleanup()


class URLsEngineThread(EngineThread):
    def run(self):
        # open file
        try:
            with open(self.params.file_with_urls, "r") as f:
                lines = f.readlines()

            # strip lines and ensure they are usable
            lines = list(
                filter(
                    lambda line: not (len(line) == 0 or line.startswith("#")),
                    map(lambda line: line.strip(), lines),
                )
            )

            if len(lines) == 0:
                raise Exception(
                    f"{self.params.file_with_urls} contains no usable URLs"
                )

            # parse URLs
            msg = []
            files = []
            for line in lines:
                parsed = urlparse(line)

                if parsed.scheme not in ("http", "https"):
                    msg.append(
                        f"{line}: only http and https protocols are supported"
                    )
                    continue

                if not parsed.path or not (
                    path := unquote_plus(parsed.path[1:])
                ):
                    msg.append(f"{line}: URL must contain a path")
                    continue

                _file = URL(line, PurePosixPath(path), time(), FileStatus.SAVED)
                files.append(_file)

            if msg:
                msgs = "\n".join(msg)
                raise Exception(
                    f"{self.params.file_with_urls} contains invalid URLs: {msgs}"
                )

            # if we get here, things should be working.
            # close task_window and send files to the queue manager
            GLib.idle_add(
                self._engine.kill_task_window,
                self._task_window,
                priority=GLib.PRIORITY_HIGH,
            )
            GLib.idle_add(
                self._engine._appwindow._queue_manager.add,
                files,
                priority=GLib.PRIORITY_HIGH,
            )
        except Exception as e:
            self._engine.cleanup()
            GLib.idle_add(
                self._engine.abort,
                self._task_window,
                e,
                priority=GLib.PRIORITY_HIGH,
            )
