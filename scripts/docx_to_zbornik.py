#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert a Word .docx exported from the Petnica template (or a close variant) into LaTeX.

This script is intentionally opinionated: it understands only the subset of
Word features common in Petnica papers. The goal is to produce a `main.tex`
file (plus any extracted media) that fits into the existing LaTeX workflow
without manual post-processing.

v0.5.0 (drop-in replacement):
- Captions: robust detection from nearby paragraphs within ±5 (skips empties), captures
  full "Label Number. Text" for bilingual Slika/Figure and Tabela/Table; removes caption
  paragraphs from body.
- Autorstvo: collect from (1) text boxes styled "Autorstvo" and (2) early paragraphs that
  look like author/mentor/school lines; emit as \AuthorEx{...} and place \AuthorExHere
  just before the first emitted content (text/figure/table).
- English abstract: if not styled, scan tail after "Literatura" → detect English Name →
  English Title → English abstract paragraphs; fill \TitleEng + AbstractEng.
- References: emit \section{Literatura} exactly once; subsequent paragraphs become \Source{...}.
- Tables: improved column counting (with gridSpan), wide-table heuristic (→ table*),
  \multicolumn for horizontal spans; warn on vMerge (no \multirow).
- Lists: preserve via w:numPr (numId/ilvl).

Compile with XeLaTeX or LuaLaTeX (sveska.cls uses fontspec).
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
        if ch in LATEX_SPECIALS:
            out.append(LATEX_SPECIALS[ch])
        else:
            out.append(ch)
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

def is_numeric_cell(s: str) -> bool:
    s = s.strip()
    return bool(re.match(r"^[\+\-]?\d+([.,]\d+)?(\s*[A-Za-z%/°\-\(\)\[\]\{\}\^_]+)?$", s))

def ascii_sanitize(stem: str) -> str:
    s = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return s or "img"

# Full caption pattern: captures label + number + tail, preserving original label (for unnumbered LaTeX)
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

@dataclass
class FigureAsset:
    block_index: int         # index in the full blocks sequence
    image_rid: str
    image_name: str          # e.g. media/image1.png

