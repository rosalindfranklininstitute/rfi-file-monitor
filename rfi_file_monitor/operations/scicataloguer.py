import gi
from numpy import isin

from rfi_file_monitor.operations.s3_uploader import S3UploaderOperation

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
from ..operation import Operation
from ..utils import query_metadata, TimeoutHTTPAdapter
from ..file import File
from ..files.directory import Directory
from ..files.regular_file import RegularFile
from ..preferences import Preference
from ..utils.decorators import supported_filetypes, with_pango_docs
from ..queue_manager import QueueManager
from munch import Munch
from pathlib import PurePath, Path, PurePosixPath
from pyscicat.client import ScicatClient
from pyscicat.model import Dataset, RawDataset, DerivedDataset
import importlib.metadata
import importlib
import os
import json
import logging
from urllib.parse import urlparse
from typing import Dict, Any, Optional, List
from ..version import __version__ as core_version

logger = logging.getLogger(__name__)


@supported_filetypes(filetypes=(RegularFile, Directory))
@with_pango_docs(filename="scicataloguer.pango")
class SciCataloguer(Operation):
    NAME = "SciCataloguer"

    def __init__(self, *args, **kwargs):
        Operation.__init__(self, *args, **kwargs)

        current_app = Gio.Application.get_default()
        instrument_prefs: Munch[
            Preference, Any
        ] = current_app.get_preferences().settings
        # TO DO - handle instrument dict later
        # self.instrument_choice = instrument_prefs[InstrumentSetup]
        # self.instr_dict = InstrumentSetup.values[self.instrument_choice]

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
                label="Upload location ",
                halign=Gtk.Align.START,
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
        self.ops_list = ["S3 Uploader", "SFTP Uploader"]
        for k in self.ops_list:
            op_combo.append_text(k)

        op_widget = self.register_widget(op_combo, "operations")
        self._grid.attach(op_widget, 3, 0, 1, 1)

        # Username
        self._grid.attach(
            Gtk.Label(
                label="Username",
                halign=Gtk.Align.START,
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
                label="Password",
                halign=Gtk.Align.START,
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
                label="Owner",
                halign=Gtk.Align.START,
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
                label="Owner Group",
                halign=Gtk.Align.START,
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
                label="Email",
                halign=Gtk.Align.START,
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
                label="Orcid",
                halign=Gtk.Align.START,
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
                label="Principal Investigator",
                halign=Gtk.Align.START,
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

        """
        self._grid.attach(
            Gtk.Label(
                label="Technique",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            4,
            1,
            1,
        )
        

        # create combo box
        
        combo = Gtk.ComboBoxText.new()
        for k in self.instr_dict["techniques"].keys():
            combo.append_text(k)
        if len(self.instr_dict["techniques"].keys()) == 1:
            combo.set_active(0)

        widget = self.register_widget(combo, "technique")
        self._grid.attach(widget, 1, 4, 1, 1)

        self.parser_list = []
        for e in importlib.metadata.entry_points()[
            "rfi_file_monitor_extensions.metadataparsers"
        ]:
            self.parser_list.append(e.load())
        """

        # Dataset name
        self._grid.attach(
            Gtk.Label(
                label="Experiment name",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            5,
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
        self._grid.attach(self._exp_name_entry, 1, 5, 1, 1)

        # Technique
        # TO DO This should really come from instrument dict somehow...
        self._grid.attach(
            Gtk.Label(
                label="Technique",
                halign=Gtk.Align.START,
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
                label="Input Datasets",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            6,
            1,
            1,
        )

        input_datasets_entry = Gtk.Entry(
            placeholder_text="e.g. /testdir/testfile.txt, /folder/file.csv",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        input_datasets_entry.connect("changed", self.input_datasets_changed)
        self._grid.attach(input_datasets_entry, 1, 6, 1, 1)

        self._grid.attach(
            Gtk.Label(
                label="Used Software",
                halign=Gtk.Align.START,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            6,
            1,
            1,
        )

        used_software_entry = Gtk.Entry(
            placeholder_text="e.g. relion, https://github.com/SciCatProject/pyscicat",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        used_software_entry.connect("changed", self.used_software_changed)
        self._grid.attach(used_software_entry, 3, 6, 1, 1)

                # create checkbox for raw/derived dataset option
        self._derived_checkbox = self.register_widget(
            Gtk.CheckButton(label="Derived Dataset"), "derived_dataset"
        )
        self._grid.attach(self._derived_checkbox, 4, 6, 1, 1)

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

    """    
    def checkbox_toggled(self, checkbox):
        # Set class attribute for derived/raw dataset
        if checkbox.get_active() == True:
            self.derived_dataset = True
            return True
        elif checkbox.get_active() == False:
            self.derived_dataset = False
            return False"""

    def input_datasets_changed(self, input_datasets_entry):
        input_text = input_datasets_entry.get_text()
        self.input_datasets = input_text.split(",")
        return

    def used_software_changed(self, used_software_entry):
        input_text = used_software_entry.get_text()
        self.used_software = input_text.split(",")
        return

    def preflight_check(self):

        try:
            r = ScicatClient(
                base_url=self.params.hostname,
                username=self.params.username,
                password=self.params.password,
            )
        except Exception as e:
            logger.error(f"Could not login to scicat: {e}")

        # check that metadata requirements are met
        # TO DO - no session starter info?
        self.session_starter_info = query_metadata(
            self.appwindow.preflight_check_metadata, "orcid", full_dict=True
        )
        # TO DO - do we want to keep session starter info
        self._check_required_fields(self.params)

        self.operations_list = [
            op.get_child().NAME
            for op in self._appwindow._operations_box.get_children()
        ]
        # Check that either s3/sftp operation selected
        if not "S3 Uploader" in self.operations_list or not "SFTP Uploader" in self.operations_list:
            raise RequiredInfoNotFound(
                "This operation requires an upload operation. Please select either S3 or SFTP uploader operations."
            )

        # Check that a technique has been selected for instruments that might have more than one technique
        # TO DO 
        if not self.params.technique:
            raise RequiredInfoNotFound(
                "Please select a technique for this instrument from the drop down list"
            )

    def run(self, file: File):

        # Create the payload
        payload = self.create_payload(file)
        try:
            try:
                scicat_session = ScicatClient(
                    base_url=self.params.hostname,
                    username=self.params.username,
                    password=self.params.password,
                )
            except Exception as e:
                logger.error(f"Could not login to scicat: {e}")
                return str(e)
            self.upsert_payload(payload, scicat_session)
        except Exception as e:
            logger.exception(f"Scicataloger.run exception")
            return str(e)
        else:
            return None

    def create_payload(self, file):
        # Extract relevant fields before initialising Payload
        host_info = PayloadHelpers.get_host_location(file, self.operations_list, self.params.operation)
        #if "access groups" in self.instr_dict:
        #    access_groups = self.instr_dict["access groups"]
        #else:
        #    access_groups = []
        access_groups = []

        # INFO - creation time is necessary for initialising Payload
        # also need to ensure only raw types have data format
        if isinstance(file, Directory):
            date_method = file._filelist_timestamp
            data_format = "directory"
        elif isinstance(file, RegularFile):
            date_method = Path(file.filename).stat().st_ctime
            fppath = PurePath(file.filename)
            data_format = fppath.suffix

        # Create Base payload with required fields
        # TO DO - don't have session starter, or technique
        default_payload = Payload(
            type="raw",  # set default required type and overwrite later if derived
            description=self.session_starter_info["experiment description"],
            sourceFolder=host_info["sourceFolder"],
            sourceFolderHost=host_info["sourceFolderHost"],
            #TO DO - this would normally be extracted from instrument preferences
            #instrumentId=str(self.instr_dict["id"]),
            owner=self.params.owner,
            contactEmail=self.params.email,
            orcidOfOwner=self.params.orcid,
            ownerGroup=self.params.owner_group,
            accessGroups=access_groups,
            techniques=[{"name": self.params.technique}],
            creationTime=(
                datetime.fromtimestamp(date_method).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                )[:-3]
                + "Z"
            ),
        )

        # Add in raw/derived specific variables
        # TO DO - don't have session starter
        if self.params.derived_dataset:
            payload = DerivedPayload(**default_payload.dict())
            payload.type = "derived"
            payload.investigator = self.params.investigator
            payload.inputDatasets = self.input_datasets
            payload.usedSoftware = self.used_software
        else:
            payload = RawPayload(**default_payload.dict())
            payload.creationLocation = str(self.instrument_choice)
            payload.principalInvestigator = self.params.investigator
            payload.endTime = payload.creationTime
            payload.dataFormat = data_format

        # Add in Directory specific payload details
        if isinstance(file, Directory):
            parser_dict = {}
            for f in file:
                try:
                    parser = self.find_parser(f[0])
                except ParserNotFound:
                    parser = None
                if parser:
                    parser_dict[f[0]] = parser
            if not parser_dict:
                logger.info(
                    " Parsers not found. Creating payload without metadata"
                )

            payload.datasetName = (
                self.params.experiment_name
                + "/"
                + str(file.relative_filename.parts[-1])
            )
            payload.size = file._total_size
            payload.numberOfFiles = len(file._filelist)

            # Scientific metadata
            # TO DO - configure later with instrument dict
            scientificMetadata: Dict[str, Dict[str, str]] = {}
            if parser_dict:
                for k, v in parser_dict.items():
                    metadata = PayloadHelpers.implement_parser(
                        self.instr_dict, self.params.technique, k, v
                    )
                    for k, v in metadata.items():
                        if k in scientificMetadata.keys():
                            if scientificMetadata[k] == v:
                                continue
                        else:
                            scientificMetadata[k] = v
            payload.scientificMetadata = (
                PayloadHelpers.scientific_metadata_concatenation(
                    scientificMetadata, payload.scientificMetadataDefaults
                )
            )

        elif isinstance(file, RegularFile):
            try:
                parser = self.find_parser(file.filename)

            except Exception as e:
                logger.exception(
                    " Parser not found. Creating payload without metadata"
                )
                parser = None

            # Creation of standard file items
            payload.datasetName = (
                self.params.experiment_name
                + "/"
                + str(PurePosixPath(file.relative_filename))
            )
            fstats = Path(file.filename).stat()
            payload.size = fstats.st_size

            # Creation of scientific metadata
            # TO DO - configure later with instrument dict
            scientificMetadata = {}
            if parser:
                scientificMetadata = PayloadHelpers.implement_parser(
                    self.instr_dict,
                    self.params.technique,
                    file.filename,
                    parser,
                )
            payload.scientificMetadata = (
                PayloadHelpers.scientific_metadata_concatenation(
                    scientificMetadata, payload.scientificMetadataDefaults
                )
            )

        del payload.scientificMetadataDefaults
        return payload

    def find_parser(self, filename):
        for parser in self.parser_list:
            if parser.supports_file(filename):
                break
        else:
            parser = None
        if not parser:
            raise ParserNotFound("parser not found")
        return parser

    # Inserts a dataset into Scicat
    def insert_payload(self, payload, scicat_session):
        try:
            r = scicat_session.upload_dataset(payload)
            if r:
                logger.info(f"Payload catalogued, PID: {r}")
        except Exception as e:
            logger.error(
                f"Could not catalogue payload in scicat: {e.statusCode} -> {e.message}"
            )
            return str(e)

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
                #   logger.error(f"Could not catalogue payload in scicat: {e}")
                #   return str(e)
            else:
                self.insert_payload(payload, scicat_session)
        else:
            self.insert_payload(payload, scicat_session)


# Base Payload Model inherits from Dataset Model
class Payload(Dataset):
    datasetlifecycle = {"retrievable": True}
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

    # TO DO - technique
    @classmethod
    def implement_parser(cls, instr_dict, technique, filename, parser):
        scientific_metadata = {}
        instr_vars = instr_dict["techniques"][technique]
        extracted = parser.extract_metadata(instr_vars, filename)
        if extracted:
            for k, v in extracted.items():
                scientific_metadata[k] = {
                    "type": "string",
                    "value": str(v),
                    "unit": "",
                }
        return scientific_metadata

    @classmethod
    def scientific_metadata_concatenation(cls, scientific_metadata, defaults):
        scientific_metadata |= defaults
        return scientific_metadata


class ParserNotFound(Exception):
    """Metadata parser not found"""

    pass


class RequiredInfoNotFound(Exception):
    """Info required in Scicat Payload not found"""

    pass