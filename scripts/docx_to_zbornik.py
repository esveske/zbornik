#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Petnica DOCX → Zbornik LaTeX converter

Overview
--------
This script converts a Microsoft Word .docx file prepared with the Petnica
template (or a close variant) into a LaTeX source file that fits the Zbornik
workflow. It targets the macro set used by the Petničke sveske / Zbornik
class (e.g. `sveska.cls`) and emits a single `main.tex` plus any extracted
media. The output is designed to compile with XeLaTeX or LuaLaTeX.

What it produces
----------------
`<output_dir>/main.tex` with the following structure (macros expected to be
provided by the Petnica LaTeX class):
  \Author{...}
  \Title{...}
  \TitleEng{...}                   % when available/recovered
  \begin{Abstract} ... \end{Abstract}
  \begin{AuthorEx} ... \end{AuthorEx}  % “Autorstvo” footnote content
  \begin{AbstractEng} ... \end{AbstractEng}
  \StartDoublePaper
  % body: text, lists, figures, tables, sections...
  \section{Literatura}
  \Source{...}                     % one per reference entry (non-empty only)
  \EndPaper

And a set of copied/normalized media files placed in `<output_dir>`.

High-level pipeline
-------------------
1) Unzip and parse the DOCX:
   - Parse `word/document.xml` as a sequence of block elements (paragraphs and tables).
   - Load `word/_rels/document.xml.rels` to resolve embedded images and hyperlinks.
   - Load `word/numbering.xml` (if present) to understand list formatting (bullet vs decimal).

2) Preprocess:
   - Collect text from any text boxes (`wps:txbx`) styled "Autorstvo" (used for the AuthorEx footnote).
   - Inspect section properties to estimate single-column width (for wide figure heuristic).

3) Convert blocks (single pass, in document order):
   - Front matter by style:
     * `Imeiprezime`: the first occurrence is taken as the authors line (flag-guarded).
     * `Autorstvo`: collected for the AuthorEx footnote.
     * `Naslov`: Serbian title.
     * `Apstrakt`: Serbian abstract paragraphs (rich text to LaTeX).
     * `TitleEng`: English title (if provided).
     * `AbstractEng`: English abstract paragraphs (if provided).
   - Body content:
     * Section headings: by Word style (`Heading2/3/4`) or by recognizable titles
       (e.g., "Uvod", "Rezultati", "Diskusija", "Zaključak", "Literatura", etc.).
       Emitted as `\section`, `\subsection`, or `\subsubsection`.
     * Lists: inspect `w:numPr` (numId/ilvl). Map bullets → `itemize`, decimals → `enumerate`.
       Maintain a nesting stack, open/close environments as needed.
     * Figures: detect inline drawings; resolve target via relationships; compute width (EMU)
       and compare with the estimated single-column width.
         - Wide figures → `\FigureDouble{file}{sr}{en}`
         - Regular figures → `\Figure[H]{file}{sr}{en}`
       Captions are detected near the figure within ±5 paragraphs, bilingual-aware:
         “Slika N: … / Figure N: …”. The caption paragraphs are marked consumed and
         not emitted as body text. If captions are embedded in the same paragraph,
         they are captured and attached to the figure at emission time.
     * Tables: convert `w:tbl` to a tabular environment, tracking horizontal spans
       (`w:gridSpan` → `\multicolumn`). Vertical merges (`w:vMerge`) are detected; a
       warning is emitted (no `\multirow` synthesis). A simple, robust column spec is
       generated using centered columns. Wide tables are selected by heuristic:
         - Many columns (≥4), or a long header line, or long cells with ≥3 columns
         → `\TableDouble{<tabular>}{sr}{en}{}`
         Else → `\Table{<tabular>}{sr}{en}{}`
       Captions are detected exactly as for figures. The “{ }” slot is reserved for
       optional notes.
     * References: the first paragraph styled "Literatura" or with literal text
       “literatura” / “references” starts a dedicated references section:
         - Emit exactly one `\section{Literatura}`.
         - While collecting references, each non-blank paragraph is emitted as
           `\Source{...}` (empty lines are ignored to avoid stray `\Source{}`).
         - Collection ends on the next heading/section marker.

4) English tail recovery (when the document lacks English title/abstract):
   - After the last “Literatura/References” marker, scan the tail:
     * Detect an English name line (Latin letters, title-case heuristic).
     * Next line that looks like a short English title (≤16 words) becomes `\TitleEng`.
     * 1–3 following English paragraphs (keyword heuristic) form `AbstractEng`.

5) Media handling:
   - All embedded images referenced by relationships are copied verbatim to `<output_dir>`.
   - Optional normalization (best-effort, if tools are present):
     * Convert EMF/WMF/TIFF → PNG using LibreOffice (`soffice --headless`).
     * Sanitize filenames to ASCII (deduplicate if necessary).
     * Optionally downsize large rasters using ImageMagick `mogrify`.
   - If filenames were changed by normalization, `main.tex` is rewritten to update paths.

Word styles and heuristics
--------------------------
Recognized front-matter styles:
  - `Imeiprezime` → `\Author{...}` (first occurrence only; a flag prevents duplicates).
  - `Autorstvo` → content for `\begin{AuthorEx}...\end{AuthorEx}`.
  - `Naslov` → `\Title{...}`.
  - `Apstrakt` → `\begin{Abstract}...\end{Abstract}`.
  - `TitleEng` → `\TitleEng{...}`.
  - `AbstractEng` → `\begin{AbstractEng}...\end{AbstractEng}`.

Section heading styles:
  - `Heading2` → `\section{...}`
  - `Heading3` → `\subsection{...}`
  - `Heading4` → `\subsubsection{...}`
  - In addition, the converter recognizes common section titles by text (e.g., “Uvod”,
    “Rezultati”, “Diskusija”, “Zaključak”, “Literatura”) and treats them as section starts.

Caption detection (figures/tables):
  - Search window: ±5 paragraphs around the figure/table block; skip empty lines.
  - Bilingual pattern (case-insensitive): `^(Slika|Figure|Tabela|Table) <N>[:.]? <text>`
  - When both Serbian and English are found, both are attached. Otherwise the available
    caption is reused for both languages. The numeric `<N>` is honored when the
    sequential counter matches; otherwise, the line is accepted opportunistically.
  - Consumed caption paragraphs are suppressed from the output.

Lists:
  - Preserve nesting and list type using `word/numbering.xml` (bullet vs decimal).
  - Gaps in nesting levels are filled with `itemize` to keep LaTeX balanced.

