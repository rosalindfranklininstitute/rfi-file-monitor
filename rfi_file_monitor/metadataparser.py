from abc import ABC, abstractmethod


class MetadataParser(ABC):
    """Each file will need it's own metadata parser, as every import library works in different ways.
    This class aims to standardise the function names across each file loader."""

    NAME = "Metadataparser"

    def __init__(self):
        self.metadata = []

    @classmethod
    @abstractmethod
    def supports_file(cls, file: str):
        """This method allows you to add the file types that the method supports"""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def extract_metadata(cls, capture_metadata, file):
        """extracts metadata, for a given set of vars"""
        raise NotImplementedError
