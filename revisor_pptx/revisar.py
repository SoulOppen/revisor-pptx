"""Spanish proofreading engine backed by the public LanguageTool HTTP API.

Calls ``https://api.languagetool.org/v2/check`` directly over HTTPS using
``requests``. No Java, no local model, no heavy dependencies: the grammar and
spelling engine lives on LanguageTool's servers and returns high-quality
Spanish corrections with alternatives.

Offsets are relative to the concatenated run text of a shape (no inserted
spaces), matching what :mod:`aplicar` rebuilds when applying corrections.

Each text segment (*e.g.* one paragraph, one table cell, or the speaker notes)
is sent as its own request with that segment's text, so LanguageTool analyses
each unit in isolation -- cell boundaries are never glued together into fake
tokens. The offset returned for a match is relative to that segment, and is
mapped into shape-absolute space by adding the segment's cumulative offset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

_API_URL = "https://api.languagetool.org/v2/check"
_HTTP_TIMEOUT = 30
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds to wait on HTTP 429 (rate limit)

# A token is "numeric" when it has digits and no alphabetic characters:
# covers figures like "$1.200.000", "12%", "5.000.000", "+8%", "-3%".
_LETTERS_RE = re.compile(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]")


@dataclass
class Correction:
    """A single proofreading finding."""

    slide_idx: int
    shape_idx: int
    segment_idx: int
    offset: int
    length: int
    original: str
    replacements: list[str]
    rule_id: str
    rule_issue: str
    context: str


def _http_check(text: str, lang: str = "es") -> list[dict]:
    """POST ``text`` to the public LanguageTool API and return raw matches.

    Retries with backoff on HTTP 429 (rate limit) so batches that brush the
    free-tier request cap still complete. Raises ``requests.HTTPError`` on a
    non-retryable error so the caller can surface it per file.
    """
    if not text or not text.strip():
        return []
    payload = {"language": lang, "text": text}
    for attempt in range(_MAX_RETRIES):
        resp = requests.post(_API_URL, data=payload, timeout=_HTTP_TIMEOUT)
        if resp.status_code == 429 and attempt < _MAX_RETRIES - 1:
            import time

            time.sleep(_RETRY_BACKOFF * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json().get("matches", [])
    return []


def _is_numeric(text: str) -> bool:
    """True for tokens that are figures only (digits, no letters).

    Used to ignore pure-numeric segments (currency/percent amounts in table
    cells) and to skip any LanguageTool match that lands inside a number.
    """
    return bool(re.search(r"\d", text)) and not _LETTERS_RE.search(text)


def _segment_corrections(slide_idx: int, shape_idx: int, segment_idx: int,
                         seg) -> list[Correction]:
    """Proofread one segment (paragraph/cell/notes) via a single request.

    The segment's ``offset`` is its cumulative position within its shape's
    concatenated text, so a match relative to the segment is shifted into
    shape-absolute space before building the :class:`Correction`.
    """
    if not seg.text or not seg.text.strip():
        return []
    if _is_numeric(seg.text.strip()):
        return []  # ignore pure-number cells: nothing to proofread

    matches = _http_check(seg.text)
    corrs: list[Correction] = []
    for match in matches:
        off_in_seg = match["offset"]
        length = match["length"]
        original = seg.text[off_in_seg : off_in_seg + length]
        if _is_numeric(original):
            continue  # never flag/suggest inside a figure
        replacements = [r["value"] for r in match.get("replacements", [])]
        raw_rule = match.get("rule", {})
        corrs.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=shape_idx,
                segment_idx=segment_idx,
                offset=seg.offset + off_in_seg,
                length=length,
                original=original,
                replacements=replacements,
                rule_id=raw_rule.get("id", ""),
                rule_issue=raw_rule.get("issueType", ""),
                context=seg.text,
            )
        )
    return corrs


def review_text(texts, lang: str = "es") -> list[Correction]:
    """Proofread extracted slide text and return a flat correction list.

    ``texts`` is a list of SlideText objects. Offsets are relative to the run
    text as rebuilt by :mod:`aplicar`. Only ``lang=="es"`` is supported.
    """
    if lang != "es":
        raise ValueError(f"Solamente se soporta español, no '{lang}'")

    corrections: list[Correction] = []
    for slide in texts or []:
        for st in slide.shapes_text:
            for segment_idx, seg in enumerate(st.segments):
                corrections += _segment_corrections(
                    slide.slide_idx, st.shape_idx, segment_idx, seg
                )
        if slide.notes and slide.notes.strip():
            corrections += _segment_corrections(
                slide.slide_idx, -1, 0, _NotesSegment(slide.notes)
            )
    return corrections


class _NotesSegment:
    """Minimal segment-like wrapper for the flat speaker-notes string."""

    __slots__ = ("text", "offset", "source")

    def __init__(self, text: str):
        self.text = text
        self.offset = 0
        self.source = "notes"
