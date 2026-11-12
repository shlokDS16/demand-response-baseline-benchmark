"""tex2docx.py: build paper/main.docx and paper/supplement.docx from the filled LaTeX of Paper B.

Pipeline (SPEC owner rules: native Word equations, black headings, ruled editable tables, 300 dpi PNG figures,
numbered citations, no en/em dashes):
  1. read the filled sources (main.tex + sections/placed/*.tex, or supplement.tex + sections/S_supplement.tex),
     strip comments, expand \\input of table files;
  2. resolve \\ref / \\eqref through the LaTeX aux files (so numbers equal the PDF), cite -> pandoc \\cite;
  3. number sections, subsections and equations; mark each equation with a number marker that the post step
     turns into a tab-aligned "(n)" next to a native OMML equation;
  4. convert algorithm2e blocks into numbered-line tables, tabular/longtable column specs into pandoc-readable
     specs, figures to PNG;
  5. run pandoc (latex-smart, citeproc with a local numeric CSL, reference.docx);
  6. post-process document.xml (equation numbers, table rules, alignment, font size, dash check).

No section prose is edited; only markup is transformed.
Usage: python src/paper/tex2docx.py [main|supplement|all]
"""
import json
import os
import re
import subprocess
import sys
import zipfile
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPER = os.path.join(ROOT, "paper")
ASSETS = os.path.join(ROOT, "src", "paper", "docx_assets")
BUILD = os.path.join(ROOT, "logs", "build_docx")
TEXTW = 9026  # twips, A4 with 1 inch margins


