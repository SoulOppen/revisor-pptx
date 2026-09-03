"""Safe copy of .pptx files into a destination folder.

Only copies .pptx files, never touches the originals. The destination folder
is created if it does not exist.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_file(src: Path, dest: Path) -> Path:
    """Copy a single .pptx file to ``dest``.

    ``dest`` is the full target file path. Its parent directory is created if
    missing. Returns the resulting Path.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def copy_directory(src: Path, dest: Path) -> list[Path]:
    """Copy every ``.pptx`` in ``src`` (top level) into ``dest``.

    Returns the list of copied paths. Non-.pptx files are ignored.
    ``dest`` (commonly ``<src>/corregidos``) is created if missing.
    """
    dest.mkdir(parents=True, exist_ok=True)
    copies: list[Path] = []
    for item in sorted(src.iterdir()):
        if not item.is_file():
            continue
        if item.suffix.lower() != ".pptx":
            continue
        target = dest / item.name
        copy_file(item, target)
        copies.append(target)
    return copies