class ConversionContext:
    def __init__(self, docx: DocxPackage):
        self.docx = docx
        self.blocks = list(findall(docx.document, ".//w:body/*"))
        self.figures: List[FigureAsset] = []
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
        - Capture inline drawings (figures) with their block indexes.
        - Collect Autorstvo from text boxes (wps:txbx).
        """
        print("Preprocessing document blocks...")
        for bidx, el in enumerate(self.blocks):
            if el.tag == qname("w", "p"):
                # scan for drawings (figures)
                for drawing in findall(el, ".//w:drawing"):
                    blip = find(drawing, ".//a:blip")
                    if blip is not None:
                        rid = blip.attrib.get(qname("r", "embed"))
                        if rid:
                            target = self.docx.relationships.get(rid)
                            if target:
                                self.figures.append(FigureAsset(bidx, rid, target))
                    # gather Autorstvo from any text box content
                    txbx = find(drawing, ".//wps:txbx")
                    if txbx is not None:
                        for inner_p in findall(txbx, ".//w:p"):
                            if self._paragraph_style(inner_p) == "Autorstvo":
                                text = self._collect_plain_text(inner_p)
                                print("Autorstvo:", text)
                        if text:
                            text = re.sub(r"\s+", " ", text).strip()
                            if text:
                                self.author_box_lines.append(text)

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

class OmmlConverter:
    """
    Convert a subset of Office Math Markup Language (OMML) into LaTeX.
    Covers the constructs observed in Petnica templates (roots, n-ary sums,
    superscripts). Falls back to concatenating child nodes for unknown tags.
    """

    OPERATOR_MAP = {
        "∑": "\\sum",
        "∏": "\\prod",
        "∫": "\\int",
    }

    def convert(self, node: ET.Element) -> str:
        if node is None:
            return ""
        tag = node.tag
        if tag in {qname("m", "oMath"), qname("m", "oMathPara"), qname("m", "e"), qname("m", "deg"), qname("m", "sub"), qname("m", "sup")}:
            return "".join(self.convert(child) for child in node)
        if tag == qname("m", "r"):
            return "".join(self.convert(child) for child in node)
        if tag == qname("m", "t"):
            text = node.text or ""
            return text.replace("\u00a0", "~")
        if tag == qname("m", "rad"):
            degree = self.convert(find(node, "m:deg"))
            body = self.convert(find(node, "m:e")).strip()
            if degree:
                return f"\\sqrt[{degree.strip()}]{{{body}}}"
            return f"\\sqrt{{{body}}}"
        if tag == qname("m", "nary"):
            return self._convert_nary(node)
        if tag in {qname("m", "sSup"), qname("m", "sSub"), qname("m", "sSubSup")}:
            return self._convert_script(node)
        if tag in {qname("m", "ctrlPr"), qname("m", "radPr"), qname("m", "naryPr"), qname("m", "sSupPr"), qname("m", "sSubPr"), qname("m", "sSubSupPr")}:
            return ""
        if tag == qname("w", "rPr"):
            return ""
        return "".join(self.convert(child) for child in node)

    def _convert_nary(self, node: ET.Element) -> str:
        symbol = "\\sum"
        use_limits = False

        pr = find(node, "m:naryPr")
        if pr is not None:
            chr_el = find(pr, "m:chr")
            if chr_el is not None:
                val = chr_el.attrib.get(qname("m", "val"), "")
                if val:
                    symbol = self.OPERATOR_MAP.get(val, val)
            lim = find(pr, "m:limLoc")
            if lim is not None and lim.attrib.get(qname("m", "val")) == "undOvr" and symbol.startswith("\\"):
                use_limits = True

        sub_part = self.convert(find(node, "m:sub")).strip()
        sup_part = self.convert(find(node, "m:sup")).strip()
        expr = self.convert(find(node, "m:e")).strip()

        out = symbol
        if use_limits and symbol.startswith("\\"):
            out += "\\limits"
        if sub_part:
            out += f"_{{{sub_part}}}"
        if sup_part:
            out += f"^{{{sup_part}}}"
        if expr:
            out += f" {expr}"
        return out

    def _convert_script(self, node: ET.Element) -> str:
        base = self.convert(find(node, "m:e")).strip()
        sub = self.convert(find(node, "m:sub")).strip()
        sup = self.convert(find(node, "m:sup")).strip()

        out = base or ""
        if sub:
            out += f"_{{{sub}}}"
        if sup:
            out += f"^{{{sup}}}"
        return out

class MathConverter:
    """Dispatch math conversion via Pandoc when available, otherwise fallback to OmmlConverter."""

    def __init__(self):
        self._pandoc_bin = shutil.which("pandoc")
        self._pandoc_supports_omml = False
        if self._pandoc_bin:
            self._pandoc_supports_omml = self._check_pandoc_supports_omml()
        self._omml = OmmlConverter()

    def convert(self, node: ET.Element, *, display: bool) -> Tuple[str, bool]:
        """
        Return (latex_snippet, already_block).
        When already_block is True the snippet already contains its own LaTeX math environment.
        """
        latex, is_block = self._pandoc_convert(node, display=display)
        if latex is None:
            latex = self._omml.convert(node).strip()
            is_block = False
        return latex, is_block

    def _pandoc_convert(self, node: ET.Element, *, display: bool) -> Tuple[Optional[str], bool]:
        if not self._pandoc_bin:
            return None, False
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
        normalized, is_block = self._normalize_output(text, display=display)
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
    def _normalize_output(text: str, *, display: bool) -> Tuple[str, bool]:
        stripped = text.strip()
        if not stripped:
            return "", False
        if stripped.startswith("\\begin"):
            return stripped, True
        if stripped.startswith("\\[") and stripped.endswith("\\]"):
            return stripped[2:-2].strip(), False
        if stripped.startswith("$$") and stripped.endswith("$$"):
            inner = stripped[2:-2].strip()
            return inner, False
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
                if latex:
                    if is_block:
                        parts.append(latex)
                    else:
                        parts.append(f"\\({latex}\\)")
            elif node.tag == qname("m", "oMathPara"):
                latex, is_block = self.math.convert(node, display=True)
                if latex:
                    if is_block:
                        parts.append(latex)
                    else:
                        parts.append(f"\\begin{{equation}}\n{latex}\n\\end{{equation}}")
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
                if latex:
                    if is_block:
                        parts.append(latex)
                    else:
                        parts.append(f"\\({latex}\\)")
            elif child.tag == qname("m", "oMathPara"):
                latex, is_block = self.math.convert(child, display=True)
                if latex:
                    if is_block:
                        parts.append(latex)
                    else:
                        parts.append(f"\\begin{{equation}}\n{latex}\n\\end{{equation}}")
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

        # Priority order: prev (closest → farther), then next (closest → farther)
        offsets = [-1, -2, -3, -4, -5, 1, 2, 3, 4, 5]
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
            # stop early if we have both
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

        # Build cells and detect spans
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

        # Column heuristics: numeric vs text
        col_numeric = [True] * ncols
        def expand(row: List[Dict[str, str]]) -> List[str]:
            out: List[str] = []
            for c in row:
                span = int(c["gridspan"])
                out.append(c["text"])
                for _ in range(span - 1):
                    out.append("")
            return out

        sample_rows = [expand(r) for r in rows_raw[: min(8, len(rows_raw))]]
        for c in range(ncols):
            for r in sample_rows:
                if c >= len(r):
                    continue
                if not is_numeric_cell(r[c]):
                    col_numeric[c] = False
                    break

        # Choose column spec
        text_cols = [i for i, isnum in enumerate(col_numeric) if not isnum]
        #primary_text = text_cols[0] if text_cols else 0
        #secondary_text = text_cols[1] if len(text_cols) > 1 else None

        colspec_parts: List[str] = []
        for c in range(ncols):
            #if c == primary_text:
            #    colspec_parts.append("p{0.50\\linewidth}")
            #elif secondary_text is not None and c == secondary_text:
            #    colspec_parts.append("p{0.30\\linewidth}")
            #else:
            colspec_parts.append("c")
        colspec = "|".join(colspec_parts)

        macro = "TableDouble" if self._should_wide_table(rows_raw) else "Table"

        # Build tabular content
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
        marker for an English name/title/abstract block.
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
            # simple English-ness heuristic
            if re.search(r"\b(the|with|model|we|using|were|was|data|results|method)\b", txt.lower()):
                abstract_en.append(txt)
                if len(abstract_en) >= 3:
                    break
            else:
                # stop if looks unrelated
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

        # Gather potential AuthorEx lines from text boxes already   
        author_ex_lines: List[str] = list(self.ctx.author_box_lines)

        # Also collect Autorstvo-like paragraphs in the front section (before first section)
        #first_section_idx = None
        #for idx, blk in self.ctx.iter_body():
        #    if blk.tag == qname("w", "p"):
        #        t = self.ctx._collect_plain_text(blk).strip()
        #        if t and (self.ctx._paragraph_style(blk) in {"Heading2", "Heading3", "Heading4"} or looks_like_section_title(t)):
        #            first_section_idx = idx
        #            break
        # There should be no front limit, becuse the english abstract is the last few paragraphs.
        #front_limit = first_section_idx if first_section_idx is not None else min(60, len(self.ctx.blocks))

        #mentor_keywords = re.compile(r"(mentor|mentorstv|gimnaz|fakult|univerz|school|faculty|university)", re.IGNORECASE)
        #for idx, blk in self.ctx.iter_body():
            #if idx >= front_limit:
            #    break
        #    if blk.tag != qname("w", "p"):
        #        continue
        #    style = self.ctx._paragraph_style(blk)
        #    txt = self.ctx._collect_plain_text(blk).strip()
        #    if not txt:
        #        continue
        #    if style == "Autorstvo" or mentor_keywords.search(txt):
        #        cleaned = re.sub(r"\s+", " ", txt)
        #        print("Ovde??")
        #        if cleaned and cleaned not in author_ex_lines:
        #            author_ex_lines.append(cleaned)
        #            print("Ovde je uso??")

        # Front matter (strict styles) for authors, title, abstract (sr)
        flagAuthors = False
        for idx, blk in self.ctx.iter_body():
            if blk.tag != qname("w", "p"): # or idx >= front_limit:
                continue
            style = self.ctx._paragraph_style(blk)
            txt = self.ctx._collect_plain_text(blk).strip()
            if not txt:
                continue
            if style == "Imeiprezime" and not flagAuthors:
                # if is_likely_name(txt):
                authors.append(escape_latex(txt))
                flagAuthors = True # TO-DO There is only latex for serbian names, we added for english should be divided
                # OR don't use language spcific things in Authors ('i' and 'and')
            if style == "Autorstvo":
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

        # Conservative fallbacks if missing authors/title_sr
        if not authors or not title_sr:
            for idx, blk in self.ctx.iter_body():
                if blk.tag != qname("w", "p"): # or idx >= front_limit:
                    continue
                txt = self.ctx._collect_plain_text(blk).strip()
                if not txt:
                    continue
                if not authors and is_likely_name(txt):
                    authors.append(escape_latex(txt))
                    continue
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
                # Fill skipped levels with itemize so LaTeX nesting stays balanced.
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
                # Insert footnote placement if not yet inserted
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

            # Start references once (single heading)
            if (style == "Literatura" or plain_text.lower() in {"literatura", "references"}) and not refs_started:
                close_lists()
                refs.append("\\section{Literatura}")
                refs_started = True
                in_refs_collect = True
                continue
            # Stop refs collection on any new section/abstract marker
            if in_refs_collect and (style in {"Heading2", "Heading3", "Heading4", "Apstrakt", "AbstractEng"} or looks_like_section_title(plain_text)):
                in_refs_collect = False

            # While in refs, emit \Source and continue
            if in_refs_collect:
                refs.append("\\Source{")
                refs.append(f"    {escape_latex(plain_text)}")
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

            # Inline drawings (figures) inside the paragraph → emit at that point
            segments: List[str | Tuple[str, ...]] = []
            cursor_parts: List[str] = []

            def flush_cursor():
                if cursor_parts:
                    t = "".join(cursor_parts).strip()
                    if t:
                        segments.append(t)
                    cursor_parts.clear()

            had_drawing = False
            for node in block:
                if node.tag == qname("w", "r"):
                    drawing = find(node, "w:drawing")
                    if drawing is not None:
                        had_drawing = True
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
                            figure_counter += 1
                            cap_sr, cap_en, consumed = self._caption_near(idx, "fig", expected_num=figure_counter)
                            if cap_sr is None and cap_en is None:
                                cap_sr, cap_en, consumed = self._caption_near(idx, "fig")
                            for j in consumed:
                                self._skip_block_indexes.add(j)
                            segments.append(("FIGURE", target, Path(target).name, width_emu, cap_sr or "", cap_en or ""))
                        continue
                    cursor_parts.append(self.para_conv._convert_run(node))
                elif node.tag == qname("w", "hyperlink"):
                    cursor_parts.append(self.para_conv._convert_hyperlink(node))
            flush_cursor()

            # Capture caption fragments embedded in the same paragraph
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
                pending_sr = None
            if pending_en and not has_figure:
                processed_segments.append(pending_en)
                pending_en = None
            segments = processed_segments

            # Emit segments
            if segments:
                if not author_ex_here_inserted and author_ex_lines:
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
                    if figure_is_wide(width_val):
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

        # If English abstract missing, try to recover from tail
        if not title_en or not abstract_en_parts:
            rec_title_en, rec_abs_en = self._recover_english_tail()
            if rec_title_en and not title_en:
                title_en = rec_title_en
            if rec_abs_en and not abstract_en_parts:
                abstract_en_parts = rec_abs_en

        # Header emission (Authors → Titles → Abstracts → StartDoublePaper)
        if not header:
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

SAFE_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".pdf"}

def normalize_media_in_place(out_dir: Path) -> dict[str, str]:
    """
    Convert unsupported formats (emf/wmf/tiff) to PNG using LibreOffice if available,
    sanitize filenames to ASCII, and return a mapping {old_basename -> new_basename}.
    """
    mapping: dict[str, str] = {}

    def have(prog: str) -> bool:
        from shutil import which
        return which(prog) is not None

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
    converter = ZbornikConverter(package)
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
