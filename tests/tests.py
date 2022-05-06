from unittest import TestCase
from rfi_file_monitor.operations.scicataloguer import (
    Payload,
    RawPayload,
    DerivedPayload,
    PayloadHelpers,
)
from rfi_file_monitor.operations.s3_uploader import S3UploaderOperation
from rfi_file_monitor.operations.sftp_uploader import SftpUploaderOperation
from rfi_file_monitor.operations.dropbox_uploader import DropboxUploaderOperation
from rfi_file_monitor.files.regular_file import RegularFile
from rfi_file_monitor.file import FileStatus
from rfi_file_monitor.files.directory import Directory
from pathlib import Path, PurePath, PurePosixPath
from datetime import datetime
from typing import Dict
import os


TEST_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


class TestPayloadGeneration(TestCase):
    def setUp(self) -> None:
        self.session_info = {
            "username": "Test User",
            "email": "test.user@testinstitute.ac.uk",
            "orcid": "0000-0001-5199-5624",
            "owner group": "Test Group",
            "principal investigator": "T. E. Sting",
            "experiment name": "test em expt",
            "experiment description": None,
            "bucket name": "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk",
        }
        self.file = RegularFile(
            filename=os.path.join(TEST_DIR, "test_data/testfile.txt"),
            relative_filename=Path("test_data/testfile.txt"),
            created=0,
            status=FileStatus.CREATED,
        )
        self.file.operation_metadata[0] = {
            "s3 object url": "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk/testfile.txt"
        }
        self.file.operation_metadata[1] = {
            "sftp url": "sftp://sftp.testinstitute.ac.uk:22/home/user/testfile.txt"
        }
        self.file_2 = RegularFile(
            filename=os.path.join(TEST_DIR, "test_data/test_data/test_dir/myfile.txt"),
            relative_filename=Path("test_data/testfile.txt"),
            created=0,
            status=FileStatus.CREATED,
        )
        self.file_2.operation_metadata[0] = {
            "s3 object url": "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk/test_dir/myfile1.txt"
        }

        self.dir = Directory(
            filename=os.path.join(TEST_DIR, "test_data/test_dir"),
            relative_filename=Path("test_dir"),
            created=0,
            status=FileStatus.CREATED,
            included_patterns=[".*"],
            excluded_patterns=[],
        )
        self.dir._filelist = [("myfile1.txt", 0), ("myfile2.txt", 1)]
        self.dir.operation_metadata[0] = {
            "my_file_1.txt": {
                "s3 object url": "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk/test_dir/myfile1.txt"
            },
            "my_file_2.txt": {
                "s3 object url": "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk/test_dir/myfile2.txt"
            },
        }

        self.dir.operation_metadata[1] = {
            "my_file_1.txt": {
                "sftp url": "sftp://sftp.testinstitute.ac.uk:22/home/user/test_dir/myfile1.txt"
            },
            "my_file_2.txt": {
                "sftp url": "sftp://sftp.testinstitute.ac.uk:22/home/user/test_dir/myfile2.txt"
            },
        }
        self.technique = "cryo-em"

        self.instr_dict = {
            "id": "0001",
            "techniques": {"cryo-em": ["ImageWidth", "ImageHeight"]},
        }
        self.instrument_choice = "Cryo-EM1"
        self.operations_list = [S3UploaderOperation.NAME, SftpUploaderOperation.NAME, DropboxUploaderOperation.NAME]

        self.parser = {}
        self.inputDatasets = ["test_dir/myfile1.txt", "test_dir/myfile2.txt"]
        self.usedSoftware = ["testsoftware"]

    def test_get_host_location(self):
        hostfolder = PayloadHelpers.get_host_location(self.file, self.operations_list, "S3 Uploader")
        self.assertEqual(hostfolder["sourceFolder"], "testfile.txt")
        self.assertEqual(
            hostfolder["sourceFolderHost"],
            "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk",
        )
        hostfolder = PayloadHelpers.get_host_location(self.file_2, self.operations_list, "S3 Uploader")
        self.assertEqual(hostfolder["sourceFolder"], "test_dir/myfile1.txt")
        self.assertEqual(
            hostfolder["sourceFolderHost"],
            "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk",
        )

    def test_payload_file_generator(self):
        host_info = PayloadHelpers.get_host_location(self.file, self.operations_list, "S3 Uploader")
        if "access groups" in self.instr_dict:
            access_groups = self.instr_dict["access groups"]
        else:
            access_groups = []
        fppath = PurePath(self.file.filename)
        data_format = fppath.suffix

        # Creation of scientific metadata
        scientificMetadata = {}
        if self.parser:
            scientificMetadata = PayloadHelpers.implement_parser(
                self.instr_dict, self.technique, self.file.filename, self.parser
            )

        payload = Payload(
            datasetName=(
                self.session_info["experiment name"]
                + "/"
                + str(PurePosixPath(self.file.relative_filename))
            ),
            size=Path(self.file.filename).stat().st_size,
            type="raw",  # set default required type and overwrite later if derived
            description=self.session_info["experiment description"],
            sourceFolder=host_info["sourceFolder"],
            sourceFolderHost=host_info["sourceFolderHost"],
            instrumentId=str(self.instr_dict["id"]),
            owner=self.session_info["username"],
            contactEmail=self.session_info["email"],
            orcidOfOwner=self.session_info["orcid"],
            ownerGroup=self.session_info["owner group"],
            accessGroups=access_groups,
            techniques=[{"name": self.technique}],
            creationTime=(
                datetime.fromtimestamp(
                    Path(self.file.filename).stat().st_ctime
                ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                + "Z"
            ),
        )

        # Test Raw/Derived specific
        derived_payload = DerivedPayload(**payload.dict())
        derived_payload.type = "derived"
        derived_payload.investigator = self.session_info["principal investigator"]
        derived_payload.inputDatasets = self.inputDatasets
        derived_payload.usedSoftware = self.usedSoftware
        derived_payload.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata, payload.scientificMetadataDefaults
            )
        )
        del derived_payload.scientificMetadataDefaults

        self.assertEqual(
            derived_payload.inputDatasets,
            ["test_dir/myfile1.txt", "test_dir/myfile2.txt"],
        )
        self.assertEqual(derived_payload.investigator, "T. E. Sting")
        self.assertEqual(derived_payload.usedSoftware, ["testsoftware"])
        self.assertEqual(derived_payload.instrumentId, "0001")
        self.assertEqual(derived_payload.datasetlifecycle["retrievable"], True)

        raw_payload = RawPayload(**payload.dict())
        raw_payload.creationLocation = str(self.instrument_choice)
        raw_payload.principalInvestigator = self.session_info["principal investigator"]
        raw_payload.endTime = payload.creationTime
        raw_payload.dataFormat = data_format

        self.assertEqual(raw_payload.creationLocation, "Cryo-EM1")
        self.assertEqual(raw_payload.dataFormat, ".txt")
        self.assertEqual("test em expt/test_data/testfile.txt", raw_payload.datasetName)
        self.assertEqual(raw_payload.sourceFolder, "testfile.txt")
        self.assertEqual(
            raw_payload.sourceFolderHost,
            "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk",
        )

    def test_payload_dir_generator(self):
        host_info = PayloadHelpers.get_host_location(self.dir, self.operations_list, "S3 Uploader")
        if "access groups" in self.instr_dict:
            access_groups = self.instr_dict["access groups"]
        else:
            access_groups = []
        data_format = "directory"

        # Creation of scientific metadata
        scientificMetadata: Dict[str, Dict[str, str]] = {}
        payload = Payload(
            datasetName=(
                self.session_info["experiment name"]
                + "/"
                + str(self.dir.relative_filename.parts[-1])
            ),
            size=self.dir._total_size,
            type="raw",  # set default required type and overwrite later if derived
            description=self.session_info["experiment description"],
            sourceFolder=host_info["sourceFolder"],
            sourceFolderHost=host_info["sourceFolderHost"],
            instrumentId=str(self.instr_dict["id"]),
            owner=self.session_info["username"],
            contactEmail=self.session_info["email"],
            orcidOfOwner=self.session_info["orcid"],
            ownerGroup=self.session_info["owner group"],
            accessGroups=access_groups,
            techniques=[{"name": self.technique}],
            creationTime=(
                datetime.fromtimestamp(self.dir._filelist_timestamp).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                )[:-3]
                + "Z"
            ),
            numberOfFiles=len(self.dir._filelist),
        )

        # Create derived dataset
        derived_payload = DerivedPayload(**payload.dict())
        derived_payload.type = "derived"
        derived_payload.investigator = self.session_info["principal investigator"]
        derived_payload.inputDatasets = self.inputDatasets
        derived_payload.usedSoftware = self.usedSoftware
        derived_payload.scientificMetadata = (
            PayloadHelpers.scientific_metadata_concatenation(
                scientificMetadata, payload.scientificMetadataDefaults
            )
        )
        del derived_payload.scientificMetadataDefaults

        # Test derived dataset
        self.assertEqual(derived_payload.investigator, "T. E. Sting")
        self.assertEqual(derived_payload.numberOfFiles, 2)
        self.assertEqual(derived_payload.usedSoftware, ["testsoftware"])
        self.assertEqual(derived_payload.instrumentId, "0001")
        self.assertEqual(derived_payload.datasetlifecycle["retrievable"], True)
        self.assertNotIn("scientificMetadataDefaults", derived_payload.dict().keys())

        # Create raw dataset
        raw_payload = RawPayload(**payload.dict())
        raw_payload.creationLocation = str(self.instrument_choice)
        raw_payload.principalInvestigator = self.session_info["principal investigator"]
        raw_payload.endTime = payload.creationTime
        raw_payload.dataFormat = data_format

        # Test raw dataset
        self.assertEqual(raw_payload.creationLocation, "Cryo-EM1")
        self.assertEqual(raw_payload.dataFormat, "directory")
        self.assertEqual("test em expt/test_dir", raw_payload.datasetName)
        self.assertEqual(raw_payload.sourceFolder, "test_dir")
        self.assertEqual(
            raw_payload.sourceFolderHost,
            "https://cryo-em1-test-em-expt-14s3.s3.testinstitute.ac.uk",
        )