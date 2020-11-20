import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ..engine import Engine
from ..file import URL, FileStatus
from ..operation import Operation
from ..utils import ExitableThread, LongTaskWindow
from ..utils.decorators import exported_filetype, with_pango_docs
from ..utils.exceptions import AlreadyRunning, NotYetRunning

import logging
from typing import Optional
from urllib.parse import urlparse, unquote_plus
from pathlib import PurePosixPath
from time import time

logger = logging.getLogger(__name__)

@with_pango_docs(filename='urls_engine.pango')
@exported_filetype(filetype=URL)
class URLsEngine(Engine):

    NAME = 'URLs from File Loader'

    def __init__(self, appwindow):
        super().__init__(appwindow)

        self.attach(Gtk.Label(label='File with URLs'), 0, 0, 1, 1)

        self._file_chooser_button = self.register_widget(Gtk.FileChooserButton(
            title="Select a file containing a list of URLs",
            action=Gtk.FileChooserAction.OPEN,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
            hexpand=True, vexpand=False), 'file_with_urls')
        self.attach(self._file_chooser_button, 1, 0, 1, 1)
        self._file_chooser_button.connect("selection-changed", self._file_chooser_button_cb)

    def _file_chooser_button_cb(self, button):
        if self.params.file_with_urls is None:
            self._valid = False
        else:
            try:
                with open(self.params.file_with_urls, 'r'):
                    pass
                self._valid = True
            except Exception:
                self._valid = False
        logger.debug(f'_file_chooser_button_cb: {self._valid}')
        self.notify('valid')

    def start(self):
        # start the engine
        # this assumes that the preflight check has been completed successfully!
        # start by looking for existing files, if requested.

        if self._running:
            raise AlreadyRunning('The engine is already running. It needs to be stopped before it may be restarted')

        # pop up a long task window
        # spawn a thread for this to avoid GUI freezes
        task_window = LongTaskWindow(self._appwindow)
        task_window.set_text(f"<b>Launching {self.NAME}</b>")
        task_window.show()
        watch_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.WATCH)
        task_window.get_window().set_cursor(watch_cursor)

        URLsEngineThread(self, task_window).start()

    def stop(self):
        if not self._running:
            raise NotYetRunning('The engine needs to be started before it can be stopped.')

        self._running = False
        self.notify('running')

    def _abort(self, task_window: Optional[LongTaskWindow], msg: str):
        if task_window:
            # destroy task window
            task_window.get_window().set_cursor(None)
            task_window.destroy()

        # display dialog with error message
        dialog = Gtk.MessageDialog(transient_for=self.get_toplevel(),
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text=f"Could not start {self.NAME}",
                secondary_text=msg)
        dialog.run()
        dialog.destroy()

        return GLib.SOURCE_REMOVE

    def _kill_task_window(self, task_window: LongTaskWindow):
        # destroy task window
        task_window.get_window().set_cursor(None)
        task_window.destroy()

        self._running = True
        self.notify('running')

        return GLib.SOURCE_REMOVE

class URLsEngineThread(ExitableThread):

    def __init__(self, engine: URLsEngine, task_window: LongTaskWindow):
        super().__init__()
        self._engine = engine
        self._task_window = task_window

    def run(self):
        # open file
        with open(self._engine.params.file_with_urls, 'r') as f:
            lines = f.readlines()

        # strip lines and ensure they are usable
        lines = list(filter(lambda line: not (len(line) == 0 or line.startswith('#')) , map(lambda line: line.strip(), lines)))
        
        if len(lines) == 0:
            GLib.idle_add(self._engine._abort, self._task_window, f'{self._engine.params.file_with_urls} contains no usable URLs', priority=GLib.PRIORITY_HIGH)
            return

        # parse URLs
        msg = []
        files = []
        for line in lines:
            parsed = urlparse(line)

            if parsed.scheme not in ('http', 'https'):
                msg.append(f'{line}: only http and https protocols are supported')
                continue

            if not parsed.path or not (path := unquote_plus(parsed.path[1:])):
                msg.append(f'{line}: URL must contain a path')
                continue
            
            _file = URL(line, PurePosixPath(path), time(), FileStatus.SAVED)
            files.append(_file)

        if msg:
            msgs = '\n'.join(msg)
            GLib.idle_add(self._engine._abort, self._task_window, f"{self._engine.params.file_with_urls} contains invalid URLs: {msgs}", priority=GLib.PRIORITY_HIGH)
            return

        # if we get here, things should be working.
        # close task_window and send files to the queue manager
        GLib.idle_add(self._engine._kill_task_window, self._task_window, priority=GLib.PRIORITY_HIGH)
        GLib.idle_add(self._engine._appwindow._queue_manager.add, files, priority=GLib.PRIORITY_HIGH)

        

