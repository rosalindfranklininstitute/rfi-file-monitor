from rfi_file_monitor.metadataparser import MetadataParser
from itertools import takewhile
import re
import logging

logger = logging.getLogger(__name__)


class CsvMetadataParser(MetadataParser):
    NAME = "CSV Parser"

    @classmethod
    def supports_file(cls, file: str):
        if file.endswith("csv") or file.endswith("tsv"):
            return True
        return False

    @classmethod
    def extract_metadata(cls, capture_metadata, file):
        # check for metadata stored as comments

        with open(file, "r") as fobj:
            # takewhile returns an iterator over all the lines
            # that start with the comment string
            headiter = takewhile(lambda s: s.startswith("#"), fobj)
            # you may want to process the headers differently,
            # but here we just convert it to a list
            metadata = list(headiter)

        scicat_metadata = {}
        for line in metadata:
            line = line.strip("#")
            line = line.strip("\n")
            for i in capture_metadata:
                if i in line:
                    splitline = re.split(r'[ ,|;"=]+', line)
                    splitline = [part for part in splitline if part != ""]
                    scicat_metadata[splitline[0]] = splitline[1]

        return scicat_metadata
