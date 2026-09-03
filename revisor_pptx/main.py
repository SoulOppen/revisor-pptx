"""revisor-pptx CLI entry point and orchestration.

Pipeline per design: copy to corregidos/ -> extract -> review -> apply ->
report. Originals never modified. The review engine is the public LanguageTool
HTTP API (no Java, no local model). High-confidence corrections are applied;
the rest are flagged in the report with context and alternatives.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .aplicar import _best_replacement, apply_corrections, filter_corrections
from .copy_ppts import copy_directory
from .extract_text import extract_pptx
from .reporte import ChangeDetail, FileReport, SlideReport, generate_report
from .revisar import review_text


def _build_report(filename: str, applied: list, pending: list) -> FileReport:
    """Accumulate applied and pending corrections into a FileReport."""
    report = FileReport(filename=filename)

    def to_detail(corr, corrected: str) -> ChangeDetail:
        return ChangeDetail(
            original=corr.original,
            corrected=corrected,
            rule=corr.rule_id,
            context=corr.context,
            alternatives=list(corr.replacements),
        )

    # Applied corrections: safe, deterministic grammar fixes.
    for corr in applied:
        _append_change(report, corr.slide_idx, to_detail(corr, _best_replacement(corr)))
    # Pending corrections: flagged for human review (no auto-correction harm).
    for corr in pending:
        _append_change(report, corr.slide_idx, to_detail(corr, ""))
    return report


def _append_change(report, slide_idx: int, detail: ChangeDetail) -> None:
    for sr in report.slides:
        if sr.slide_idx == slide_idx:
            sr.changes.append(detail)
            return
    sr = SlideReport(slide_idx=slide_idx)
    sr.changes.append(detail)
    report.slides.append(sr)


def run_dir(dir_path: Path) -> int:
    """Process a directory of .pptx files. Returns process exit code."""
    if not dir_path.is_dir():
        print(f"❌ {dir_path} no es un directorio válido")
        return 1

    pptx_files = [
        p
        for p in sorted(dir_path.iterdir())
        if p.is_file() and p.suffix.lower() == ".pptx"
    ]
    if not pptx_files:
        print(f"No se encontraron archivos .pptx en {dir_path}")
        return 0

    dest = dir_path / "corregidos"
    copies = copy_directory(dir_path, dest)

    all_reports: list[FileReport] = []

    for copy in copies:
        try:
            slides = extract_pptx(copy)
        except Exception:  # noqa: BLE001 - corrupt file is skipped, batch continues
            print(f"⚠ {copy.name}: archivo corrupto, saltado")
            all_reports.append(FileReport(filename=copy.name))
            continue

        try:
            corr = review_text(slides, lang="es")
        except Exception as exc:  # noqa: BLE001 - network/API failure per file
            print(f"⚠ {copy.name}: error de revisión ({exc})")
            all_reports.append(FileReport(filename=copy.name))
            continue

        # Apply only high-confidence corrections; flag the rest for review.
        to_apply = filter_corrections(corr)
        applied_set = {id(c) for c in to_apply}
        pending = [c for c in corr if id(c) not in applied_set]
        applied = apply_corrections(copy, slides, to_apply)

        report = _build_report(copy.name, applied, pending)
        all_reports.append(report)
        print(
            f"✓ {copy.name}: {len(applied)} corregida(s), "
            f"{len(pending)} pendiente(s) de revisión"
        )

    report_path = dest / "reporte.md"
    report_path.write_text(generate_report(all_reports), encoding="utf-8")
    print(f"\nReporte: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="revisor-pptx",
        description="Corrector ortográfico/gramatical por lotes de archivos .pptx en español.",
    )
    parser.add_argument("dir", help="Directorio con los archivos .pptx a corregir")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args(argv)

    return run_dir(Path(args.dir))


if __name__ == "__main__":
    sys.exit(main())
