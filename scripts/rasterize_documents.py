import argparse
import json
import sys
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(); parser.add_argument("--round", default="round-1"); args = parser.parse_args()
folder = ROOT / ".work/midterm" / args.round
manifest = []
for pdf in sorted(folder.glob("*.pdf")):
    doc = pdfium.PdfDocument(pdf); reader = PdfReader(pdf)
    out = folder / pdf.stem; out.mkdir(exist_ok=True)
    thumbs = []
    for i, page in enumerate(doc):
        img = page.render(scale=1.8).to_pil().convert("RGB"); img.save(out / f"page-{i+1:02}.png")
        content = reader.pages[i].extract_text() or ""
        (out / f"page-{i+1:02}.txt").write_text(content, encoding="utf-8")
        thumb = ImageOps.contain(img, (450, 640)); canvas = Image.new("RGB", (470, 675), "#e5e5e5"); canvas.paste(thumb, ((470-thumb.width)//2, 25)); ImageDraw.Draw(canvas).text((10, 5), f"page {i+1}", fill="black"); thumbs.append(canvas)
    for start in range(0, len(thumbs), 4):
        sheet = Image.new("RGB", (940, 1350), "white")
        for i, thumb in enumerate(thumbs[start:start+4]): sheet.paste(thumb, ((i%2)*470, (i//2)*675))
        sheet.save(out / f"contact-{start//4+1}.png")
    manifest.append({"document": pdf.stem, "pages": len(doc), "renderPath": str(out)})
    print(pdf.stem, len(doc), "pages")
(folder / "render-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
