import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
import dropbox
import keyring

from ..operation import Operation
from ..utils.exceptions import SkippedOperation
from ..queue_manager import QueueManager
from ..utils.decorators import with_pango_docs
from ..utils import get_random_string
from ..file import File

import logging
import os
from pathlib import PurePosixPath
import hashlib
import re
import webbrowser
from threading import Thread

logger = logging.getLogger(__name__)

APP_KEY = 'l9wed9kx1tq965c'

# taken from https://github.com/dropbox/dropbox-api-content-hasher/blob/master/python/dropbox_content_hasher.py
class DropboxContentHasher(object):
    """
    Computes a hash using the same algorithm that the Dropbox API uses for the
    the "content_hash" metadata field.
    The digest() method returns a raw binary representation of the hash.  The
    hexdigest() convenience method returns a hexadecimal-encoded version, which
    is what the "content_hash" metadata field uses.
    This class has the same interface as the hashers in the standard 'hashlib'
    package.
    Example:
        hasher = DropboxContentHasher()
        with open('some-file', 'rb') as f:
            while True:
                chunk = f.read(1024)  # or whatever chunk size you want
                if len(chunk) == 0:
                    break
                hasher.update(chunk)
        print(hasher.hexdigest())
    """

    BLOCK_SIZE = 4 * 1024 * 1024

    def __init__(self):
        self._overall_hasher = hashlib.sha256()
        self._block_hasher = hashlib.sha256()
        self._block_pos = 0

        self.digest_size = self._overall_hasher.digest_size

    def update(self, new_data):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest()")

        new_data_pos = 0
        while new_data_pos < len(new_data):
            if self._block_pos == self.BLOCK_SIZE:
                self._overall_hasher.update(self._block_hasher.digest())
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0

            space_in_block = self.BLOCK_SIZE - self._block_pos
            part = new_data[new_data_pos:(new_data_pos+space_in_block)]
            self._block_hasher.update(part)

            self._block_pos += len(part)
            new_data_pos += len(part)

    def _finish(self):
        if self._overall_hasher is None:
            raise AssertionError(
                "can't use this object anymore; you already called digest() or hexdigest()")

        if self._block_pos > 0:
            self._overall_hasher.update(self._block_hasher.digest())
            self._block_hasher = None
        h = self._overall_hasher
        self._overall_hasher = None  # Make sure we can't use this object anymore.
        return h

    def digest(self):
        return self._finish().digest()

    def hexdigest(self):
        return self._finish().hexdigest()

class DropboxLinkDialog(Gtk.Dialog):
    def __init__(self, appwindow):
        Gtk.Dialog.__init__(self, title="Link Dropbox", transient_for=appwindow, modal=True, flags=0)
        self._authorization_code = None
        self._okbutton = self.add_button('Confirm', Gtk.ResponseType.OK)
        self._okbutton.set_sensitive(False)
        
        self.set_default_size(150, 100)

        box = self.get_content_area()
        grid = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            border_width=5,
            hexpand=True, vexpand=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.FILL)
        box.add(grid)

        label = Gtk.Label(label='<b>Follow these steps to link your Dropbox account with the RFI-File-Monitor</b>',
            use_markup=True,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False)
        frame = Gtk.Frame(
            height_request=50, border_width=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.START,
            hexpand=True, vexpand=False)
        frame.add(label)
        grid.attach(frame, 0, 0, 1, 1)

        grid1 = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            hexpand=True, vexpand=False,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        label = Gtk.Label(label='1. Click the button to open Dropbox in your browser',
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False)
        grid1.attach(label, 0, 0, 1, 1)
        dbx_button = Gtk.Button(label='Open Dropbox',
            halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False)
        grid1.attach(dbx_button, 1, 0, 1, 1)
        grid.attach(grid1, 0, 1, 1, 1)
        dbx_button.connect('clicked', self._dropbox_button_clicked)

        label = Gtk.Label(label='2. Click "Allow" (you may have to log in first).',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False)
        grid.attach(label, 0, 2, 1, 1)

        grid3 = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            hexpand=True, vexpand=False,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER)
        label = Gtk.Label(label='3. Copy the authorization token into the box',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False)
        grid3.attach(label, 0, 0, 1, 1)
        self._entry = Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False)
        self._entry.set_sensitive(False)
        self._entry.connect('changed', self._dropbox_entry_changed)
        grid3.attach(self._entry, 1, 0, 1, 1)
        grid.attach(grid3, 0, 3, 1, 1)

        self.show_all()

    def _dropbox_entry_changed(self, entry):
        self._okbutton.set_sensitive(True)
        self._authorization_code = entry.get_text().strip()

    def _dropbox_button_clicked(self, button):
        self._auth_flow = dropbox.oauth.DropboxOAuth2FlowNoRedirect(
            consumer_key=APP_KEY,
            use_pkce=True,
            token_access_type='offline',
        )
        url = self._auth_flow.start()
        webbrowser.open_new_tab(url)
        button.set_sensitive(False)
        self._entry.set_sensitive(True)

    @property
    def authorization_code(self) -> str:
        return self._authorization_code

    @property
    def auth_flow(self) -> dropbox.oauth.DropboxOAuth2FlowNoRedirect:
        return self._auth_flow

