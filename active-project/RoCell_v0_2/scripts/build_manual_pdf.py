#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

import mistune
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return s or "section"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="ASSEMBLY_MANUAL.md")
    parser.add_argument("--output", default="ASSEMBLY_MANUAL.pdf")
    parser.add_argument("--running-title", default="RoCell v0.2 - Assembly Manual")
    args = parser.parse_args()
    md = Path(args.source)
    if not md.is_absolute():
        md = ROOT / md
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    markdown = mistune.create_markdown(plugins=["table", "strikethrough", "task_lists", "url"])
    body_html = markdown(md.read_text(encoding="utf-8"))
    soup = BeautifulSoup(body_html, "html.parser")

    headings = []
    used = set()
    for h in soup.find_all(["h1", "h2"]):
        base = slugify(h.get_text(" ", strip=True))
        slug = base
        n = 2
        while slug in used:
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        h["id"] = slug
        headings.append((h.name, h.get_text(" ", strip=True), slug))

    toc = BeautifulSoup("<section class='toc'><h1>Contents</h1><ol></ol></section>", "html.parser")
    ol = toc.ol
    for tag, text, slug in headings[1:]:  # visible TOC shows major sections only
        if tag != "h1":
            continue
        li = soup.new_tag("li")
        li["class"] = "toc-h1"
        a = soup.new_tag("a", href=f"#{slug}")
        a.string = text
        li.append(a)
        ol.append(li)
    second_h1 = soup.find_all("h1")[1]
    second_h1.insert_before(toc.section)

    css = r'''
    @page {
      size: Letter;
      margin: 17mm 16mm 18mm 16mm;
      @top-left {
        content: "RUNNING_TITLE";
        font-family: DejaVu Sans, sans-serif;
        font-size: 7.5pt;
        color: #5b6470;
      }
      @top-right {
        content: string(chapter);
        font-family: DejaVu Sans, sans-serif;
        font-size: 7.5pt;
        color: #5b6470;
      }
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: DejaVu Sans, sans-serif;
        font-size: 8pt;
        color: #5b6470;
      }
    }
    @page:first {
      @top-left { content: none; }
      @top-right { content: none; }
      @bottom-center { content: none; }
    }
    html { font-family: DejaVu Sans, sans-serif; color: #17202a; font-size: 9.4pt; line-height: 1.38; }
    body { margin: 0; }
    h1 { color: #123f62; font-size: 19pt; line-height: 1.12; margin: 0 0 8pt 0; string-set: chapter content(); break-before: page; }
    body > h1:first-of-type { break-before: avoid; font-size: 29pt; margin-top: 14mm; color: #0a3656; }
    body > h2:first-of-type { font-size: 16pt; color: #2f668e; margin-top: 0; }
    h2 { color: #2f668e; font-size: 13.5pt; margin-top: 15pt; margin-bottom: 6pt; break-after: avoid; }
    h3 { color: #36576d; font-size: 11.5pt; margin-top: 12pt; margin-bottom: 5pt; break-after: avoid; }
    p { margin: 5pt 0 7pt 0; orphans: 3; widows: 3; }
    ul, ol { margin: 5pt 0 8pt 17pt; padding: 0; }
    li { margin: 2.3pt 0; }
    strong { color: #0a3656; }
    blockquote { border-left: 4pt solid #d88916; background: #fff6e8; padding: 8pt 10pt; margin: 10pt 0 13pt; color: #4c3412; break-inside: avoid; }
    blockquote p { margin: 0; }
    table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt; font-size: 7.9pt; break-inside: auto; }
    thead { display: table-header-group; }
    tr { break-inside: avoid; }
    th { background: #dfeaf2; color: #173c56; font-weight: bold; text-align: left; padding: 4pt; border: 0.5pt solid #8fa7b7; }
    td { padding: 3.3pt 4pt; border: 0.5pt solid #b6c4ce; vertical-align: top; }
    tbody tr:nth-child(even) { background: #f7f9fa; }
    code { font-family: DejaVu Sans Mono, monospace; background: #eef2f4; color: #1d3646; padding: 0.5pt 2pt; border-radius: 2pt; font-size: 8.2pt; }
    pre { background: #17242d; color: #f5f7f8; padding: 8pt; border-radius: 4pt; font-size: 7.8pt; line-height: 1.28; white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; }
    pre code { background: transparent; color: inherit; padding: 0; }
    img { display: block; max-width: 100%; max-height: 150mm; margin: 10pt auto 13pt; object-fit: contain; break-inside: avoid; }
    a { color: #1c6592; text-decoration: none; }
    .toc { break-before: page; break-after: page; }
    .toc h1 { break-before: avoid; }
    .toc ol { list-style: none; margin-left: 0; }
    .toc li { border-bottom: 0.3pt dotted #a8b4bd; padding: 3pt 0; }
    .toc-h2 { padding-left: 14pt !important; font-size: 8.6pt; }
    body > table:first-of-type { margin-top: 12pt; font-size: 9pt; }
    body > img:first-of-type { max-height: 105mm; margin-top: 13mm; }
    body > blockquote:first-of-type { margin-top: 10pt; }
    '''.replace("RUNNING_TITLE", args.running_title.replace('"', "'"))

    base_uri = ROOT.resolve().as_uri() + "/"
    document = f"""<!doctype html>
<html><head><meta charset='utf-8'><base href='{base_uri}'><style>{css}</style></head>
<body>{str(soup)}</body></html>"""
    rendered = False
    if os.name != "nt":
        try:
            from weasyprint import HTML
            HTML(string=document, base_url=str(ROOT)).write_pdf(str(out))
            rendered = True
        except (ImportError, OSError):
            pass
    if not rendered:
        candidates = [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        ]
        browser = next((path for path in candidates if path.exists()), None)
        if browser is None:
            raise RuntimeError("WeasyPrint is unavailable and no supported browser was found")
        with tempfile.TemporaryDirectory(prefix="rocell-manual-") as temp_dir:
            html_path = Path(temp_dir) / f"{md.stem}.html"
            html_path.write_text(document, encoding="utf-8")
            subprocess.run([
                str(browser), "--headless=new", "--disable-gpu",
                "--no-pdf-header-footer", f"--print-to-pdf={out}",
                html_path.resolve().as_uri(),
            ], check=True)
    print(out)


if __name__ == "__main__":
    main()