def rd(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def wr(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


# ---------------------------------------------------------------- helpers
def strip_comments(t):
    out = []
    for line in t.split("\n"):
        line = re.sub(r"(?<!\\)%.*$", "", line)
        out.append(line)
    return "\n".join(out)


def group(s, i):
    """s[i] == '{'. Return (content, index after closing brace)."""
    assert s[i] == "{", s[i:i + 40]
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced: " + s[i:i + 60])


def skip_ws(s, i):
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def read_labels():
    lab = {}
    for name in ("main.aux", "supplement.aux"):
        p = os.path.join(PAPER, name)
        if not os.path.exists(p):
            continue
        for m in re.finditer(r"\\newlabel\{([^}@]+)\}\{\{([^}]*)\}", rd(p)):
            lab.setdefault(m.group(1), m.group(2))
    return lab


# ---------------------------------------------------------------- algorithm2e
def parse_alg_block(s, lvl, out, funcs, counter):
    i = 0
    n = len(s)
    ind = "~~~~" * lvl

    def emit(text, lvl_=lvl):
        counter[0] += 1
        out.append((counter[0], "~~~~" * lvl_ + re.sub(r"\s+", " ", text).strip()))

    while i < n:
        i = skip_ws(s, i)
        if i >= n:
            break
        if s.startswith("\\;", i):
            i += 2
            continue
        m = re.match(r"\\(Fn|ForEach|lForEach|lIf|If|Return)(?![a-zA-Z])", s[i:])
        if m:
            cmd = m.group(1)
            i += m.end()
            if cmd == "Fn":
                i = skip_ws(s, i)
                a1, i = group(s, i)
                i = skip_ws(s, i)
                body, i = group(s, i)
                mm = re.match(r"\s*\\([A-Za-z]+)\{(.*)\}\s*$", a1, re.S)
                name = funcs.get(mm.group(1), mm.group(1))
                emit("\\textbf{Function} %s(%s):" % (name, mm.group(2)))
                parse_alg_block(body, lvl + 1, out, funcs, counter)
            elif cmd == "ForEach":
                i = skip_ws(s, i)
                cond, i = group(s, i)
                i = skip_ws(s, i)
                body, i = group(s, i)
                emit("\\textbf{for each} %s \\textbf{do}" % cond)
                parse_alg_block(body, lvl + 1, out, funcs, counter)
            elif cmd == "If":
                i = skip_ws(s, i)
                cond, i = group(s, i)
                i = skip_ws(s, i)
                body, i = group(s, i)
                emit("\\textbf{if} %s \\textbf{then}" % cond)
                parse_alg_block(body, lvl + 1, out, funcs, counter)
            elif cmd == "lForEach":
                i = skip_ws(s, i)
                cond, i = group(s, i)
                i = skip_ws(s, i)
                body, i = group(s, i)
                emit("\\textbf{for each} %s \\textbf{do} %s" % (cond, body.strip()))
            elif cmd == "lIf":
                i = skip_ws(s, i)
                cond, i = group(s, i)
                i = skip_ws(s, i)
                body, i = group(s, i)
                # \Return{x} inside a one-line if printed nothing in Word ("if ... then" with no action)
                body = re.sub(r"\\Return\s*\{(.*)\}\s*$", r"\\textbf{return} \1", body.strip(), flags=re.S)
                emit("\\textbf{if} %s \\textbf{then} %s" % (cond, body.strip()))
            elif cmd == "Return":
                i = skip_ws(s, i)
                if i < n and s[i] == "{":
                    body, i = group(s, i)
                else:
                    body = ""
                emit("\\textbf{return} %s" % body)
            continue
        # plain statement until \; at depth 0
        depth = 0
        j = i
        while j < n:
            c = s[j]
            if c == "\\":
                if depth == 0 and s.startswith("\\;", j):
                    break
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        text = s[i:j].strip()
        if text:
            emit(text)
        i = j + 2


def convert_algorithm(body, labels, meta):
    cap_m = re.search(r"\\caption\{", body)
    cap, e = group(body, cap_m.end() - 1)
    lab = re.search(r"\\label\{([^}]+)\}", body).group(1)
    num = labels[lab]
    funcs = {}
    for m in re.finditer(r"\\SetKwFunction\{\\?([A-Za-z]+)\}\{([^}]*)\}", body):
        funcs[m.group(1)] = m.group(2)
    rest = body[e:]
    rest = re.sub(r"\\label\{[^}]*\}", "", rest)
    rest = re.sub(r"\\SetKwFunction\{[^}]*\}\{[^}]*\}", "", rest)
    rest = re.sub(r"\\SetKwProg\{[^}]*\}\{[^}]*\}\{[^}]*\}\{[^}]*\}", "", rest)
    heads = []
    for kw, lab_ in (("KwIn", "Input"), ("KwData", "Data"), ("KwOut", "Output")):
        m = re.search(r"\\" + kw + r"\{", rest)
        if m:
            txt, e2 = group(rest, m.end() - 1)
            heads.append((lab_, re.sub(r"\s+", " ", txt).strip()))
            rest = rest[:m.start()] + rest[e2:]
    out = []
    parse_alg_block(rest, 0, out, funcs, [0])
    meta.append({"kind": "alg", "align": ["l", "l"], "wide": False, "head_rows": len(heads)})
    rows = []
    for lab_, txt in heads:
        rows.append(" & \\textbf{%s:} %s \\\\" % (lab_, txt))
    lines = ["\\begin{table}", "\\caption{\\textbf{Algorithm %s.} %s}" % (num, cap),
             "\\begin{tabular}{p{0.8cm}p{14.8cm}}", "\\toprule"]
    lines += rows
    lines.append("\\midrule")
    for k, txt in out:
        lines.append("%d & %s \\\\" % (k, txt))
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- tables
def parse_colspec(spec):
    cols = []
    i = 0
    pend = None
    while i < len(spec):
        c = spec[i]
        if c == "@" or c == "!":
            _, i = group(spec, i + 1)
            continue
        if c == ">":
            g, i = group(spec, i + 1)
            if "raggedleft" in g:
                pend = "r"
            elif "centering" in g:
                pend = "c"
            else:
                pend = "l"
            continue
        if c in "lrc":
            cols.append((c, None))
            pend = None
            i += 1
            continue
        if c == "p":
            w, i = group(spec, i + 1)
            cols.append((pend or "l", w))
            pend = None
            continue
        i += 1
    return cols


def clean_spec(cols):
    out = ""
    wide = len(cols) >= 8
    for a, w in cols:
        # widths given as a fraction of the text width (Table S11) collapsed in Word: convert to cm (A4, 1 in margins)
        fm = re.match(r"\s*([0-9.]+)\s*\\(textwidth|linewidth)\s*$", w or "")
        if fm:
            w = "%.2fcm" % (15.9 * float(fm.group(1)))
        if w and wide and a == "r":
            mm = re.match(r"([0-9.]+)cm$", w)
            if mm and float(mm.group(1)) >= 2.0:
                w = "3.2cm"
        out += "p{%s}" % w if w else a
    return out


def convert_tabular(env, body, meta):
    i = skip_ws(body, 0)
    spec, i = group(body, i)
    cols = parse_colspec(spec)
    content = body[i:]
    content = re.sub(r"\\(raggedright|raggedleft|centering|arraybackslash)\b", "", content)
    # longtable's no-page-break row end "\\*" left a literal "*" at the start of the next row in Word
    content = re.sub(r"\\\\\*", r"\\\\", content)
    content = re.sub(r"\\(midrule|toprule|bottomrule)\s*(\\end(?:firsthead|head|foot|lastfoot))", r"\\\1\n\2", content)

    if env == "longtable" and "\\endfirsthead" in content and "\\endhead" in content:
        a_ = content.index("\\endfirsthead") + len("\\endfirsthead")
        b_ = content.index("\\endhead") + len("\\endhead")
        if b_ > a_:
            content = content[:a_] + content[b_:]
    if env == "longtable":
        # the page-break footer ("continued on the next page") printed as a body row in Word: drop \endfoot blocks
        # and keep only the closing rule of \endlastfoot
        content = re.sub(r"(\\endhead|\\endfirsthead)(.*?)\\endfoot", r"\1", content, count=1, flags=re.S)
        content = re.sub(r"\\bottomrule\s*\\endlastfoot", "", content)
        if "\\bottomrule" not in content:
            content = content.rstrip() + "\n\\bottomrule\n"

    def mc(m):
        spec_ = re.sub(r"[|@]", "", m.group(2))
        return "\\multicolumn{%s}{%s}" % (m.group(1), spec_ if spec_ in ("l", "c", "r") else "l")
    content = re.sub(r"\\multicolumn\{(\d+)\}\{((?:[^{}]|\{[^{}]*\})*)\}", mc, content)
    spec_out = clean_spec(cols)
    wcm = [float(x) for x in re.findall(r"p\{([0-9.]+)cm\}", spec_out)]
    meta.append({"kind": env, "align": [a for a, _ in cols], "wide": len(cols) >= 7,
                 "widths_cm": wcm if len(wcm) == len(cols) else None})
    return "\\begin{%s}{%s}%s\\end{%s}" % (env, spec_out, content, env)


def process_floats(t, labels, meta):
    """Single pass in document order over algorithm, table, figure and bare longtable."""
    pat = re.compile(r"\\begin\{(algorithm|table|figure|longtable)\}")
    out = []
    pos = 0
    while True:
        m = pat.search(t, pos)
        if not m:
            out.append(t[pos:])
            break
        env = m.group(1)
        out.append(t[pos:m.start()])
        e = t.index("\\end{%s}" % env, m.end())
        body = t[m.end():e]
        pos = e + len("\\end{%s}" % env)
        if env == "algorithm":
            body = re.sub(r"^\[[a-z!]*\]", "", body.strip())
            out.append("\n\n" + convert_algorithm(body, labels, meta) + "\n\n")
        elif env == "table":
            body = re.sub(r"^\[[a-z!]*\]", "", body.strip())
            cm = re.search(r"\\caption\{", body)
            cap, ce = group(body, cm.end() - 1)
            lab = re.search(r"\\label\{([^}]+)\}", body).group(1)
            num = labels[lab]
            tm = re.search(r"\\begin\{tabular\}", body)
            te = body.index("\\end{tabular}")
            inner = body[tm.end():te]
            tab = convert_tabular("tabular", inner, meta)
            out.append("\n\n\\begin{table}\n\\caption{\\textbf{Table %s.} %s}\n%s\n\\end{table}\n\n" % (num, cap, tab))
            # table notes (\par\smallskip{\footnotesize ...} after the tabular) were dropped; keep them as a paragraph below the table
            note = body[te + len("\\end{tabular}"):].strip()
            if note:
                # @@NOTE@@ marks the paragraph for docx_post (9 pt, no indent), like the footnote-size note in the PDF
                note = re.sub(r"^\\par\\smallskip\{\\footnotesize(\\raggedright)?\s*", "\n\n" + r"\\par\\smallskip{@@NOTE@@", note)
                note = re.sub(r"\\par\\smallskip\{\\footnotesize(\\raggedright)?\s*", "\n\n" + r"\\par\\smallskip{@@NOTE@@", note)
                out.append("\n\n" + note + "\n\n")
        elif env == "longtable":
            # caption lives inside the longtable
            cm = re.search(r"\\caption\{", body)
            lab = re.search(r"\\label\{([^}]+)\}", body)
            if cm:
                cap, ce = group(body, cm.end() - 1)
                num = labels[lab.group(1)]
                body = body[:cm.start()] + "\\caption{\\textbf{Table %s.} %s}" % (num, cap) + body[ce:]
                body = re.sub(r"\\label\{[^}]*\}", "", body)
            else:
                pass
            # strip the colspec like tabular does
            inner = convert_tabular("longtable", body, meta)
            out.append("\n\n" + inner + "\n\n")
        else:  # figure
            body = re.sub(r"^\[[a-z!]*\]", "", body.strip())
            cm = re.search(r"\\caption\{", body)
            cap, ce = group(body, cm.end() - 1)
            lab = re.search(r"\\label\{([^}]+)\}", body).group(1)
            num = labels[lab]
            gm = re.search(r"\\includegraphics\[width=([^\]]*)\]\{([^}]*)\}", body)
            w, path = gm.group(1), gm.group(2)
            path = re.sub(r"\.pdf$", ".png", path)
            wmap = {"\\FigD": 6.2, "\\FigM": 5.3, "\\FigS": 3.7, "\\FigOne": 6.2, "\\linewidth": 6.2}
            wi = wmap.get(w)
            if wi is None:
                f = re.match(r"([0-9.]+)\\(linewidth|textwidth)", w)
                wi = 6.2 * float(f.group(1))
            out.append("\n\n\\begin{figure}\n\\includegraphics[width=%.2fin]{%s}\n\\caption{\\textbf{Figure %s.} %s}\n\\end{figure}\n\n"
                       % (wi, path, num, cap))
    return "".join(out)


# ---------------------------------------------------------------- sectioning and equations
def roman_letter(k):
    return chr(ord("A") + k - 1)


def process_sections(t, labels, supp, warn):
    cmd = re.compile(r"\\(appendix|setcounter\{equation\}\{0\}|setcounter\{section\}\{0\}|section\*?|subsection\*?|subsubsection\*?|paragraph\*?|begin\{equation\})")
    out = []
    pos = 0
    sec = sub = ssub = 0
    eq = 0
    appendix = False
    eqprefix = ""
    while True:
        m = cmd.search(t, pos)
        if not m:
            out.append(t[pos:])
            break
        out.append(t[pos:m.start()])
        c = m.group(1)
        i = m.end()
        if c == "appendix":
            appendix = True
            sec = 0
            pos = i
            continue
        if c.startswith("setcounter"):
            if "equation" in c:
                eq = 0
                eqprefix = "B."
            pos = i
            continue
        if c.startswith("begin{equation}"):
            e = t.index("\\end{equation}", i)
            body = t[i:e]
            pos = e + len("\\end{equation}")
            lm = re.search(r"\\label\{([^}]+)\}", body)
            body = re.sub(r"\\label\{[^}]*\}", "", body).strip()
            eq += 1
            num = eqprefix + str(eq)
            if lm and lm.group(1) in labels and labels[lm.group(1)] != num:
                warn.append("equation %s computed %s aux %s" % (lm.group(1), num, labels[lm.group(1)]))
            out.append("\n\n$$%s\\text{@@EQ:%s@@}$$\n\n" % (body, num))
            continue
        star = c.endswith("*")
        base = c.rstrip("*")
        i = skip_ws(t, i)
        if i < len(t) and t[i] == "[":
            i = t.index("]", i) + 1
        title, i = group(t, i)
        lm = re.match(r"\s*\\label\{([^}]+)\}", t[i:])
        lab = None
        if lm:
            lab = lm.group(1)
            i += lm.end()
        pos = i
        if base == "paragraph":
            out.append("\n\n\\textbf{%s.} " % title)
            continue
        if star and base != "paragraph":
            out.append("\n\n\\%s*{%s}\n\n" % (base, title))
            continue
        if base == "section":
            sec += 1
            sub = ssub = 0
            if supp:
                num = "S%d" % sec
            elif appendix:
                num = roman_letter(sec)
            else:
                num = str(sec)
            head = ("Appendix %s. %s" % (num, title)) if (appendix and not supp) else ("%s %s" % (num, title))
            out.append("\n\n\\section*{%s}\n\n" % head)
        elif base == "subsection":
            sub += 1
            ssub = 0
            if supp:
                num = "S%d.%d" % (sec, sub)
            elif appendix:
                num = "%s.%d" % (roman_letter(sec), sub)
            else:
                num = "%d.%d" % (sec, sub)
            out.append("\n\n\\subsection*{%s %s}\n\n" % (num, title))
        else:
            ssub += 1
            if supp:
                num = "S%d.%d.%d" % (sec, sub, ssub)
            elif appendix:
                num = "%s.%d.%d" % (roman_letter(sec), sub, ssub)
            else:
                num = "%d.%d.%d" % (sec, sub, ssub)
            out.append("\n\n\\subsubsection*{%s %s}\n\n" % (num, title))
        if lab and lab in labels:
            exp = labels[lab]
            if appendix and not supp:
                exp = exp  # aux holds the letter form where defined
            if exp.replace("Appendix~", "").replace("Appendix ", "") != num and exp != num:
                warn.append("section %s computed %s aux %s" % (lab, num, exp))
    return "".join(out)


# ---------------------------------------------------------------- front matter
def frontmatter(t):
    title = re.search(r"\\title\{", t)
    ttl, _ = group(t, title.end() - 1)
    au = re.search(r"\\author\[[^\]]*\]\{", t)
    aut, _ = group(t, au.end() - 1)
    aut = re.sub(r"\\corref\{[^}]*\}", "", aut)
    ad = re.search(r"\\address\[[^\]]*\]\{", t)
    addr, _ = group(t, ad.end() - 1)
    ct = re.search(r"\\cortext\[[^\]]*\]\{", t)
    cort, _ = group(t, ct.end() - 1)
    ab = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S).group(1).strip()
    hl = re.search(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", t, re.S).group(1).strip()
    kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", t, re.S).group(1).strip()
    kw = re.sub(r"\s*\\sep\s*", "; ", kw)
    body = ("\n\n%s\n\n%s\n\n%s\n\n\\section*{Abstract}\n\n%s\n\n\\textbf{Keywords:} %s\n\n"
            "\\section*{Highlights}\n\n\\begin{itemize}\n%s\n\\end{itemize}\n\n") % (aut, addr, cort, ab, kw, hl.replace("\\item", "\\item"))
    return ttl, body


# ---------------------------------------------------------------- main assembly
def assemble(kind, labels):
    warn = []
    if kind == "main":
        main = strip_comments(rd(os.path.join(PAPER, "main.tex")))
        parts = re.findall(r"\\input\{(sections/placed/[^}]+)\}", main)
        text = ""
        for p in parts:
            text += strip_comments(rd(os.path.join(PAPER, p + ".tex"))) + "\n\n"
        # front matter
        fm = re.search(r"\\begin\{frontmatter\}(.*?)\\end\{frontmatter\}", text, re.S)
        ttl, fbody = frontmatter(fm.group(1))
        text = text.replace(fm.group(0), fbody)
        supp = False
    else:
        text = strip_comments(rd(os.path.join(PAPER, "sections", "S_supplement.tex")))
        sup = strip_comments(rd(os.path.join(PAPER, "supplement.tex")))
        tm = re.search(r"\\title\{", sup)
        ttl, _ = group(sup, tm.end() - 1)
        ttl = ttl.replace("Supplementary material to: ", "Supplementary material to: ")
        text = "\n\nShlok Kumar Goenka, N. Balaji and G. N. Balaji\n\n" + text
        supp = True
    # strip counters / numbering redefinitions
    text = re.sub(r"\\setcounter\{(table|figure|algocf)\}\{0\}", "", text)
    text = re.sub(r"^\\renewcommand\{\\the(section|table|figure|algocf|equation)\}.*$", "", text, flags=re.M)
    # expand \input of tables
    def inp(m):
        f = m.group(1)
        if not f.endswith(".tex"):
            f += ".tex"
        return strip_comments(rd(os.path.join(ROOT, f)))
    text = re.sub(r"\\input\{(tables/[^}]+)\}", inp, text)
    # refs
    def ref(m):
        k = m.group(2)
        if k not in labels:
            warn.append("missing label " + k)
            return "??"
        return ("(%s)" % labels[k]) if m.group(1) == "eqref" else labels[k]
    text = re.sub(r"\\(eqref|ref)\{([^}]+)\}", ref, text)
    text = re.sub(r"\\citep\b", r"\\cite", text)
    if supp:
        # the supplement prints the reference numbers of the main text (xr-hyper in the PDF)
        bibn = {}
        for m in re.finditer(r"\\bibcite\{([^}]+)\}\{\{(\d+)\}", rd(os.path.join(PAPER, "main.aux"))):
            bibn[m.group(1)] = int(m.group(2))

        def lit(m):
            keys = [k.strip() for k in m.group(1).split(",")]
            return "[" + ", ".join(str(x) for x in sorted(bibn[k] for k in keys)) + "]"
        text = re.sub(r"\\cite\{([^}]+)\}", lit, text)
    # figure / table / algorithm blocks, then sections and equations
    meta = []
    text = process_floats(text, labels, meta)
    text = process_sections(text, labels, supp, warn)
    # notes under longtables (outside a table float) get the same 9 pt note marker as the floating tables
    text = re.sub(r"\\par\\smallskip\{\\footnotesize(\\raggedright)?\s*", "\n\n" + r"\\par\\smallskip{@@NOTE@@", text)
    # \allowbreak swallowed the next group in pandoc ("H1.\allowbreak {*}" printed "H1."): drop it and unbrace {*}
    text = re.sub(r"\\allowbreak\s*", "", text).replace("{*}", "*")
    # cleanup layout macros
    text = re.sub(r"\\(footnotesize|scriptsize|small|smallskip|clearpage|centering|raggedright|raggedleft|arraybackslash|par)(?![a-zA-Z])", "", text)
    text = re.sub(r"\\setlength\{[^}]*\}\{[^}]*\}", "", text)
    text = re.sub(r"\\needspace\{[^}]*\}", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    # enumerate with custom item labels -> plain paragraphs
    def enum(m):
        b = m.group(1)
        b = re.sub(r"\\item\[([^\]]*)\]\s*", lambda x: "\n\n%s~" % x.group(1), b)
        return b
    text = re.sub(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", enum, text, flags=re.S)
    text = text.replace("``", "“").replace("''", "”")
    if not supp:
        text = text + "\n\n\\section*{References}\n\n"
    return ttl, text, meta, warn


def build(kind):
    os.makedirs(BUILD, exist_ok=True)
    labels = read_labels()
    ttl, text, meta, warn = assemble(kind, labels)
    texp = os.path.join(BUILD, kind + "_pre.tex")
    wr(texp, text)
    wr(os.path.join(BUILD, kind + "_tablemeta.json"), json.dumps(meta))
    # bib copy without double hyphens
    bib = rd(os.path.join(PAPER, "references.bib"))
    bib = bib.replace("---", "-").replace("--", "-")
    # corporate names with "and" must not be read as name lists
    bib = re.sub(r"^(\s*(?:institution|organization|publisher)\s*=\s*\{)(.*)(\},?\s*)$",
                 lambda m: m.group(1) + m.group(2).replace(" and ", " {and} ") + m.group(3), bib, flags=re.M)
    bibp = os.path.join(BUILD, "references_docx.bib")
    wr(bibp, bib)
    yaml = os.path.join(BUILD, kind + "_meta.yaml")
    wr(yaml, "---\ntitle: '%s'\nlang: en-GB\nreference-section-title: ''\n---\n" % re.sub(r"\s+", " ", ttl).replace("'", "''"))
    raw = os.path.join(BUILD, kind + "_raw.docx")
    cite = (["--citeproc", "--bibliography", bibp, "--csl", os.path.join(ASSETS, "numeric-nodash.csl")]
            if kind == "main" else [])
    cmd = ["pandoc", "-f", "latex-smart", "-t", "docx", texp, "--metadata-file", yaml] + cite + [
           "--reference-doc", os.path.join(ASSETS, "reference.docx"),
           "--resource-path", ROOT, "-o", raw]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    wr(os.path.join(BUILD, kind + "_pandoc.log"), r.stderr)
    print(kind, "pandoc rc", r.returncode, "stderr lines", len(r.stderr.splitlines()))
    for w in warn:
        print("WARN", w)
    sys.path.insert(0, os.path.dirname(__file__))
    import docx_post
    final = os.path.join(PAPER, "main.docx" if kind == "main" else "supplement.docx")
    stats = docx_post.post(raw, final, meta, re.sub(r"\s+", " ", ttl))
    print(kind, stats)
    return raw, meta


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    kinds = ["main", "supplement"] if which == "all" else [which]
    for k in kinds:
        build(k)
