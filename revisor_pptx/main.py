"""revisor-pptx CLI entry point and orchestration.

Pipeline per design: check Java -> init LanguageTool -> copy to corregidos/
-> extract -> review -> filter -> apply -> report. Originals never modified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .aplicar import apply_corrections, filter_corrections
from .copy_ppts import copy_directory
from .extract_text import extract_pptx
from .reporte import ChangeDetail, FileReport, SlideReport, generate_report
from .revisar import init_languagetool, review_text


def _build_report(filename: str, applied: list) -> FileReport:
    """Accumulate applied corrections into a FileReport structure."""
    report = FileReport(filename=filename)
    # Group applied corrections by slide index.
    slides: dict[int, list] = {}
    for corr in applied:
        slides.setdefault(corr.slide_idx, []).append(corr)
    for slide_idx in sorted(slides):
        slide_report = SlideReport(slide_idx=slide_idx)
        for corr in slides[slide_idx]:
            slide_report.changes.append(
                ChangeDetail(
                    original=corr.original,
                    corrected=_best_replacement(corr),
                    rule=corr.rule_id,
                )
            )
        report.slides.append(slide_report)
    return report


def run_dir(dir_path: Path, prefer_local: bool = True) -> int:
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

    tool, source = init_languagetool(prefer_local=prefer_local)
    if tool is None:
        print(
            "❌ LanguageTool no disponible (instale Java o verifique la conexión). "
            "Los archivos quedan copiados en corregidos/ sin corrección."
        )
        reports = [FileReport(filename=c.name) for c in copies]
        (dest / "reporte.md").write_text(generate_report(reports), encoding="utf-8")
        return 2

    if source == "cloud":
        print(
            "⚠ Java no encontrado. Usando API pública de LanguageTool (puede ser más lento)"
        )

    all_reports: list[FileReport] = []

    for copy in copies:
        try:
            slides = extract_pptx(copy)
        except Exception:  # noqa: BLE001 - corrupt file is skipped, batch continues
            print(f"⚠ {copy.name}: archivo corrupto, saltado")
            all_reports.append(FileReport(filename=copy.name))
            continue

        corr = review_text(slides, lang="es")
        kept = filter_corrections(corr)
        applied = apply_corrections(copy, slides, kept)

        report = _build_report(copy.name, applied)
        all_reports.append(report)
        print(f"✓ {copy.name}: {len(applied)} corrección(es)")

    report_path = dest / "reporte.md"
    report_path.write_text(generate_report(all_reports), encoding="utf-8")
    print(f"\nReporte: {report_path}")
    return 0


def _best_replacement(corr) -> str:
    if not corr.replacements:
        return ""
    exact = [r for r in corr.replacements if len(r) == len(corr.original)]
    return exact[0] if exact else corr.replacements[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="revisor-pptx",
        description="Corrector ortográfico/gramatical por lotes de archivos .pptx en español.",
    )
    parser.add_argument("dir", help="Directorio con los archivos .pptx a corregir")
    parser.add_argument(
        "--no-local",
        action="store_true",
        help="No intentar el servidor local de LanguageTool (usar solo la API pública)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args(argv)

    return run_dir(Path(args.dir), prefer_local=not args.no_local)


if __name__ == "__main__":
    sys.exit(main())
