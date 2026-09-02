"""Tests for text extraction."""

from __future__ import annotations

import types

from revisor_pptx.extract_text import extract_pptx, extract_slide_text


def _make_run(text):
    run = types.SimpleNamespace(text=text)
    return run


def _make_frame(*texts):
    paragraphs = [types.SimpleNamespace(runs=[_make_run(t)]) for t in texts]
    return types.SimpleNamespace(paragraphs=paragraphs)


def _make_shape(shape_id, name, has_table=False, text_frame=None):
    return types.SimpleNamespace(
        shape_id=shape_id,
        name=name,
        has_table=has_table,
        has_text_frame=text_frame is not None,
        text_frame=text_frame,
    )


def test_extract_slide_text_offsets():
    """Verify cumulative offsets across multiple paragraphs in one shape."""
    slide = types.SimpleNamespace(
        slide_id=1,
        has_notes_slide=False,
        notes_slide=None,
        shapes=[
            _make_shape(10, "Text 1", text_frame=_make_frame("hola", "mundo")),
            _make_shape(11, "Text 2", text_frame=_make_frame("a", "b c")),
        ],
    )
    result = extract_slide_text(slide)
    assert result.slide_idx == 1
    assert len(result.shapes_text) == 2

    segs = result.shapes_text[0].segments
    assert [s.text for s in segs] == ["hola", "mundo"]
    assert [s.offset for s in segs] == [0, 4]

    segs2 = result.shapes_text[1].segments
    assert [s.text for s in segs2] == ["a", "b c"]
    assert [s.offset for s in segs2] == [0, 1]


def test_extract_slide_text_empty_shape_skipped():
    slide = types.SimpleNamespace(
        slide_id=2,
        has_notes_slide=False,
        notes_slide=None,
        shapes=[_make_shape(12, "Empty", text_frame=_make_frame(""))],
    )
    result = extract_slide_text(slide)
    # Empty text blocks are silently skipped (shape entry has no segments).
    assert len(result.shapes_text) == 1
    assert result.shapes_text[0].segments == []


def test_extract_slide_text_notes_included():
    notes_frame = _make_frame("nota con errata")
    slide = types.SimpleNamespace(
        slide_id=3,
        has_notes_slide=True,
        notes_slide=types.SimpleNamespace(notes_text_frame=notes_frame),
        shapes=[],
    )
    result = extract_slide_text(slide)
    assert result.notes == "nota con errata"


def test_extract_pptx_with_fixture(make_pptx):
    path = make_pptx(name="sample.pptx")
    slides = extract_pptx(path)
    # 3 slides: 2 with content, 1 empty.
    assert len(slides) == 3
    # Empty slide (index 2) yields no shape text and no notes.
    empty = slides[2]
    assert empty.shapes_text == []
    assert empty.notes == ""


def test_empty_slide_no_error(make_pptx):
    path = make_pptx(name="empty.pptx", with_table=False, with_notes=False)
    slides = extract_pptx(path)
    assert len(slides) == 3
