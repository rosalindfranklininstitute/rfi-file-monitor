from rfi_file_monitor.utils import ExitableThread
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import time
from threading import current_thread
import logging
from random import random

from ..operation import Operation
from ..utils.exceptions import SkippedOperation
from ..utils.decorators import with_pango_docs, supported_filetypes, add_directory_support
from ..file import File, RegularFile, S3Object, URL, Directory

logger = logging.getLogger(__name__)

@with_pango_docs(filename='dummy_operation.pango')
@supported_filetypes(filetypes=[RegularFile, S3Object, URL, Directory])
class DummyOperation(Operation):

    NAME = "Dummy Operation"
    DEBUG = True

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            row_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)
        self._grid.attach(Gtk.Label(label='This is a dummy operation'), 0, 0, 1, 1)
        combobox = Gtk.ComboBoxText()
        combobox.append_text('Text1')
        combobox.append_text('Text2')
        combobox.append_text('Text3')
        combobox.set_active(0)
        self.register_widget(combobox, 'dummy_combo')
        self._grid.attach(combobox, 0, 1, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Use bucket tags",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_bucket_tags')
        self._grid.attach(widget, 0, 2, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Use object tags",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_object_tags')
        self._grid.attach(widget, 0, 3, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Test Echo ACL",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_echo_acl')
        self._grid.attach(widget, 0, 4, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Fail randomly",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_random_fails')
        self._grid.attach(widget, 0, 5, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Skip randomly",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_random_skips')
        self._grid.attach(widget, 0, 6, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Process as directories if supported",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'enable_directories')
        self._grid.attach(widget, 0, 7, 2, 1)

        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Add Operational Metadata",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'add_metadata')
        self._grid.attach(widget, 0, 8, 2, 1)

    def preflight_check(self):
        metadata = dict()

        if self.params.enable_echo_acl:
            metadata['bucket_acl_options'] = {
                'AccessControlPolicy': {
                    'Grants': [
                        {
                            'Grantee': {
                                'ID': 'rfi-ai',
                                'Type': 'CanonicalUser',
                            },
                            'Permission': 'FULL_CONTROL',
                        },
                        {
                            'Grantee': {
                                'ID': 'rfi-instrument-xevo',
                                'Type': 'CanonicalUser',
                            },
                            'Permission': 'FULL_CONTROL',
                        },
                    ],
                    'Owner': {
                        'ID': 'rfi-instrument-xevo',
                    }
                },
            }
            metadata['object_acl_options'] = metadata['bucket_acl_options']

        if self.params.enable_bucket_tags:
            metadata['bucket_tags'] = {
                'owner': 'Tom',
                'group': 'Toms friends',
                'experiment name': 'Black magic part1'
            }

        if self.params.enable_object_tags:
            metadata['object_tags'] = {
                'owner': 'Laura',
                'group': 'Lauras friends',
                'experiment name': 'Alchemy part2'
            }

        if metadata:
            self.appwindow.preflight_check_metadata[self.index] = metadata

    def run(self, file: File):
        if isinstance(file, Directory) and self.params.enable_directories:
            return add_directory_support(type(self)._run)(self, file)
        return self._run(file)

    @classmethod
    def _attach_metadata(cls, file: File, operation_index:int):
        file.operation_metadata[operation_index] = {'number': random()}

    def _run(self, file: File):
        logger.debug(f'Processing {file.filename}')
        thread = current_thread()
        for i in range(10):
            if isinstance(thread, ExitableThread) and thread.should_exit:
                logger.info(f"Killing thread {thread.name}")
                return str('Thread killed')
            time.sleep(1.0)

            if self.params.enable_random_fails and random() < 0.02:
                return "Unfavorable RNG!!!"
            elif self.params.enable_random_skips and random() < 0.02:
                raise SkippedOperation("Unfavorable RNG!")

            file.update_progressbar(self.index, (i + 1) * 10)
            if self.params.add_metadata:
                self._attach_metadata(file, self.index)
        # None indicates success, a string failure, with its contents set to an error message
        return None

