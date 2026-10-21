"""记录甲方模板的布局、可编辑位置与包级保留清单，不改动原模板。"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image, ImageDraw, ImageOps
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".work/midterm"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
parser = argparse.ArgumentParser()
parser.add_argument("--test-template", type=Path, required=True)
args = parser.parse_args()
sources = [(WORK / "attachment2-reference.docx", WORK / "attachment2-reference.pdf", [0, 1, 2, 3]),
           (args.test_template.resolve(), WORK / "attachment3-reference.pdf", list(range(13)))]
evidence = []
for path, pdf, pages in sources:
    with ZipFile(path) as z:
        xml = etree.fromstring(z.read("word/document.xml"))
        styles = etree.fromstring(z.read("word/styles.xml"))
        body = xml.find("w:body", NS)
        item = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "parts": {i.filename: {"bytes": i.file_size, "sha256": hashlib.sha256(z.read(i.filename)).hexdigest()} for i in z.infolist()},
                "sections": [etree.tostring(s).decode() for s in xml.findall(".//w:sectPr", NS)],
                "stylesXml": etree.tostring(styles).decode(),
                "slots": [{"bodyIndex": i, "kind": e.tag.split("}")[-1], "text": "".join(e.itertext()) if False else "".join(t.text or "" for t in e.findall(".//w:t", NS))} for i, e in enumerate(body)]}
    doc = pdfium.PdfDocument(pdf)
    item["pages"] = len(doc); evidence.append(item)
    folder = WORK / (path.stem + "-render"); folder.mkdir(exist_ok=True)
    thumbs = []
    for i in pages:
        image = doc[i].render(scale=1.5).to_pil().convert("RGB"); image.save(folder / f"page-{i+1:02}.png")
        thumb = ImageOps.contain(image, (450, 640)); canvas = Image.new("RGB", (470, 675), "#e5e5e5"); canvas.paste(thumb, ((470-thumb.width)//2, 25)); ImageDraw.Draw(canvas).text((10, 5), f"page {i+1}", fill="black"); thumbs.append(canvas)
    for start in range(0, len(thumbs), 4):
        sheet = Image.new("RGB", (940, 1350), "white")
        for j, thumb in enumerate(thumbs[start:start+4]): sheet.paste(thumb, ((j%2)*470, (j//2)*675))
        sheet.save(folder / f"contact-{start//4+1}.png")
(WORK / "template-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
text = """# 中期检查文档模板执行约定

## 参考与证据
附件2 WPS原件只读转换为 attachment2-reference.docx；原件及转换件均保留，来源路径与 SHA-256 见 template-evidence.json。附件3原DOCX保留不变。转换与渲染使用本机 WPS COM；标准 render_docx.py 已尝试，因未安装 LibreOffice 失败，故使用 WPS 导出 PDF 并由 PDFium 逐页生成 PNG 复核。

## 页面与字体
所有原始节的纸张、页边距、页眉页脚距离、字号、字体及段落属性完整记录在 template-evidence.json 的 sections 与 stylesXml。附件2年度报告选用正文节点8至42，保留源封面与正文两种版式；正文为源黑体标题及仿宋正文，段落固定23磅行距。附件2意见稿选用0至7及年度报告节末几何；附件3大纲选用0至63，报告选用64至105，保留各自封面、目录、正文及附表版式。附件3以源14磅正文与源表格字体排版，英文数字沿用新罗马，中文沿用仿宋。

## 编辑位置
年度报告：封面年份改2026，单位等基本信息留空；26至41按原八节标题逐节写入 PlanCoder 技术成果。意见稿：替换示例叙述为供专家审定的技术事实，评估结论、经费意见、专家名单与签名留空。测试大纲：替换目的、依据、方案、场景及风险正文，克隆源场景表格形成五场景；评审意见改为待专家填写的空白位置。测试报告：写入实际内部自测及历史记录复算，克隆结果表填写自测实际结果；专家现场结论及签字留空。

## 保留与允许变更
仅变更 word/document.xml、word/settings.xml，以及必要的Title语义样式；其余包部件、关系、图片、页眉页脚与编号逐字节保留。所有表格沿用源网格与边框，移除可能截断扩展文字的固定行高。克隆段落不复制重复书签。源目录中的示例x页码改为无页码的实际章节目录，避免假页码。独立文档页码重置，设置打开时更新字段。封面与正文的标题字号、纸张、页边距不套用新设计。

## 交付检查
源文件哈希保持不变；包级非编辑部件哈希相同；八节结构及测试场景齐全；基本信息与全部经费数值留空；不预填专家通过意见，不写录用或项目验收结论。逐页渲染检查文字、表格、分页及页码，交付仅四份DOCX。
"""
(WORK / "artifact.md").write_text(text, encoding="utf-8")
print("Template contract and reference page images prepared.")
