"""Pure markdown report generation (no IO in these functions)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChangeDetail:
    original: str
    corrected: str
    rule: str
    context: str = ""
    alternatives: list[str] = field(default_factory=list)


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
    total = sum(len(s.changes) for f in results for s in f.slides)
    lines.append(
        f"Se revisaron **{len(results)}** archivo(s) y se detectaron "
        f"**{total}** punto(s) de mejora."
    )
    lines.append("")

    if not results:
        lines.append("No se procesaron archivos con texto apto para corrección.")
        lines.append("")
        return "\n".join(lines)

    for file_report in results:
        lines.append(f"## {file_report.filename}")
        lines.append("")
        if not file_report.slides:
            lines.append("_sin correcciones_")
            lines.append("")
            continue

        for slide in file_report.slides:
            applied = [c for c in slide.changes if c.corrected]
            pending = [c for c in slide.changes if not c.corrected]
            if not applied and not pending:
                continue
            lines.append(f"### Diapositiva {slide.slide_idx}")
            lines.append("")

            if pending:
                lines.append("**Pendientes de revisión (no auto-corregidos):**")
                lines.append("")
                lines.append("| Contexto | Original | Alternativas sugeridas |")
                lines.append("|---|---|---|")
                for ch in pending:
                    ctx = _md_escape(ch.context)
                    alts = " · ".join(_md_escape(a) for a in ch.alternatives) or "—"
                    lines.append(
                        f"| {ctx} | **{_md_escape(ch.original)}** | {alts} |"
                    )
                lines.append("")

            if applied:
                lines.append("**Aplicados:**")
                lines.append("")
                lines.append("| Original | Corregido | Regla |")
                lines.append("|---|---|---|")
                for ch in applied:
                    lines.append(
                        f"| {_md_escape(ch.original)} | {_md_escape(ch.corrected)} "
                        f"| {_md_escape(ch.rule)} |"
                    )
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"
