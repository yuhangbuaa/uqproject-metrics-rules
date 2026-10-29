"""Export the revised 2026-10-25 Markdown reports and reviewer responses to Word.

Keeps the imported Word originals intact. Run from any directory:
    python scripts/export_20261025_revisions.py
"""

from __future__ import annotations

import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.dom import Node, minidom

import export_research_reports as layout


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "deliverables" / "研究报告_20261025"
REPORT_NAMES = ("分析分类量化", "不确定性感知")
REVIEW_SOURCE = REPORT_DIR / "评审意见表-1025.docx"
REVIEW_MARKDOWN = REPORT_DIR / "评审意见表-1025.md"
OUTPUT_SUFFIX = "_修改版.docx"
REVIEW_OUTPUT = REPORT_DIR / f"评审意见表-1025{OUTPUT_SUFFIX}"


def set_a4_page(section):
    size = layout.ensure(section, "pgSz")
    layout.setv(size, "w", 11906)
    layout.setv(size, "h", 16838)
    margins = layout.ensure(section, "pgMar")
    for key, value in (("top", 1440), ("right", 1440), ("bottom", 1440), ("left", 1440), ("header", 720), ("footer", 720), ("gutter", 0)):
        layout.setv(margins, key, value)


def review_rows():
    source = REVIEW_MARKDOWN.read_text(encoding="utf-8")
    table = ET.fromstring(source[source.index("<table"):])
    rows = table.findall("./tbody/tr")[1:]
    if len(rows) != 5:
        raise ValueError("Expected one review-table row per expert")
    result = []
    for row in rows:
        cells = row.findall("td")
        if len(cells) != 3:
            raise ValueError("Expected three review-table columns")
        expert = "".join(cells[0].itertext()).strip()
        opinions = ["".join(item.itertext()).strip() for item in cells[1].findall("ol/li")]
        responses = ["".join(item.itertext()).strip() for item in cells[2].findall("ol/li")]
        if len(opinions) != len(responses) or not all(response.startswith("采纳。") and len(response) > len(opinion) for opinion, response in zip(opinions, responses)):
            raise ValueError(f"Review responses are incomplete for {expert}")
        result.append((expert, opinions, responses))
    if sum(len(opinions) for _, opinions, _ in result) != 13:
        raise ValueError("Expected thirteen reviewer opinions")
    return result


def paragraph_text(paragraph):
    return "".join(node.firstChild.data for node in layout.all_nodes(paragraph, "t") if node.firstChild)


def make_response_paragraph(document, template, response, number_id):
    paragraph = template.cloneNode(deep=True)
    for node in list(paragraph.childNodes):
        if node.nodeType == Node.ELEMENT_NODE and node.localName != "pPr":
            paragraph.removeChild(node)
    properties = layout.ensure(paragraph, "pPr", first=True)
    numbering = layout.ensure(properties, "numPr")
    layout.setv(layout.ensure(numbering, "numId"), "val", number_id)
    run = layout.make(document, "r")
    original_run = next(iter(layout.all_nodes(template, "r")), None)
    original_properties = layout.child(original_run, "rPr") if original_run is not None else None
    if original_properties is not None:
        run.appendChild(original_properties.cloneNode(deep=True))
    content = layout.make(document, "t")
    content.setAttribute("xml:space", "preserve")
    content.appendChild(document.createTextNode(response))
    run.appendChild(content)
    paragraph.appendChild(run)
    return paragraph


