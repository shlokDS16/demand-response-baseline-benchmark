"""Shared helpers for the Paper B figures and tables. Numbers come only from tables/summary.csv and results/run/*.pkl."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
import csv
import gc
import pickle
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
TAB = ROOT / "tables"
RUN = ROOT / "results" / "run"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

# Okabe-Ito, one colour per method family (FIGURES_PLAN)
BLUE, VERM, GREEN, GREY, PURPLE = "#0072B2", "#D55E00", "#009E73", "#999999", "#CC79A7"
SKY, ORANGE, YELLOW, BLACK = "#56B4E9", "#E69F00", "#F0E442", "#000000"
INK, INK2, GRID = "#222222", "#555555", "#DDDDDD"
W1, W15, W2 = 90 / 25.4, 140 / 25.4, 190 / 25.4   # Elsevier single, 1.5, double column (inches)

FAMILY = {"prev": GREY, "mid8": BLUE, "pjm0": BLUE, "caiso0": BLUE, "ny0": BLUE, "isone0": BLUE, "dm0": BLUE, "wm0": BLUE,
          "m3": BLUE, "pjmA": VERM, "caisoA": VERM, "nyA": VERM, "isoneA": VERM, "dmA": VERM, "wmA": VERM, "m3A": VERM,
          "cg0": GREEN, "cgA": GREEN, "scmR": GREEN, "scmC": GREEN}
NAME = {"prev": "prev", "pjm0": "PJM", "pjmA": "PJM-adj", "caiso0": "CAISO", "caisoA": "CAISO-adj", "ny0": "NYISO",
        "nyA": "NYISO-adj", "isone0": "ISO-NE", "isoneA": "ISO-NE-adj", "dm0": "DM", "dmA": "DM-adj", "wm0": "WM",
        "wmA": "WM-adj", "m3": "M3", "mid8": "Mid8", "cg0": "CG", "cgA": "CG-adj", "scmR": "SCM-ridge", "scmC": "SCM-classic"}


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 7.5,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.linewidth": 0.6,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False, "grid.color": GRID,
        "grid.linewidth": 0.5, "lines.linewidth": 1.2, "savefig.dpi": 300, "figure.dpi": 100,
        "pdf.fonttype": 42, "ps.fonttype": 42, "legend.frameon": False, "figure.facecolor": "white",
        "axes.facecolor": "white", "savefig.facecolor": "white"})


class Ledger:
    """Reads tables/summary.csv; every access is recorded and printed at the end. Missing key = error."""

    def __init__(self, name="summary.csv"):
        with open(TAB / name, newline="") as fh:
            self.rows = {r["key"]: r for r in csv.DictReader(fh)}
        self.used = []

    def row(self, k):
        if k not in self.rows:
            raise KeyError("ledger key missing: " + k)
        self.used.append(k)
        return self.rows[k]

    def v(self, k):
        s = self.row(k)["value"]
        try:
            return float(s)
        except ValueError:
            return s

    def ci(self, k):
        r = self.row(k)
        return float(r["ci_low"]), float(r["ci_high"])

    def has(self, k):
        return k in self.rows

    def report(self):
        u = list(dict.fromkeys(self.used))
        print("LEDGER KEYS USED (%d):" % len(u))
        print("; ".join(u))
        return u


def load_pkl(name):
    with open(RUN / name, "rb") as fh:
        return pickle.load(fh)


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / ("%s.%s" % (stem, ext)), dpi=300, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    gc.collect()
    print("saved", FIG / (stem + ".png"))


def panel(ax, letter, dx=-0.0, dy=1.02):
    ax.text(dx, dy, "(%s)" % letter, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom", ha="left")


def tex_text(s):
    """Escape a table cell for LaTeX text mode; a hyphen-minus before a digit becomes a true minus."""
    import re
    t = str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")
    t = re.sub(r"(?<![\w$])-(?=\d)", "$-$", t)          # -0.05, [-0.1, ...
    t = re.sub(r"\b(s)-(?=\d)", r"\1$-$", t)            # s-4 (hours before the window start)
    t = t.replace("I-donor+I-morn", "I-donor + I-morn")  # layout: break at the plus sign, not inside "I-morn"
    return t


def write_tex(path, header, rows, colspec, notes=None):
    """booktabs table, editable text, no resizebox. A row ("MC", c1, c2, text) spans the remaining columns.
    notes: raw LaTeX paragraph(s) placed under the tabular (footnote size)."""
    ncol = len(header)
    L = [r"\begin{tabular}{%s}" % colspec, r"\toprule", " & ".join(tex_text(h) for h in header) + r" \\", r"\midrule"]
    for r in rows:
        if r and r[0] == "MC":
            L.append("%s & %s & \\multicolumn{%d}{l}{%s} \\\\" % (tex_text(r[1]), tex_text(r[2]), ncol - 2, tex_text(r[3])))
        else:
            L.append(" & ".join(tex_text(c) for c in r) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    for n in (notes or []):
        L.append(r"\par\smallskip{\footnotesize\raggedright " + n + r"\par}")   # notes flush left, not centered
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


class MultiLedger:
    """Several ledger tables searched in order (summary, secondary, exploratory, derived). Missing key = error."""

    def __init__(self, names=("summary.csv", "summary_secondary.csv", "summary_exploratory.csv", "summary_derived.csv")):
        self.parts = [Ledger(n) for n in names]

    def _find(self, k):
        for p in self.parts:
            if k in p.rows:
                return p
        raise KeyError("ledger key missing: " + k)

    def row(self, k):
        return self._find(k).row(k)

    def v(self, k):
        return self._find(k).v(k)

    def ci(self, k):
        return self._find(k).ci(k)

    def has(self, k):
        return any(k in p.rows for p in self.parts)

    @property
    def used(self):
        return [k for p in self.parts for k in p.used]

    def report(self):
        u = list(dict.fromkeys(self.used))
        print("LEDGER KEYS USED (%d):" % len(u))
        print("; ".join(u))
        return u
