"""Tests for the spaCy + pyspellchecker proofreading engine.

These exercise ``review_text`` end-to-end and thus load the spaCy
``es_core_news_lg`` model (a few seconds on first call within a session).
"""

from __future__ import annotations

import pytest

from revisor_pptx.extract_text import ShapeText, SlideText, TextSegment
from revisor_pptx.revisar import review_text


def _seg(text: str, offset: int = 0, source: str = "shape") -> TextSegment:
    return TextSegment(text=text, offset=offset, source=source)


def _slide(shapes_text, notes: str = "") -> SlideText:
    return SlideText(slide_idx=1, shapes_text=shapes_text, notes=notes)


def _shape(segments, shape_idx: int = 10, name: str = "box") -> ShapeText:
    return ShapeText(shape_idx=shape_idx, shape_name=name, segments=segments)


def test_review_rejects_non_spanish():
    slide = _slide([_shape([_seg("hola")])])
    with pytest.raises(ValueError):
        review_text([slide], lang="en")


def test_review_detects_misspelling_with_replacement():
    slide = _slide([_shape([_seg("hola munod como estas")])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    c = corrs[0]
    assert c.original == "munod"
    assert c.rule_id == "SPACY_OOV"
    assert c.rule_issue == "misspelling"
    assert "mundo" in c.replacements
    assert c.offset == 5
    assert c.length == 5
    assert c.shape_idx == 10


def test_review_offset_accumulates_across_segments():
    # Second segment has offset 4 (first segment "hola" is length 4).
    slide = _slide([_shape([_seg("hola", 0), _seg("munod", 4)])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    assert corrs[0].original == "munod"
    assert corrs[0].offset == 4


def test_review_clean_text_yields_no_corrections():
    slide = _slide([_shape([_seg("El proyecto fue un éxito")])])
    corrs = review_text([slide])
    assert corrs == []


def test_review_detects_grammar_in_determiner_noun():
    slide = _slide([_shape([_seg("la casa bonitos")])])
    corrs = review_text([slide])
    grammar = [c for c in corrs if c.rule_id == "AGREE_AMOD"]
    assert len(grammar) == 1
    assert grammar[0].original == "bonitos"
    assert grammar[0].rule_issue == "grammar"


def test_review_detects_subject_copula_agreement_and_fixes():
    slide = _slide([_shape([_seg("Esta son malas")])])
    corrs = review_text([slide])
    fixes = [c for c in corrs if c.rule_id == "AGREE_SUBJCOP"]
    assert len(fixes) == 1
    assert fixes[0].original == "son"
    assert fixes[0].replacements == ["es"]
    assert fixes[0].offset == 5


def test_review_notes_typo_routed_to_shape_minus_one():
    slide = _slide([_shape([_seg("texto correcto")])], notes="nota con munod mal escrito")
    corrs = review_text([slide])
    note_typo = [c for c in corrs if c.rule_id == "SPACY_OOV" and c.original == "munod"]
    assert len(note_typo) == 1
    assert note_typo[0].shape_idx == -1
    assert "mundo" in note_typo[0].replacements
