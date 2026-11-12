"""Build src/paper/docx_assets/reference.docx from pandoc's default: A4, 1 inch margins, serif body,
black headings, caption styles, compact table text."""
import os
import subprocess
from docx import Document
from docx.shared import Pt, Emu
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = os.path.join(ROOT, "src", "paper", "docx_assets")
out = os.path.join(ASSETS, "reference.docx")
raw = subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], capture_output=True)
with open(out, "wb") as f:
    f.write(raw.stdout)

FONT = "Times New Roman"
doc = Document(out)


def set_font(style, size=None, bold=None, italic=None):
    rpr = style.element.get_or_add_rPr()
    for el in rpr.findall(qn("w:rFonts")):
        rpr.remove(el)
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), FONT)
    rpr.insert(0, rf)
    for el in rpr.findall(qn("w:color")):
        rpr.remove(el)
    col = OxmlElement("w:color")
    col.set(qn("w:val"), "000000")
    rpr.append(col)
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic


names = [s.name for s in doc.styles]
for nm, size, bold in [("Normal", 11, None), ("Body Text", 11, None), ("First Paragraph", 11, None), ("Compact", 9, None),
                       ("Title", 17, True), ("Author", 11, None), ("Date", 11, None), ("Abstract", 10, None),
                       ("Heading 1", 14, True), ("Heading 2", 12, True), ("Heading 3", 11, True), ("Heading 4", 11, True),
                       ("Heading 5", 11, True), ("Heading 6", 11, True), ("Heading 7", 11, True), ("Heading 8", 11, True), ("Heading 9", 11, True),
                       ("Table Caption", 10, None), ("Image Caption", 10, None), ("Figure", 11, None), ("Captioned Figure", 11, None),
                       ("Bibliography", 9, None), ("Block Text", 11, None), ("Footnote Text", 9, None)]:
    if nm in names:
        st = doc.styles[nm]
        set_font(st, size, bold)
        if nm.startswith("Heading") or nm == "Title":
            st.font.italic = False
            pf = st.paragraph_format
            pf.space_before = Pt(12)
            pf.space_after = Pt(4)
            pf.keep_with_next = True
        if nm in ("Body Text", "First Paragraph"):
            st.paragraph_format.space_after = Pt(6)
            st.paragraph_format.space_before = Pt(0)
            st.paragraph_format.line_spacing = 1.15
        if nm == "Title":
            st.paragraph_format.alignment = 1
        if nm in ("Table Caption", "Image Caption"):
            st.font.italic = False
        if nm in ("Table Caption",):
            st.paragraph_format.keep_with_next = True
            st.paragraph_format.space_before = Pt(8)
            st.paragraph_format.space_after = Pt(3)
        if nm in ("Image Caption",):
            st.paragraph_format.space_after = Pt(8)
# theme colour / theme font attributes left on headings would still tint them: remove them
for st in doc.styles:
    try:
        rpr = st.element.rPr
    except Exception:
        continue
    if rpr is None or st.name == "Hyperlink":
        continue
    for el in rpr.findall(qn("w:color")):
        for a in (qn("w:themeColor"), qn("w:themeShade"), qn("w:themeTint")):
            if a in el.attrib:
                del el.attrib[a]
        el.set(qn("w:val"), "000000")
    for el in rpr.findall(qn("w:rFonts")):
        for a in list(el.attrib):
            if "Theme" in a:
                del el.attrib[a]
# Hyperlink char style stays the Word-blue (clickable DOI), not heading colour. The loop above used to blacken it too
# (DOIs printed black in main.docx), so it is skipped there and set explicitly here.
if "Hyperlink" in names:
    hrpr = doc.styles["Hyperlink"].element.get_or_add_rPr()
    for el in hrpr.findall(qn("w:color")):
        hrpr.remove(el)
    hc = OxmlElement("w:color")
    hc.set(qn("w:val"), "0563C1")
    hrpr.append(hc)
sec = doc.sections[0]
sec.page_width = Emu(7560310)   # A4
sec.page_height = Emu(10692130)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Emu(914400))
doc.save(out)
print("reference.docx written", [n for n in names if n.startswith(("Heading", "Table", "Image", "Compact", "Title"))])
