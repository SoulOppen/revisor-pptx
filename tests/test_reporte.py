"""Tests for markdown report rendering."""

from __future__ import annotations

from revisor_pptx.reporte import ChangeDetail, FileReport, SlideReport, generate_report


def test_report_empty_results():
    out = generate_report([])
    assert "**0**" in out
    assert "sin correcciones" not in out


def test_report_no_corrections_in_file():
    reports = [FileReport(filename="a.pptx", slides=[])]
    out = generate_report(reports)
    assert "## a.pptx" in out
    assert "sin correcciones" in out  # file present with no changes


def test_report_single_file_single_slide():
    report = FileReport(
        filename="a.pptx",
        slides=[
            SlideReport(
                slide_idx=123,
                changes=[ChangeDetail(original="munod", corrected="mundo", rule="M")],
            )
        ],
    )
    out = generate_report([report])
    assert "# Reporte de correcciones" in out
    assert "## a.pptx" in out
    assert "### Diapositiva 123" in out
    assert "| munod | **mundo** | — | M |" in out


def test_report_multi_file_multi_slide():
    reports = [
        FileReport(
            filename="a.pptx",
            slides=[
                SlideReport(
                    slide_idx=1,
                    changes=[
                        ChangeDetail("un", "una", "R1"),
                        ChangeDetail("munod", "mundo", "R2"),
                    ],
                ),
                SlideReport(
                    slide_idx=2, changes=[ChangeDetail("errta", "errata", "R3")]
                ),
            ],
        ),
        FileReport(filename="b.pptx", slides=[]),
    ]
    out = generate_report(reports)
    assert "## a.pptx" in out
    assert "## b.pptx" in out
    assert "### Diapositiva 1" in out
    assert "### Diapositiva 2" in out
    assert "| un | **una** | — | R1 |" in out
    assert "| errta | **errata** | — | R3 |" in out
    # b.pptx has no slides -> sin correcciones
    assert "sin correcciones" in out


def test_report_escapes_pipe_in_text():
    report = FileReport(
        filename="x.pptx",
        slides=[
            SlideReport(slide_idx=1, changes=[ChangeDetail("a|b", "a\\|b_ok", "R")])
        ],
    )
    out = generate_report([report])
    assert "a\\|b" in out