Math conversion (Pandoc required)
---------------------------------
- Math is converted **only via Pandoc**:
  1) Try Pandoc’s OMML reader (`-f omml -t latex`) directly on the math XML nodes.
  2) If unavailable, wrap the math in a minimal DOCX and let Pandoc convert from DOCX.
- If Pandoc is missing or both conversion paths fail, the converter aborts with a
  clear error message. There is **no internal OMML fallback**.
- Inline math is emitted as `\( ... \)`, display math as `\begin{equation}...\end{equation}`
  unless Pandoc has already produced a block environment.

Hyperlinks and inline formatting
--------------------------------
- Hyperlinks created in Word (with relationship targets) are converted to `\href{...}{text}`.
- Inline text runs retain a subset of formatting: bold, italic, underline, code
  (`\texttt{}`), superscript (`\textsuperscript{}`), subscript (`\textsubscript{}`).
- Text is escaped for LaTeX special characters.

AuthorEx placement
------------------
- All “Autorstvo” lines are collected into `\begin{AuthorEx}...\end{AuthorEx}` in the header.
- `\AuthorExHere` is inserted automatically just before the **first piece of emitted content**
  (text/figure/table/heading) in the body, ensuring the footnote marker appears in the right place.

Wide/regular figures and tables
-------------------------------
- The script estimates the single-column width from section properties (`w:sectPr/w:cols`)
  and compares it to the image’s EMU width from the drawing `wp:extent`.
- Figures wider than ~105% of one column are emitted as `\FigureDouble{...}` (two columns),
  otherwise `\Figure[H]{...}`.
- Tables use a simple heuristic (column count/length) to choose between `\Table` and
  `\TableDouble`.

References
----------
- The references section is emitted exactly once as `\section{Literatura}`.
- Each **non-blank** paragraph while collecting references becomes one `\Source{...}`.
  (Blank paragraphs are ignored to avoid stray `\Source{}`.)
- Reference collection ends on the next heading/section marker or abstract marker.

CLI
---
Usage:
  python3 docx_to_zbornik.py INPUT.docx OUTPUT_DIR [--label LABEL]

Arguments:
  INPUT.docx   Path to the source DOCX.
  OUTPUT_DIR   Directory where `main.tex` and media files are written.
  --label      Optional LaTeX label to add after `\StartDoublePaper`. If omitted,
               a label is generated from the input filename: `doc:<slug>`.

Exit codes:
  0  Success.
  2  Input file not found.
  3  Pandoc missing or failed to convert math (hard error).

External tools (optional but supported):
  - LibreOffice (`soffice`) for EMF/WMF/TIFF → PNG conversion.
  - ImageMagick (`mogrify`) for optional raster downscaling.

Assumptions and limitations
---------------------------
- The converter targets the subset of Word features typical for Petnica papers.
- Vertical table merges (`w:vMerge`) are detected, but no `\multirow` is generated;
  a warning is printed to stderr.
- Only the **first** `Imeiprezime` paragraph is used as the authors line (flag-guarded),
  reflecting the expected Petnica template usage.
- Captions are matched by a narrow bilingual pattern and a small neighborhood window.
- Complex shapes, floating text frames (other than text boxes used for “Autorstvo”),
  and exotic numbering/custom styles are not fully supported.
- Bibliographic formatting is not interpreted; references are passed verbatim to
  `\Source{...}` entries.
- The LaTeX macros referenced here must exist in the document class/style you compile with.

Implementation notes
--------------------
- XML is parsed with `xml.etree.ElementTree`.
- Namespaces are centralized via `NS` and accessed through helper functions.
- Lists are decoded using `word/numbering.xml` mapping from `numId`/`ilvl` to
  abstract list definitions, simplified to bullet vs decimal.
- Filenames are sanitized to ASCII and deduplicated; any renames are reflected back
  into `main.tex`.
- Diagnostic warnings and errors are printed to stderr; progress messages (like
  “Wrote …” and “Copied media …”) go to stdout.

Compile the result with XeLaTeX or LuaLaTeX under the Petnica/Zbornik class.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
import shutil
import zipfile
import tempfile
from copy import deepcopy
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import xml.etree.ElementTree as ET

# Namespace map used throughout the document
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}

ET.register_namespace("w", NS["w"])
ET.register_namespace("m", NS["m"])
ET.register_namespace("r", NS["r"])

_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

# -------------------------------------------------------------------------
# Convenience wrappers
def qname(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"

def find(parent: ET.Element, path: str) -> Optional[ET.Element]:
    return parent.find(path, NS)

def findall(parent: ET.Element, path: str) -> List[ET.Element]:
    return parent.findall(path, NS)

# -------------------------------------------------------------------------
# Utility helpers

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

def escape_latex(text: str) -> str:
    out: List[str] = []
    for ch in text:
        out.append(LATEX_SPECIALS.get(ch, ch))
    return "".join(out)

def slugify(text: str, *, fallback: str = "paper") -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or fallback

def is_likely_name(line: str) -> bool:
    """Heuristic for author names."""
    line = line.strip()
    if not line or any(ch.isdigit() for ch in line):
        return False
    if line.lower() == "ime i prezime":
        return False
    words = [w for w in re.split(r"\s+", line) if w]
    if not (1 <= len(words) <= 6):
        return False
    good = 0
    for w in words:
        parts = w.split("-")
        if all(p and p[0].isupper() for p in parts):
            good += 1
    return good >= max(1, len(words) - 1)

def looks_like_section_title(text: str) -> bool:
    s = text.strip().lower()
    candidates = {
        "uvod", "introdukcija", "introduction",
        "materijal i metode", "materials and methods",
        "rezultati", "results",
        "diskusija", "discussion",
        "zaključak", "zakljucak", "conclusion", "conclusions",
        "literatura", "references", "reference",
        "prilog", "appendix",
    }
    return s in candidates

def ascii_sanitize(stem: str) -> str:
    s = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return s or "img"

# Full caption pattern
CAP_FULL = re.compile(
    r"^\s*(Slika|Figure|Tabela|Table)\s+(\d+)[:\.]?\s*(.*\S)?\s*$",
    re.IGNORECASE,
)

EMU_PER_INCH = 914400
TWIPS_PER_INCH = 1440
EMU_PER_TWIP = EMU_PER_INCH / TWIPS_PER_INCH

# -------------------------------------------------------------------------
# DOCX plumbing

class DocxPackage:
    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path)
        self._document: Optional[ET.Element] = None
        self._relationships: Optional[Dict[str, str]] = None
        self._numbering: Optional[Dict[str, Dict[int, str]]] = None

    @property
    def document(self) -> ET.Element:
        if self._document is None:
            data = self.zip.read("word/document.xml")
            self._document = ET.fromstring(data)
        return self._document

    @property
    def relationships(self) -> Dict[str, str]:
        if self._relationships is None:
            rels: Dict[str, str] = {}
            tree = ET.fromstring(self.zip.read("word/_rels/document.xml.rels"))
            for node in tree.findall(".//rel:Relationship", {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}):
                r_id = node.attrib["Id"]
                target = node.attrib["Target"]
                rels[r_id] = target
            self._relationships = rels
        return self._relationships

    @property
    def numbering(self) -> Dict[str, Dict[int, str]]:
        """Return mapping: numId -> {level -> numFmt} (bullet, decimal, ...)."""
        if self._numbering is not None:
            return self._numbering
        result: Dict[str, Dict[int, str]] = defaultdict(dict)
        try:
            data = self.zip.read("word/numbering.xml")
        except KeyError:
            self._numbering = result
            return result
        root = ET.fromstring(data)
        abstract_fmt: Dict[str, Dict[int, str]] = defaultdict(dict)
        for abs_num in root.findall("w:abstractNum", NS):
            abs_id = abs_num.attrib[qname("w", "abstractNumId")]
            for lvl in abs_num.findall("w:lvl", NS):
                ilvl = int(lvl.attrib[qname("w", "ilvl")])
                fmt = lvl.find("w:numFmt", NS)
                if fmt is not None:
                    abstract_fmt[abs_id][ilvl] = fmt.attrib[qname("w", "val")]
        for num in root.findall("w:num", NS):
            num_id = num.attrib[qname("w", "numId")]
            abs_id = find(num, "w:abstractNumId")
            if abs_id is None:
                continue
            abs_val = abs_id.attrib[qname("w", "val")]
            result[num_id] = abstract_fmt.get(abs_val, {})
        self._numbering = result
        return result

    def read_image(self, target: str) -> bytes:
        normalized = Path("word") / Path(target)
        with self.zip.open(str(normalized)) as fh:
            return fh.read()

