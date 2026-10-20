"""Compile a session's runs into one report, as DOCX and PDF.

Layout follows the project's manuscript formatting spec: Times New Roman
everywhere, justified, double-spaced body with 0.5 inch first-line indent,
only subsection headings italic, 10 pt tables with a bold header row, short
non-italic captions, page numbers, title page with a short title, keyboard
characters only. The PDF is drawn directly (fpdf2), so no office suite is
needed on the researcher's machine.
"""
from __future__ import annotations

import datetime as dt
import io
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from fpdf import FPDF
from fpdf.fonts import FontFace

from . import __version__, citations
from .catalog import TECHNIQUES, tiers

FONT = "Times New Roman"


def ascii_only(s: str) -> str:
    """The formatting spec allows keyboard characters only."""
    repl = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
            "†": "+", "²": "^2", "µ": "u", "…": "...", "→": "->", "×": "x",
            "≤": "<=", "≥": ">=", "≈": "~", "±": "+/-", "−": "-", "°": " deg ",
            "→": "->", "α": "alpha", "β": "beta", "γ": "gamma", "Γ": "Gamma",
            "Δ": "Delta", "μ": "u", "Å": "A"}
    s = "".join(repl.get(ch, ch) for ch in str(s))
    s = s.replace("**", "").replace("`", "")                # markdown carried in from toolkit evidence
    return s.encode("ascii", "replace").decode("ascii")


def build_content(runs: list[dict], meta: dict) -> dict:
    """One neutral structure that both writers render."""
    sections, refs, followups = [], [], []
    repeated = {r["technique"] for r in runs if sum(x["technique"] == r["technique"] for x in runs) > 1}
    for i, run in enumerate(runs, 1):
        t = TECHNIQUES[run["technique"]]
        method = next((m for m in t.methods if m.key == run["method"]), None)
        label = method.label if method else run["method"]
        sections.append({
            "title": f"3.{i} {t.title}" + (f" ({label})" if t.id in repeated else ""),
            "method": method.label if method else run["method"],
            "principle": method.principle if method else "",
            "data_note": run.get("data_note", ""),
            "values": run["values"], "figures": run["figures"],
            "conclusion": run["conclusion"], "warnings": run["warnings"],
            "tiers": tiers(t, run["toolkit_calls"]), "calls": run["toolkit_calls"],
        })
        for k in t.citations + ["surfactantkit"]:
            if k not in refs:
                refs.append(k)
        for f in t.followups:
            if f not in followups:
                followups.append(f)
    return {"meta": meta, "sections": sections, "refs": citations.for_keys(refs), "followups": followups}


def _tier_rows(content: dict) -> list[list[str]]:
    """One row per (analysis, function), in report order; repeated runs do not repeat rows."""
    rows, seen = [], set()
    for s in content["sections"]:
        name = s["title"].split(" ", 1)[1]
        for t in s["tiers"]:
            if (name, t["tool"]) not in seen:
                seen.add((name, t["tool"]))
                rows.append([name, t["tool"], t["tier"], t["evidence"] or t["meaning"]])
    return rows


# ------------------------------------------------------------------- DOCX
def _font(run, size=12, bold=False, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)