# taken from Maestral
class DropboxSpaceUsage(dropbox.users.SpaceUsage):
    @property
    def allocation_type(self) -> str:
        if self.allocation.is_team():
            return "team"
        elif self.allocation.is_individual():
            return "individual"
        else:
            return ""

    def __str__(self) -> str:

        if self.allocation.is_individual():
            used = self.used
            allocated = self.allocation.get_individual().allocated
        elif self.allocation.is_team():
            used = self.allocation.get_team().used
            allocated = self.allocation.get_team().allocated
        else:
            return self.natural_size(self.used)

        percent = used / allocated
        if percent <= 0.8:
            color = "green"
        elif percent <= 0.95:
            color = "orange"
        else:
            color = "red"
        return f'<span weight="bold" foreground="{color}">{percent:.1%} of {self.natural_size(allocated)}</span>'

    @classmethod
    def natural_size(cls, num: float, unit: str = "B", sep: bool = True) -> str:
        """
        Convert number to a human readable string with decimal prefix.
        :param float num: Value in given unit.
        :param unit: Unit suffix.
        :param sep: Whether to separate unit and value with a space.
        :returns: Human readable string with decimal prefixes.
        """
        sep_char = " " if sep else ""

        for prefix in ("", "K", "M", "G"):
            if abs(num) < 1000.0:
                return f"{num:3.1f}{sep_char}{prefix}{unit}"
            num /= 1000.0

        prefix = "T"
        return f"{num:.1f}{sep_char}{prefix}{unit}"

    @classmethod
    def from_dbx_space_usage(cls, su: dropbox.users.SpaceUsage):
        return cls(used=su.used, allocation=su.allocation)

class DropboxSpaceCheckerThread(Thread):
    def __init__(self, operation):
        super().__init__()
        self._operation = operation
    
    def run(self):
        if self._operation._dropbox:
            try:
                usage = DropboxSpaceUsage.from_dbx_space_usage(self._operation._dropbox.users_get_space_usage())
            except Exception as e:
                usage = f"error getting usage: {str(e)}"
        else:
            usage = "not available"
        GLib.idle_add(self._operation._update_space_usage, usage, priority=GLib.PRIORITY_DEFAULT_IDLE)

