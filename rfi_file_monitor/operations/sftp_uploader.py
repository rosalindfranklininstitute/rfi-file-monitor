import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import paramiko
from paramiko import AutoAddPolicy, RejectPolicy
from munch import Munch

from ..operation import Operation
from ..file import File

import logging
import os
import tempfile
from pathlib import PurePosixPath
from stat import S_ISDIR, S_ISREG
import posixpath

logger = logging.getLogger(__name__)

class SftpUploaderOperation(Operation):
    NAME = "SFTP Uploader"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self.add(self._grid)

        # we need boxes for at least
        # hostname
        # port
        # username
        # password
        # auto add new host keys
        # remote directory
        # create remote directory if necessary

        # Hostname
        tempgrid = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False
        )
        self._grid.attach(tempgrid, 0, 0 , 1, 1)
        tempgrid.attach(Gtk.Label(
            label='Hostname',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'hostname')
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Port
        tempgrid.attach(Gtk.Label(
            label='Port',
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 2, 0, 1, 1)
        widget = self.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=1,
                upper=10000,
                value=5,
                page_size=0,
                step_increment=1),
            value=22,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=5,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'port')
        tempgrid.attach(widget, 3, 0, 1, 1)

        # Username
        tempgrid = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 1, 1, 1)
        tempgrid.attach(Gtk.Label(
            label='Username',
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'username')
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Password
        tempgrid.attach(Gtk.Label(
            label='Password',
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 2, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            visibility=False,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'password', exportable=False)
        tempgrid.attach(widget, 3, 0, 1, 1)

        # Remote directory
        tempgrid = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 2, 1, 1)
        tempgrid.attach(Gtk.Label(
            label='Destination folder',
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        widget = self.register_widget(Gtk.Entry(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'destination')
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Create directory
        widget = self.register_widget(Gtk.CheckButton(
            active=True, label="Create destination folder if necessary",
            halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 'force_folder_creation')
        tempgrid.attach(widget, 2, 0, 1, 1)

        # Automatically accept new host keys
        tempgrid = Gtk.Grid(
            row_spacing=5, column_spacing=5,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 3, 1, 1)
        widget = self.register_widget(Gtk.CheckButton(
            active=False, label="Automatically accept new host keys (dangerous!!)",
            halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 'auto_add_keys')
        tempgrid.attach(widget, 0, 0, 1, 1)

    @classmethod
    def _preflight_check(cls, params: Munch):
        # try connecting to server and copy a simple file
        logger.debug(f"Try opening an ssh connection to {params.hostname}")
        with paramiko.SSHClient() as client:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(AutoAddPolicy if params.auto_add_keys else RejectPolicy)
            client.connect(params.hostname,
                port=int(params.port),
                username=params.username,
                password=params.password,
                )
            logger.debug(f"Try opening an sftp connection to {params.hostname}")
            with client.open_sftp() as sftp_client:
                try:
                    sftp_client.chdir(params.destination)
                except IOError:
                    if params.force_folder_creation:
                        makedirs(sftp_client, params.destination)
                    else:
                        raise
                # cd back to home folder
                sftp_client.chdir()

                # try copying a file
                logger.debug(f"Try uploading a test file to {params.destination}")
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(os.urandom(1024)) # 1 kB
                    tmpfile = f.name
                try:
                    sftp_client.put(tmpfile, params.destination + '/' + os.path.basename(tmpfile))
                except:
                    raise
                else:
                    # if successful, remove it
                    sftp_client.remove(params.destination + '/' + os.path.basename(tmpfile))
                finally:
                    os.unlink(tmpfile)

    def preflight_check(self):
        self._preflight_check(self.params)

    @classmethod
    def _run(cls, file: File, params: Munch, operation_index: int):
        try:
            with paramiko.SSHClient() as client:
                client.load_system_host_keys()
                client.set_missing_host_key_policy(AutoAddPolicy if params.auto_add_keys else RejectPolicy)
                client.connect(params.hostname,
                    port=int(params.port),
                    username=params.username,
                    password=params.password,
                    )
                logger.debug(f"Try opening an sftp connection to {params.hostname}")
                with client.open_sftp() as sftp_client:
                    sftp_client.chdir(params.destination)
                    rel_filename = str(PurePosixPath(*file.relative_filename.parts))
                    makedirs(sftp_client, posixpath.dirname(rel_filename))
                    sftp_client.put(file.filename, rel_filename, callback=SftpProgressPercentage(file, operation_index))
                    remote_filename_full = sftp_client.normalize(rel_filename)
                    logger.debug(f"File {remote_filename_full} has been written")
        except Exception as e:
            logger.exception(f'SftpUploaderOperation.run exception')
            return str(e)
        else:
            #add object URL to metadata
            file.operation_metadata[operation_index] = {'sftp url':
                f'sftp://{params.username}@{params.hostname}:{int(params.port)}{remote_filename_full}'}
            logger.debug(f"{file.operation_metadata[operation_index]=}")
        return None

    def run(self, file: File):
        return self._run(file, self.params, self.index)


class SftpProgressPercentage(object):

    def __init__(self, file: File, operation_index: int):
        self._file = file
        self._last_percentage = 0
        self._operation_index = operation_index

    def __call__(self, bytes_so_far: int, bytes_total: int):
        percentage = (bytes_so_far / bytes_total) * 100
        if int(percentage) > self._last_percentage:
            self._last_percentage = int(percentage)
            self._file.update_progressbar(self._operation_index, self._last_percentage)


# the following methods have been inspired by pysftp
def isdir(sftp_client: paramiko.SFTPClient, remotepath: str):
    try:
        return S_ISDIR(sftp_client.stat(remotepath).st_mode)
    except IOError: # no such file
        return False

def isfile(sftp_client: paramiko.SFTPClient, remotepath: str):
    try:
        return S_ISREG(sftp_client.stat(remotepath).st_mode)
    except IOError: # no such file
        return False

def makedirs(sftp_client: paramiko.SFTPClient, remotedir: str, mode=777):
    if isdir(sftp_client, remotedir):
        pass
    elif isfile(sftp_client, remotedir):
        raise OSError(f'a file with the same name as the remotedir {remotedir} already exists')
    else:
        head, tail = posixpath.split(remotedir)
        if head and not isdir(sftp_client, head):
            makedirs(sftp_client, head, mode)
        if tail:
            sftp_client.mkdir(remotedir, mode=int(str(mode), 8))
        