# -------------------------------------------------------------------------
# Conversion context

class ConversionContext:
    def __init__(self, docx: DocxPackage):
        self.docx = docx
        self.blocks = list(findall(docx.document, ".//w:body/*"))
        self.author_box_lines: List[str] = []
        self._preprocess_blocks()
        self.single_column_width_emu: Optional[float] = self._compute_single_column_width_emu()

    def _collect_plain_text(self, paragraph: ET.Element) -> str:
        parts: List[str] = []
        for node in paragraph:
            if node.tag == qname("w", "r"):
                parts.append(self._convert_run_plain(node))
            elif node.tag == qname("w", "hyperlink"):
                parts.append(self._convert_hyperlink_plain(node))
        return "".join(parts)

    def _convert_run_plain(self, run: ET.Element) -> str:
        text_parts: List[str] = []
        for child in run:
            if child.tag == qname("w", "t"):
                text_parts.append(child.text or "")
            elif child.tag == qname("w", "tab"):
                text_parts.append("\t")
            elif child.tag == qname("w", "br"):
                text_parts.append("\n")
        return "".join(text_parts)

    def _convert_hyperlink_plain(self, node: ET.Element) -> str:
        parts: List[str] = []
        for child in node:
            if child.tag == qname("w", "r"):
                parts.append(self._convert_run_plain(child))
        return "".join(parts)

    def _paragraph_style(self, paragraph: ET.Element) -> Optional[str]:
        ppr = find(paragraph, "w:pPr")
        if ppr is None:
            return None
        style = find(ppr, "w:pStyle")
        if style is None:
            return None
        return style.attrib.get(qname("w", "val"))

    def _preprocess_blocks(self) -> None:
        """
        - Collect Autorstvo from text boxes (wps:txbx) styled "Autorstvo".
        """
        for el in self.blocks:
            if el.tag != qname("w", "p"):
                continue
            for drawing in findall(el, ".//w:drawing"):
                txbx = find(drawing, ".//wps:txbx")
                if txbx is None:
                    continue
                tmp_lines: List[str] = []
                for inner_p in findall(txbx, ".//w:p"):
                    if self._paragraph_style(inner_p) == "Autorstvo":
                        text = self._collect_plain_text(inner_p)
                        text = re.sub(r"\s+", " ", text).strip()
                        if text:
                            tmp_lines.append(text)
                if tmp_lines:
                    self.author_box_lines.extend(tmp_lines)

    def _compute_single_column_width_emu(self) -> Optional[float]:
        """
        Inspect the first section properties to estimate single-column width.
        Returns width in EMU units when the document is multi-column.
        """
        sect = find(self.docx.document, ".//w:sectPr")
        if sect is None:
            return None
        cols = find(sect, "w:cols")
        if cols is None:
            return None
        num_cols = int(cols.attrib.get(qname("w", "num"), "1"))
        if num_cols <= 1:
            return None

        widths: List[int] = []
        for col in findall(cols, "w:col"):
            attr = col.attrib.get(qname("w", "w"))
            if attr:
                try:
                    widths.append(int(attr))
                except ValueError:
                    continue
        if widths:
            col_twips = max(widths)
            return float(col_twips) * EMU_PER_TWIP

        pg_sz = find(sect, "w:pgSz")
        pg_mar = find(sect, "w:pgMar")
        if pg_sz is None or pg_mar is None:
            return None
        try:
            width_twips = int(pg_sz.attrib.get(qname("w", "w"), "0"))
            left = int(pg_mar.attrib.get(qname("w", "left"), "0"))
            right = int(pg_mar.attrib.get(qname("w", "right"), "0"))
            space = int(cols.attrib.get(qname("w", "space"), "0"))
        except ValueError:
            return None

        usable = width_twips - left - right
        if usable <= 0:
            return None
        total_space = space * (num_cols - 1)
        if usable <= total_space:
            return None
        col_twips = (usable - total_space) / num_cols
        if col_twips <= 0:
            return None
        return float(col_twips) * EMU_PER_TWIP

    def iter_body(self) -> Iterator[Tuple[int, ET.Element]]:
        for idx, el in enumerate(self.blocks):
            yield idx, el

# -------------------------------------------------------------------------
# Text conversion

@dataclass
class InlineFormatting:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    code: bool = False
    superscript: bool = False
    subscript: bool = False

    def wrap(self, text: str) -> str:
        result = text
        if self.code:
            result = f"\\texttt{{{result}}}"
        if self.bold:
            result = f"\\textbf{{{result}}}"
        if self.italic:
            result = f"\\textit{{{result}}}"
        if self.underline:
            result = f"\\uline{{{result}}}"
        if self.superscript:
            result = f"\\textsuperscript{{{result}}}"
        if self.subscript:
            result = f"\\textsubscript{{{result}}}"
        return result

