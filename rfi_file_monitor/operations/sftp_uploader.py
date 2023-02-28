import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
import paramiko
from munch import Munch
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_log,
    after_log,
    before_sleep_log,
)

from ..operation import Operation
from ..utils.exceptions import SkippedOperation
from ..file import File
from ..files.regular_file import RegularFile
from ..files.directory import Directory
from ..utils import monitor_retry_condition
from ..utils.decorators import (
    with_pango_docs,
    supported_filetypes,
    add_directory_support,
)

import logging
import os
import tempfile
from pathlib import PurePosixPath, Path
import stat
import posixpath
from typing import List
from threading import RLock

logger = logging.getLogger(__name__)


@with_pango_docs(filename="sftp_uploader.pango")
@supported_filetypes(filetypes=(RegularFile, Directory))
class SftpUploaderOperation(Operation):

    NAME = "SFTP Uploader"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)
        self._grid = Gtk.Grid(
            border_width=5,
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
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
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 0, 1, 1)
        tempgrid.attach(
            Gtk.Label(
                label="Hostname",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "hostname",
        )
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Port
        tempgrid.attach(
            Gtk.Label(
                label="Port",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            0,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.SpinButton(
                adjustment=Gtk.Adjustment(
                    lower=1, upper=10000, value=5, page_size=0, step_increment=1
                ),
                value=22,
                update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
                numeric=True,
                climb_rate=5,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "port",
        )
        tempgrid.attach(widget, 3, 0, 1, 1)

        # Username
        tempgrid = Gtk.Grid(
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 1, 1, 1)
        tempgrid.attach(
            Gtk.Label(
                label="Username",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "username",
        )
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Password
        tempgrid.attach(
            Gtk.Label(
                label="Password",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            0,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.Entry(
                visibility=False,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "password",
            exportable=False,
        )
        tempgrid.attach(widget, 3, 0, 1, 1)

        # Remote directory
        tempgrid = Gtk.Grid(
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 2, 1, 1)
        tempgrid.attach(
            Gtk.Label(
                label="Destination folder",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            0,
            1,
            1,
        )
        widget = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "destination",
        )
        tempgrid.attach(widget, 1, 0, 1, 1)

        # Create directory
        widget = self.register_widget(
            Gtk.CheckButton(
                active=True,
                label="Create destination folder if necessary",
                halign=Gtk.Align.END,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "force_folder_creation",
        )
        tempgrid.attach(widget, 2, 0, 1, 1)

        # Automatically accept new host keys
        tempgrid = Gtk.Grid(
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 3, 1, 1)
        widget = self.register_widget(
            Gtk.CheckButton(
                active=False,
                label="Automatically accept new host keys (dangerous!!)",
                halign=Gtk.Align.END,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            "auto_add_keys",
        )
        tempgrid.attach(widget, 0, 0, 1, 1)

        # Advanced options expander
        advanced_options = Gtk.Expander(
            label="Advanced Options",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(advanced_options, 0, 4, 1, 1)

        advanced_options_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            row_spacing=5,
            column_spacing=5,
        )
        advanced_options.add(advanced_options_grid)

        advanced_options_grid.attach(
            self._get_chmod_grid("file", "644"), 0, 0, 1, 1
        )
        advanced_options_grid.attach(
            self._get_chmod_grid("directory", "755"), 1, 0, 1, 1
        )

    def _get_chmod_grid(self, kind: str, default_octal: str):
        permissions = (
            (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
            (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
            (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH),
        )

        default_octal_as_int = int(default_octal, base=8)

        chmod_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            row_spacing=5,
            column_spacing=5,
        )

        title_grid = Gtk.Grid(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
            row_spacing=5,
            column_spacing=5,
        )
        chmod_grid.attach(title_grid, 0, 0, 4, 1)
        chmod_grid._checkbutton = self.register_widget(
            Gtk.CheckButton(
                label=f"<b>Override {kind} UNIX permissions</b>",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            f"{kind}_chmod_enabled",
        )
        chmod_grid._checkbutton.get_child().props.use_markup = True
        title_grid.attach(chmod_grid._checkbutton, 0, 0, 1, 1)

        chmod_grid._entry = self.register_widget(
            Gtk.Entry(
                editable=False,
                text=default_octal,
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            f"{kind}_chmod_octal",
        )
        chmod_grid._entry_handler_id = chmod_grid._entry.connect(
            "changed", self._chmod_grid_entry_changed_cb, chmod_grid
        )
        title_grid.attach(chmod_grid._entry, 1, 0, 1, 1)

        label = Gtk.Label(
            label="<b>Read</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 1, 1, 1, 1)
        label = Gtk.Label(
            label="<b>Write</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 2, 1, 1, 1)
        label = Gtk.Label(
            label="<b>Execute</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 3, 1, 1, 1)

        label = Gtk.Label(
            label="<b>User</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 0, 2, 1, 1)
        label = Gtk.Label(
            label="<b>Group</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 0, 3, 1, 1)
        label = Gtk.Label(
            label="<b>Others</b>",
            use_markup=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        chmod_grid.attach(label, 0, 4, 1, 1)

        for i in range(3):
            for j in range(3):
                check_button = Gtk.CheckButton(
                    halign=Gtk.Align.CENTER,
                    valign=Gtk.Align.CENTER,
                    hexpand=True,
                    vexpand=False,
                )
                chmod_grid.attach(check_button, j + 1, i + 2, 1, 1)
                check_button._permission = permissions[i][j]
                check_button._handler_id = check_button.connect(
                    "clicked",
                    self._chmod_grid_check_button_clicked_cb,
                    chmod_grid,
                )
                if check_button._permission & default_octal_as_int:
                    with check_button.handler_block(check_button._handler_id):
                        check_button.props.active = True

        return chmod_grid

    def _chmod_grid_check_button_clicked_cb(self, button, chmod_grid):
        # get entry value as int
        octal = int(chmod_grid._entry.props.text.strip(), base=8)

        if button.props.active:
            octal |= button._permission
        else:
            octal &= ~button._permission

        # update entry
        with chmod_grid._entry.handler_block(chmod_grid._entry_handler_id):
            chmod_grid._entry.props.text = f"{octal:03o}"

    def _chmod_grid_entry_changed_cb(self, entry, chmod_grid):
        # this method will only be called when loading from yaml
        # get entry value as int
        octal = int(chmod_grid._entry.props.text.strip(), base=8)

        for child in chmod_grid:
            if hasattr(child, "_permission"):
                # block the clicked handler to avoid signal loop
                with child.handler_block(child._handler_id):
                    child.props.active = octal & child._permission

    @classmethod
    def _preflight_check(cls, params: Munch):
        # try connecting to server and copy a simple file
        with paramiko.Transport(
            (params.hostname, int(params.port))
        ) as transport:

            transport.connect(
                username=params.username,
                password=params.password,
            )
            folder_created = False
            with paramiko.SFTPClient.from_transport(transport) as sftp_client:
                try:
                    sftp_client.chdir(params.destination)
                except IOError:
                    if params.force_folder_creation:
                        makedirs(sftp_client, params.destination)
                        if params.directory_chmod_enabled:
                            sftp_client.chmod(
                                params.destination,
                                int(params.directory_chmod_octal, base=8),
                            )
                        folder_created = True
                    else:
                        raise
                # cd back to home folder
                sftp_client.chdir()

                # try copying a file
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(os.urandom(1024))  # 1 kB
                    tmpfile = f.name
                file_destination = (
                    params.destination + "/" + os.path.basename(tmpfile)
                )
                try:
                    sftp_client.put(tmpfile, file_destination)
                except:
                    if folder_created:
                        sftp_client.rmdir(params.destination)
                    raise
                else:
                    try:
                        if params.file_chmod_enabled:
                            sftp_client.chmod(
                                file_destination,
                                int(params.file_chmod_octal, base=8),
                            )
                    except:
                        # cleanup
                        sftp_client.remove(file_destination)
                        if folder_created:
                            sftp_client.rmdir(params.destination)
                        raise
                    else:
                        # if successful, remove it
                        sftp_client.remove(file_destination)
                finally:
                    os.unlink(tmpfile)

    def preflight_check(self):
        self._processed_dirs: List[str] = []
        self._processed_dirs_lock: RLock = RLock()
        self._preflight_check(self.params)

    @classmethod
    def _attach_metadata(
        cls,
        file: File,
        remote_filename_full: str,
        params: Munch,
        operation_index: int,
    ):
        file.operation_metadata[operation_index] = {
            "sftp url": f"sftp://{params.username}@{params.hostname}:{int(params.port)}{remote_filename_full}"
        }

    @classmethod
    @retry(
        retry=monitor_retry_condition(),
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
    )
    def _run(
        cls,
        file: File,
        params: Munch,
        operation_index: int,
        processed_dirs: List[str],
        processed_dirs_lock: RLock,
    ):
        try:
            with paramiko.Transport(
                (params.hostname, int(params.port))
            ) as transport:

                transport.connect(
                    username=params.username,
                    password=params.password,
                )

                with paramiko.SFTPClient.from_transport(
                    transport
                ) as sftp_client:
                    sftp_client.chdir(params.destination)
                    rel_filename = str(
                        PurePosixPath(*file.relative_filename.parts)
                    )
                    dirname = posixpath.dirname(rel_filename)
                    with processed_dirs_lock:
                        if dirname not in processed_dirs:
                            if not isdir(sftp_client, dirname):
                                makedirs(sftp_client, dirname)

                                if params.directory_chmod_enabled:
                                    sftp_client.chmod(
                                        dirname,
                                        int(
                                            params.directory_chmod_octal, base=8
                                        ),
                                    )

                            processed_dirs.append(dirname)

                    # check if file already exists
                    # Note: ideally this would be done by calculating the checksum
                    # on the server, but very few SSH server implementations support
                    # this protocol extension, even though Paramiko does:
                    # http://docs.paramiko.org/en/stable/api/sftp.html#paramiko.sftp_file.SFTPFile.check
                    try:
                        remote_stat = sftp_client.stat(rel_filename)
                    except IOError:
                        pass
                    else:
                        # file exists -> compare with local stat
                        local_stat = Path(file.filename).stat()
                        # if local file is more recent or size differs -> upload again!
                        if (
                            local_stat.st_size == remote_stat.st_size
                            and local_stat.st_mtime <= remote_stat.st_mtime
                        ):
                            # add object URL to metadata
                            remote_filename_full = sftp_client.normalize(
                                rel_filename
                            )
                            cls._attach_metadata(
                                file,
                                remote_filename_full,
                                params,
                                operation_index,
                            )
                            raise SkippedOperation(
                                "File has been uploaded already"
                            )

                    # upload the file to the remote server
                    sftp_client.put(
                        file.filename,
                        rel_filename,
                        callback=SftpProgressPercentage(file, operation_index),
                    )
                    if params.file_chmod_enabled:
                        sftp_client.chmod(
                            rel_filename, int(params.file_chmod_octal, base=8)
                        )
                    remote_filename_full = sftp_client.normalize(rel_filename)
        except SkippedOperation:
            raise
        except Exception as e:
            logger.exception(f"SftpUploaderOperation.run exception")
            return str(e)
        else:
            # add object URL to metadata
            cls._attach_metadata(
                file, remote_filename_full, params, operation_index
            )
        return None

    @add_directory_support
    def run(self, file: File):
        return self._run(
            file,
            self.params,
            self.index,
            self._processed_dirs,
            self._processed_dirs_lock,
        )


class SftpProgressPercentage(object):
    def __init__(self, file: File, operation_index: int):
        self._file = file
        self._last_percentage = 0
        self._operation_index = operation_index

    def __call__(self, bytes_so_far: int, bytes_total: int):
        percentage = (bytes_so_far / bytes_total) * 100
        if int(percentage) > self._last_percentage:
            self._last_percentage = int(percentage)
            self._file.update_progressbar(
                self._operation_index, self._last_percentage
            )


# the following methods have been inspired by pysftp
def isdir(sftp_client: paramiko.SFTPClient, remotepath: str):
    try:
        return stat.S_ISDIR(sftp_client.stat(remotepath).st_mode)
    except IOError:  # no such file
        return False


def isfile(sftp_client: paramiko.SFTPClient, remotepath: str):
    try:
        return stat.S_ISREG(sftp_client.stat(remotepath).st_mode)
    except IOError:  # no such file
        return False


def makedirs(sftp_client: paramiko.SFTPClient, remotedir: str, mode="777"):
    if isdir(sftp_client, remotedir):
        pass
    elif isfile(sftp_client, remotedir):
        raise OSError(
            f"a file with the same name as the remotedir {remotedir} already exists"
        )
    else:
        head, tail = posixpath.split(remotedir)
        if head and not isdir(sftp_client, head):
            makedirs(sftp_client, head, mode)
        if tail:
            sftp_client.mkdir(remotedir, mode=int(mode, 8))
