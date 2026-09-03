"""Tests for correction filtering and application."""

from __future__ import annotations

import shutil

from revisor_pptx.aplicar import apply_corrections, filter_corrections
from revisor_pptx.extract_text import extract_pptx
from revisor_pptx.revisar import Correction


def _corr(issue="misspelling", replacements=("mundo",), original="munod", length=5):
    return Correction(
        slide_idx=1,
        shape_idx=1,
        segment_idx=0,
        offset=5,
        length=length,
        original=original,
        replacements=list(replacements),
        rule_id="MORFOLOGIK_RULE_ES",
        rule_issue=issue,
        context="... munod ...",
    )


# --- filter_corrections: table-driven ---


def test_filter_accepts_single_replacement_misspelling():
    c = _corr(issue="misspelling", replacements=("mundo",))
    assert filter_corrections([c]) == [c]


def test_filter_accepts_grammar_autocorrect():
    c = _corr(issue="grammar", replacements=("una",), original="un", length=2)
    assert filter_corrections([c]) == [c]


def test_filter_accepts_typo():
    c = _corr(issue="typo", replacements=("correcto",))
    assert filter_corrections([c]) == [c]


def test_filter_accepts_inconsistency_agreement():
    # A determinante/noun agreement mistake (e.g. "del empresa") is a real
    # grammar error reported by LanguageTool as issueType "inconsistency".
    c = _corr(
        issue="inconsistency",
        replacements=("de la empresa",),
        original="del empresa",
        length=11,
    )
    assert filter_corrections([c]) == [c]


def test_filter_rejects_style():
    c = _corr(issue="style")
    assert filter_corrections([c]) == []


def test_filter_rejects_whitespace():
    c = _corr(issue="whitespace")
    assert filter_corrections([c]) == []


def test_filter_rejects_casing():
    c = _corr(issue="casing")
    assert filter_corrections([c]) == []


def test_filter_rejects_no_replacements():
    c = _corr(replacements=())
    assert filter_corrections([c]) == []


def test_filter_accepts_multiple_long_replacements():
    # First (best) replacement is applied even when several long alternatives
    # exist; the rest are only recorded in the report.
    c = _corr(
        original="hola",
        length=4,
        replacements=("un texto muy largo", "varias palabras"),
    )
    assert filter_corrections([c]) == [c]


def test_filter_accepts_close_length_multiple():
    c = _corr(original="mi", length=2, replacements=("mis", "mira"))
    assert filter_corrections([c]) == [c]


def test_filter_rejects_unknown_issue():
    c = _corr(issue="colloquialism")
    assert filter_corrections([c]) == []


# --- apply_corrections: integration with a real fixture ---


def _find_munod_segment(slides):
    """Locate the ShapeText + segment whose text contains 'munod'."""
    for slide in slides:
        for shape in slide.shapes_text:
            for seg in shape.segments:
                if "munod" in seg.text:
                    return slide, shape, seg
    raise AssertionError("segment with 'munod' not found")


def _munod_correction(slides):
    slide, shape, seg = _find_munod_segment(slides)
    start = seg.text.index("munod")
    corr = Correction(
        slide_idx=slide.slide_idx,
        shape_idx=shape.shape_idx,
        segment_idx=0,
        offset=start,
        length=5,
        original="munod",
        replacements=["mundo"],
        rule_id="MORFOLOGIK_RULE_ES",
        rule_issue="misspelling",
        context="",
    )
    return slide, shape, seg, corr


def test_apply_corrects_shape_text(make_pptx):
    path = make_pptx(name="apply.pptx")
    slides = extract_pptx(path)
    _, _, _, corr = _munod_correction(slides)
    applied = apply_corrections(path, slides, [corr])
    assert len(applied) == 1

    re_extracted = extract_pptx(path)
    texts = " ".join(
        s.text
        for slide in re_extracted
        for st in slide.shapes_text
        for s in st.segments
    )
    assert "mundo" in texts
    assert "munod" not in texts


def test_apply_leaves_original_untouched(make_pptx, tmp_path):
    from hashlib import sha256

    path = make_pptx(name="orig.pptx")
    # Work on a COPY (in the same dir), leaving the source of the factory intact.
    copy_path = tmp_path / "copy.pptx"
    shutil.copy2(path, copy_path)
    orig_hash = sha256(path.read_bytes()).hexdigest()

    slides = extract_pptx(copy_path)
    _, _, _, corr = _munod_correction(slides)
    apply_corrections(copy_path, slides, [corr])
    # The factory source file is untouched.
    assert sha256(path.read_bytes()).hexdigest() == orig_hash
    # The copy differs.
    assert (
        sha256(copy_path.read_bytes()).hexdigest()
        != sha256(path.read_bytes()).hexdigest()
    )


def test_apply_skips_non_matching_offset(make_pptx):
    path = make_pptx(name="nomatch.pptx")
    slides = extract_pptx(path)
    slide, shape, _, _ = _munod_correction(slides)
    corrections = [
        Correction(
            slide_idx=slide.slide_idx,
            shape_idx=shape.shape_idx,
            segment_idx=0,
            offset=0,
            length=5,
            original="xxxxx",  # does not match the text at offset 0
            replacements=["mundo"],
            rule_id="M",
            rule_issue="misspelling",
            context="",
        )
    ]
    applied = apply_corrections(path, slides, corrections)
    assert applied == []