@with_pango_docs(filename='dropbox_uploader.pango')
class DropboxUploaderOperation(Operation):
    NAME = "Dropbox Uploader"

    SESSION = dropbox.create_session(max_connections=QueueManager.MAX_JOBS)
    CHUNK_SIZE = 1024 * 1024 # 1MB

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)

        self._dropbox = None
        self._space_thread = None

        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)

        # In the initial version, use only access-key and folder name
        self._grid.attach(Gtk.Label(
            label="Destination folder",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'destination_folder')
        self._grid.attach(widget, 1, 0, 2, 1)

        self._grid.attach(Gtk.Label(
            label="Email address",
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        self._email_entry = self.register_widget(Gtk.Entry(
            placeholder_text="Address used for registering with Dropbox",
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'email')
        self._grid.attach(self._email_entry, 1, 1, 1, 1)
        self._email_entry.connect('changed', self._email_entry_changed_cb)

        button = Gtk.Button(
            label='Validate',
            halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        )
        self._grid.attach(button, 2, 1, 1, 1)
        button.connect('clicked', self._validate_button_clicked_cb)

        self._space_label = Gtk.Label(
            label='Space Usage: not available', use_markup=True,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=True,
        )
        self._grid.attach(self._space_label, 0, 2, 3, 1)

        # check space usage every 60 seconds and update the corresponding label
        GLib.timeout_add_seconds(60, self._launch_space_usage_thread, False, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def _launch_space_usage_thread(self, kill):
        logger.debug('Calling _launch_space_usage_thread')
        space_thread = DropboxSpaceCheckerThread(self)
        space_thread.start()

        if kill:
            return GLib.SOURCE_REMOVE
        else:
            return GLib.SOURCE_CONTINUE

    def _update_space_usage(self, usage):
        self._space_label.props.label = f'Space Usage: {str(usage)}'

        return GLib.SOURCE_REMOVE

    def _email_entry_changed_cb(self, entry):
        # any changes to the email address reset the Dropbox client
        self._dropbox = None
        self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')

    def _validate_button_clicked_cb(self, button):
        # first confirm that we have a proper email address
        if not re.fullmatch(r'[^@]+@[^@]+\.[^@]+', self.params.email):
            dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text=f'{self.params.email} is not a vaild email address'
            )
            dialog.run()
            dialog.destroy()
            self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
            return
        
        # check keyring
        try:
            refresh_token = keyring.get_password('RFI-File-Monitor-Dropbox', self.params.email.lower())
        except keyring.errors.KeyringError as e:
            dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text='Error accessing keyring',
                secondary_text=str(e),
            )
            dialog.run()
            dialog.destroy()
            self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
            return

        if refresh_token:
            logger.debug(f'{refresh_token=}')
            # use refresh token to launch dropbox session
            self._dropbox = dropbox.Dropbox(
                oauth2_refresh_token=refresh_token, session=self.SESSION, app_key=APP_KEY
            )
            exc = None
            try:
                account_info = self._dropbox.users_get_current_account()
            except dropbox.exceptions.AuthError as e:
                if e.error.is_invalid_access_token():
                    logger.debug('Token has been revoked!')
                    self._dropbox = None
                    # delete keyring password
                    keyring.delete_password('RFI-File-Monitor-Dropbox', self.params.email.lower())
                    self._validate_button_clicked_cb(button)
                    return
                exc = e
            except Exception as e:
                exc = e
            if exc:
                dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                    modal=True, destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE, text='Could not get user information',
                    secondary_text=str(exc)
                )
                dialog.run()
                dialog.destroy()
                self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
                self._dropbox = None
                return

            logger.debug(f'{account_info=}')
            if account_info.email.lower() != self.params.email.lower(): 
                dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                    modal=True, destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE, text='Email address does not match Dropbox user records',
                )
                dialog.run()
                dialog.destroy()
                self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
                self._dropbox = None
            else:
                self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-default')
                GLib.idle_add(self._launch_space_usage_thread, True, priority=GLib.PRIORITY_DEFAULT_IDLE)
            return

        # without refresh token -> link app
        dbx_dialog = DropboxLinkDialog(self.appwindow)
        if dbx_dialog.run() != Gtk.ResponseType.OK:
            # not OK means that the auth flow was not started or aborted
            self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
            self._dropbox = None
            dbx_dialog.destroy()
            return
        
        authorization_code = dbx_dialog.authorization_code
        auth_flow = dbx_dialog.auth_flow
        dbx_dialog.destroy()
        try:
            res = auth_flow.finish(authorization_code)
        except Exception as e:
            dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text='Could not link RFI-File-Monitor to Dropbox',
                secondary_text=str(e)
            )
            dialog.run()
            dialog.destroy()
            self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-unreadable')
            self._dropbox = None
            return

        refresh_token = res.refresh_token
        self._dropbox = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token, session=self.SESSION, app_key=APP_KEY
        )
        self._email_entry.set_icon_from_icon_name(icon_pos=Gtk.EntryIconPosition.SECONDARY , icon_name='emblem-default')
        GLib.idle_add(self._launch_space_usage_thread, True, priority=GLib.PRIORITY_DEFAULT_IDLE)
        # save token in keyring
        try:
            keyring.set_password('RFI-File-Monitor-Dropbox', self.params.email.lower(), refresh_token)
        except keyring.errors.KeyringError as e:
            dialog = Gtk.MessageDialog(transient_for=self.appwindow,
                modal=True, destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, text='Error accessing keyring. Dropbox should still work in this session though.',
                secondary_text=str(e),
            )
            dialog.run()
            dialog.destroy()

    def preflight_check(self):
        if not self.params.destination_folder:
            raise Exception('Destination folder cannot be an empty string')

        if not self._dropbox:
            raise Exception('Validate the email address and link the Dropbox account')

        echo_user = self._dropbox.check_user('test-user')
        logger.debug(f'{echo_user=}')
        account_info = self._dropbox.users_get_current_account()
        logger.debug(f'{account_info=}')
        space_usage = self._dropbox.users_get_space_usage()
        logger.debug(f'{space_usage=}')

        # create folder and upload test file
        self._base_folder = f'/{self.params.destination_folder}'
        try:
            self._dropbox.files_create_folder_v2(self._base_folder)
        except dropbox.exceptions.ApiError:
            # an exception is thrown if the directory already exists
            pass
        test_filename = f'{self._base_folder}/test-file-{get_random_string(6)}.txt'
        self._dropbox.files_upload(b'Dummy contents', path=test_filename)

        # delete file
        self._dropbox.files_delete_v2(test_filename)

    def run(self, file: File):
        # check first if file already exists
        # if it does, then first get its size
        # if the size matches, calculate checksum.
        # if checksums match, SKIP
        # else: remove file and upload new version

        dbx_filename = str(PurePosixPath(self._base_folder, *file.relative_filename.parts))
        size = os.path.getsize(file.filename)

        try:
            metadata = self._dropbox.files_get_metadata(dbx_filename)
        except dropbox.exceptions.ApiError:
            pass
        else:
            if size == metadata.size:
                # calculate content hash of local file
                hasher = DropboxContentHasher()
                with open(file.filename, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if len(chunk) == 0:
                            break
                        hasher.update(chunk)
                if hasher.hexdigest() == metadata.content_hash:
                    raise SkippedOperation('File has already been uploaded to Dropbox')
                else:
                    # delete remote file
                    self._dropbox.files_delete_v2(dbx_filename)
            else:
                # delete remote file
                self._dropbox.files_delete_v2(dbx_filename)
        
        # the following was inspired by Maestral
        if size <= self.CHUNK_SIZE:
            # upload small file
            with open(file.filename, 'rb') as f:
                self._dropbox.files_upload(f.read(), dbx_filename)
        else:
            # upload large file
            with open(file.filename, 'rb') as f:
                session_start = self._dropbox.files_upload_session_start(f.read(self.CHUNK_SIZE))
                uploaded = f.tell()

                cursor = dropbox.files.UploadSessionCursor(
                    session_id=session_start.session_id,
                    offset=uploaded
                )
                commit = dropbox.files.CommitInfo(
                    path=dbx_filename)

                while True:
                    try:
                        if size - f.tell() <= self.CHUNK_SIZE:
                            md = self._dropbox.files_upload_session_finish(
                                f.read(self.CHUNK_SIZE),
                                cursor,
                                commit
                            )

                        else:
                            self._dropbox.files_upload_session_append_v2(
                                f.read(self.CHUNK_SIZE),
                                cursor
                            )
                            md = None

                        # housekeeping
                        uploaded = f.tell()

                        # upload progressbar
                        file.update_progressbar(self.index, 100*uploaded/size)

                        if md:
                            break
                        else:
                            cursor.offset = uploaded

                    except dropbox.exceptions.DropboxException as exc:
                        error = getattr(exc, 'error', None)
                        if (isinstance(error, dropbox.files.UploadSessionFinishError)
                                and error.is_lookup_failed()):
                            session_lookup_error = error.get_lookup_failed()
                        elif isinstance(error, dropbox.files.UploadSessionLookupError):
                            session_lookup_error = error
                        else:
                            return str(exc)

                        if session_lookup_error.is_incorrect_offset():
                            o = session_lookup_error.get_incorrect_offset().correct_offset
                            # reset position in file
                            f.seek(o)
                            cursor.offset = f.tell()
                        else:
                            return str(exc)
                            

        return None
