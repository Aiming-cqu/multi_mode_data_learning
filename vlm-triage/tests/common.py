from __future__ import absolute_import, annotations

import os, typing as tp

from pathlib import Path
from typing_extensions import override


TEST_DATA_DIR = Path(os.environ["PROJECT_ROOT"], 'tests', 'data')
r"""Base directory for test data files."""


def read_data(rel_paths: tp.Sequence[str]) -> list[bytes]:
    r"""
    Load test image files and return their binary content.

    Args:
        rel_paths: List of image filenames relative to the test data directory.

    Returns:
        List of binary image data.
    """
    return [(TEST_DATA_DIR / p).read_bytes() for p in rel_paths]


class FileGroupLoader(tp.Iterable[list[bytes]]):
    r"""
    Lazy loader for file groups.

    Provides an iterator that loads files on demand to avoid memory
    issues when dealing with large numbers of files.

    Attributes:
        path_groups: Sequence of file path groups to load.
    """

    def __init__(self, path_groups: tp.Sequence[tp.Sequence[str]]):
        r"""
        Initialize the file group loader.

        Args:
            path_groups: Sequence of file path groups, where each group
                is a sequence of file paths.
        """
        self.path_groups: tp.Sequence[tp.Sequence[str]] = path_groups

    @override
    def __iter__(self) -> tp.Iterator[list[bytes]]:
        r"""
        Iterate over file groups, loading each group on demand.

        Yields:
            List of binary file contents for each group.
        """
        for path_group in self.path_groups:
            yield read_data(path_group)

    def __len__(self) -> int:
        r"""
        Return the number of file groups.

        Returns:
            Number of path groups.
        """
        return len(self.path_groups)

    def __getitem__(self, index: int) -> list[bytes]:
        r"""
        Get a specific file group by index.

        Args:
            index: Index of the file group to retrieve.

        Returns:
            List of binary file contents for the specified group.
        """
        return read_data(self.path_groups[index])

    def items(self) -> tp.Iterator[tuple[list[str], list[bytes]]]:
        r"""
        Iterate over file groups with their paths.

        Yields:
            Tuples of (path_group, file_contents) for each group.
        """
        for path_group in self.path_groups:
            yield (path_group, read_data(path_group))
