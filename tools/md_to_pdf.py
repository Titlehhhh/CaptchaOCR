"""Markdown -> print-ready HTML, for Edge headless -> PDF.

    python tools/md_to_pdf.py reports/research/00_SYNTHESIS.md out.html

The converter is deliberately small: it covers exactly the markdown that the
project's reports use - headings, paragraphs, tables, fenced code, ordered and
unordered lists, blockquotes, horizontal rules, and inline emphasis, code and
links. It is not a general markdown implementation, and it is not meant to be.

Then print it with the browser that is already on the machine:

    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" ^
        --headless=new --disable-gpu --no-pdf-header-footer ^
        --user-data-dir=%TEMP%\\edge-pdf --print-to-pdf=out.pdf file:///.../out.html
"""

import html
import re
import sys


def inline(text: str) -> str:
    """Inline markdown: code, links, bold, italic."""
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        part = html.escape(part)
        part = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                      r'<a href="\2">\1</a>', part)
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", part)
        out.append(part)
    return "".join(out)


def cells(row: str) -> list:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def is_separator(row: str) -> bool:
    return bool(row.strip()) and set(row.strip()) <= set("|-: ")


def convert(md: str) -> str:
    lines = md.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            continue

        # horizontal rule
        if stripped in ("---", "***", "___"):
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # table
        if stripped.startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            head = cells(stripped)
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(cells(lines[i].strip()))
                i += 1
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>")
            for row in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
            continue

        # blockquote
        if stripped.startswith(">"):
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(block)) + "</blockquote>")
            continue

        # lists
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            ordered = bool(re.match(r"^\d+\.\s", stripped))
            items = []
            while i < len(lines) and re.match(r"^([-*+]|\d+\.)\s+", lines[i].strip()):
                items.append(re.sub(r"^([-*+]|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(it)}</li>" for it in items)
                       + f"</{tag}>")
            continue

        # paragraph
        if stripped:
            block = []
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"^(#{1,6}\s|[-*+]\s|\d+\.\s|\||>|```|---$)", lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            out.append("<p>" + inline(" ".join(block)) + "</p>")
            continue

        i += 1
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
       font-size: 11pt; line-height: 1.5; color: #1a1a1a; max-width: 100%; }
h1 { font-size: 22pt; border-bottom: 2px solid #222; padding-bottom: 6px; }
h2 { font-size: 16pt; margin-top: 26px; border-bottom: 1px solid #bbb;
     padding-bottom: 4px; }
h3 { font-size: 13pt; margin-top: 20px; }
h4 { font-size: 11.5pt; margin-top: 16px; color: #333; }
p { margin: 9px 0; }
ul, ol { margin: 8px 0 12px 22px; padding: 0; }
li { margin: 4px 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0;
        font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #b9b9b9; padding: 5px 7px; text-align: left;
         vertical-align: top; }
th { background: #ececec; font-weight: 600; }
tr:nth-child(even) td { background: #f8f8f8; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9.5pt;
       background: #f0f0f0; padding: 1px 3px; border-radius: 2px; }
pre { background: #f4f4f4; border-left: 3px solid #999; padding: 9px 11px;
      overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 9pt; }
blockquote { border-left: 3px solid #ccc; margin: 10px 0; padding: 2px 12px;
             color: #444; background: #fafafa; }
a { color: #14508c; text-decoration: none; }
hr { border: none; border-top: 1px solid #ccc; margin: 18px 0; }
strong { font-weight: 650; }
"""


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        md = f.read()
    body = convert(md)
    page = ("<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(src)}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {dst} ({len(page)} bytes) from {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
