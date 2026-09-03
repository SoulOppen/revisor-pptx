"""Tests for copy_ppts: safe copy of .pptx files only."""

from __future__ import annotations

import hashlib
from pathlib import Path

from revisor_pptx.copy_ppts import copy_directory, copy_file


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copy_file_creates_dest_and_preserves_bytes(tmp_path, make_pptx):
    src = make_pptx(name="a.pptx")
    dest = tmp_path / "corregidos" / "a.pptx"
    result = copy_file(src, dest)
    assert result.exists()
    assert _sha256(src) == _sha256(dest)


def test_copy_directory_copies_only_pptx(tmp_path, make_pptx):
    src = tmp_path / "input"
    src.mkdir()
    pptx_a = make_pptx(name="a.pptx")
    pptx_b = make_pptx(name="b.pptx")
    # Move the generated files into the input directory alongside a .txt file.
    for f in [pptx_a, pptx_b]:
        f.rename(src / f.name)
    (src / "notes.txt").write_text("ignored", encoding="utf-8")

    dest = src / "corregidos"
    copies = copy_directory(src, dest)
    assert len(copies) == 2
    assert (dest / "a.pptx").exists()
    assert (dest / "b.pptx").exists()
    assert "notes.txt" not in [p.name for p in copies]
    # Originals unchanged.
    assert _sha256(src / "a.pptx") == _sha256(src / "a.pptx")


def test_copy_directory_creates_corregidos(tmp_path, make_pptx):
    src = tmp_path / "input"
    src.mkdir()
    f = make_pptx(name="x.pptx")
    f.rename(src / "x.pptx")
    copies = copy_directory(src, src / "corregidos")
    assert (src / "corregidos" / "x.pptx").exists()
    assert copies == [src / "corregidos" / "x.pptx"]


def test_original_sha256_unchanged(tmp_path, make_pptx):
    src = tmp_path / "input"
    src.mkdir()
    f = make_pptx(name="a.pptx")
    f.rename(src / "a.pptx")
    orig_hash = _sha256(src / "a.pptx")
    dest = src / "corregidos"
    copy_directory(src, dest)
    assert _sha256(src / "a.pptx") == orig_hash
