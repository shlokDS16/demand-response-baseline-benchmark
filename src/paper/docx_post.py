"""Post-process a pandoc docx: numbered native equations, ruled tables, column alignment, table font size,
typographic apostrophes, dash sanitising. Returns a small stats dict."""
import copy
import json
import re
import shutil
import zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}
TEXTW = 9026


def q(tag):
    p, t = tag.split(":")
    return "{%s}%s" % (NS[p], t)


def sub(parent, tag, **attrs):
    el = etree.SubElement(parent, q(tag))
    for k, v in attrs.items():
        el.set(q("w:" + k), str(v))
    return el


def insert_in_order(parent, el, order):
    """Insert el into parent so that the child order follows the schema sequence `order` (list of local names)."""
    name = etree.QName(el).localname
    idx = order.index(name)
    pos = len(parent)
    for k, ch in enumerate(parent):
        ln = etree.QName(ch).localname
        if ln in order and order.index(ln) > idx:
            pos = k
            break
    parent.insert(pos, el)


TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize", "tblW", "jc",
               "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"]
TCPR_ORDER = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"]
PPR_ORDER = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd",
             "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi",
             "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
             "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"]
RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
             "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u",
             "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath"]


def get_child(parent, tag, order):
    el = parent.find(q(tag))
    if el is None:
        el = etree.Element(q(tag))
        insert_in_order(parent, el, order)
    return el


def set_border(parent, side, sz):
    for ex in parent.findall(q("w:" + side)):
        parent.remove(ex)
    b = etree.SubElement(parent, q("w:" + side))
    b.set(q("w:val"), "single")
    b.set(q("w:sz"), str(sz))
    b.set(q("w:space"), "0")
    b.set(q("w:color"), "000000")
    return b


def left_cell_math(body, stats):
    """A table cell whose paragraph holds only one formula (nomenclature rows of pi and kappa) is shown by Word as
    centered display math. Wrap it in an oMathPara justified left, like the other rows."""
    k = 0
    for tc in body.iter(q("w:tc")):
        for para in tc.findall(q("w:p")):
            maths = para.findall(q("m:oMath"))
            text = "".join(t.text or "" for t in para.iter(q("w:t")))
            if len(maths) != 1 or text.replace("\u200b", "").strip():   # pandoc pads the cell with a zero-width space (removed later)
                continue
            om = maths[0]
            idx = list(para).index(om)
            omp = etree.Element(q("m:oMathPara"))
            pp = etree.SubElement(omp, q("m:oMathParaPr"))
            etree.SubElement(pp, q("m:jc")).set(q("m:val"), "left")
            para.remove(om)
            omp.append(om)
            para.insert(idx, omp)
            k += 1
    stats["cell_math_left"] = k


def fix_table_notes(body, stats):
    """Paragraphs that start with @@NOTE@@ (table notes, tex2docx.py) are set in 9 pt, flush left, tight spacing."""
    k = 0
    for para in body.iter(q("w:p")):
        ts = [t for t in para.iter(q("w:t"))]
        if not ts or "@@NOTE@@" not in "".join(t.text or "" for t in ts[:3]):
            continue
        for t in ts:
            if t.text and "@@NOTE@@" in t.text:
                t.text = t.text.replace("@@NOTE@@", "").lstrip()
                break
        ppr = para.find(q("w:pPr"))
        if ppr is None:
            ppr = etree.Element(q("w:pPr"))
            para.insert(0, ppr)
        for ex in ppr.findall(q("w:spacing")):
            ppr.remove(ex)
        sp = etree.Element(q("w:spacing"))
        sp.set(q("w:before"), "40")
        sp.set(q("w:after"), "160")
        sp.set(q("w:line"), "240")
        sp.set(q("w:lineRule"), "auto")
        insert_in_order(ppr, sp, PPR_ORDER)
        for r in para.iter(q("w:r")):
            rpr = r.find(q("w:rPr"))
            if rpr is None:
                rpr = etree.Element(q("w:rPr"))
                r.insert(0, rpr)
            for tag in ("sz", "szCs"):
                for ex in rpr.findall(q("w:" + tag)):
                    rpr.remove(ex)
                e = etree.Element(q("w:" + tag))
                e.set(q("w:val"), "18")
                insert_in_order(rpr, e, RPR_ORDER)
        k += 1
    stats["table_notes"] = k