def set_review_table_widths(document, table):
    # Keep the source form's A4 page and overall table width; give replies room.
    widths = (1003, 2758, 4598)  # 12%, 33%, 55% of the original 8359 twips.
    properties = layout.ensure(table, "tblPr", first=True)
    layout.setv(layout.ensure(properties, "tblW"), "type", "dxa")
    layout.setv(layout.ensure(properties, "tblW"), "w", sum(widths))
    layout.setv(layout.ensure(properties, "tblLayout"), "type", "fixed")
    grid = layout.ensure(table, "tblGrid")
    for col in list(layout.children(grid, "gridCol")):
        grid.removeChild(col)
    for width in widths:
        col = layout.make(document, "gridCol")
        layout.setv(col, "w", width)
        grid.appendChild(col)
    for row in layout.children(table, "tr"):
        cells = layout.children(row, "tc")
        if len(cells) != 3:
            raise ValueError("Expected three cells in every review-table row")
        for index, cell in enumerate(cells):
            cell_properties = layout.ensure(cell, "tcPr", first=True)
            cell_width = layout.ensure(cell_properties, "tcW")
            layout.setv(cell_width, "w", widths[index])
            layout.setv(cell_width, "type", "dxa")


def export_review_form():
    content = review_rows()
    with zipfile.ZipFile(REVIEW_SOURCE) as archive:
        infos = archive.infolist()
        parts = {item.filename: archive.read(item.filename) for item in infos}
    document = minidom.parseString(parts["word/document.xml"])
    numbering = minidom.parseString(parts["word/numbering.xml"])
    table = next(iter(layout.all_nodes(document.documentElement, "tbl")), None)
    if table is None:
        raise ValueError("Source review form has no table")
    rows = layout.children(table, "tr")
    if len(rows) != 6:
        raise ValueError("Source review form must have one header and five experts")
    first_response = layout.children(rows[1], "tc")[2]
    template = layout.children(first_response, "p")[0]
    nums = layout.all_nodes(numbering.documentElement, "num")
    template_num = next((node for node in nums if layout.val(node, "numId") == "2"), None)
    if template_num is None:
        raise ValueError("Source review form has no response numbering style")
    max_num = max(int(layout.val(node, "numId")) for node in nums)
    for row_index, (expert, opinions, responses) in enumerate(content, start=1):
        cells = layout.children(rows[row_index], "tc")
        source_expert = paragraph_text(layout.children(cells[0], "p")[0]).strip()
        if "".join(source_expert.split()) != "".join(expert.split()):
            raise ValueError(f"Expert mismatch: {source_expert} vs {expert}")
        if len(layout.children(cells[1], "p")) != len(opinions):
            raise ValueError(f"Opinion count changed for {expert}")
        if row_index == 1:
            number_id = 2
        else:
            max_num += 1
            number_id = max_num
            new_num = template_num.cloneNode(deep=True)
            layout.setv(new_num, "numId", number_id)
            numbering.documentElement.appendChild(new_num)
        response_cell = cells[2]
        for node in list(response_cell.childNodes):
            if node.nodeType == Node.ELEMENT_NODE and node.localName != "tcPr":
                response_cell.removeChild(node)
        for response in responses:
            response_cell.appendChild(make_response_paragraph(document, template, response, number_id))
    set_review_table_widths(document, table)
    replacements = {
        "word/document.xml": document.toxml(encoding="utf-8"),
        "word/numbering.xml": numbering.toxml(encoding="utf-8"),
    }
    handle, temporary = tempfile.mkstemp(prefix=".review-export-", suffix=".docx", dir=REPORT_DIR)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for info in infos:
                archive.writestr(info, replacements.get(info.filename, parts[info.filename]))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("Generated review form failed ZIP validation")
        os.replace(temporary, REVIEW_OUTPUT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"已生成：{REVIEW_OUTPUT}")


def main():
    if shutil.which("pandoc") is None:
        raise RuntimeError("Pandoc was not found on PATH")
    layout.REPORT_DIR = REPORT_DIR
    layout.TABLE_WIDTH = 9026  # A4 page with 1-inch side margins.
    layout.set_page = set_a4_page
    work_root = ROOT / ".work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-report-export-", dir=work_root) as temporary:
        workdir = Path(temporary)
        for name in REPORT_NAMES:
            layout.export_report(name, REPORT_DIR / f"{name}{OUTPUT_SUFFIX}", workdir)
    export_review_form()


if __name__ == "__main__":
    main()
