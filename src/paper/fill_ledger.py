#!/usr/bin/env python
"""fill_ledger.py - the only route by which numbers enter the manuscript.

Reads *.tmpl.tex, replaces {{key}} / {{key:field|fmt}} / {{key|fmt}} placeholders
with values from tables/summary.csv, tables/summary_secondary.csv and
tables/summary_derived.csv (derived counts, src/paper/derived_keys.py; optional) and
tables/summary_exploratory.csv (D22 X2/X4/X6; optional, src/paper/exploratory_keys.py) and
tables/summary_dev.csv (2016 development rows for Supplement S1; optional; admitted only via ALLOW_DEV_KEYS),
a key present in more than one of these files is an error. Writes the
filled .tex (same name without ".tmpl") and paper/ledger_used.csv.

Usage:  python -I src/paper/fill_ledger.py [--strict] [--check-only] [files...]
Standard library only (csv module), so it works under python -I.

Rules (see also logs/IMPL_fill.md)
  fields : value (default), ci_low, ci_high, p_raw, p_holm, n_sites, n_buildings, n_events
  fmts   : .Nf  fixed decimals          .Ng  significant digits (never exponent;
                                              integer-valued numbers print exactly)
           pctN value*100, N decimals, then \\,\\%
           int  rounded, thousands separator {,}   e.g. 9{,}550
           sci  m \\times 10^{k}, 2 significant digits
           p    p-value, 3 significant digits, below 0.001 -> <0.001
           raw  string as is, LaTeX-escaped
  default fmt: raw for non-numeric, .3g for numeric.
  Minus rule : negative numbers are emitted as "-" when the placeholder sits in math
               mode ($..$, \\(..\\), \\[..\\], $$..$$, equation/align/gather/multline/
               eqnarray/displaymath/math environments) and as "$-$" in text mode.
               sci in text mode is wrapped in $...$ as a whole; p "<" is "$<$" in text mode.
  Admission  : data_year == 2017 and freeze_hash != 'dev-unfrozen', unless the key is
               listed in paper/ALLOW_DEV_KEYS.txt.
  Literals   : decimals (3.14), thousands groups (9{,}550) and percentages (12 \\%)
               in template prose outside placeholders are reported unless listed in
               paper/ALLOW_LITERALS.txt (compared after removing spaces, ~, \\, and
               braces). Arguments of \\label \\ref \\eqref \\cite* \\includegraphics etc.,
               key=value option brackets, and numbers with a LaTeX unit are skipped.
"""
import argparse
import csv
import glob
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIELDS = ("value", "ci_low", "ci_high", "p_raw", "p_holm",
          "n_sites", "n_buildings", "n_events")
LEDGER_COLS = ["file", "line", "placeholder", "key", "field", "fmt",
               "rendered", "source_file_row"]

PH_RE = re.compile(
    r"\{\{\s*([^{}|:\s][^{}|:]*?)\s*"
    r"(?::\s*([A-Za-z_]\w*)\s*)?"
    r"(?:\|\s*([^{}]*?)\s*)?\}\}")

MATH_ENVS = {"equation", "align", "gather", "multline", "eqnarray", "displaymath",
             "math", "flalign", "alignat"}


class FillError(Exception):
    pass


# ----------------------------------------------------------------- helpers
def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def read_list(path, inline_comments):
    """Lines of an allow-list file; '#' lines are comments; absent file = empty."""
    out = set()
    if not path or not os.path.isfile(path):
        return out
    for ln in read_text(path).splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if inline_comments:
            s = re.split(r"\s+#", s, maxsplit=1)[0].strip()
        out.add(s)
    return out


def norm_literal(s):
    return re.sub(r"[\s~\\{}]", "", s)


def lineno(text, pos):
    return text.count("\n", 0, pos) + 1


