import gi

gi.require_version("Gtk", "3.0")

from ..file import File, FileStatus
from pathlib import PurePath, Path
from ..utils import match_path
from typing import List, Tuple
from time import time


class Directory(File):
    def __init__(
        self,
        filename: str,
        relative_filename: PurePath,
        created: int,
        status: FileStatus,
        included_patterns: List[str],
        excluded_patterns: List[str],
    ):

        super().__init__(
            filename,
            relative_filename,
            created,
            status,
        )

        self._included_patterns = included_patterns
        self._excluded_patterns = excluded_patterns

        self._filelist: List[Tuple[str, int]] = []
        self._filelist_timestamp: int = 0
        self._total_size: int = 0

    @property
    def included_patterns(self):
        return self._included_patterns

    @property
    def excluded_patterns(self):
        return self._excluded_patterns

    def _get_filelist(self, _dir: Path) -> List[Tuple[str, int]]:
        rv: List[Tuple[str, int]] = []
        for entry in _dir.iterdir():
            if not match_path(
                entry,
                included_patterns=self._included_patterns,
                excluded_patterns=self._excluded_patterns,
                case_sensitive=False,
            ):
                continue
            if entry.is_file() and not entry.is_symlink():
                size = entry.stat().st_size
                self._total_size += size
                rv.append(
                    (
                        str(entry),
                        size,
                    )
                )
            elif entry.is_dir() and not entry.is_symlink():
                rv.extend(self._get_filelist(entry))
        return rv

    def _refresh_filelist(self):
        self._total_size = 0
        self._filelist = self._get_filelist(Path(self.filename))
        self._filelist_timestamp = time()

    @property
    def total_size(self):
        if self._filelist_timestamp < self._saved:
            self._refresh_filelist()
        return self._total_size

    def __iter__(self):
        if self._filelist_timestamp < self._saved:
            self._refresh_filelist()
        yield from self._filelist

    def __len__(self):
        return len(self._filelist)
