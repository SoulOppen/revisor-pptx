"""LanguageTool integration and lifecycle management.

Provides a module-level singleton LanguageTool client, Java detection, and
graceful degradation to the public cloud API when the local server cannot
start.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import warnings
from dataclasses import dataclass
from typing import Any, Literal

# Module-level singleton: a (language_tool, source) tuple or None.
_lt_singleton: Any = None
_lt_source: str = "none"


@dataclass
class Correction:
    """A single proofreading match from LanguageTool."""

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


def check_java() -> bool:
    """Return True if ``java`` is available on the PATH."""
    if shutil.which("java") is None:
        return False
    try:
        proc = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _tool_from_local() -> Any:
    import language_tool_python

    return language_tool_python.LanguageTool("es", remote_server=None)


def _tool_from_cloud() -> Any:
    import language_tool_python

    return language_tool_python.LanguageToolPublicAPI("es")


def init_languagetool(prefer_local: bool = True) -> tuple[Any, str]:
    """Initialise the LanguageTool singleton.

    Returns ``(tool, source_name)``. When ``prefer_local`` and Java is present,
    an attempt is made to start the local server; on any failure it falls back
    to the public cloud API. If both fail, ``(None, "none")`` is returned.
    """
    global _lt_singleton, _lt_source

    if _lt_singleton is not None:
        return _lt_singleton, _lt_source

    tool = None
    source = "none"

    if prefer_local and check_java():
        try:
            tool = _tool_from_local()
            source = "local"
        except Exception:  # noqa: BLE001 - graceful degradation is intentional
            tool = None
            source = "none"

    if tool is None:
        try:
            tool = _tool_from_cloud()
            source = "cloud"
        except Exception:  # noqa: BLE001 - graceful degradation is intentional
            tool = None
            source = "none"

    _lt_singleton = tool
    _lt_source = source

    if tool is not None:
        atexit.register(_close_lt)

    return tool, source


def _close_lt() -> None:
    global _lt_singleton
    if _lt_singleton is not None:
        try:
            _lt_singleton.close()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"No se pudo cerrar LanguageTool: {exc}", RuntimeWarning)
        _lt_singleton = None


def _segments_corrections(
    matches: list[Any],
    slide_idx: int,
    shape_idx: int,
    source: Literal["shape", "table", "notes"],
) -> list[Correction]:
    """Convert raw LanguageTool match objects into Correction dataclasses."""
    corrections: list[Correction] = []
    # Notes corrections are routed by shape_idx == -1 (no real shape).
    routed_shape_idx = -1 if source == "notes" else shape_idx
    for m in matches:
        replacements = [r["value"] for r in (m.get("replacements") or [])]
        rule = m.get("rule") or {}
        issue = (rule.get("issueType") or "").lower()
        corrections.append(
            Correction(
                slide_idx=slide_idx,
                shape_idx=routed_shape_idx,
                segment_idx=0,
                offset=m.get("offset", 0),
                length=m.get("length", 0),
                original=m.get("text", ""),
                replacements=replacements,
                rule_id=rule.get("id") or m.get("ruleId") or "",
                rule_issue=issue,
                context=m.get("context", {}).get("text", ""),
            )
        )
    return corrections


def review_text(texts, lang: str = "es") -> list[Correction]:
    """IO boundary: run proofreading over extracted slide text.

    ``texts`` is a list of SlideText objects. Returns the flat list of
    Corrections across all slides.
    """
    tool, _ = init_languagetool()
    if tool is None:
        return []

    corrections: list[Correction] = []
    for slide in texts or []:
        # Each shape contributes its concatenated segment text.
        for st in slide.shapes_text:
            seq = [seg.text for seg in st.segments]
            if seq:
                matches = tool.check(" ".join(seq))
                corrections.extend(
                    _segments_corrections(
                        matches, slide.slide_idx, st.shape_idx, "shape"
                    )
                )
        if slide.notes:
            matches = tool.check(slide.notes)
            corrections.extend(
                _segments_corrections(matches, slide.slide_idx, -1, "notes")
            )
    return corrections