def _para(doc, text, size=12, bold=False, italic=False, indent=True, double=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = align
    pf.space_before = Pt(2)
    pf.space_after = Pt(2)
    pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE if double else WD_LINE_SPACING.SINGLE
    pf.first_line_indent = Inches(0.5) if indent else None
    _font(p.add_run(ascii_only(text)), size, bold, italic)
    return p


def _heading(doc, text, sub=False):
    # top-level: bold, upright; subsection: bold, whole heading italic (the only italics allowed)
    return _para(doc, text, 12, bold=True, italic=sub, indent=False)


def _page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    _font(run, 10)


def _table(doc, rows, header):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for cell, h in zip(t.rows[0].cells, header):
        cell.text = ""
        r = cell.paragraphs[0].add_run(ascii_only(h))
        _font(r, 10, bold=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for row in rows:
        cells = t.add_row().cells
        for cell, v in zip(cells, row):
            cell.text = ""
            r = cell.paragraphs[0].add_run(ascii_only(v))
            _font(r, 10)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return t


def to_docx(content: dict) -> bytes:
    m = content["meta"]
    doc = Document()
    sec = doc.sections[0]
    _page_number_footer(sec)

    _para(doc, m["title"], 16, bold=True, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, f"Short title: {m['short_title']}", indent=False, align=WD_ALIGN_PARAGRAPH.CENTER)
    for line in (m.get("author", ""), m.get("affiliation", ""), m["date"]):
        if line:
            _para(doc, line, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, "Analysis performed locally with SurfactantKit Studio; the data did not leave this computer.",
          10, indent=False, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_section(WD_SECTION.NEW_PAGE)

    tcount = fcount = 0
    _heading(doc, "1. Summary")
    for s in content["sections"]:
        _para(doc, f"{s['title'][4:]}: " + " ".join(s["conclusion"]))
    _heading(doc, "2. Data and methods")
    _para(doc, "Each analysis below states the method used and the principle behind it. Values were computed "
               "with the SurfactantKit library; the function calls are listed in the appendix.")
    _heading(doc, "3. Results")
    for s in content["sections"]:
        _heading(doc, s["title"], sub=True)
        _para(doc, f"Method: {s['method']}. {s['principle']}")
        if s["data_note"]:
            _para(doc, s["data_note"])
        tcount += 1
        _para(doc, f"Table {tcount}. Results: {s['title'][4:]}.", 10, indent=False, double=False)
        _table(doc, [[v["label"], v["text"]] for v in s["values"]], ["Quantity", "Value"])
        for f in s["figures"]:
            fcount += 1
            doc.add_picture(io.BytesIO(f["png"]), width=Inches(5.0))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _para(doc, f"Figure {fcount}. {f['caption']}", 10, indent=False, double=False)
        for c in s["conclusion"]:
            _para(doc, c)
        for w in s["warnings"]:
            _para(doc, f"Caution: {w}")
    _heading(doc, "4. Accuracy and validation")
    _para(doc, "Each SurfactantKit function carries a validation tier: T1 reproduces published numbers from the "
               "primary literature; T2 means the equation was checked against its source but no published worked "
               "number exists to match; T3 is an estimate by construction. Tiers describe the method, not your data: "
               "the quality of the measured curve still limits the result.")
    rows = _tier_rows(content)
    tcount += 1
    _para(doc, f"Table {tcount}. Validation tier of each function used.", 10, indent=False, double=False)
    _table(doc, rows, ["Analysis", "Function", "Tier", "Evidence"])
    _heading(doc, "5. Suggested next steps")
    for f in content["followups"]:
        _para(doc, f)
    _heading(doc, "References")
    for i, r in enumerate(content["refs"], 1):
        doi = f" https://doi.org/{r['doi']}" if r["doi"] else ""
        _para(doc, f"[{i}] {r['text']}{doi}", indent=False)
    _heading(doc, "Appendix: software and function calls")
    _para(doc, f"SurfactantKit Studio {__version__}; SurfactantKit {m['toolkit_version']}.", indent=False)
    for s in content["sections"]:
        _para(doc, f"{s['title'][4:]}: " + "; ".join(s["calls"]), 10, indent=False, double=False)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# -------------------------------------------------------------------- PDF
class _PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Times", "", 10)
        self.cell(0, 10, str(self.page_no()), align="C")


def to_pdf(content: dict) -> bytes:
    m = content["meta"]
    pdf = _PDF(format="A4")
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(True, 25)
    lh = 10  # double spacing for 12 pt body (approx. 2 x 4.2 mm)
    W = pdf.w - 50

    def para(text, size=12, style="", indent=True, double=True, align="J"):
        pdf.set_font("Times", style, size)
        # line_height is a multiple of the font size: 2.0 = double spacing
        with pdf.text_columns(text_align=align, line_height=2.0 if double else 1.15) as cols:
            with cols.paragraph(first_line_indent=12.7 if indent else 0, top_margin=0.7) as p:
                p.write(ascii_only(text))
        pdf.ln(0.7)

    def heading(text, sub=False):
        para(text, 12, "BI" if sub else "B", indent=False)

    pdf.add_page()
    pdf.ln(50)
    para(m["title"], 16, "B", indent=False, align="C")
    para(f"Short title: {m['short_title']}", indent=False, align="C")
    for line in (m.get("author", ""), m.get("affiliation", ""), m["date"]):
        if line:
            para(line, indent=False, align="C")
    para("Analysis performed locally with SurfactantKit Studio; the data did not leave this computer.",
         10, indent=False, align="C")

    pdf.add_page()
    tcount = fcount = 0
    heading("1. Summary")
    for s in content["sections"]:
        para(f"{s['title'][4:]}: " + " ".join(s["conclusion"]))
    heading("2. Data and methods")
    para("Each analysis below states the method used and the principle behind it. Values were computed with the "
         "SurfactantKit library; the function calls are listed in the appendix.")
    heading("3. Results")

    def table(rows, header, widths):
        pdf.set_font("Times", "", 10)
        with pdf.table(col_widths=widths, text_align="J", line_height=5,
                       headings_style=FontFace(emphasis="BOLD")) as tb:
            hr = tb.row()
            for h in header:
                hr.cell(ascii_only(h))
            for row in rows:
                r = tb.row()
                for v in row:
                    r.cell(ascii_only(v))
        pdf.ln(2)

    for s in content["sections"]:
        heading(s["title"], sub=True)
        para(f"Method: {s['method']}. {s['principle']}")
        if s["data_note"]:
            para(s["data_note"])
        tcount += 1
        para(f"Table {tcount}. Results: {s['title'][4:]}.", 10, indent=False, double=False)
        table([[v["label"], v["text"]] for v in s["values"]], ["Quantity", "Value"], (3, 2))
        for f in s["figures"]:
            fcount += 1
            pdf.image(io.BytesIO(f["png"]), w=120, x=(pdf.w - 120) / 2)
            para(f"Figure {fcount}. {f['caption']}", 10, indent=False, double=False)
        for c in s["conclusion"]:
            para(c)
        for w in s["warnings"]:
            para(f"Caution: {w}")
    heading("4. Accuracy and validation")
    para("Each SurfactantKit function carries a validation tier: T1 reproduces published numbers from the primary "
         "literature; T2 means the equation was checked against its source but no published worked number exists to "
         "match; T3 is an estimate by construction. Tiers describe the method, not your data: the quality of the "
         "measured curve still limits the result.")
    rows = _tier_rows(content)
    tcount += 1
    para(f"Table {tcount}. Validation tier of each function used.", 10, indent=False, double=False)
    table(rows, ["Analysis", "Function", "Tier", "Evidence"], (3, 4, 1, 6))
    heading("5. Suggested next steps")
    for f in content["followups"]:
        para(f)
    heading("References")
    for i, r in enumerate(content["refs"], 1):
        doi = f" https://doi.org/{r['doi']}" if r["doi"] else ""
        para(f"[{i}] {r['text']}{doi}", indent=False)
    heading("Appendix: software and function calls")
    para(f"SurfactantKit Studio {__version__}; SurfactantKit {m['toolkit_version']}.", indent=False)
    for s in content["sections"]:
        para(f"{s['title'][4:]}: " + "; ".join(s["calls"]), 10, indent=False, double=False)
    return bytes(pdf.output())


def default_meta(sample: str = "", author: str = "", affiliation: str = "") -> dict:
    import surfactantkit
    title = f"Surfactant analysis report{': ' + sample if sample else ''}"
    short = re.sub(r"\s+", " ", f"Analysis {sample}".strip())[:40]
    return {"title": title, "short_title": short, "author": author, "affiliation": affiliation,
            "date": dt.date.today().isoformat(),
            "toolkit_version": getattr(surfactantkit, "__version__", "unknown")}
