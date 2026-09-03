"""Spanish proofreading engine (spaCy + pyspellchecker).

Replaces the LanguageTool integration. Runs 100% local: no Java, no network,
no rate limits.

Architecture (three layers, in order of confidence):
  1. Orthography detection  -> spaCy ``is_oov`` on ``es_core_news_lg``. Unlike
     pyspellchecker's built-in dictionary, spaCy's vocab does NOT flag common
     correctly-spelled words (``fue``, ``vio``, ``dio``, ``cómo``, ``qué``).
  2. Spelling suggestions    -> pyspellchecker (Levenshtein) is used only as a
     candidate generator for a word spaCy already flagged as unknown.
  3. Grammar (agreement)     -> rule-based checks over spaCy morphological
     features (determiner->noun, adjective->noun, subject->copular verb).
     Auto-corrected only when the fix is deterministic; otherwise reported.

Offsets are relative to the concatenated run text of a shape (no inserted
spaces), matching what :doc:`aplicar` rebuilds when applying corrections.
"""

from __future__ import annotations

from dataclasses import dataclass

# Module-level singletons, loaded lazily on first use.
_nlp = None
_spell = None

_SPACY_MODEL = "es_core_news_lg"

_RULE_ORTHO = "SPACY_OOV"
_RULE_AGREE_PREFIX = "AGREE_"

# Copula forms we can deterministically agree with the subject's number.
_COPULA_NUMBER_MAP = {
    "es": "es",
    "son": "son",
    "era": "era",
    "eran": "eran",
    "fue": "fue",
    "fueron": "fueron",
}


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


def _get_nlp():
    """Load and cache the spaCy Spanish model."""
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load(_SPACY_MODEL, disable=["ner", "lemmatizer"])
    return _nlp


def _get_spell():
    """Load and cache the pyspellchecker Spanish spell checker."""
    global _spell
    if _spell is None:
        from spellchecker import SpellChecker

        _spell = SpellChecker(language="es")
    return _spell


def _number(token) -> str:
    vals = token.morph.get("Number")
    return vals[0] if vals else ""


def _gender(token) -> str:
    vals = token.morph.get("Gender")
    return vals[0] if vals else ""


def _ortho_corrections(doc, seg_offset: int, segment_idx: int,
                       slide_idx: int, shape_idx: int, context: str,
                       ) -> list[Correction]:
    """Spelling findings: spaCy ``is_oov`` + validated suggestions.

    Suggestions come from pyspellchecker but are filtered through spaCy's
    vocab: only candidates that spaCy recognises as real words (not OOV) are
    kept. This drops non-words pyspell occasionally proposes (e.g. ``jertas``
    for ``vebtas``) while keeping valid alternatives.
    """
    parser = _get_nlp()
    spell = _get_spell()
    corrs: list[Correction] = []
    for tok in doc:
        # Only alphabetic unknown tokens are candidates; skip punctuation/digits.
        if not tok.is_oov or not tok.text.isalpha():
            continue
        word = tok.text
        raw = [r for r in (spell.candidates(word) or []) if r]
        # Keep only candidates spaCy knows as real Spanish words.
        candidates = [r for r in raw if not parser.make_doc(r)[0].is_oov]
        # pyspell orders by likelihood; keep that order (no length tie-break,
        # which wrongly favoured real-but-wrong words before).
        candidates = candidates[:3]
        if not candidates:
            continue  # nothing to suggest safely; skip rather than guess
        corrs.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=shape_idx,
                segment_idx=segment_idx,
                offset=seg_offset + tok.idx,
                length=len(word),
                original=word,
                replacements=candidates,
                rule_id=_RULE_ORTHO,
                rule_issue="misspelling",
                context=context,
            )
        )
    return corrs


