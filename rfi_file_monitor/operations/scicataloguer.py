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
import importlib.metadata
import importlib
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

        tempgrid = Gtk.Grid(
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(tempgrid, 0, 0, 1, 1)

        # Hostname
        tempgrid.attach(
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
        tempgrid.attach(self._hostname_entry, 1, 0, 1, 1)

        # Operation upload
        tempgrid.attach(
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
        tempgrid.attach(op_widget, 3, 0, 1, 1)

        # Username
        tempgrid.attach(
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
        tempgrid.attach(self._username_entry, 1, 1, 1, 1)

        # Password
        tempgrid.attach(
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
        tempgrid.attach(self._password_entry, 3, 1, 1, 1)

        # Owner
        tempgrid.attach(
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
        tempgrid.attach(self._owner_entry, 1, 2, 1, 1)

        # Owner group
        tempgrid.attach(
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
        tempgrid.attach(self._owner_grp_entry, 3, 2, 1, 1)

        # Comtact email
        tempgrid.attach(
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
        tempgrid.attach(self._email_entry, 1, 3, 1, 1)

        # Orcid
        tempgrid.attach(
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
        tempgrid.attach(self._orcid_entry, 3, 3, 1, 1)

        # PI
        tempgrid.attach(
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
        tempgrid.attach(self._pi_entry, 1, 4, 1, 1)

        # Dataset name
        tempgrid.attach(
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
        tempgrid.attach(self._exp_name_entry, 3, 4, 1, 1)

        # Instrument
        # TO DO - this is temporary until instrument preferences configured
        tempgrid.attach(
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
        tempgrid.attach(self._instrument_entry, 1, 5, 1, 1)

        # Technique
        tempgrid.attach(
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
        tempgrid.attach(self._technique_entry, 3, 5, 1, 1)

        # Input boxes for derived dataset specific fields
        tempgrid.attach(
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
        tempgrid.attach(self._input_datasets_entry, 1, 7, 1, 1)

        tempgrid.attach(
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
        tempgrid.attach(self._used_software_entry, 3, 7, 1, 1)

        self._derived_checkbox = Gtk.CheckButton(label="Derived Dataset")
        self._derived_checkbox.connect("toggled", self.checkbox_toggled)
        self.params.derived_dataset = self.checkbox_toggled(
            self._derived_checkbox
        )
        tempgrid.attach(self._derived_checkbox, 0, 6, 1, 1)

        self.tempgrid = Gtk.Grid(
            row_spacing=5,
            column_spacing=5,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self._grid.attach(self.tempgrid, 0, 1, 1, 1)

        self.counter = 0  # counter for number of rows added
        b = Gtk.Button.new_with_label("Manually add metadata")
        b.connect("clicked", self.on_add_clicked)
        self.tempgrid.attach(b, 3, 0, 1, 1)

        self.extra_widgets = {}

        self.parser_list = []
        for e in importlib.metadata.entry_points()[
            "rfi_file_monitor.metadataparsers"
        ]:
            self.parser_list.append(e.load())

    # Add in textboxes to provide metadata manually
    def on_add_clicked(self, button):
        i = self.counter

        self.tempgrid.attach(
            Gtk.Label(
                label="Name",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            0,
            1 + i,
            1,
            1,
        )
        widget = Gtk.Entry(
            placeholder_text="Required",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.tempgrid.attach(widget, 1, 1 + i, 1, 1)
        self.extra_widgets["name" + str(i)] = widget

        self.tempgrid.attach(
            Gtk.Label(
                label="Value",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            2,
            1 + i,
            1,
            1,
        )
        widget = Gtk.Entry(
            placeholder_text="Required",
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.tempgrid.attach(widget, 3, 1 + i, 1, 1)
        self.extra_widgets["value" + str(i)] = widget

        self.tempgrid.attach(
            Gtk.Label(
                label="Unit",
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
                hexpand=False,
                vexpand=False,
            ),
            4,
            1 + i,
            1,
            1,
        )
        widget = Gtk.Entry(
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=False,
        )
        self.tempgrid.attach(widget, 5, 1 + i, 1, 1)
        self.extra_widgets["unit" + str(i)] = widget

        self.tempgrid.show_all()
        self.counter += 1

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

    # Iterates over every metadata row and extracts data
    def _fetch_additional_metadata(self):
        self.params.additional_metadata = {}
        rows = int(len(self.extra_widgets) / 3)
        for i in range(0, rows):
            _name = self.extra_widgets["name" + str(i)].get_text()
            _value = self.extra_widgets["value" + str(i)].get_text()
            _unit = self.extra_widgets["unit" + str(i)].get_text()
            if _name and _value:
                self.additional_metadata[_name] = {
                    "type": "string",
                    "value": _value,
                    "unit": _unit,
                }
            # don't throw exception if row left empty, just ignore
            elif not _name and not _value:
                logger.info(
                    "name and value not provided for additional metadata row, skipping"
                )
            else:
                raise RequiredInfoNotFound(
                    "Both type and value are required metadata fields."
                )

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

        # Fetch additional metadata
        self._fetch_additional_metadata

    def run(self, file: File):
        self.params.keywords = []
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
    def is_file_payload(self, _payload, file):
        _payload.datasetName = (
            self.params.experiment_name
            + "/"
            + str(PurePosixPath(file.relative_filename))
        )
        fstats = Path(file.filename).stat()
        _payload.size = fstats.st_size

        try:
            parser = self.find_parser(file.filename)
        except Exception as e:
            logger.info(" Parser not found. Creating payload without metadata")
            parser = None

        # Scientific metadata
        scientificMetadata = {}
        if parser:
            scientificMetadata = PayloadHelpers.implement_parser(
                self.instr_dict,
                self.params.technique,
                file.filename,
                parser,
            )

        _payload.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata,
                _payload.scientificMetadataDefaults,
                self.params.additional_metadata,
            )
        )

        _payload.creationTime = (
            datetime.fromtimestamp(
                Path(file.filename).stat().st_ctime
            ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z"
        )
        return _payload

    # Adds directory specific payload data
    def is_dir_payload(self, _payload, file):
        _payload.datasetName = (
            self.params.experiment_name
            + "/"
            + str(file.relative_filename.parts[-1])
        )
        _payload.size = file._total_size
        _payload.numberOfFiles = len(file._filelist)

        parser_dict = {}
        for f in file:
            try:
                parser = self.find_parser(f[0])
            except ParserNotFound:
                parser = None
        if parser:
            parser_dict[f[0]] = parser
        if not parser_dict:
            logger.info(" Parsers not found. Creating payload without metadata")

        # Scientific metadata
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
        _payload.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata,
                _payload.scientificMetadataDefaults,
                self.params.additional_metadata,
            )
        )

        _payload.creationTime = (
            datetime.fromtimestamp(file._filelist_timestamp).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3]
            + "Z"
        )

        return _payload

    # Adds raw dataset specific data
    def is_raw_payload(self, _payload, _data_format):
        _payload.creationLocation = str(self.params.instrument_choice)
        _payload.principalInvestigator = self.params.investigator
        _payload.endTime = _payload.creationTime
        _payload.dataFormat = _data_format
        return _payload

    # Adds derived dataset specific data
    def is_derived_payload(self, _payload):
        _payload.investigator = self.params.investigator
        _payload.inputDatasets = self.params.input_datasets.split(",")
        _payload.usedSoftware = self.params.used_software.split(",")
        return _payload

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
            raise Exception(f"Could not catalogue payload in scicat: {e}")

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