class MathConverter:
    """
    Math conversion via Pandoc only.
    - Requires Pandoc to be installed and on PATH.
    - Tries Pandoc OMML reader first; if unavailable, tries Pandoc via DOCX snippet.
    - If both paths fail, raises RuntimeError.
    """

    def __init__(self):
        self._pandoc_bin = shutil.which("pandoc")
        if not self._pandoc_bin:
            raise RuntimeError("Error: Pandoc is required for math conversion but was not found on PATH.")
        self._pandoc_supports_omml = self._check_pandoc_supports_omml()

    def convert(self, node: ET.Element, *, display: bool) -> Tuple[str, bool]:
        latex, is_block = self._pandoc_convert(node, display=display)
        if latex is None:
            raise RuntimeError("Error: Pandoc failed to convert OMML math (neither OMML reader nor DOCX path succeeded).")
        return latex, is_block

    def _pandoc_convert(self, node: ET.Element, *, display: bool) -> Tuple[Optional[str], bool]:
        try:
            xml = ET.tostring(node, encoding="utf-8")
        except Exception:
            return None, False
        text: Optional[str] = None
        if self._pandoc_supports_omml:
            text = self._pandoc_from_omml(xml)
        if text is None:
            text = self._pandoc_via_docx(node, display=display)
        if not text:
            return None, False
        normalized, is_block = self._normalize_output(text)
        if not normalized:
            return None, False
        return normalized, is_block

    def _pandoc_from_omml(self, xml: bytes) -> Optional[str]:
        try:
            result = subprocess.run(
                [self._pandoc_bin, "-f", "omml", "-t", "latex"],
                input=xml,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            self._pandoc_supports_omml = False
            return None
        text = result.stdout.decode("utf-8").strip()
        return text or None

    def _pandoc_via_docx(self, node: ET.Element, *, display: bool) -> Optional[str]:
        try:
            doc_xml = self._build_docx_document(node, display=display)
        except Exception:
            return None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                docx_path = Path(tmpdir) / "snippet.docx"
                with zipfile.ZipFile(docx_path, "w") as zf:
                    zf.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
                    zf.writestr("_rels/.rels", _DOCX_RELS)
                    zf.writestr("word/document.xml", doc_xml)
                result = subprocess.run(
                    [self._pandoc_bin, "-f", "docx", "-t", "latex", str(docx_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True,
                )
        except (OSError, subprocess.CalledProcessError, zipfile.BadZipFile):
            return None
        return result.stdout.strip() or None

    def _build_docx_document(self, node: ET.Element, *, display: bool) -> bytes:
        math_node = deepcopy(node)
        document = ET.Element(qname("w", "document"))
        body = ET.SubElement(document, qname("w", "body"))
        paragraph = ET.SubElement(body, qname("w", "p"))

        if display:
            if math_node.tag != qname("m", "oMathPara"):
                wrapper = ET.Element(qname("m", "oMathPara"))
                wrapper.append(math_node)
                math_elem = wrapper
            else:
                math_elem = math_node
            paragraph.append(math_elem)
        else:
            if math_node.tag == qname("m", "oMathPara"):
                paragraph.append(math_node)
            else:
                run = ET.SubElement(paragraph, qname("w", "r"))
                run.append(math_node)
        ET.SubElement(body, qname("w", "sectPr"))
        return ET.tostring(document, encoding="utf-8", xml_declaration=True)

    def _check_pandoc_supports_omml(self) -> bool:
        try:
            result = subprocess.run(
                [self._pandoc_bin, "--list-input-formats"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return False
        formats = {line.strip() for line in result.stdout.splitlines()}
        return "omml" in formats

    @staticmethod
    def _normalize_output(text: str) -> Tuple[str, bool]:
        """
        Normalize Pandoc output; return (latex, is_block-env-already).
        """
        stripped = text.strip()
        if not stripped:
            return "", False
        if stripped.startswith("\\begin"):
            return stripped, True
        if stripped.startswith("\\[") and stripped.endswith("\\]"):
            return stripped[2:-2].strip(), False
        if stripped.startswith("$$") and stripped.endswith("$"):
            # rare malformed case; trim the trailing single '$'
            return stripped[2:-1].strip(), False
        if stripped.startswith("$$") and stripped.endswith("$$"):
            return stripped[2:-2].strip(), False
        if stripped.startswith("\\(") and stripped.endswith("\\)"):
            return stripped[2:-2].strip(), False
        if stripped.startswith("$") and stripped.endswith("$") and len(stripped) >= 2:
            return stripped[1:-1].strip(), False
        return stripped, False

class ParagraphConverter:
    def __init__(self, package: DocxPackage):
        self.package = package
        self.math = MathConverter()

    def convert_runs(self, parent: ET.Element) -> str:
        parts: List[str] = []
        for node in parent:
            if node.tag == qname("w", "r"):
                parts.append(self._convert_run(node))
            elif node.tag == qname("w", "hyperlink"):
                parts.append(self._convert_hyperlink(node))
            elif node.tag == qname("m", "oMath"):
                latex, is_block = self.math.convert(node, display=False)
                parts.append(latex if is_block else f"\\({latex}\\)")
            elif node.tag == qname("m", "oMathPara"):
                latex, is_block = self.math.convert(node, display=True)
                parts.append(latex if is_block else f"\\begin{{equation}}\n{latex}\n\\end{{equation}}")
        return "".join(parts)

    def _convert_run(self, run: ET.Element) -> str:
        text = self._collect_text(run)
        if not text:
            return ""
        fmt = self._collect_formatting(run)
        return fmt.wrap(text)

    def _collect_text(self, run: ET.Element) -> str:
        parts: List[str] = []
        for child in run:
            if child.tag == qname("w", "t"):
                parts.append(escape_latex(child.text or ""))
            elif child.tag == qname("w", "tab"):
                parts.append("\t")
            elif child.tag == qname("w", "br"):
                parts.append("\\\\")
            elif child.tag == qname("m", "oMath"):
                latex, is_block = self.math.convert(child, display=False)
                parts.append(latex if is_block else f"\\({latex}\\)")
            elif child.tag == qname("m", "oMathPara"):
                latex, is_block = self.math.convert(child, display=True)
                parts.append(latex if is_block else f"\\begin{{equation}}\n{latex}\n\\end{{equation}}")
        return "".join(parts)

    def _collect_formatting(self, run: ET.Element) -> InlineFormatting:
        fmt = InlineFormatting()
        rpr = find(run, "w:rPr")
        if rpr is None:
            return fmt
        if find(rpr, "w:b") is not None:
            fmt.bold = True
        if find(rpr, "w:i") is not None or find(rpr, "w:em") is not None:
            fmt.italic = True
        if find(rpr, "w:u") is not None:
            fmt.underline = True
        vert = find(rpr, "w:vertAlign")
        if vert is not None:
            val = vert.attrib.get(qname("w", "val"))
            if val == "superscript":
                fmt.superscript = True
            elif val == "subscript":
                fmt.subscript = True
        rstyle = find(rpr, "w:rStyle")
        if rstyle is not None and rstyle.attrib.get(qname("w", "val")) == "Code":
            fmt.code = True
        return fmt

    def _convert_hyperlink(self, node: ET.Element) -> str:
        rid = node.attrib.get(qname("r", "id"))
        text = "".join(self._convert_run(r) for r in findall(node, "w:r"))
        if not rid:
            return text
        target = self.package.relationships.get(rid)
        if not target:
            return text
        target = escape_latex(target)
        return f"\\href{{{target}}}{{{text}}}"

# -------------------------------------------------------------------------
# High-level conversion

@dataclass
class LatexOutput:
    header_lines: List[str]
    body_lines: List[str]
    reference_lines: List[str]
    copied_images: List[Tuple[str, str]]  # (target path inside docx, local filename)

class ZbornikConverter:
    def __init__(self, package: DocxPackage):
        self.package = package
        self.ctx = ConversionContext(package)
        self.para_conv = ParagraphConverter(package)
        self._skip_block_indexes: set[int] = set()  # blocks consumed as captions

    # -------- Caption detection: scan within ±5 paragraphs -------------------
    def _caption_near(self, idx: int, kind: str, expected_num: Optional[int] = None) -> Tuple[Optional[str], Optional[str], List[int]]:
        """
        Search nearby paragraphs around block index `idx` for bilingual caption lines.
        Return (sr_full, en_full, consumed_indexes).
        """
        consumed: List[int] = []
        sr_full: Optional[str] = None
        en_full: Optional[str] = None

        offsets = [1, 2, 3, 4, 5, -1, -2, -3, -4, -5]
        for off in offsets:
            j = idx + off
            if not (0 <= j < len(self.ctx.blocks)):
                continue
            if j in self._skip_block_indexes:
                continue
            el = self.ctx.blocks[j]
            if el.tag != qname("w", "p"):
                continue
            raw = self.ctx._collect_plain_text(el).strip()
            if not raw:
                continue
            m = CAP_FULL.match(raw)
            if not m:
                continue
            label, num, tail = m.group(1), m.group(2), (m.group(3) or "").strip()
            label_l = label.lower()
            if kind == "fig" and label_l not in {"slika", "figure"}:
                continue
            if kind == "tbl" and label_l not in {"tabela", "table"}:
                continue
            try:
                caption_num = int(num)
            except ValueError:
                caption_num = None
            if expected_num is not None:
                if caption_num is None or caption_num != expected_num:
                    continue
            full = f"{label} {num}. {escape_latex(tail)}" if tail else f"{label} {num}."
            if label_l in {"slika", "tabela"} and sr_full is None:
                sr_full = full
                consumed.append(j)
            elif label_l in {"figure", "table"} and en_full is None:
                en_full = full
                consumed.append(j)
            if sr_full and en_full:
                break

        return sr_full, en_full, consumed

    @staticmethod
    def _strip_caption_prefix(text: str) -> str:
        if not text:
            return ""
        match = CAP_FULL.match(text)
        if not match:
            return text.strip()
        tail = match.group(3) or ""
        return tail.strip()

    # -------- Paragraph/List emission ---------------------------------------
    def _emit_list_item_or_par(self, paragraph: ET.Element, text: str, body: List[str],
                               list_stack: List[str], ensure_list, close_lists):
        numbering = find(paragraph, "w:pPr/w:numPr")
        if numbering is not None:
            num_id_el = find(numbering, "w:numId")
            ilvl_el = find(numbering, "w:ilvl")
            if num_id_el is not None and ilvl_el is not None:
                num_id = num_id_el.attrib.get(qname("w", "val"))
                lvl = int(ilvl_el.attrib.get(qname("w", "val")))
                fmt = self.package.numbering.get(num_id, {}).get(lvl, "bullet")
                ensure_list(lvl + 1, fmt)
                body.append(f"\\item {text.strip()}")
                return
        else:
            close_lists()
        if text:
            body.append(text)

    # -------- Tables ---------------------------------------------------------
    def _should_wide_table(self, rows_raw: List[List[Dict[str, str]]]) -> bool:
        ncols = 0
        header_len = 0
        long_cell = False
        if rows_raw:
            for c in rows_raw[0]:
                header_len += len(c.get("text", ""))
                ncols += max(1, int(c.get("gridspan", 1)))
        for row in rows_raw:
            for c in row:
                if len(c.get("text", "")) > 30:
                    long_cell = True
                    break
            if long_cell:
                break
        return ncols >= 4 or header_len > 60 or (long_cell and ncols >= 3)

    def _convert_table(self, idx: int, tbl: ET.Element, cap_sr_full: Optional[str], cap_en_full: Optional[str]) -> List[str]:
        lines: List[str] = []

        rows_raw: List[List[Dict[str, str]]] = []
        ncols = 0
        vmerge_seen = False
        for tr in findall(tbl, "w:tr"):
            row_cells: List[Dict[str, str]] = []
            for tc in findall(tr, "w:tc"):
                texts = []
                for p in findall(tc, "w:p"):
                    texts.append(self.para_conv.convert_runs(p).strip())
                txt = escape_latex(" ".join(t for t in texts if t))
                gridspan_el = find(tc, "w:tcPr/w:gridSpan")
                vmerge_el = find(tc, "w:tcPr/w:vMerge")
                gridspan = int(gridspan_el.attrib.get(qname("w", "val"), "1")) if gridspan_el is not None else 1
                if vmerge_el is not None:
                    vmerge_seen = True
                row_cells.append({"text": txt, "gridspan": gridspan})
            ncols = max(ncols, sum(int(c["gridspan"]) for c in row_cells))
            rows_raw.append(row_cells)

        colspec = "|".join("c" for _ in range(ncols))
        macro = "TableDouble" if self._should_wide_table(rows_raw) else "Table"

        tabular_lines: List[str] = []
        tabular_lines.append(f"\\begin{{tabular}}{{|{colspec}|}}")
        tabular_lines.append("\\hline")
        for row in rows_raw:
            cells_out: List[str] = []
            for c in row:
                txt = c["text"]
                span = int(c["gridspan"])
                if span > 1:
                    cells_out.append(f"\\multicolumn{{{span}}}{{c|}}{{{txt}}}")
                else:
                    cells_out.append(txt)
            used = sum(int(c["gridspan"]) for c in row)
            if used < ncols:
                cells_out.extend([""] * (ncols - used))
            tabular_lines.append(" {} \\\\".format(" & ".join(cells_out)))
            tabular_lines.append("\\hline")
        tabular_lines.append("\\end{tabular}")

        sr_caption = self._strip_caption_prefix(cap_sr_full) if cap_sr_full else ""
        en_caption = self._strip_caption_prefix(cap_en_full) if cap_en_full else ""
        if not sr_caption and en_caption:
            sr_caption = en_caption
        if not en_caption and sr_caption:
            en_caption = sr_caption
        if not sr_caption:
            sr_caption = "TODO"
        if not en_caption:
            en_caption = "TODO"

        lines.append(f"\\{macro}{{%")
        for tab_line in tabular_lines:
            lines.append(f"    {tab_line}")
        lines.append(f"}}{{{sr_caption}}}{{{en_caption}}}{{}}")

        if vmerge_seen:
            sys.stderr.write("[warn] table with vertical merges (vMerge) encountered; multirow not rendered.\n")
        return lines

    # -------- English tail recovery (after Literatura) -----------------------
    def _recover_english_tail(self) -> Tuple[Optional[str], List[str]]:
        """
        If TitleEng / AbstractEng are missing, scan after the last 'Literatura'/'References'
        for an English name → English title → 1–3 abstract paragraphs.
        """
        n = len(self.ctx.blocks)
        lit_idx = -1
        for i, blk in enumerate(self.ctx.blocks):
            if blk.tag == qname("w", "p"):
                t = self.ctx._collect_plain_text(blk).strip()
                if t and t.lower() in {"literatura", "references"}:
                    lit_idx = i

        if lit_idx < 0:
            return None, []

        tail = self.ctx.blocks[lit_idx + 1 : min(n, lit_idx + 120)]
        # find English name
        i = 0
        while i < len(tail):
            el = tail[i]
            if el.tag != qname("w", "p"):
                i += 1
                continue
            txt = self.ctx._collect_plain_text(el).strip()
            if is_likely_name(txt) and re.fullmatch(r"[A-Za-z .,'-]+", txt):
                i += 1
                break
            i += 1
        # English title
        title_en = None
        while i < len(tail):
            el = tail[i]
            if el.tag != qname("w", "p"):
                i += 1
                continue
            txt = self.ctx._collect_plain_text(el).strip()
            if txt and not looks_like_section_title(txt) and len(txt.split()) <= 16 and re.search(r"[A-Za-z]", txt):
                title_en = escape_latex(txt)
                i += 1
                break
            i += 1
        # English abstract paragraphs (1–3)
        abstract_en: List[str] = []
        while i < len(tail):
            el = tail[i]
            if el.tag != qname("w", "p"):
                i += 1
                continue
            txt = self.para_conv.convert_runs(el).strip()
            low = txt.lower()
            if not txt or looks_like_section_title(low) or low in {"zbornik radova", "petničke sveske"}:
                break
            if re.search(r"\b(the|with|model|we|using|were|was|data|results|method)\b", txt.lower()):
                abstract_en.append(txt)
                if len(abstract_en) >= 3:
                    break
            else:
                if abstract_en:
                    break
            i += 1

        return title_en, abstract_en

    # -------- Conversion driver ---------------------------------------------
    def convert(self, *, label: Optional[str] = None) -> LatexOutput:
        header: List[str] = []
        body: List[str] = []
        refs: List[str] = []
        images_to_copy: List[Tuple[str, str]] = []

        authors: List[str] = []
        title_sr: Optional[str] = None
        title_en: Optional[str] = None
        abstract_sr_parts: List[str] = []
        abstract_en_parts: List[str] = []

        author_ex_lines: List[str] = list(self.ctx.author_box_lines)

        # Front matter (strict styles)
        flagAuthors = False
        for _, blk in self.ctx.iter_body():
            if blk.tag != qname("w", "p"):
                continue
            style = self.ctx._paragraph_style(blk)
            txt = self.ctx._collect_plain_text(blk).strip()
            if not txt:
                continue
            if style == "Imeiprezime" and not flagAuthors:
                authors.append(escape_latex(txt))
                flagAuthors = True
            elif style == "Autorstvo":
                author_ex_lines.append(escape_latex(txt))
            elif style == "Naslov":
                title_sr = escape_latex(txt)
            elif style == "Apstrakt":
                p = self.para_conv.convert_runs(blk).strip()
                if p:
                    abstract_sr_parts.append(p)
            elif style == "TitleEng":
                title_en = escape_latex(txt)
            elif style == "AbstractEng":
                p = self.para_conv.convert_runs(blk).strip()
                if p:
                    abstract_en_parts.append(p)

        # Fallbacks if missing authors/title_sr (kept, but flagAuthors prevents duplicates)
        if (not authors) or (not title_sr):
            for _, blk in self.ctx.iter_body():
                if blk.tag != qname("w", "p"):
                    continue
                txt = self.ctx._collect_plain_text(blk).strip()
                if not txt:
                    continue
                if not authors and is_likely_name(txt):
                    authors.append(escape_latex(txt))
                    break
                if not title_sr and not is_likely_name(txt) and len(txt.split()) >= 5 and not looks_like_section_title(txt):
                    title_sr = escape_latex(txt)
                    break

        # State for lists and references
        list_stack: List[str] = []
        def close_lists(upto: int = 0) -> None:
            nonlocal list_stack
            while len(list_stack) > upto:
                env = list_stack.pop()
                body.append(f"\\end{{{env}}}")

        def ensure_list(level: int, list_type: str) -> None:
            if level < 1:
                level = 1
            desired_env = "itemize" if list_type == "bullet" else "enumerate"

            if len(list_stack) > level:
                close_lists(level)

            if len(list_stack) == level:
                current_env = list_stack[level - 1]
                if current_env != desired_env:
                    close_lists(level - 1)
                    body.append(f"\\begin{{{desired_env}}}")
                    list_stack.append(desired_env)
                return

            while len(list_stack) < level - 1:
                body.append("\\begin{itemize}")
                list_stack.append("itemize")

            if len(list_stack) < level:
                body.append(f"\\begin{{{desired_env}}}")
                list_stack.append(desired_env)

        author_ex_here_inserted = False
        refs_started = False
        in_refs_collect = False
        figure_counter = 0
        table_counter = 0

        def figure_is_wide(width_emu: Optional[float]) -> bool:
            col_width = self.ctx.single_column_width_emu
            if width_emu is None or col_width is None:
                return False
            return width_emu > col_width * 1.05

        # Main pass through blocks
        for idx, block in self.ctx.iter_body():
            if idx in self._skip_block_indexes:
                continue

            # TABLES
            if block.tag == qname("w", "tbl"):
                if in_refs_collect:
                    in_refs_collect = False
                close_lists()
                if not author_ex_here_inserted and author_ex_lines:
                    body.append("\\AuthorExHere")
                    author_ex_here_inserted = True
                table_counter += 1
                cap_sr, cap_en, consumed = self._caption_near(idx, "tbl", expected_num=table_counter)
                if cap_sr is None and cap_en is None:
                    cap_sr, cap_en, consumed = self._caption_near(idx, "tbl")
                for j in consumed:
                    self._skip_block_indexes.add(j)
                table_lines = self._convert_table(idx, block, cap_sr, cap_en)
                body.extend(table_lines)
                continue

            # PARAGRAPHS
            if block.tag != qname("w", "p"):
                continue

            style = self.ctx._paragraph_style(block)
            plain_text = self.ctx._collect_plain_text(block).strip()
            if not plain_text and not list(block):
                continue

            # Skip front-matter styles in body
            if style in {"Naslov", "TitleEng", "Imeiprezime", "Apstrakt", "AbstractEng", "Autorstvo"}:
                continue

            # Start references once
            if (style == "Literatura" or plain_text.lower() in {"literatura", "references"}) and not refs_started:
                close_lists()
                refs.append("\\section{Literatura}")
                refs_started = True
                in_refs_collect = True
                continue
            # Stop refs collection on any new section/abstract marker
            if in_refs_collect and (style in {"Heading2", "Heading3", "Heading4", "Apstrakt", "AbstractEng"} or looks_like_section_title(plain_text)):
                in_refs_collect = False

            # While in refs, emit \Source for non-empty lines only
            if in_refs_collect:
                content = escape_latex(plain_text).strip()
                if content:  # <-- prevents empty \Source{}
                    refs.append("\\Source{")
                    refs.append(f"    {content}")
                    refs.append("}")
                continue

            # Headings → sectioning
            if style in {"Heading2", "Heading3", "Heading4"} or looks_like_section_title(plain_text):
                close_lists()
                if not author_ex_here_inserted and author_ex_lines:
                    body.append("\\AuthorExHere")
                    author_ex_here_inserted = True
                if style == "Heading2" or looks_like_section_title(plain_text):
                    body.append(f"\\section{{{escape_latex(plain_text)}}}")
                elif style == "Heading3":
                    body.append(f"\\subsection{{{escape_latex(plain_text)}}}")
                else:
                    body.append(f"\\subsubsection{{{escape_latex(plain_text)}}}")
                continue

            # Inline drawings (figures)
            segments: List[str | Tuple[str, ...]] = []
            cursor_parts: List[str] = []

            def flush_cursor():
                if cursor_parts:
                    t = "".join(cursor_parts).strip()
                    if t:
                        segments.append(t)
                    cursor_parts.clear()

            for node in block:
                if node.tag == qname("w", "r"):
                    drawing = find(node, "w:drawing")
                    if drawing is not None:
                        flush_cursor()
                        width_emu: Optional[float] = None
                        inline = find(drawing, "wp:inline")
                        anchor = find(drawing, "wp:anchor") if inline is None else None
                        extent_el: Optional[ET.Element] = None
                        if inline is not None:
                            extent_el = find(inline, "wp:extent")
                        if extent_el is None and anchor is not None:
                            extent_el = find(anchor, "wp:extent")
                        if extent_el is None:
                            extent_el = find(drawing, ".//wp:extent")
                        if extent_el is not None:
                            try:
                                width_emu = float(extent_el.attrib.get("cx", "0"))
                            except ValueError:
                                width_emu = None
                        for blip in findall(drawing, ".//a:blip"):
                            rid = blip.attrib.get(qname("r", "embed"))
                            if not rid:
                                continue
                            target = self.package.relationships.get(rid)
                            if not target:
                                continue
                            sr_cap, en_cap, consumed = self._caption_near(idx, "fig", None)
                            for j in consumed:
                                self._skip_block_indexes.add(j)
                            segments.append(("FIGURE", target, Path(target).name, width_emu, sr_cap or "", en_cap or ""))
                        continue
                    cursor_parts.append(self.para_conv._convert_run(node))
                elif node.tag == qname("w", "hyperlink"):
                    cursor_parts.append(self.para_conv._convert_hyperlink(node))
            flush_cursor()

            # Merge in-paragraph caption fragments
            processed_segments: List[str | Tuple[str, ...]] = []
            has_figure = any(isinstance(seg, tuple) and seg[0] == "FIGURE" for seg in segments)
            pending_sr: Optional[str] = None
            pending_en: Optional[str] = None
            for seg in segments:
                if isinstance(seg, str):
                    stripped = seg.strip()
                    if not stripped:
                        continue
                    m = CAP_FULL.match(stripped)
                    if m and has_figure:
                        label = m.group(1).lower()
                        candidate = stripped
                        attached = False
                        if processed_segments and isinstance(processed_segments[-1], tuple):
                            typ, target, fname, width_val, sr_cur, en_cur = processed_segments[-1]
                            if label in {"slika", "tabela"} and not sr_cur:
                                processed_segments[-1] = (typ, target, fname, width_val, candidate, en_cur)
                                attached = True
                            elif label in {"figure", "table"} and not en_cur:
                                processed_segments[-1] = (typ, target, fname, width_val, sr_cur, candidate)
                                attached = True
                        if not attached:
                            if label in {"slika", "tabela"} and not pending_sr:
                                pending_sr = candidate
                            elif label in {"figure", "table"} and not pending_en:
                                pending_en = candidate
                        continue
                    processed_segments.append(stripped)
                else:
                    typ, target, fname, width_val, cap_sr_full, cap_en_full = seg
                    sr_val = cap_sr_full or pending_sr or ""
                    en_val = cap_en_full or pending_en or ""
                    processed_segments.append((typ, target, fname, width_val, sr_val, en_val))
                    pending_sr = None
                    pending_en = None
            if pending_sr and not has_figure:
                processed_segments.append(pending_sr)
            if pending_en and not has_figure:
                processed_segments.append(pending_en)
            segments = processed_segments

            # Emit segments
            if segments and (not author_ex_here_inserted) and author_ex_lines:
                body.append("\\AuthorExHere")
                author_ex_here_inserted = True

            for seg in segments:
                if isinstance(seg, str):
                    self._emit_list_item_or_par(block, seg, body, list_stack, ensure_list, close_lists)
                else:
                    close_lists()
                    _, target, fname, width_val, cap_sr_full, cap_en_full = seg
                    images_to_copy.append((target, fname))
                    fig_path = escape_latex(Path(fname).name)
                    sr_text = self._strip_caption_prefix(cap_sr_full) if cap_sr_full else ""
                    en_text = self._strip_caption_prefix(cap_en_full) if cap_en_full else ""
                    if not sr_text:
                        sr_text = "TODO"
                    if not en_text:
                        en_text = "TODO"
                    if figure_is_wide(width_emu=width_val):
                        body.append(f"\\FigureDouble{{{fig_path}}}{{{sr_text}}}{{{en_text}}}")
                    else:
                        body.append(f"\\Figure[H]{{{fig_path}}}{{{sr_text}}}{{{en_text}}}")

            # Pure text paragraph
            if not segments:
                paragraph_tex = self.para_conv.convert_runs(block).strip()
                if paragraph_tex:
                    self._emit_list_item_or_par(block, paragraph_tex, body, list_stack, ensure_list, close_lists)
                    if not author_ex_here_inserted and author_ex_lines:
                        body.append("\\AuthorExHere")
                        author_ex_here_inserted = True

        # Close any pending lists
        while list_stack:
            env = list_stack.pop()
            body.append(f"\\end{{{env}}}")

        # Recover English tail if missing
        if not title_en or not abstract_en_parts:
            rec_title_en, rec_abs_en = self._recover_english_tail()
            if rec_title_en and not title_en:
                title_en = rec_title_en
            if rec_abs_en and not abstract_en_parts:
                abstract_en_parts = rec_abs_en

        # Header emission
        if authors:
            authors_joined = " \\\\ ".join(authors)
            header.append(f"\\Author{{{authors_joined}}}")
        header.append(f"\\Title{{{title_sr or 'TODO naslov'}}}")
        if title_en:
            header.append(f"\\TitleEng{{{title_en}}}")
        if abstract_sr_parts:
            header.append("\\begin{Abstract}")
            header.extend(abstract_sr_parts)
            header.append("\\end{Abstract}")
        if author_ex_lines:
            header.append("\\begin{AuthorEx}")
            header.append(" \\ ".join(escape_latex(l) for l in author_ex_lines))
            header.append("\\end{AuthorEx}")
        if abstract_en_parts:
            header.append("\\begin{AbstractEng}")
            header.extend(abstract_en_parts)
            header.append("\\end{AbstractEng}")
        header.append("\\StartDoublePaper")
        if label:
            header.append(f"\\label{{{label}}}")

        return LatexOutput(header, body, refs, images_to_copy)

# -------------------------------------------------------------------------
# Media normalization

def normalize_media_in_place(out_dir: Path) -> dict[str, str]:
    """
    Convert unsupported formats (emf/wmf/tiff) to PNG using LibreOffice if available,
    sanitize filenames to ASCII, and return a mapping {old_basename -> new_basename}.
    """
    mapping: dict[str, str] = {}

    def have(prog: str) -> bool:
        return shutil.which(prog) is not None

    # 1) Convert EMF/WMF/TIFF -> PNG via LibreOffice headless (if available)
    for p in list(out_dir.glob("*")):
        if p.suffix.lower() in {".emf", ".wmf", ".tif", ".tiff"} and have("soffice"):
            try:
                subprocess.run(
                    ["soffice", "--headless", "--convert-to", "png", "--outdir", str(out_dir), str(p)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                png_out = out_dir / (p.stem + ".png")
                if png_out.exists():
                    mapping[p.name] = png_out.name
                    p.unlink(missing_ok=True)
            except Exception as e:
                sys.stderr.write(f"[warn] failed to convert {p.name} via LibreOffice: {e}\n")

    # 2) Sanitize names and dedupe
    used: set[str] = set()
    for f in list(out_dir.iterdir()):
        if not f.is_file():
            continue
        stem, ext = os.path.splitext(f.name)
        newname = ascii_sanitize(stem) + ext.lower()
        i = 2
        while (newname in used) or ((f.parent / newname) != f and (f.parent / newname).exists()):
            newname = f"{ascii_sanitize(stem)}_{i}{ext.lower()}"
            i += 1
        if newname != f.name:
            f.rename(f.parent / newname)
            mapping.setdefault(f.name, newname)
        used.add(newname)

    # 3) Optional: downsize large rasters if ImageMagick is available
    if have("mogrify"):
        pngs = [str(p) for p in out_dir.glob("*.png")]
        jpgs = [str(p) for p in out_dir.glob("*.jpg")] + [str(p) for p in out_dir.glob("*.jpeg")]
        for batch in (pngs, jpgs):
            if batch:
                subprocess.run(["mogrify", "-strip", "-resize", "3000x>"] + batch, check=False)

    return mapping

# -------------------------------------------------------------------------
# CLI

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert Petnica docx to LaTeX (Zbornik).")
    p.add_argument("input", type=Path, help="Path to .docx")
    p.add_argument("output_dir", type=Path, help="Directory to write LaTeX + media")
    p.add_argument("--label", default=None, help="Optional LaTeX label to attach to the paper")
    return p.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.input.exists():
        sys.stderr.write(f"Input not found: {args.input}\n")
        return 2

    package = DocxPackage(args.input)

    # Ensure we fail cleanly if Pandoc isn't available (MathConverter checks too)
    if not shutil.which("pandoc"):
        sys.stderr.write("Error: Pandoc is required for math conversion but was not found on PATH.\n")
        return 3

    try:
        converter = ZbornikConverter(package)
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        return 3

    label = args.label or f"doc:{slugify(args.input.stem)}"
    output = converter.convert(label=label)

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / "main.tex"

    with tex_path.open("w", encoding="utf-8") as fh:
        for line in output.header_lines:
            fh.write(line.rstrip() + "\n")
        fh.write("\n")
        for line in output.body_lines:
            fh.write(line.rstrip() + "\n")
        if output.reference_lines:
            fh.write("\n")
            for line in output.reference_lines:
                fh.write(line.rstrip() + "\n")
        fh.write("\n\\EndPaper\n")

    # Copy media as-is
    for target, filename in output.copied_images:
        data = package.read_image(target)
        dest = out_dir / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            fh.write(data)

    # Normalize media and rewrite main.tex if names/formats changed
    rename_map = normalize_media_in_place(out_dir)
    if rename_map:
        tex = tex_path.read_text(encoding="utf-8")
        for old, new in rename_map.items():
            tex = tex.replace(old, new)
        tex_path.write_text(tex, encoding="utf-8")

    print(f"Wrote {tex_path}")
    if output.copied_images:
        copied = ", ".join(name for _, name in output.copied_images)
        print(f"Copied media: {copied}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
