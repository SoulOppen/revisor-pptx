"""Pure markdown report generation (no IO in these functions)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChangeDetail:
    original: str
    corrected: str
    rule: str


@dataclass
class SlideReport:
    slide_idx: int
    changes: list[ChangeDetail] = field(default_factory=list)


@dataclass
class FileReport:
    filename: str
    slides: list[SlideReport] = field(default_factory=list)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def generate_report(results: list[FileReport]) -> str:
    """Pure: render a list of FileReport into a markdown report string."""
    lines: list[str] = ["# Reporte de correcciones", ""]
    total_changes = sum(len(s.changes) for f in results for s in f.slides)
    lines.append(
        f"Se aplicaron **{total_changes}** correcciones en **{len(results)}** archivo(s)."
    )
    lines.append("")

    if not results:
        lines.append("No se procesaron archivos con texto apto para corrección.")
        lines.append("")
        return "\n".join(lines)

    for file_report in results:
        total_file = sum(len(s.changes) for s in file_report.slides)
        lines.append(f"## {file_report.filename}")
        lines.append("")
        if not file_report.slides or total_file == 0:
            lines.append("_sin correcciones_")
            lines.append("")
            continue
        for slide in file_report.slides:
            if not slide.changes:
                continue
            lines.append(f"### Diapositiva {slide.slide_idx}")
            lines.append("")
            lines.append("| Original | Corregido | Regla |")
            lines.append("|---|---|---|")
            for change in slide.changes:
                lines.append(
                    f"| {_md_escape(change.original)} | {_md_escape(change.corrected)} "
                    f"| {_md_escape(change.rule)} |"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
