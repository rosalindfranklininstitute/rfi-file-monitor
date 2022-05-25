import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from datetime import datetime
from ..operation import Operation
from ..file import File
from ..files.directory import Directory
from ..files.regular_file import RegularFile
from ..utils.decorators import supported_filetypes, with_pango_docs
from pathlib import PurePath, Path, PurePosixPath
from pyscicat.client import ScicatClient
from pyscicat.model import Dataset, RawDataset, DerivedDataset
import logging
from urllib.parse import urlparse
from typing import Dict, Optional, List
from ..version import __version__ as core_version

logger = logging.getLogger(__name__)


@supported_filetypes(filetypes=(RegularFile, Directory))
@with_pango_docs(filename="scicataloguer.pango")
class SciCataloguer(Operation):
    NAME = "SciCataloguer"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)

        self._grid = Gtk.Grid(
            row_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.add(self._grid)

        # Hostname
        self._grid.attach(
            Gtk.Label(
                label=" SciCat Hostname ",
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
        self._hostname_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "hostname",
        )
        self._grid.attach(self._hostname_entry, 1, 0, 1, 1)

        # Operation upload
        self._grid.attach(
            Gtk.Label(
                label=" Upload location ",
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
        op_combo = Gtk.ComboBoxText.new()
        self.ops_list = ["S3 Uploader", "SFTP Uploader", "Dropbox Uploader"]
        for k in self.ops_list:
            op_combo.append_text(k)

        op_widget = self.register_widget(op_combo, "operation")
        self._grid.attach(op_widget, 3, 0, 1, 1)

        # Username
        self._grid.attach(
            Gtk.Label(
                label=" Username ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            1,
            1,
            1,
        )
        self._username_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "username",
        )
        self._grid.attach(self._username_entry, 1, 1, 1, 1)

        # Password
        self._grid.attach(
            Gtk.Label(
                label=" Password ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            1,
            1,
            1,
        )
        self._password_entry = self.register_widget(
            Gtk.Entry(
                visibility=False,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "password",
        )
        self._grid.attach(self._password_entry, 3, 1, 1, 1)

        # Owner
        self._grid.attach(
            Gtk.Label(
                label=" Owner ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            2,
            1,
            1,
        )
        self._owner_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "owner",
        )
        self._grid.attach(self._owner_entry, 1, 2, 1, 1)

        # Owner group
        self._grid.attach(
            Gtk.Label(
                label=" Owner Group ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            2,
            1,
            1,
        )
        self._owner_grp_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "owner_group",
        )
        self._grid.attach(self._owner_grp_entry, 3, 2, 1, 1)

        # Comtact email
        self._grid.attach(
            Gtk.Label(
                label=" Email ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            3,
            1,
            1,
        )
        self._email_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "email",
        )
        self._grid.attach(self._email_entry, 1, 3, 1, 1)

        # Orcid
        self._grid.attach(
            Gtk.Label(
                label=" Orcid ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            3,
            1,
            1,
        )
        self._orcid_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "orcid",
        )
        self._grid.attach(self._orcid_entry, 3, 3, 1, 1)

        # PI
        self._grid.attach(
            Gtk.Label(
                label=" Principal Investigator ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            4,
            1,
            1,
        )
        self._pi_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "investigator",
        )
        self._grid.attach(self._pi_entry, 1, 4, 1, 1)

        # Dataset name
        self._grid.attach(
            Gtk.Label(
                label=" Experiment name ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            4,
            1,
            1,
        )
        self._exp_name_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "experiment_name",
        )
        self._grid.attach(self._exp_name_entry, 3, 4, 1, 1)

        # Instrument
        # TO DO - this is temporary until instrument preferences configured
        self._grid.attach(
            Gtk.Label(
                label=" Instrument ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            5,
            1,
            1,
        )
        self._instrument_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "instrument_choice",
        )
        self._grid.attach(self._instrument_entry, 1, 5, 1, 1)

        # Technique
        self._grid.attach(
            Gtk.Label(
                label=" Technique ",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            5,
            1,
            1,
        )
        self._technique_entry = self.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "technique",
        )
        self._grid.attach(self._technique_entry, 3, 5, 1, 1)

        # Input boxes for derived dataset specific fields
        self._grid.attach(
            Gtk.Label(
                label=" Input Datasets ",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            7,
            1,
            1,
        )

        self._input_datasets_entry = self.register_widget(
            Gtk.Entry(
                placeholder_text="e.g. /testdir/testfile.txt, /folder/file.csv",
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "input_datasets",
        )
        self._grid.attach(self._input_datasets_entry, 1, 7, 1, 1)

        self._grid.attach(
            Gtk.Label(
                label=" Used Software ",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
                sensitive=True,
            ),
            2,
            7,
            1,
            1,
        )
        self._used_software_entry = self.register_widget(
            Gtk.Entry(
                placeholder_text="e.g. relion, https://github.com/SciCatProject/pyscicat",
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=False,
            ),
            "used_software",
        )
        self._grid.attach(self._used_software_entry, 3, 7, 1, 1)

        self._derived_checkbox = Gtk.CheckButton(label="Derived Dataset")
        self._derived_checkbox.connect("toggled", self.checkbox_toggled)
        self.params.derived_dataset = self.checkbox_toggled(
            self._derived_checkbox
        )
        self._grid.attach(self._derived_checkbox, 0, 6, 1, 1)

    # Makes input datasets/used software boxes editable if dataset is derived
    def checkbox_toggled(self, checkbox):
        # Set class attribute for derived/raw dataset
        if checkbox.get_active() == True:
            self.params.derived_dataset = True
            self._input_datasets_entry.set_sensitive(True)
            self._used_software_entry.set_sensitive(True)
            return True
        elif checkbox.get_active() == False:
            self.params.derived_dataset = False
            self._input_datasets_entry.set_sensitive(False)
            self._used_software_entry.set_sensitive(False)
            return False

    @staticmethod
    def _check_required_fields(params):
        if not params.hostname:
            raise RequiredInfoNotFound("SciCat hostname required")
        if not params.username or not params.password:
            raise RequiredInfoNotFound("SciCat login information required")
        if not params.email:
            raise RequiredInfoNotFound("Contact Email required")
        if not params.investigator:
            raise RequiredInfoNotFound("Principal Investigator required")
        if not params.owner:
            raise RequiredInfoNotFound("Owner required")
        if not params.owner_group:
            raise RequiredInfoNotFound("Owner group required")

    def preflight_check(self):
        self._preflight_check(self.params)

    def _preflight_check(self, params):
        self._check_required_fields(params)
        try:
            ScicatClient(
                base_url=params.hostname,
                username=params.username,
                password=params.password,
            )
        except Exception as e:
            raise Exception(f"Could not login to scicat: {e}")

        self.operations_list = [
            op.get_child().NAME
            for op in self._appwindow._operations_box.get_children()
        ]
        # Check that either upload operation selected
        if not any(
            "Uploader" in operation for operation in self.operations_list
        ):
            raise RequiredInfoNotFound(
                "This operation requires an upload operation. Please select one."
            )

        # Check that a technique has been selected for instruments that might have more than one technique
        if not params.technique:
            raise RequiredInfoNotFound(
                "Please name a technique for this instrument."
            )

    def run(self, file: File):
        self.params.keywords = []
        # This can be added manually in future? TO DO
        self.params.additional_metadata = {}
        return self._run(file, self.params)

    def _run(self, file: File, params):

        # Create the payload
        payload = self.create_payload(file, params)
        try:
            try:
                scicat_session = ScicatClient(
                    base_url=params.hostname,
                    username=params.username,
                    password=params.password,
                )
            except Exception as e:
                raise Exception(f"Could not login to scicat: {e}")
            self.upsert_payload(payload, scicat_session)
        except Exception as e:
            raise Exception(f"Scicataloger.run exception")
        else:
            return None

    # Creates payload to send to scicat
    def create_payload(self, file, params):
        # Extract host information
        host_info = PayloadHelpers.get_host_location(
            file, self.operations_list, params.operation
        )

        # Base payload with required fields
        default_payload = Payload(
            sourceFolder=host_info["sourceFolder"],
            sourceFolderHost=host_info["sourceFolderHost"],
            owner=params.owner,
            contactEmail=params.email,
            orcidOfOwner=params.orcid,
            ownerGroup=params.owner_group,
            accessGroups=[],
            techniques=[{"name": params.technique}],
            creationTime="",
            keywords=params.keywords,
        )

        # Add in Directory/File specific payload details
        if isinstance(file, Directory):
            data_format = "directory"
            default_payload = self.is_dir_payload(default_payload, file)
        elif isinstance(file, RegularFile):
            fppath = PurePath(file.filename)
            data_format = fppath.suffix
            default_payload = self.is_file_payload(default_payload, file)

        # Modify base into raw or derived payload
        if params.derived_dataset:
            default_payload.type = "derived"
            payload = DerivedPayload(**default_payload.dict())
            payload = self.is_derived_payload(payload)
        else:
            payload = RawPayload(**default_payload.dict())
            payload = self.is_raw_payload(payload, data_format)

        # Remove unneeded metadata defaults
        del payload.scientificMetadataDefaults
        return payload

    # Adds file specific payload data
    def is_file_payload(self, _pl, file):
        _pl.datasetName = (
            self.params.experiment_name
            + "/"
            + str(PurePosixPath(file.relative_filename))
        )
        fstats = Path(file.filename).stat()
        _pl.size = fstats.st_size

        # Scientific metadata
        scientificMetadata = {}
        _pl.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata,
                _pl.scientificMetadataDefaults,
                self.params.additional_metadata,
            )
        )

        _pl.creationTime = (
            datetime.fromtimestamp(
                Path(file.filename).stat().st_ctime
            ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z"
        )
        return _pl

    # Adds directory specific payload data
    def is_dir_payload(self, _pl, file):
        _pl.datasetName = (
            self.params.experiment_name
            + "/"
            + str(file.relative_filename.parts[-1])
        )
        _pl.size = file._total_size
        _pl.numberOfFiles = len(file._filelist)

        # Scientific metadata
        scientificMetadata: Dict[str, Dict[str, str]] = {}
        _pl.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata,
                _pl.scientificMetadataDefaults,
                self.params.additional_metadata,
            )
        )

        _pl.creationTime = (
            datetime.fromtimestamp(file._filelist_timestamp).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3]
            + "Z"
        )

        return _pl

    # Adds raw dataset specific data
    def is_raw_payload(self, _pl, _data_format):
        _pl.creationLocation = str(self.params.instrument_choice)
        _pl.principalInvestigator = self.params.investigator
        _pl.endTime = _pl.creationTime
        _pl.dataFormat = _data_format
        return _pl

    # Adds derived dataset specific data
    def is_derived_payload(self, _pl):
        _pl.investigator = self.params.investigator
        _pl.inputDatasets = self.params.input_datasets.split(",")
        _pl.usedSoftware = self.params.used_software.split(",")
        return _pl

    # Inserts a dataset into Scicat
    def insert_payload(self, payload, scicat_session):
        try:
            r = scicat_session.upload_dataset(payload)
            if r:
                logger.info(f"Payload catalogued, PID: {r}")
        except Exception as e:
            raise Exception(
                f"Could not catalogue payload in scicat: {e}"
            )

    # Upserts dataset in Scicat
    # This won't work with upserting until features added into PySciCat
    def upsert_payload(self, payload, scicat_session):
        # Ensure that raw/derived datasets don't overwrite each other
        query_results = scicat_session.get_datasets(
            {"datasetName": payload.datasetName, "type": payload.type}
        )
        if query_results:
            if query_results[0]["datasetName"] == payload.datasetName:
                logger.info("pretending to upsert payload")
                # try:
                # if payload.type == "raw":
                # r = scicat_session.upsert_raw_dataset(payload, {"datasetName": payload.datasetName, "type": payload.type})
                # else:
                # r = scicat_session.upsert_derived_dataset(payload, {"datasetName": payload.datasetName, "type": payload.type})
                # if r:
                #    logger.info(f"Payload upserted, PID: {r}")
                # except Exception as e:
                #   raise Exception(f"Could not catalogue payload in scicat: {e}")
                #   return str(e)
            else:
                self.insert_payload(payload, scicat_session)
        else:
            self.insert_payload(payload, scicat_session)


# Base Payload Model inherits from Dataset Model
class Payload(Dataset):
    type: Optional[str] = "raw"
    datasetlifecycle = {"retrievable": True}
    scientificMetadata = {}
    scientificMetadataDefaults = {}
    scientificMetadataDefaults["RFI File Monitor Version"] = {
        "type": "string",
        "value": core_version,
        "unit": "",
    }


# Extends Payload for raw data
class RawPayload(RawDataset, Payload):
    dataFormat: Optional[str]


# Extends Payload for derived data
class DerivedPayload(DerivedDataset, Payload):
    inputDatasets: Optional[List[str]]
    usedSoftware: Optional[List[str]]


class PayloadHelpers:
    @classmethod
    def get_host_location(cls, file: File, operations_list, operation):
        """method used in payload to get source folder host"""
        # Ceph Uploader must always be included to use the Scicataloguer, therefore the location must be the ceph location.

        # TO DO - do we want to change from just checking for s3 url?
        operation_ind = operations_list.index(operation)
        url_split = None
        if isinstance(file, RegularFile):
            url_split = urlparse(
                file.operation_metadata[operation_ind]["s3 object url"]
            )
        elif isinstance(file, Directory):
            for value in file.operation_metadata[operation_ind].values():
                if "s3 object url" in value:
                    url_split = urlparse(value["s3 object url"])
                    break  # only need top entry for dir

        source_folders = {}
        if url_split:  # file metadata is not there if rerunning saved dirs
            source_folders["sourceFolderHost"] = (
                url_split.scheme + "://" + url_split.netloc
            )
            if isinstance(file, RegularFile):
                source_folders["sourceFolder"] = url_split.path.strip("/")
            elif isinstance(file, Directory):
                path_obj = PurePath(url_split.path)
                source_folders["sourceFolder"] = path_obj.relative_to(
                    path_obj.root
                ).parts[0]

        return source_folders

    @classmethod
    def scientific_metadata_concatenation(
        cls, scientific_metadata, defaults, additional
    ):
        scientific_metadata |= defaults
        scientific_metadata |= additional
        return scientific_metadata


class ParserNotFound(Exception):
    """Metadata parser not found"""

    pass


class RequiredInfoNotFound(Exception):
    """Info required in Scicat Payload not found"""

    pass
