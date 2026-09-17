#!/usr/bin/env python
"""Build the print-ready PDF package (no pandoc, no deps).

Converts the blueprint markdown documents into self-contained, print-optimized
HTML files under dist/. To get a PDF: open the HTML in any browser and print
(Ctrl+P) to "Save as PDF" — page margins, page breaks and the cover page are
styled in @media print.

  python scripts/build_pdf_package.py            # SWARMAX + SWARMAX_EN + ONEPAGER
  python scripts/build_pdf_package.py file.md …  # specific documents
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

DEFAULT_DOCS = ["SWARMAX.md", "SWARMAX_EN.md", "SWARMAX_ONEPAGER.md",
                "AI_ACT_COMPLIANCE.md", "UPGRADE_GUIDE.md",
                "LABELING_TEMPLATES.md"]

CSS = """
:root { color-scheme: light }
body { font-family: Georgia, 'Times New Roman', serif; margin: 0 auto; max-width: 52em;
       padding: 2em; line-height: 1.55; color: #1a1a1a; background: white }
h1, h2, h3, h4 { font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.25;
                 color: #111; page-break-after: avoid }
h1 { font-size: 1.7em; border-bottom: 2px solid #222; padding-bottom: .3em }
h2 { font-size: 1.3em; margin-top: 2em; border-bottom: 1px solid #999 }
h3 { font-size: 1.1em; margin-top: 1.5em }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .85em;
        font-family: 'Helvetica Neue', Arial, sans-serif; page-break-inside: avoid }
th, td { border: 1px solid #bbb; padding: 5px 8px; text-align: left; vertical-align: top }
th { background: #efefef }
code { font-family: 'SF Mono', Consolas, monospace; font-size: .85em; background: #f4f4f4;
       padding: 1px 4px; border-radius: 3px }
pre { background: #f6f6f6; border: 1px solid #ddd; border-radius: 6px; padding: 12px;
      overflow-x: auto; page-break-inside: avoid }
pre code { background: none; padding: 0 }
blockquote { border-left: 4px solid #888; margin: 1em 0; padding: .2em 1em; color: #333;
             background: #f9f9f9 }
a { color: #0a4d8c; text-decoration: none }
.cover { text-align: center; padding-top: 30vh; page-break-after: always }
.cover h1 { border: none; font-size: 2.4em }
.cover .sub { color: #555; font-size: 1.05em }
@media print {
  body { max-width: none; padding: 0; font-size: 10.5pt }
  @page { size: A4; margin: 18mm 16mm; @bottom-center { content: counter(page) " / " counter(pages);
          font-family: Arial; font-size: 9pt; color: #666 } }
  h2 { page-break-before: auto }
  a { color: #1a1a1a }
}
"""


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    # protect code spans so their ``*``/``_`` never feed the emphasis regexes
    codes: list[str] = []

    def _stash(m: re.Match) -> str:
        codes.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", _stash, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)  # lazy: crosses nested tags
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    for i, c in enumerate(codes):
        s = s.replace(f"\x00{i}\x00", c)
    return s


def _table(lines: list[str], out: list[str]) -> None:
    rows = [l for l in lines if re.match(r"^\s*\|.*\|\s*$", l)]
    if len(rows) < 2 or not re.match(r"^\s*\|[\s:|-]+\|\s*$", rows[1]):
        for l in lines:
            out.append(f"<p>{_inline(l.strip().strip('|'))}</p>")
        return
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    out.append("<table><thead><tr>" +
               "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        cells += [""] * (len(header) - len(cells))
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table>")


def md_to_html(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i, n = 0, len(lines)
    para: list[str] = []
    while i < n:
        line = lines[i]
        if line.startswith("```"):  # fenced code
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            lang = line[3:].strip()
            body: list[str] = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                body.append(lines[i]); i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>")
        elif re.match(r"^\s*\|", line):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            block: list[str] = []
            while i < n and re.match(r"^\s*\|", lines[i]):
                block.append(lines[i]); i += 1
            _table(block, out)
            continue
        elif line.startswith("$$"):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            stripped = line.rstrip()
            if stripped.endswith("$$") and len(stripped) > 4:
                # single-line display math: $$ … $$
                out.append("<pre class='formula'><code>" +
                           html.escape(stripped.strip("$ ")) + "</code></pre>")
                i += 1
                continue
            formula = [stripped.strip("$")]
            i += 1
            while i < n and not lines[i].rstrip().endswith("$$"):
                formula.append(lines[i]); i += 1
            if i < n:
                formula.append(lines[i].rstrip().rstrip("$"))
                i += 1
            out.append("<pre class='formula'><code>" + html.escape("\n".join(
                l.strip("$") for l in formula)) + "</code></pre>")
            continue
        elif re.match(r"^#{1,4}\s", line):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            m = re.match(r"^(#{1,4})\s+(.*)", line)
            lvl, txt = len(m.group(1)), m.group(2)
            out.append(f"<h{lvl}>{_inline(txt)}</h{lvl}>")
        elif line.startswith(">"):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            # consecutive quote lines merge into paragraphs; a blank quote line
            # starts a new one (markdown soft-wrap must not split **bold**)
            quote: list[str] = []
            while i < n and lines[i].startswith(">"):
                text = lines[i].lstrip("> ").rstrip()
                if text:
                    quote.append(text)
                elif quote:
                    out.append("<blockquote><p>" + _inline(" ".join(quote)) + "</p></blockquote>")
                    quote = []
                i += 1
            if quote:
                out.append("<blockquote><p>" + _inline(" ".join(quote)) + "</p></blockquote>")
            continue
        elif re.match(r"^\s*[-*]\s", line) or re.match(r"^\s*\d+\.\s", line):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items: list[str] = []
            while i < n and (re.match(r"^\s*[-*]\s", lines[i]) or
                             (ordered and re.match(r"^\s*\d+\.\s", lines[i]))):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i])); i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(it)}</li>" for it in items) +
                       f"</{tag}>")
            continue
        elif line.strip() in ("---", "***", "___"):
            if para:
                out.append(f"<p>{_inline(' '.join(para))}</p>"); para = []
            out.append("<hr>")
        elif line.strip():
            para.append(line.strip())
        elif para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para = []
        i += 1
    if para:
        out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out)


def build(path: Path) -> Path:
    md = path.read_text(encoding="utf-8")
    title_m = re.match(r"^#\s+(.+)", md)
    title = title_m.group(1) if title_m else path.stem
    status_m = re.search(r"\*\*(?:Sürüm|Edition|Version):\*\*\s*v?([\d.]+)", md)
    date_m = re.search(r"\*\*(?:Tarih|Date):\*\*\s*([\d-]+)", md)
    version = status_m.group(1) if status_m else ""
    date = date_m.group(1) if date_m else ""
    body = md_to_html(md)
    cover = (f"<div class='cover'><h1>{html.escape(title)}</h1>"
             f"<p class='sub'>SWARMAX blueprint package · version {html.escape(version)}"
             f" · {html.escape(date)}</p>"
             f"<p class='sub'>Print: Ctrl/Cmd+P → Save as PDF</p></div>")
    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
           f"{cover}{body}</body></html>")
    DIST.mkdir(exist_ok=True)
    out = DIST / (path.stem + ".html")
    out.write_text(doc, encoding="utf-8")
    return out


def main() -> int:
    names = sys.argv[1:] or DEFAULT_DOCS
    for name in names:
        p = ROOT / name
        if not p.exists():
            print(f"skip (missing): {name}")
            continue
        out = build(p)
        print(f"built {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    print("\nPDF: open a dist/*.html file in a browser and print to 'Save as PDF'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
