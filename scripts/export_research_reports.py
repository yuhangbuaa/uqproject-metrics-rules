"""Rebuild the two research reports from Markdown with the agreed Word layout.

Requires Pandoc on PATH. Uses only Python's standard library otherwise.
Run from any directory: python scripts/export_research_reports.py
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.dom import Node, minidom


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "deliverables" / "研究报告_20261023"
REPORT_NAMES = (
    "决策不确定性及其来源的分析-分类-量化方法_研究报告_20261023",
    "智能软件决策多元不确定性主动感知方法_研究报告_20261023",
)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
TABLE_WIDTH = 9360  # Letter page with 1-inch left/right margins, in twips.


def children(parent, local=None, namespace=W):
    return [
        node for node in parent.childNodes
        if node.nodeType == Node.ELEMENT_NODE
        and (local is None or (node.namespaceURI == namespace and node.localName == local))
    ]


def child(parent, local, namespace=W):
    return next(iter(children(parent, local, namespace)), None)


def all_nodes(parent, local, namespace=W):
    return parent.getElementsByTagNameNS(namespace, local)


def make(doc, local, namespace=W, prefix="w"):
    return doc.createElementNS(namespace, f"{prefix}:{local}")


def ensure(parent, local, first=False):
    node = child(parent, local)
    if node is not None:
        return node
    node = make(parent.ownerDocument, local)
    if first and parent.firstChild is not None:
        parent.insertBefore(node, parent.firstChild)
    else:
        parent.appendChild(node)
    return node


def setv(node, key, value):
    node.setAttributeNS(W, f"w:{key}", str(value))


def val(node, key):
    return node.getAttributeNS(W, key) if node is not None else ""


def clear_theme(node):
    for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme", "themeColor", "themeShade", "themeTint"):
        if node.hasAttributeNS(W, key):
            node.removeAttributeNS(W, key)


def set_font(rpr, chinese, western, points=None, color=None):
    fonts = ensure(rpr, "rFonts", first=True)
    clear_theme(fonts)
    for key, value in (("ascii", western), ("hAnsi", western), ("cs", western), ("eastAsia", chinese)):
        setv(fonts, key, value)
    if points is not None:
        for key in ("sz", "szCs"):
            setv(ensure(rpr, key), "val", round(points * 2))
    if color is not None:
        color_node = ensure(rpr, "color")
        clear_theme(color_node)
        setv(color_node, "val", color)


def set_paragraph(ppr, *, first_chars=0, before=0, after=0, line=360, align=None):
    spacing = ensure(ppr, "spacing")
    for key, value in (("before", before), ("after", after), ("line", line), ("lineRule", "auto")):
        setv(spacing, key, value)
    indent = ensure(ppr, "ind")
    setv(indent, "firstLineChars", first_chars * 100)
    for key in ("firstLine", "hanging", "hangingChars"):
        if indent.hasAttributeNS(W, key):
            indent.removeAttributeNS(W, key)
    if align:
        setv(ensure(ppr, "jc"), "val", align)


def set_code_paragraph(ppr):
    set_paragraph(ppr, line=280, before=120, after=120, align="left")
    indent = ensure(ppr, "ind")
    setv(indent, "left", 220)
    setv(indent, "right", 220)
    setv(ensure(ppr, "wordWrap"), "val", "on")
    shade = ensure(ppr, "shd")
    setv(shade, "val", "clear")
    setv(shade, "fill", "F7F7F7")
    borders = ensure(ppr, "pBdr")
    for edge in ("top", "left", "bottom", "right"):
        border = ensure(borders, edge)
        for key, value in (("val", "single"), ("sz", 4), ("space", 5), ("color", "D9D9D9")):
            setv(border, key, value)


def paragraph_style(paragraph):
    ppr = child(paragraph, "pPr")
    return val(child(ppr, "pStyle"), "val") if ppr else ""


def change_style(paragraph, style):
    ppr = ensure(paragraph, "pPr", first=True)
    setv(ensure(ppr, "pStyle", first=True), "val", style)


def text_of(paragraph):
    return "".join(node.firstChild.data for node in all_nodes(paragraph, "t") if node.firstChild)


def style_properties(style, ppr_settings, font_settings, bold=False):
    ppr = child(style, "pPr")
    if ppr is None:
        ppr = make(style.ownerDocument, "pPr")
        next_run = child(style, "rPr")
        style.insertBefore(ppr, next_run) if next_run is not None else style.appendChild(ppr)
    set_paragraph(ppr, **ppr_settings)
    rpr = ensure(style, "rPr")
    set_font(rpr, **font_settings)
    if bold:
        setv(ensure(rpr, "b"), "val", 1)
    if val(style, "styleId").startswith("Heading"):
        ensure(ppr, "keepNext")


def format_styles(styles):
    root = styles.documentElement
    defaults = child(root, "docDefaults")
    if defaults is not None:
        rdefault = child(defaults, "rPrDefault")
        if rdefault is not None:
            set_font(ensure(rdefault, "rPr"), "仿宋_GB2312", "Times New Roman", 14)
    style_map = {val(style, "styleId"): style for style in all_nodes(root, "style")}
    specs = {
        "Normal": (dict(first_chars=2, align="both"), dict(chinese="仿宋_GB2312", western="Times New Roman", points=14), False),
        "BodyText": (dict(first_chars=2, align="both"), dict(chinese="仿宋_GB2312", western="Times New Roman", points=14), False),
        "FirstParagraph": (dict(first_chars=2, align="both"), dict(chinese="仿宋_GB2312", western="Times New Roman", points=14), False),
        "Title": (dict(before=600, after=500, align="center"), dict(chinese="黑体", western="黑体", points=18, color="000000"), True),
        "Heading1": (dict(before=280, after=140, align="left"), dict(chinese="黑体", western="黑体", points=14, color="000000"), True),
        "Heading2": (dict(before=200, after=80, align="left"), dict(chinese="黑体", western="黑体", points=14, color="000000"), True),
        "Heading3": (dict(before=180, after=80, align="left"), dict(chinese="黑体", western="黑体", points=14, color="000000"), True),
        "TOCHeading": (dict(before=180, after=160, align="center"), dict(chinese="黑体", western="黑体", points=14, color="000000"), True),
        "Compact": (dict(align="left"), dict(chinese="宋体", western="Times New Roman", points=10.5), False),
        "Table": (dict(align="left"), dict(chinese="宋体", western="Times New Roman", points=10.5), False),
        "CaptionedFigure": (dict(before=120, after=0, align="center"), dict(chinese="宋体", western="Times New Roman", points=10.5), False),
        "ImageCaption": (dict(before=40, after=120, align="center"), dict(chinese="宋体", western="Times New Roman", points=10.5), False),
    }
    for sid, (ppr, font, bold) in specs.items():
        if sid in style_map:
            style_properties(style_map[sid], ppr, font, bold)
    if "CaptionedFigure" in style_map:
        ensure(ensure(style_map["CaptionedFigure"], "pPr"), "keepNext")
    if "ImageCaption" in style_map:
        setv(ensure(ensure(style_map["ImageCaption"], "rPr"), "i"), "val", 0)
    if "SourceCode" in style_map:
        set_code_paragraph(ensure(style_map["SourceCode"], "pPr"))
    for sid, level in (("TOC1", 1), ("TOC2", 2)):
        style = style_map.get(sid)
        if style is None:
            style = make(styles, "style")
            setv(style, "type", "paragraph")
            setv(style, "styleId", sid)
            name = make(styles, "name")
            setv(name, "val", f"toc {level}")
            style.appendChild(name)
            root.appendChild(style)
        style_properties(style, dict(after=40, align="left"), dict(chinese="仿宋_GB2312", western="Times New Roman", points=12 if level == 1 else 10.5))
        setv(ensure(ensure(style, "pPr"), "ind"), "left", (level - 1) * 360)


def set_page(section):
    size = ensure(section, "pgSz")
    setv(size, "w", 12240)
    setv(size, "h", 15840)
    margins = ensure(section, "pgMar")
    for key, value in (("top", 1440), ("right", 1440), ("bottom", 1440), ("left", 1440), ("header", 720), ("footer", 720), ("gutter", 0)):
        setv(margins, key, value)


def format_cover_and_sections(document, footer_id):
    body = child(document.documentElement, "body")
    toc = next((node for node in children(body) if node.localName == "sdt"), None)
    title = next((p for p in children(body, "p") if paragraph_style(p) == "Heading1"), None)
    date = next((p for p in children(body, "p") if text_of(p).startswith("编制日期：")), None)
    if toc is None or title is None or date is None:
        raise ValueError("Expected Pandoc TOC, document title, and cover metadata")
    change_style(title, "Title")
    for paragraph in children(body, "p"):
        sid = paragraph_style(paragraph)
        if sid == "Heading2":
            change_style(paragraph, "Heading1")
        elif sid == "Heading3":
            change_style(paragraph, "Heading2")
    current = title.nextSibling
    while current is not None and current is not date.nextSibling:
        next_node = current.nextSibling
        if current.nodeType == Node.ELEMENT_NODE and current.localName == "p":
            ppr = ensure(current, "pPr", first=True)
            set_paragraph(ppr, after=120, align="left")
            setv(ensure(ppr, "ind"), "left", 720)
        current = next_node
    page_run = make(document, "r")
    page_break = make(document, "br")
    setv(page_break, "type", "page")
    page_run.appendChild(page_break)
    date.appendChild(page_run)
    body.removeChild(toc)
    body.insertBefore(toc, date.nextSibling)
    toc_heading = next((p for p in all_nodes(toc, "p") if paragraph_style(p) == "TOCHeading"), None)
    if toc_heading is not None:
        for node in all_nodes(toc_heading, "t"):
            while node.firstChild:
                node.removeChild(node.firstChild)
            node.appendChild(document.createTextNode("目录"))
            break
    section_end = make(document, "p")
    ppr = make(document, "pPr")
    first_section = make(document, "sectPr")
    setv(ensure(first_section, "type"), "val", "nextPage")
    set_page(first_section)
    ppr.appendChild(first_section)
    section_end.appendChild(ppr)
    body.insertBefore(section_end, toc.nextSibling)
    final_section = child(body, "sectPr")
    if final_section is None:
        final_section = make(document, "sectPr")
        body.appendChild(final_section)
    reference = make(document, "footerReference")
    setv(reference, "type", "default")
    reference.setAttributeNS(R, "r:id", footer_id)
    final_section.insertBefore(reference, final_section.firstChild)
    set_page(final_section)
    setv(ensure(final_section, "pgNumType"), "start", 1)


def table_widths(rows, columns):
    def visual_length(text):
        return sum(1 if ord(char) > 127 else 0.55 for char in text)

    scores = []
    for index in range(columns):
        values = sorted(visual_length(text_of(cells[index])) for row in rows if len(cells := children(row, "tc")) > index)
        percentile = values[math.floor(0.8 * (len(values) - 1))] if values else 6
        scores.append(math.sqrt(max(6, min(60, percentile))))
    equal = TABLE_WIDTH / columns
    widths = [max(equal * 0.62, min(equal * 1.8, TABLE_WIDTH * score / sum(scores))) for score in scores]
    for _ in range(5):
        delta = TABLE_WIDTH - sum(widths)
        if abs(delta) < 2:
            break
        available = [i for i, width in enumerate(widths) if (delta > 0 and width < equal * 1.8 - 1) or (delta < 0 and width > equal * 0.62 + 1)]
        if not available:
            break
        for index in available:
            widths[index] = max(equal * 0.62, min(equal * 1.8, widths[index] + delta / len(available)))
    minimums = [equal * 0.62] * columns
    for index, cell in enumerate(children(rows[0], "tc")):
        words = re.findall(r"[A-Za-z]{8,}", text_of(cell))
        if words:
            minimums[index] = min(equal * 1.8, max(minimums[index], 120 * max(map(len, words)) + 240))
    for index, minimum in enumerate(minimums):
        deficit = max(0, minimum - widths[index])
        for donor in sorted(range(columns), key=lambda i: widths[i] - minimums[i], reverse=True):
            if donor == index or deficit < 1:
                continue
            amount = min(deficit, max(0, widths[donor] - minimums[donor]))
            widths[donor] -= amount
            widths[index] += amount
            deficit -= amount
    rounded = [round(width) for width in widths]
    rounded[-1] += TABLE_WIDTH - sum(rounded)
    return rounded


def format_tables(document):
    for table in all_nodes(document.documentElement, "tbl"):
        rows = children(table, "tr")
        if not rows:
            continue
        columns = max(len(children(row, "tc")) for row in rows)
        widths = table_widths(rows, columns)
        tblpr = ensure(table, "tblPr", first=True)
        table_width = ensure(tblpr, "tblW")
        setv(table_width, "type", "dxa")
        setv(table_width, "w", TABLE_WIDTH)
        setv(ensure(tblpr, "tblLayout"), "type", "fixed")
        borders = ensure(tblpr, "tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = ensure(borders, edge)
            for key, value in (("val", "single"), ("sz", 4), ("color", "D9D9D9")):
                setv(border, key, value)
        margins = ensure(tblpr, "tblCellMar")
        for edge, size in (("top", 80), ("bottom", 80), ("left", 100), ("right", 100)):
            margin = ensure(margins, edge)
            setv(margin, "w", size)
            setv(margin, "type", "dxa")
        grid = ensure(table, "tblGrid")
        for col in list(children(grid, "gridCol")):
            grid.removeChild(col)
        for width in widths:
            col = make(document, "gridCol")
            setv(col, "w", width)
            grid.appendChild(col)
        for row_index, row in enumerate(rows):
            if row_index == 0:
                setv(ensure(ensure(row, "trPr", first=True), "tblHeader"), "val", "on")
            for col_index, cell in enumerate(children(row, "tc")):
                tcpr = ensure(cell, "tcPr", first=True)
                tcw = ensure(tcpr, "tcW", first=True)
                setv(tcw, "w", widths[min(col_index, columns - 1)])
                setv(tcw, "type", "dxa")
                setv(ensure(tcpr, "vAlign"), "val", "center")
                if row_index == 0:
                    shade = ensure(tcpr, "shd")
                    setv(shade, "val", "clear")
                    setv(shade, "fill", "EDEDED")
                for paragraph in all_nodes(cell, "p"):
                    set_paragraph(ensure(paragraph, "pPr", first=True), align="center" if row_index == 0 else "left")
                for run in all_nodes(cell, "r"):
                    rpr = ensure(run, "rPr", first=True)
                    set_font(rpr, "宋体", "Times New Roman", 10.5)
                    if row_index == 0:
                        setv(ensure(rpr, "b"), "val", 1)


def format_headings_and_code(document):
    headings = {"Title", "Heading1", "Heading2", "Heading3", "TOCHeading"}
    code_count = 0
    for paragraph in all_nodes(document.documentElement, "p"):
        sid = paragraph_style(paragraph)
        if sid in headings:
            for run in all_nodes(paragraph, "r"):
                set_font(ensure(run, "rPr", first=True), "黑体", "黑体", color="000000")
        elif sid == "SourceCode":
            code_count += 1
            set_code_paragraph(ensure(paragraph, "pPr", first=True))
            for run in all_nodes(paragraph, "r"):
                set_font(ensure(run, "rPr", first=True), "宋体", "Consolas", 10.5, "333333")
    return code_count


def footer_xml():
    doc = minidom.Document()
    footer = doc.createElementNS(W, "w:ftr")
    footer.setAttribute("xmlns:w", W)
    doc.appendChild(footer)
    paragraph = make(doc, "p")
    ppr = make(doc, "pPr")
    setv(ensure(ppr, "jc"), "val", "center")
    paragraph.appendChild(ppr)
    for index, field_name in enumerate(("PAGE", "SECTIONPAGES")):
        for item_type, value in (("char", "begin"), ("instr", f" {field_name} "), ("char", "separate"), ("text", "1"), ("char", "end")):
            run = make(doc, "r")
            rpr = make(doc, "rPr")
            set_font(rpr, "Times New Roman", "Times New Roman", 9)
            run.appendChild(rpr)
            if item_type == "char":
                node = make(doc, "fldChar")
                setv(node, "fldCharType", value)
                if value == "begin":
                    setv(node, "dirty", "true")
            elif item_type == "instr":
                node = make(doc, "instrText")
                node.setAttribute("xml:space", "preserve")
                node.appendChild(doc.createTextNode(value))
            else:
                node = make(doc, "t")
                node.appendChild(doc.createTextNode(value))
            run.appendChild(node)
            paragraph.appendChild(run)
        if index == 0:
            slash = make(doc, "r")
            rpr = make(doc, "rPr")
            set_font(rpr, "Times New Roman", "Times New Roman", 9)
            slash.appendChild(rpr)
            text = make(doc, "t")
            text.appendChild(doc.createTextNode("/"))
            slash.appendChild(text)
            paragraph.appendChild(slash)
    footer.appendChild(paragraph)
    return doc.toxml(encoding="utf-8")


def add_footer_parts(rels, content_types, existing_parts):
    relationship_ids = [int(match.group(1)) for node in children(rels.documentElement, namespace=PR) if (match := re.fullmatch(r"rId(\d+)", node.getAttribute("Id")))]
    rid = f"rId{max(relationship_ids, default=0) + 1}"
    number = 1
    while f"word/footer{number}.xml" in existing_parts:
        number += 1
    footer_name = f"word/footer{number}.xml"
    relation = rels.createElementNS(PR, "Relationship")
    relation.setAttribute("Id", rid)
    relation.setAttribute("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer")
    relation.setAttribute("Target", f"footer{number}.xml")
    rels.documentElement.appendChild(relation)
    override = content_types.createElementNS(CT, "Override")
    override.setAttribute("PartName", f"/{footer_name}")
    override.setAttribute("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
    content_types.documentElement.appendChild(override)
    return rid, footer_name


def report_text_without_toc(document):
    body = child(document.documentElement, "body")
    return "".join(text_of(node) for node in children(body) if node.localName != "sdt")


def format_docx(source, output):
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        parts = {item.filename: archive.read(item.filename) for item in infos}
    document = minidom.parseString(parts["word/document.xml"])
    original_text = report_text_without_toc(document)
    original_math = len(all_nodes(document.documentElement, "oMath", M))
    styles = minidom.parseString(parts["word/styles.xml"])
    rels = minidom.parseString(parts["word/_rels/document.xml.rels"])
    content_types = minidom.parseString(parts["[Content_Types].xml"])
    settings = minidom.parseString(parts["word/settings.xml"])
    format_styles(styles)
    footer_id, footer_name = add_footer_parts(rels, content_types, parts)
    format_cover_and_sections(document, footer_id)
    format_tables(document)
    code_count = format_headings_and_code(document)
    setv(ensure(settings.documentElement, "updateFields"), "val", 1)
    if report_text_without_toc(document) != original_text:
        raise ValueError("Formatting unexpectedly changed report text")
    if len(all_nodes(document.documentElement, "oMath", M)) != original_math:
        raise ValueError("Formatting unexpectedly changed equation count")
    replacements = {
        "word/document.xml": document.toxml(encoding="utf-8"),
        "word/styles.xml": styles.toxml(encoding="utf-8"),
        "word/_rels/document.xml.rels": rels.toxml(encoding="utf-8"),
        "[Content_Types].xml": content_types.toxml(encoding="utf-8"),
        "word/settings.xml": settings.toxml(encoding="utf-8"),
        footer_name: footer_xml(),
    }
    with zipfile.ZipFile(output, "w") as archive:
        for info in infos:
            archive.writestr(info, replacements.pop(info.filename, parts[info.filename]))
        for name, data in replacements.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"Corrupt DOCX generated: {output}")
    return code_count


def export_report(name, destination, workdir):
    markdown = REPORT_DIR / f"{name}.md"
    if not markdown.is_file():
        raise FileNotFoundError(markdown)
    raw_docx = workdir / f"{name}-raw.docx"
    formatted_docx = workdir / f"{name}-formatted.docx"
    command = [
        "pandoc", "--from=markdown+tex_math_dollars", "--to=docx", "--standalone",
        "--toc", "--toc-depth=2", f"--resource-path={REPORT_DIR}",
        f"--output={raw_docx}", str(markdown),
    ]
    subprocess.run(command, check=True)
    code_count = format_docx(raw_docx, formatted_docx)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".report-export-", suffix=".docx", dir=destination.parent)
    os.close(handle)
    try:
        shutil.copyfile(formatted_docx, temporary)
        os.replace(temporary, destination)
    except PermissionError as exc:
        raise PermissionError(f"请先关闭正在打开的 Word 文件：{destination}") from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"已生成：{destination}（代码块 {code_count} 处）")


def main():
    parser = argparse.ArgumentParser(description="由两份 Markdown 研究报告重建排版后的 DOCX")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR, help="输出目录；默认覆盖同目录下原有 DOCX")
    args = parser.parse_args()
    if shutil.which("pandoc") is None:
        parser.error("未找到 Pandoc，请先安装并加入 PATH")
    work_root = ROOT / ".work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-report-export-", dir=work_root) as temporary:
        workdir = Path(temporary)
        for name in REPORT_NAMES:
            export_report(name, args.output_dir / f"{name}.docx", workdir)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"转换失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