# ------------------------------------------------------------ math / comments
def scan_modes(text):
    """Return (math, comment) bytearrays: 1 where position is in math / a % comment."""
    n = len(text)
    math_ = bytearray(n)
    comm = bytearray(n)
    i = 0
    dollar = False       # inside $...$
    ddollar = False      # inside $$...$$
    paren = False        # \( ... \)
    brack = False        # \[ ... \]
    env_depth = 0
    envre = re.compile(r"\\(begin|end)\{([A-Za-z]+)\*?\}")
    while i < n:
        c = text[i]
        in_math = dollar or ddollar or paren or brack or env_depth > 0
        if c == "%":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                comm[k] = 1
            i = j
            continue
        if c == "\\":
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt == "(":
                paren = True
                i += 2
                continue
            if nxt == ")":
                paren = False
                i += 2
                continue
            if nxt == "[":
                brack = True
                i += 2
                continue
            if nxt == "]":
                brack = False
                i += 2
                continue
            m = envre.match(text, i)
            if m:
                if m.group(2) in MATH_ENVS:
                    env_depth += 1 if m.group(1) == "begin" else -1
                    env_depth = max(env_depth, 0)
                for k in range(i, m.end()):
                    math_[k] = 1 if (env_depth > 0 or in_math) else 0
                i = m.end()
                continue
            # any other escape (\\ \$ \% \&): consume two chars
            if in_math:
                math_[i] = 1
                if i + 1 < n:
                    math_[i + 1] = 1
            i += 2
            continue
        if c == "$":
            if text.startswith("$$", i):
                ddollar = not ddollar
                i += 2
                continue
            dollar = not dollar
            i += 1
            continue
        if in_math:
            math_[i] = 1
        i += 1
    return math_, comm


# ----------------------------------------------------------------- sources
class Source:
    def __init__(self):
        self.rows = {}      # key -> dict(row..., _loc=...)
        self.errors = []


def load_sources(paths, rel_to):
    src = Source()
    for path in paths:
        before = dict(src.rows)
        rel = os.path.relpath(path, rel_to).replace("\\", "/")
        if not os.path.isfile(path):
            src.errors.append("%s: source file not found" % rel)
            continue
        with open(path, "r", encoding="utf-8", newline="") as f:
            rd = csv.reader(f)
            try:
                header = next(rd)
            except StopIteration:
                src.errors.append("%s:1: empty source file" % rel)
                continue
            header = [h.strip().lstrip("\ufeff") for h in header]
            if "key" not in header or "value" not in header:
                src.errors.append("%s:1: header lacks key/value columns" % rel)
                continue
            prev_end = rd.line_num
            for r in rd:
                start = prev_end + 1
                prev_end = rd.line_num
                if not r or all(not c.strip() for c in r):
                    continue
                row = {h: (r[i] if i < len(r) else "") for i, h in enumerate(header)}
                key = row["key"].strip()
                if not key:
                    src.errors.append("%s:%d: row with empty key" % (rel, start))
                    continue
                row["_loc"] = "%s:%d" % (rel, start)
                if key in before:
                    src.errors.append(
                        "%s: duplicate key '%s' across source files (first at %s)"
                        % (row["_loc"], key, before[key]["_loc"]))
                    continue
                if key in src.rows:
                    old = src.rows[key]
                    same = all(old.get(h) == row.get(h) for h in header if h != "key")
                    if not same:
                        src.errors.append(
                            "%s: duplicate key '%s' with differing fields (first at %s)"
                            % (row["_loc"], key, old["_loc"]))
                    continue
                src.rows[key] = row
    return src