def fix_equations(body, stats):
    n = 0
    for para in list(body.iter(q("w:p"))):
        omp = para.find(q("m:oMathPara"))
        if omp is None:
            continue
        num = None
        for r in omp.iter(q("m:r")):
            t = "".join(x.text or "" for x in r.iter(q("m:t")))
            mm = re.search(r"@@EQ:([^@]+)@@", t)
            if mm:
                num = mm.group(1)
                r.getparent().remove(r)
                break
        if num is None:
            # a table cell holding only one formula (nomenclature rows of pi and kappa) is display math, which Word
            # centers: justify it left like the other rows
            anc = para.getparent()
            while anc is not None and anc.tag != q("w:tc"):
                anc = anc.getparent()
            if anc is not None and omp.find(q("m:oMathParaPr")) is None:
                pp = etree.Element(q("m:oMathParaPr"))
                jc = etree.SubElement(pp, q("m:jc"))
                jc.set(q("m:val"), "left")
                omp.insert(0, pp)
                stats["cell_math_left"] = stats.get("cell_math_left", 0) + 1
            continue
        oMath = omp.find(q("m:oMath"))
        # new paragraph properties
        old = para.find(q("w:pPr"))
        style = None
        if old is not None and old.find(q("w:pStyle")) is not None:
            style = old.find(q("w:pStyle")).get(q("w:val"))
        if old is not None:
            para.remove(old)
        ppr = etree.Element(q("w:pPr"))
        if style:
            sub(ppr, "w:pStyle", val=style)
        tabs = sub(ppr, "w:tabs")
        sub(tabs, "w:tab", val="center", pos=TEXTW // 2)
        sub(tabs, "w:tab", val="right", pos=TEXTW)
        sub(ppr, "w:spacing", before=60, after=60)
        para.insert(0, ppr)
        para.remove(omp)
        r1 = sub(para, "w:r")
        sub(r1, "w:tab")
        para.append(oMath)
        r2 = sub(para, "w:r")
        sub(r2, "w:tab")
        r3 = sub(para, "w:r")
        tt = sub(r3, "w:t")
        tt.text = "(%s)" % num
        n += 1
    stats["equation_paragraphs"] = n


def fix_tables(body, meta, stats):
    tbls = [c for c in body if c.tag == q("w:tbl")]
    stats["tables"] = len(tbls)
    stats["tablemeta"] = len(meta)
    stats["table_borders_ok"] = 0
    stats["table_no_header"] = 0
    for t, md in zip(tbls, meta):
        tblPr = t.find(q("w:tblPr"))
        for ex in tblPr.findall(q("w:tblBorders")):
            tblPr.remove(ex)
        bd = etree.Element(q("w:tblBorders"))
        for side in ("top", "bottom"):
            set_border(bd, side, 12)
        insert_in_order(tblPr, bd, TBLPR_ORDER)
        for ex in tblPr.findall(q("w:tblCellMar")):
            tblPr.remove(ex)
        cm = etree.Element(q("w:tblCellMar"))
        for side, v in (("top", 20), ("left", 60), ("bottom", 20), ("right", 60)):
            sub(cm, "w:" + side, w=v, type="dxa")
        insert_in_order(tblPr, cm, TBLPR_ORDER)
        rows = t.findall(q("w:tr"))
        hdr = [r for r in rows if r.find(q("w:trPr")) is not None and r.find(q("w:trPr")).find(q("w:tblHeader")) is not None]
        if not hdr:
            stats["table_no_header"] += 1
            if md.get("head_rows"):
                hdr = rows[:md["head_rows"]]
                stats["alg_head_rule"] = stats.get("alg_head_rule", 0) + 1
        # header rule under the last header row
        if hdr:
            for tc in hdr[-1].findall(q("w:tc")):
                tcPr = get_child(tc, "w:tcPr", ["tcPr"]) if tc.find(q("w:tcPr")) is None else tc.find(q("w:tcPr"))
                if tc.find(q("w:tcPr")) is None:
                    tc.insert(0, tcPr)
                tb = tcPr.find(q("w:tcBorders"))
                if tb is None:
                    tb = etree.Element(q("w:tcBorders"))
                    insert_in_order(tcPr, tb, TCPR_ORDER)
                set_border(tb, "bottom", 6)
        stats["table_borders_ok"] += 1
        grid = t.find(q("w:tblGrid"))
        wcm = md.get("widths_cm")
        if grid is not None and wcm:
            gcs = grid.findall(q("w:gridCol"))
            if len(gcs) == len(wcm) and len({g.get(q("w:w")) for g in gcs}) == 1 and len(gcs) > 1:
                # pandoc ignored the p{} widths of the inventory longtable (equal columns): apply them, in twips
                tw = [int(round(c * 567)) for c in wcm]
                for g, v in zip(gcs, tw):
                    g.set(q("w:w"), str(v))
                # fixed layout: Word's autofit otherwise widens the unbreakable key column and squeezes the others
                for ex in tblPr.findall(q("w:tblW")) + tblPr.findall(q("w:tblLayout")):
                    tblPr.remove(ex)
                tws = etree.Element(q("w:tblW"))
                tws.set(q("w:w"), str(sum(tw)))
                tws.set(q("w:type"), "dxa")
                insert_in_order(tblPr, tws, TBLPR_ORDER)
                lay = etree.Element(q("w:tblLayout"))
                lay.set(q("w:type"), "fixed")
                insert_in_order(tblPr, lay, TBLPR_ORDER)
                for row in rows:
                    ci = 0
                    for tc in row.findall(q("w:tc")):
                        tcPr = tc.find(q("w:tcPr"))
                        span = 1
                        if tcPr is not None and tcPr.find(q("w:gridSpan")) is not None:
                            span = int(tcPr.find(q("w:gridSpan")).get(q("w:val")))
                        if tcPr is None:
                            tcPr = etree.Element(q("w:tcPr"))
                            tc.insert(0, tcPr)
                        for ex in tcPr.findall(q("w:tcW")):
                            tcPr.remove(ex)
                        e = etree.Element(q("w:tcW"))
                        e.set(q("w:w"), str(sum(tw[ci:ci + span])))
                        e.set(q("w:type"), "dxa")
                        tcPr.insert(0, e)
                        ci += span
                stats["table_widths_set"] = stats.get("table_widths_set", 0) + 1
        if md["kind"] == "alg":
            # algorithm boxes: full text width (B.2 shrank to its content)
            for ex in tblPr.findall(q("w:tblW")):
                tblPr.remove(ex)
            tw = etree.Element(q("w:tblW"))
            tw.set(q("w:w"), "5000")
            tw.set(q("w:type"), "pct")
            insert_in_order(tblPr, tw, TBLPR_ORDER)
        if md["kind"] == "alg" or len(rows) <= 16:
            # algorithm boxes and short tables stay on one page (B.2 split after line 7; Table S5 left its header alone)
            for row in rows[:-1]:
                for p in row.iter(q("w:p")):
                    ppr = p.find(q("w:pPr"))
                    if ppr is None:
                        ppr = etree.Element(q("w:pPr"))
                        p.insert(0, ppr)
                    if ppr.find(q("w:keepNext")) is None:
                        insert_in_order(ppr, etree.Element(q("w:keepNext")), PPR_ORDER)
            stats["alg_kept_together"] = stats.get("alg_kept_together", 0) + 1
        size = 16 if md.get("wide") else 18
        align = md["align"]
        for ri, row in enumerate(rows):
            ishdr = row in hdr
            col = 0
            for tc in row.findall(q("w:tc")):
                span = 1
                tcPr = tc.find(q("w:tcPr"))
                if tcPr is not None and tcPr.find(q("w:gridSpan")) is not None:
                    span = int(tcPr.find(q("w:gridSpan")).get(q("w:val")))
                a = align[col] if col < len(align) else "l"
                if span > 1 and ishdr:
                    a = "c"
                for p in tc.findall(q("w:p")):
                    ppr = get_child(p, "w:pPr", ["pPr"]) if p.find(q("w:pPr")) is None else p.find(q("w:pPr"))
                    if p.find(q("w:pPr")) is None:
                        p.insert(0, ppr)
                    for ex in ppr.findall(q("w:jc")):
                        ppr.remove(ex)
                    if a in ("r", "c"):
                        jc = etree.Element(q("w:jc"))
                        jc.set(q("w:val"), "right" if a == "r" else "center")
                        insert_in_order(ppr, jc, PPR_ORDER)
                    for r in p.iter(q("w:r")):
                        rpr = r.find(q("w:rPr"))
                        if rpr is None:
                            rpr = etree.Element(q("w:rPr"))
                            r.insert(0, rpr)
                        for tag in ("sz", "szCs"):
                            for ex in rpr.findall(q("w:" + tag)):
                                rpr.remove(ex)
                            e = etree.Element(q("w:" + tag))
                            e.set(q("w:val"), str(size))
                            insert_in_order(rpr, e, RPR_ORDER)
                        if ishdr and md["kind"] != "alg" and rpr.find(q("w:b")) is None:
                            b = etree.Element(q("w:b"))
                            insert_in_order(rpr, b, RPR_ORDER)
                col += span


def fix_text(root, stats):
    n_dash = 0
    for t in root.iter(q("w:t"), q("m:t")):
        s = t.text or ""
        if "​" in s:
            # pandoc's OMML uses a ZWSP as the empty superscript of an n-ary operator; an empty m:t is equivalent
            stats["zwsp_removed"] = stats.get("zwsp_removed", 0) + s.count("​")
            s = s.replace("​", "")
        if "–" in s or "—" in s:
            n_dash += s.count("–") + s.count("—")
            s = s.replace("–", "-").replace("—", "-")
        if t.tag == q("w:t"):
            s = re.sub(r"(?<=\w)'(?=\w)", "’", s)
            s = re.sub(r"(?<=\w)'(?=\s|$|[.,;:)])", "’", s)
            s = re.sub(r"(?<=\s)'(?=\w)", "‘", s)
        t.text = s
    stats["dashes_replaced"] = n_dash


def post(raw, out, meta, title):
    stats = {}
    shutil.copyfile(raw, out)
    zin = zipfile.ZipFile(raw)
    zout = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/document.xml":
            root = etree.fromstring(data)
            body = root.find(q("w:body"))
            fix_equations(body, stats)
            left_cell_math(body, stats)
            fix_table_notes(body, stats)
            fix_tables(body, meta, stats)
            fix_text(root, stats)
            data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        elif item.filename in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"):
            root = etree.fromstring(data)
            fix_text(root, {})
            data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        elif item.filename == "docProps/core.xml":
            s = data.decode("utf-8")
            s = re.sub(r"<dc:title>.*?</dc:title>", "<dc:title>%s</dc:title>" % re.sub(r"[<>&]", "", title), s, flags=re.S)
            data = s.encode("utf-8")
        zout.writestr(item, data)
    zout.close()
    return stats
