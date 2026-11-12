"""build_paper.py: fill the templates, place the floats, build the PDFs (paper B).

Steps
 1. python -I src/paper/fill_ledger.py --strict on paper/sections/*.tmpl.tex, floats.tmpl.tex, main.tmpl.tex, supplement.tmpl.tex
 2. split paper/floats.tex at the "%%FLOAT <label>" markers
 3. copy each filled section to paper/sections/placed/<name>.tex and insert each float after the paragraph that holds its
    first \\ref (placement table PLACE below; the section files themselves are never edited for layout)
 4. check that the highlights in 00_frontmatter match paper/highlights.tmpl.txt; write paper/highlights.txt (filled)
 5. unless --no-tex: pdflatex, bibtex, pdflatex x2 for main and supplement (run from paper/)
Usage: python -I src/paper/build_paper.py [--no-tex] [--no-fill]
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "paper")
SEC = os.path.join(PAPER, "sections")

BODY = ["00_frontmatter", "01_intro", "02_background", "03_data", "04_methods", "05_results", "06_discussion",
        "07_conclusion", "08_declarations", "09_appendix"]

# host section -> ordered list of floats; each float follows the paragraph with its first \ref in that host
PLACE = {
    "01_intro": ["fig:design"],
    "02_background": ["tab:methods"],
    # REVISION_1: tab:data, fig:h1bias, fig:robustness and tab:secondary moved to the supplement (S_supplement.tmpl.tex)
    "05_results": ["fig:sample", "tab:accuracy", "fig:accuracy", "fig:h2h3", "fig:precool",
                   "fig:pstar", "fig:dispatch", "tab:h5windows", "fig:payment", "tab:confirmatory"],
}


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)


def fill():
    files = sorted(glob.glob(os.path.join(SEC, "*.tmpl.tex")))
    files += [os.path.join(PAPER, n) for n in ("floats.tmpl.tex", "main.tmpl.tex", "supplement.tmpl.tex")]
    cmd = [sys.executable, "-I", os.path.join(ROOT, "src", "paper", "fill_ledger.py"), "--strict"] + files
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit("fill_ledger failed")


def split_floats():
    t = read(os.path.join(PAPER, "floats.tex"))
    parts = re.split(r"^%%FLOAT (\S+)\s*$", t, flags=re.M)
    return {parts[i]: parts[i + 1].strip("\n") + "\n" for i in range(1, len(parts), 2)}


def place(text, labels, floats):
    lines = text.split("\n")
    depth = 0
    depth_at = []
    for ln in lines:
        depth_at.append(depth)
        depth += len(re.findall(r"\\begin\{", re.sub(r"(?<!\\)%.*", "", ln)))
        depth -= len(re.findall(r"\\end\{", re.sub(r"(?<!\\)%.*", "", ln)))
    inserts = {}
    for lab in labels:
        pat = re.compile(r"\\ref\{" + re.escape(lab) + r"\}")
        idx = next((i for i, ln in enumerate(lines) if pat.search(ln)), None)
        if idx is None:
            sys.exit("no \\ref{%s} in host section" % lab)
        j = idx
        while True:
            end_depth = depth_at[j + 1] if j + 1 < len(lines) else 0
            nxt_blank = (j + 1 >= len(lines)) or lines[j + 1].strip() == ""
            if end_depth == 0 and nxt_blank:
                break
            j += 1
        inserts.setdefault(j, []).append(lab)
    out = []
    for i, ln in enumerate(lines):
        out.append(ln)
        for lab in inserts.get(i, []):
            out.append("")
            out.append(floats[lab].rstrip("\n"))
    return "\n".join(out)


def make_placed():
    floats = split_floats()
    used = set()
    for name in BODY:
        t = read(os.path.join(SEC, name + ".tex"))
        if name in PLACE:
            t = place(t, PLACE[name], floats)
            used.update(PLACE[name])
        write(os.path.join(SEC, "placed", name + ".tex"), t)
    missing = set(floats) - used
    if missing:
        sys.exit("floats not placed: %s" % sorted(missing))
    print("placed %d floats" % len(used))


def highlights():
    fm = read(os.path.join(SEC, "00_frontmatter.tex"))
    m = re.search(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", fm, flags=re.S)
    items = [s.strip() for s in re.split(r"\\item", m.group(1)) if s.strip()]
    items = [i.replace("\\,", " ").replace("\\%", "%") for i in items]
    txt = read(os.path.join(PAPER, "highlights.tmpl.txt")).strip().split("\n")
    # compare the unfilled text of the template with the unfilled frontmatter: placeholders are identical strings
    tm = read(os.path.join(SEC, "00_frontmatter.tmpl.tex"))
    mm = re.search(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", tm, flags=re.S)
    titems = [s.strip() for s in re.split(r"\\item", mm.group(1)) if s.strip()]
    assert titems == [s.strip() for s in txt], "highlights.tmpl.txt differs from the frontmatter highlights"
    write(os.path.join(PAPER, "highlights.txt"), "\n".join(items) + "\n")
    print("highlights (chars):", [len(i) for i in items])


def tex():
    def run(cmd):
        r = subprocess.run(cmd, cwd=PAPER, capture_output=True, text=True)
        return r
    for doc in ("main", "supplement"):
        pass
    for step in (["pdflatex", "-interaction=nonstopmode", "-file-line-error", "main.tex"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "supplement.tex"],
                 ["bibtex", "main"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "main.tex"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "supplement.tex"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "main.tex"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "supplement.tex"],
                 ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "main.tex"]):
        r = run(step)
        print(" ".join(step[:1] + step[-1:]), "->", r.returncode)


if __name__ == "__main__":
    if "--no-fill" not in sys.argv:
        fill()
    make_placed()
    highlights()
    if "--no-tex" not in sys.argv:
        tex()