# ------------------------------------------------------------------ format
def to_float(s):
    try:
        v = float(s.strip())
    except (ValueError, AttributeError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def minus(in_math):
    return "-" if in_math else "$-$"


def sig_str(x, nsig):
    """x to nsig significant digits, never exponent; integer-valued stays exact."""
    if x == int(x) and abs(x) >= 10 ** nsig:
        return str(int(x))
    s = format(x, ".%dg" % nsig)
    if "e" in s or "E" in s:
        from decimal import Decimal
        s = format(Decimal(s), "f")
    return s


def signed(body_abs, neg, in_math):
    """Prefix a minus (LaTeX-aware) unless the rendered magnitude is zero."""
    if neg and re.search(r"[1-9]", body_abs):
        return minus(in_math) + body_abs
    return body_abs


def latex_escape(s):
    out = []
    for ch in s:
        if ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch in "&%$#_{}":
            out.append("\\" + ch)
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        elif ch == "^":
            out.append(r"\textasciicircum{}")
        else:
            out.append(ch)
    return "".join(out)


FMT_RE = re.compile(r"^(?:\.(\d+)([fg])|pct(\d+)|int|sci|p|raw)$")


def render(raw, fmt, in_math):
    """Render the raw CSV string; raises FillError on problems."""
    if fmt is None or fmt == "":
        fmt = ".3g" if to_float(raw) is not None else "raw"
    m = FMT_RE.match(fmt)
    if not m:
        raise FillError("unknown fmt '%s'" % fmt)
    if fmt == "raw":
        return latex_escape(raw), fmt
    x = to_float(raw)
    if x is None:
        raise FillError("non-numeric value '%s' with numeric fmt '%s'" % (raw, fmt))
    neg = x < 0
    ax = abs(x)
    if m.group(2) == "f":
        body = format(ax, ".%df" % int(m.group(1)))
        return signed(body, neg, in_math), fmt
    if m.group(2) == "g":
        nsig = max(int(m.group(1)), 1)
        return signed(sig_str(ax, nsig), neg, in_math), fmt
    if m.group(3) is not None:
        body = format(ax * 100.0, ".%df" % int(m.group(3))) + r"\,\%"
        return signed(body, neg, in_math), fmt
    if fmt == "int":
        body = format(int(round(ax)), ",").replace(",", "{,}")
        return signed(body, neg, in_math), fmt
    if fmt == "sci":
        if x == 0:
            return "0", fmt
        mant, exp = ("%.1e" % ax).split("e")
        body = r"%s\times 10^{%d}" % (mant, int(exp))
        if neg:
            body = "-" + body
        return (body if in_math else "$" + body + "$"), fmt
    if fmt == "p":
        if x < 0 or x > 1:
            raise FillError("p-value %s outside [0,1]" % raw)
        if x < 0.001:
            return ("<0.001" if in_math else "$<$0.001"), fmt
        return sig_str(x, 3), fmt
    raise FillError("unhandled fmt '%s'" % fmt)


# ---------------------------------------------------------- literal scanning
SKIP_ARG_CMDS = (r"label|ref|eqref|pageref|autoref|cref|Cref|nameref|cite\w*|"
                 r"includegraphics|input|include|url|href|vspace|hspace|setlength|"
                 r"addtolength|rule|usepackage|documentclass|bibliographystyle|"
                 r"bibliography|geometry|setcounter|numberwithin|renewcommand|"
                 r"newcommand|providecommand|def|hypersetup|captionsetup")
SKIP_ARG_RE = re.compile(
    r"\\(?:%s)\*?(?:\s*\[[^\]]*\])*\s*\{[^{}]*\}(?:\s*\{[^{}]*\})?" % SKIP_ARG_CMDS)
OPTION_RE = re.compile(r"\[[^\]\n]*=[^\]\n]*\]")
UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:pt|cm|mm|em|ex|in|bp|sp|dd|cc|pc|\\(?:text|line|column|paper)"
    r"(?:width|height)|\\(?:hsize|vsize|baselineskip|parindent))")
LITERAL_RE = re.compile(
    r"(?<![\w.\\])(?:\d+\.\d+|\d{1,3}(?:\{,\}\d{3})+)(?:\s*(?:\\,|~)?\s*\\%)?(?![\w])"
    r"|(?<![\w.\\])\d+(?:\s*(?:\\,|~)?\s*\\%)")


def find_literals(text, comm, ph_spans, allow):
    """Yield (pos, literal) for result-like numbers in prose."""
    n = len(text)
    mask = bytearray(n)

    def cover(a, b):
        for k in range(a, b):
            mask[k] = 1

    for k in range(n):
        if comm[k]:
            mask[k] = 1
    for a, b in ph_spans:
        cover(a, b)
    for rx in (SKIP_ARG_RE, OPTION_RE, UNIT_RE):
        for m in rx.finditer(text):
            cover(m.start(), m.end())
    out = []
    for m in LITERAL_RE.finditer(text):
        if mask[m.start()]:
            continue
        lit = m.group(0)
        if norm_literal(lit) in allow:
            continue
        out.append((m.start(), lit))
    return out


# ------------------------------------------------------------------- engine
def fill_text(text, relname, src, allow_dev, allow_lit, errors, warnings, ledger):
    math_, comm = scan_modes(text)
    spans = []
    pieces = []
    last = 0
    for m in PH_RE.finditer(text):
        a, b = m.span()
        if comm[a]:
            continue
        spans.append((a, b))
        key, field, fmt = m.group(1).strip(), m.group(2), m.group(3)
        field = field or "value"
        ln = lineno(text, a)
        where = "%s:%d: %s" % (relname, ln, m.group(0))
        pieces.append(text[last:a])
        last = b
        try:
            if field not in FIELDS:
                raise FillError("unknown field '%s'" % field)
            row = src.rows.get(key)
            if row is None:
                raise FillError("key '%s' not found in ledger" % key)
            admitted = (row.get("data_year", "").strip() == "2017"
                        and row.get("freeze_hash", "").strip() != "dev-unfrozen")
            if not admitted and key not in allow_dev:
                raise FillError(
                    "key '%s' not admitted (data_year=%r, freeze_hash=%r at %s) and "
                    "not in ALLOW_DEV_KEYS" % (key, row.get("data_year", ""),
                                               row.get("freeze_hash", ""), row["_loc"]))
            raw = row.get(field, "")
            if raw is None or raw.strip() == "":
                raise FillError("field '%s' empty for key '%s' (%s)" % (field, key, row["_loc"]))
            rendered, used_fmt = render(raw, fmt, bool(math_[a]))
        except FillError as e:
            errors.append("%s -> %s" % (where, e))
            pieces.append(m.group(0))
            continue
        pieces.append(rendered)
        ledger.append({"file": relname, "line": ln, "placeholder": m.group(0),
                       "key": key, "field": field, "fmt": used_fmt,
                       "rendered": rendered, "source_file_row": row["_loc"]})
    pieces.append(text[last:])
    for pos, lit in find_literals(text, comm, spans, allow_lit):
        warnings.append("%s:%d: literal-number warning: '%s' outside a placeholder"
                        % (relname, lineno(text, pos), lit))
    return "".join(pieces)