def _agreement_corrections(doc, seg_offset: int, segment_idx: int,
                           slide_idx: int, shape_idx: int, context: str,
                           ) -> list[Correction]:
    """Rule-based grammar findings over spaCy morphological features.

    Returns "reportable" corrections. Only fully deterministic fixes carry a
    replacement (so they may auto-apply); uncertain ones have an empty
    replacement list and are surfaced for manual review only.
    """
    corrs: list[Correction] = []

    # 1) Determiner -> head noun agreement (gender + number).
    for tok in doc:
        if tok.dep_ != "det":
            continue
        head = tok.head
        if head is None or head.pos_ not in ("NOUN", "PROPN"):
            continue
        flag = ""
        if _gender(tok) and _gender(head) and _gender(tok) != _gender(head):
            flag = "Gender"
        if _number(tok) and _number(head) and _number(tok) != _number(head):
            flag = flag + "Number" if flag else "Number"
        if not flag:
            continue
        corrs.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=shape_idx,
                segment_idx=segment_idx,
                offset=seg_offset + tok.idx,
                length=len(tok.text),
                original=tok.text,
                replacements=[],  # not deterministically fixable
                rule_id=_RULE_AGREE_PREFIX + "DET",
                rule_issue="grammar",
                context=context,
            )
        )

    # 2) Adjective (amod) -> head noun agreement (gender + number).
    for tok in doc:
        if tok.dep_ != "amod":
            continue
        head = tok.head
        if head is None or head.pos_ != "NOUN":
            continue
        flag = ""
        if _gender(tok) and _gender(head) and _gender(tok) != _gender(head):
            flag = "Gender"
        if _number(tok) and _number(head) and _number(tok) != _number(head):
            flag = flag + "Number" if flag else "Number"
        if not flag:
            continue
        corrs.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=shape_idx,
                segment_idx=segment_idx,
                offset=seg_offset + tok.idx,
                length=len(tok.text),
                original=tok.text,
                replacements=[],
                rule_id=_RULE_AGREE_PREFIX + "AMOD",
                rule_issue="grammar",
                context=context,
            )
        )

    # 3) Subject -> copular verb agreement (number), with deterministic fix.
    for tok in doc:
        if tok.dep_ != "cop":
            continue
        lower = tok.text.lower()
        if lower not in _COPULA_NUMBER_MAP:
            continue
        subj = next((c for c in tok.head.children if c.dep_ in ("nsubj", "nsubj:pass")), None)
        if subj is None:
            continue
        subj_num = _number(subj)
        verb_num = _number(tok)
        if not subj_num or not verb_num or subj_num == verb_num:
            continue
        # Map the correct copula form for the subject's number within the tense.
        desired = _desired_copula(tok.text, subj_num)
        if not desired:
            continue
        corrs.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=shape_idx,
                segment_idx=segment_idx,
                offset=seg_offset + tok.idx,
                length=len(tok.text),
                original=tok.text,
                replacements=[desired] if desired.lower() != tok.text.lower() else [],
                rule_id=_RULE_AGREE_PREFIX + "SUBJCOP",
                rule_issue="grammar",
                context=context,
            )
        )
    return corrs


def _desired_copula(original: str, subject_number: str) -> str:
    """Agree a copular verb with the subject's number within its tense.

    Only present/imperfect/perfect tenses of ``ser`` are handled deterministically;
    anything else returns '' (not auto-fixable).
    """
    pairs = {
        ("es", "Sing"): "es",
        ("es", "Plur"): "son",
        ("son", "Sing"): "es",
        ("son", "Plur"): "son",
        ("era", "Sing"): "era",
        ("era", "Plur"): "eran",
        ("eran", "Sing"): "era",
        ("eran", "Plur"): "eran",
        ("fue", "Sing"): "fue",
        ("fue", "Plur"): "fueron",
        ("fueron", "Sing"): "fue",
        ("fueron", "Plur"): "fueron",
    }
    return pairs.get((original.lower(), subject_number), "")


def _segment_corrections(seg, seg_offset: int, segment_idx: int,
                         slide_idx: int, shape_idx: int) -> list[Correction]:
    """Run detection over a single text segment."""
    if not seg.text.strip():
        return []
    parser = _get_nlp()
    doc = parser(seg.text)
    context = seg.text

    corrs: list[Correction] = []
    corrs += _ortho_corrections(
        doc, seg_offset, segment_idx, slide_idx, shape_idx, context
    )
    corrs += _agreement_corrections(
        doc, seg_offset, segment_idx, slide_idx, shape_idx, context
    )
    return corrs


def review_text(texts, lang: str = "es") -> list[Correction]:
    """Proofread extracted slide text and return a flat correction list.

    ``texts`` is a list of SlideText objects. Offsets are relative to the run
    text as rebuilt by :mod:`aplicar`. Only ``lang=="es"`` is supported.
    """
    if lang != "es":
        raise ValueError(f"Solamente se soporta español, no '{lang}'")

    # Force model load early so failures surface once, predictably.
    _get_nlp()

    corrections: list[Correction] = []
    for slide in texts or []:
        for st in slide.shapes_text:
            for segment_idx, seg in enumerate(st.segments):
                corrections += _segment_corrections(
                    seg,
                    seg_offset=seg.offset,
                    segment_idx=segment_idx,
                    slide_idx=slide.slide_idx,
                    shape_idx=st.shape_idx,
                )
        if slide.notes:
            # Notes are a single flat string; offset relative to note text.
            parser = _get_nlp()
            doc = parser(slide.notes)
            context = slide.notes
            corrections += _ortho_corrections(
                doc, 0, 0, slide.slide_idx, -1, context
            )
            corrections += _agreement_corrections(
                doc, 0, 0, slide.slide_idx, -1, context
            )
    return corrections
