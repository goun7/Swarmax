"""PDF package builder: converter correctness (WS-4 regression)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_pdf_package as b  # noqa: E402


def test_bold_with_code_spans_and_emphasis():
    src = "v4.2.0 ships **all `gen_ai.*` attributes Development** status and *honest* claims."
    html_out = b.md_to_html(src)
    assert "<strong>" in html_out and "<em>honest</em>" in html_out
    assert "<code>gen_ai.*</code>" in html_out
    assert "**" not in html_out


def test_single_line_display_math():
    src = "$$\\mu_t = \\alpha C_t$$\n\nAfter the formula, **bold** continues."
    html_out = b.md_to_html(src)
    assert "formula" in html_out and "\\mu_t" in html_out
    assert "After the formula" in html_out
    assert "**bold**" not in html_out


def test_blockquote_softwrap_keeps_bold():
    src = ("> Positioning note: Swarmax is not an\n"
           "> \"AI Act certification\"; it is a **technical\n"
           "> infrastructure provider**.\n")
    html_out = b.md_to_html(src)
    assert html_out.count("<blockquote>") == 1
    assert "<strong>technical infrastructure provider</strong>" in html_out


def test_build_generates_cover_and_clean_body(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "DIST", tmp_path)
    src = tmp_path / "mini.md"
    src.write_text("# Mini Blueprint\n\n> **Edition:** English · **Version:** v1.0 · "
                   "**Date:** 2026-09-16\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                   encoding="utf-8")
    out = b.build(src)
    doc = out.read_text(encoding="utf-8")
    assert "cover" in doc and "<table>" in doc and "**" not in doc