def out_path_for(tmpl):
    if not tmpl.endswith(".tmpl.tex"):
        raise FillError("%s: input must end in .tmpl.tex" % tmpl)
    return tmpl[:-len(".tmpl.tex")] + ".tex"


def run(files, root, strict=False, check_only=False, tables_dir=None,
        sources=None, allow_dev_path=None, allow_lit_path=None, ledger_out=None,
        out=sys.stdout, err=sys.stderr):
    tables_dir = tables_dir or os.path.join(root, "tables")
    sources = sources or [os.path.join(tables_dir, "summary.csv"),
                          os.path.join(tables_dir, "summary_secondary.csv")]
    derived = os.path.join(tables_dir, "summary_derived.csv")
    dev = os.path.join(tables_dir, "summary_dev.csv")
    expl = os.path.join(tables_dir, "summary_exploratory.csv")
    for extra in (derived, dev, expl):
        if os.path.isfile(extra) and extra not in sources:
            sources = list(sources) + [extra]
    allow_dev_path = allow_dev_path or os.path.join(root, "paper", "ALLOW_DEV_KEYS.txt")
    allow_lit_path = allow_lit_path or os.path.join(root, "paper", "ALLOW_LITERALS.txt")
    ledger_out = ledger_out or os.path.join(root, "paper", "ledger_used.csv")
    if not files:
        files = sorted(glob.glob(os.path.join(root, "paper", "sections", "*.tmpl.tex")))
        if not files:
            print("fill_ledger: no *.tmpl.tex found in paper/sections; nothing to do", file=out)
            return 0
    src = load_sources(sources, root)
    allow_dev = read_list(allow_dev_path, True)
    allow_lit = {norm_literal(s) for s in read_list(allow_lit_path, False)}
    errors = list(src.errors)
    warnings = []
    ledger = []
    outputs = []
    for f in files:
        f = os.path.abspath(f)
        try:
            dest = out_path_for(f)
            text = read_text(f)
        except (FillError, OSError) as e:
            errors.append(str(e))
            continue
        rel = os.path.relpath(f, root).replace("\\", "/")
        filled = fill_text(text, rel, src, allow_dev, allow_lit, errors, warnings, ledger)
        outputs.append((dest, filled))
    for w in warnings:
        print(("ERROR " if strict else "WARN  ") + w, file=err)
    if strict and warnings:
        errors.append("%d literal-number warning(s) treated as errors (--strict)" % len(warnings))
    for e in errors:
        print("ERROR " + e, file=err)
    if errors:
        print("fill_ledger: FAILED (%d error(s), %d warning(s)); nothing written"
              % (len(errors), len(warnings)), file=out)
        return 1
    if not check_only:
        for dest, filled in outputs:
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(filled)
        os.makedirs(os.path.dirname(os.path.abspath(ledger_out)), exist_ok=True)
        with open(ledger_out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=LEDGER_COLS, lineterminator="\n")
            w.writeheader()
            w.writerows(ledger)
    print("fill_ledger: OK (%d file(s), %d placeholder(s), %d literal warning(s))%s"
          % (len(outputs), len(ledger), len(warnings), " [check-only]" if check_only else ""),
          file=out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="*.tmpl.tex files (default paper/sections/*.tmpl.tex)")
    ap.add_argument("--strict", action="store_true", help="literal-number warnings are errors")
    ap.add_argument("--check-only", action="store_true", help="validate, write nothing")
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--tables-dir", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--allow-dev", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--allow-literals", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--ledger-out", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    return run(a.files, a.root, a.strict, a.check_only, a.tables_dir, None,
               a.allow_dev, a.allow_literals, a.ledger_out)


if __name__ == "__main__":
    sys.exit(main())
