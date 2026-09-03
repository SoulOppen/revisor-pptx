"""Tests for the LanguageTool HTTP API proofreading engine.

The API call itself (``_http_check``) is mocked in every test so the suite is
deterministic and offline. These tests cover the mapping of raw LanguageTool
``matches`` onto the ``Correction`` contract consumed by :mod:`revisor_pptx.aplicar`.
"""

from __future__ import annotations

import pytest

from revisor_pptx.extract_text import ShapeText, SlideText, TextSegment
from revisor_pptx.revisar import _rank_by_context, review_text


def _seg(text: str, offset: int = 0, source: str = "shape") -> TextSegment:
    return TextSegment(text=text, offset=offset, source=source)


def _slide(shapes_text, notes: str = "") -> SlideText:
    return SlideText(slide_idx=1, shapes_text=shapes_text, notes=notes)


def _shape(segments, shape_idx: int = 10, name: str = "box") -> ShapeText:
    return ShapeText(shape_idx=shape_idx, shape_name=name, segments=segments)


def _match(offset: int, length: int, value: str, issue: str = "misspelling",
           rid: str = "MORFOLOGIK_RULE_ES") -> dict:
    return {
        "offset": offset,
        "length": length,
        "message": "posible error",
        "replacements": [{"value": value}],
        "rule": {"id": rid, "issueType": issue},
        "context": {"text": "ctx", "offset": offset, "length": length},
    }


def _nocheck(text, lang="es"):
    """Stub ``_http_check`` that returns no matches."""
    return []


def test_review_rejects_non_spanish(monkeypatch):
    monkeypatch.setattr("revisor_pptx.revisar._http_check", _nocheck)
    slide = _slide([_shape([_seg("hola")])])
    with pytest.raises(ValueError):
        review_text([slide], lang="en")


def test_review_detects_misspelling_and_maps_fields(monkeypatch):
    def fake_check(text, lang="es"):
        assert text == "hola munod como estas"
        return [_match(offset=5, length=5, value="mundo")]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("hola munod como estas")])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    c = corrs[0]
    assert c.original == "munod"
    assert c.rule_id == "MORFOLOGIK_RULE_ES"
    assert c.rule_issue == "misspelling"
    assert c.replacements == ["mundo"]
    assert c.offset == 5
    assert c.length == 5
    assert c.shape_idx == 10
    assert c.segment_idx == 0


def test_review_offset_absolute_within_shape(monkeypatch):
    # Shape has two segments "hola"(offset 0) and "munod"(offset 4). Each
    # segment is sent separately; the second returns a match at its own
    # offset 0, which maps to shape-absolute offset 4.
    def fake_check(text, lang="es"):
        if text == "munod":
            return [_match(offset=0, length=5, value="mundo")]
        return []

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("hola", 0), _seg("munod", 4)])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    assert corrs[0].original == "munod"
    assert corrs[0].offset == 4
    assert corrs[0].segment_idx == 1


def test_review_clean_text_yields_no_corrections(monkeypatch):
    monkeypatch.setattr("revisor_pptx.revisar._http_check", _nocheck)
    slide = _slide([_shape([_seg("El proyecto fue un éxito")])])
    corrs = review_text([slide])
    assert corrs == []


def test_review_grammar_match_with_issue_type(monkeypatch):
    def fake_check(text, lang="es"):
        return [_match(offset=5, length=2, value="son", issue="grammar", rid="ES_CONCORDANCIA")]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("Esto es malo")])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    assert corrs[0].rule_issue == "grammar"
    assert corrs[0].rule_id == "ES_CONCORDANCIA"
    assert corrs[0].original == "es"


def test_review_notes_routed_to_shape_minus_one(monkeypatch):
    def fake_check(text, lang="es"):
        if text == "nota con munod mal escrito":
            return [_match(offset=9, length=5, value="mundo")]
        return []

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("texto correcto")])], notes="nota con munod mal escrito")
    corrs = review_text([slide])
    notes_corr = [c for c in corrs if c.original == "munod"]
    assert len(notes_corr) == 1
    assert notes_corr[0].shape_idx == -1
    assert notes_corr[0].offset == 9


def test_review_ignores_numeric_segment_without_calling_api(monkeypatch):
    # A pure-numeric cell ("$1.200.000") is skipped before any network call.
    def fail_check(text, lang="es"):
        raise AssertionError("no API call expected for numeric segments")

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fail_check)
    slide = _slide([_shape([_seg("$1.200.000", 0)])])
    corrs = review_text([slide])
    assert corrs == []


def test_review_discards_match_inside_figure_in_mixed_text(monkeypatch):
    # In "12%" LanguageTool might flag something; it must be dropped.
    def fake_check(text, lang="es"):
        assert text == "Crecimiento 12% anual"
        return [_match(offset=12, length=3, value="12 %")]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("Crecimiento 12% anual")])])
    corrs = review_text([slide])
    assert corrs == []


def test_review_keeps_replacement_for_two_words_joined(monkeypatch):
    # "LatinoamericaReducir" was a glued-token from glued cells. As its own
    # segment is no longer glued (per-segment mode), this test asserts a real
    # joined word ("pieza clave") stays fixable when the API returns a match.
    def fake_check(text, lang="es"):
        assert text == "esta es una piezacla"
        return [_match(offset=12, length=8, value="pieza clave")]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("esta es una piezacla")])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    assert corrs[0].original == "piezacla"
    assert corrs[0].replacements == ["pieza clave"]


def test_rank_by_context_picks_cleanest_candidate(monkeypatch):
    # "titlo": LanguageTool ranks "tillo" (a rare but valid word) first, yet the
    # contextually correct fix is "título". The candidate that yields the
    # cleanest re-sent text ("el título de la presentación") must win.
    def fake_check(text, lang="es"):
        if "título" in text:
            return []  # the correct candidate is clean in the replacement zone
        # A wrong candidate ("el tillo ...") is flagged right where it sits
        # (offset 3, the replacement zone), which must lose.
        return [_match(offset=3, length=5, value="título")]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    ranked = _rank_by_context(
        "el titlo de la presentación",
        3, 5,
        ["tillo", "título", "titulo"],
    )
    assert ranked[0] == "título"
    # The other options are still kept for the report.
    assert set(ranked[1:]) == {"tillo", "titulo"}


def test_review_uses_context_best_as_first_replacement(monkeypatch):
    # End-to-end through review_text: the match has several alternatives, and
    # the re-scoring pass must lift "título" (cleanest) to the front so it gets
    # auto-applied.
    def fake_check(text, lang="es"):
        if text == "el titlo del informe":
            return [{
                "offset": 3,
                "length": 5,
                "message": "posible error",
                "replacements": [
                    {"value": "tillo"},
                    {"value": "título"},
                    {"value": "titulo"},
                ],
                "rule": {"id": "MORFOLOGIK_RULE_ES", "issueType": "misspelling"},
                "context": {"text": text, "offset": 3, "length": 5},
            }]
        if "título" in text:
            return []
        return [{
            "offset": 3, "length": 5, "message": "otro",
            "replacements": [{"value": "título"}],
            "rule": {"id": "MORFOLOGIK_RULE_ES", "issueType": "misspelling"},
            "context": {"text": text, "offset": 3, "length": 5},
        }]

    monkeypatch.setattr("revisor_pptx.revisar._http_check", fake_check)
    slide = _slide([_shape([_seg("el titlo del informe")])])
    corrs = review_text([slide])
    assert len(corrs) == 1
    assert corrs[0].original == "titlo"
    # Contextually correct option is now first (what _best_replacement applies).
    assert corrs[0].replacements[0] == "título"

