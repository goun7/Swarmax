"""Pitch deck (WS-D): structure and evidence-citation regression."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build() -> str:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_pitch_deck.py")],
                   check=True, capture_output=True)
    return (ROOT / "dist" / "pitch_deck.html").read_text(encoding="utf-8")


def test_deck_has_ten_slides():
    doc = _build()
    assert doc.count("class='slide'") == 10
    assert "10" in doc.split("class='slide'")[1]  # page counter present


def test_deck_cites_evidence_and_print_css():
    doc = _build()
    for tag in ("E1", "E4", "E5", "E11", "MT-1…MT-8", "119 tests", "@page"):
        assert tag in doc, f"missing: {tag}"
    assert "landscape" in doc  # A4 landscape print hint
