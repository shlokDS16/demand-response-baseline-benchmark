"""Table B.1 (full methods longtable): tables/TB1_methodsfull.tex, generated from tables/T2.csv (no new computation) plus the
per-rule document vintage and deviation notes below, taken from research/team/E2_cbl_rules.md and E2b_baseline_defs.md.
Values that those files do not record are written "n/a" (listed in logs/FIX_tables_v1.md). Methods that were not evaluated
(M3-adj, GSCM) are NOT rows of T2/T4; they appear here only, with the reason.
Also writes tables/T2_compact.tex (body Table 1). Run: python src/figures/table_TB1.py"""
import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = list(csv.DictReader(open(os.path.join(ROOT, "tables", "T2.csv"), encoding="utf-8")))
assert not any("not run" in r["Definition"] for r in rows), "T2.csv must hold evaluated methods only"


def esc(s):
    """Escape plain text; \\cite{...} groups pass through unchanged."""
    out = []
    for part in re.split(r"(\\cite\{[^}]*\})", s):
        if part.startswith(r"\cite{"):
            out.append(part)
            continue
        part = part.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
        part = re.sub(r"\bs-(\d)", r"s$-$\1", part)
        part = part.replace("I-donor+I-morn", "I-donor + I-morn")   # layout: break at the plus sign
        out.append(part)
    return "".join(out)


# source documents as cite keys (same URLs as paper/references.bib)
SRC = {"prev": "n/a (trivial baseline)",
       "PJM": r"\cite{pjm_manual11,pjm_attk}", "PJM-adj": r"\cite{pjm_manual11,pjm_attk}",
       "CAISO": r"\cite{caiso_tariff}", "CAISO-adj": r"\cite{caiso_tariff}",
       "NYISO": r"\cite{nyiso_manual7}", "NYISO-adj": r"\cite{nyiso_manual7}",
       "ISO-NE": r"\cite{isone_mr1}", "ISO-NE-adj": r"\cite{isone_mr1}",
       "DM": r"\cite{granderson2021}", "DM-adj": r"\cite{granderson2021}",
       "WM": r"\cite{granderson2021}", "WM-adj": r"\cite{granderson2021}",
       "M3": r"\cite{mathieu2011}",
       "Mid8": "this study (ERCOT-style day-matching variant)",
       "TOWT-70": r"\cite{mathieu2011,granderson2021}", "TOWT-70-adj": r"\cite{mathieu2011,granderson2021}",
       "TOWT-7": r"\cite{mathieu2011,granderson2021}",
       "CG": "this study", "CG-adj": "this study",
       "SCM-ridge": r"\cite{sievers2026}", "SCM-classic": r"\cite{sievers2026}",
       "LightGBM-morn": "this study", "LightGBM-donor": "this study",
       "MLP-morn": "this study", "MLP-donor": "this study"}
V_PJM = (r"Manual 11 rev.\ 137 (eff.\ 2026-07-28); Tariff Att.\ K App.\ 3.3A, 2026 text and 2015 redline (identical). "
         "2016 and 2017 text not opened")
V_CAISO = "Tariff 4.13.4.1 as of 2025-05-02; same text in the 2018 ER18-2242 filing. 2016 and 2017 text: n/a"
V_NY = r"Manual 7 v9.1 (eff.\ 2025-05-20), s5.2.2. 2016 and 2017 text not opened (unverified)"
V_ISO = "Market Rule 1, Section III.8, current text. Version of 2016 and 2017 (filing ER16-167): unverified, n/a"
V_GR = "Granderson et al. 2021 (published method); no dated rule document"
V_MA = "Mathieu et al. 2011, LBNL author version; window lengths from Granderson et al. 2021"
D_ADJ = ("adjustment hours fixed at s-4, s-3 for every window; the source states a two-hour block ending two hours "
         "before the window only for some windows")
VD = {  # method: (document vintage, our deviation)
    "prev": ("n/a", "none (baseline defined here)"),
    "PJM": (V_PJM, "25 % exclusion applied after taking the five most recent weekdays"),
    "PJM-adj": (V_PJM, "none beyond PJM; additive and uncapped as in the tariff"),
    "CAISO": (V_CAISO, "none recorded"),
    "CAISO-adj": (V_CAISO, "none recorded"),
    "NYISO": (V_NY, "none recorded"),
    "NYISO-adj": (V_NY, "adjustment is optional in the source; reported as a separate variant"),
    "ISO-NE": (V_ISO, "hourly approximation of a five-minute rule"),
    "ISO-NE-adj": (V_ISO, "hourly approximation of a five-minute rule; source adjusts on the intervals before start-up"),
    "DM": (V_GR, "none recorded"),
    "DM-adj": (V_GR, D_ADJ),
    "WM": (V_GR, "weekday filter, tie-breaking and holiday handling are not stated in the source (project choices)"),
    "WM-adj": (V_GR, D_ADJ),
    "M3": ("Mathieu et al. 2011, literature survey of benchmarks; not defined in Granderson et al. 2021 or 2023",
           "n/a (one-line source description; selection details not recorded)"),
    "Mid8": ("n/a (no verified ERCOT document; not presented as ERCOT's rule)",
             "unadjusted middle 8 of 10 recent weekdays only"),
    "TOWT-70": (V_MA, "hourly data: 120 weekday hour-of-week terms, six equal-width temperature bins, occupancy set "
                      "automatically from the load profile; source uses 15-minute data and hand-set occupancy"),
    "TOWT-70-adj": (V_MA, "as TOWT-70; adjustment and cap as for weather matching"),
    "TOWT-7": (V_MA, "as TOWT-70 with seven training days"),
    "CG": ("n/a (this study)", "n/a (project design)"),
    "CG-adj": ("n/a (this study)", "n/a (project design)"),
    "SCM-ridge": ("arXiv v1, 2026-04-20", "source is residential with one static ridge fit; here a short pre-period "
                                          "window, hourly data, penalty 3 and event days, which the source lacks"),
    "SCM-classic": ("arXiv v1, 2026-04-20", "windowed per event; project design"),
    "LightGBM-morn": ("n/a (this study)", "n/a (project design)"),
    "LightGBM-donor": ("n/a (this study)", "n/a (project design)"),
    "MLP-morn": ("n/a (this study)", "n/a (project design)"),
    "MLP-donor": ("n/a (this study)", "n/a (project design)"),
}
# evaluated methods are exactly the rows of T2.csv; the dicts must cover them
assert {r["Method"] for r in rows} == set(VD) == set(SRC), ({r["Method"] for r in rows} ^ set(VD), set(VD) ^ set(SRC))


def params(r):
    lb, adj, cap = r["Lookback"], r["Adjustment"], r["Cap"]
    if adj == "none":
        return lb + "; no adjustment"
    return "%s; %s; cap %s" % (lb, adj, cap) if adj.startswith(("ratio", "additive")) else "%s; %s; %s" % (lb, adj, cap)


NOT_EVAL = [("M3-adj", "I-morn", "Mathieu 3 of 10 with adjustment",
             "not evaluated: dropped from the design and no result keys exist"),
            ("GSCM", "I-donor", "Augmented synthetic control",
             "not evaluated: cut, because the best variant needs lagged treated load, which is unavailable on an event day")]

W = [1.8, 1.6, 2.2, 2.2, 1.4, 2.6, 2.8]          # cm, sum 14.6; with 12 gaps of 3 pt (1.27 cm) = 15.87 cm <= supplement text width 16.0 cm
spec = "@{}" + "".join(r">{\raggedright\arraybackslash}p{%.1fcm}" % w for w in W) + "@{}"
cols = ["Method", "Info. set", "Definition", "Parameters", "Source", "Document vintage", "Our deviation"]
head = " & ".join(r"\textbf{%s}" % c for c in cols) + r" \\"
span_w = sum(W[3:]) + 18 / 28.4527                # four spanned columns plus three inner column gaps (6 pt each)
out = [r"\begingroup\footnotesize\setlength{\tabcolsep}{3pt}", r"\begin{longtable}{" + spec + "}",
       r"\caption{Full list of baseline methods: information set, definition, parameters (lookback; adjustment; cap), source, "
       r"document vintage and our deviation from the source. Methods without results are listed at the end with the reason. "
       r"``n/a'' marks a value that the source notes do not record. The tuned LightGBM variants use the same definitions with parameters from the pre-registered search; the MLP rows are the tuned MLP variants (same search budget).}\label{tabS:methodsfull}\\",
       r"\toprule", head, r"\midrule\endfirsthead", r"\toprule", head, r"\midrule\endhead", r"\bottomrule\endfoot"]
for r in rows:
    m = r["Method"]
    v, d = VD[m]
    vals = [esc(m), esc(r["Information set"]), esc(r["Definition"]), esc(params(r)), esc(SRC[m]), esc(v), esc(d)]
    out.append(" & ".join(vals) + r" \\")
out.append(r"\midrule")
for m, info, d, why in NOT_EVAL:
    out.append(r"%s & %s & %s & \multicolumn{4}{>{\raggedright\arraybackslash}p{%.2fcm}}{%s} \\"
               % (esc(m), esc(info), esc(d), span_w, esc(why)))
out.append(r"\end{longtable}")
# the source notes of the generated T2 (PJM documents, CAISO/ISO-NE coincidence) go under the full table
t2 = open(os.path.join(ROOT, "tables", "T2.tex"), encoding="utf-8").read().split("\n")
out += [ln for ln in t2 if ln.startswith(r"\par\smallskip")]
out.append(r"\endgroup")
open(os.path.join(ROOT, "tables", "TB1_methodsfull.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print("wrote tables/TB1_methodsfull.tex,", len(rows), "evaluated rows,", len(NOT_EVAL), "not-evaluated rows")

# compact Table 1 (body): the confirmatory-family methods and the methods that appear in Figs. 6-8; no source column
keep = ["prev", "PJM", "PJM-adj", "CAISO", "CAISO-adj", "NYISO-adj", "ISO-NE-adj", "WM-adj", "CG", "CG-adj", "SCM-ridge"]
ccols = ["Method", "Information set", "Definition", "Lookback", "Adjustment", "Cap"]
cspec = (r">{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{1.7cm}"
         r">{\raggedright\arraybackslash}p{4.4cm}>{\raggedright\arraybackslash}p{2.2cm}"
         r">{\raggedright\arraybackslash}p{3.2cm}>{\raggedright\arraybackslash}p{1.9cm}")
byname = {r["Method"]: r for r in rows}
c = [r"\begin{tabular}{" + cspec + "}", r"\toprule", " & ".join(ccols) + r" \\", r"\midrule"]
for k in keep:
    c.append(" & ".join(esc(byname[k][x]) for x in ccols) + r" \\")
c += [r"\bottomrule", r"\end{tabular}",
      r"\par\smallskip{\footnotesize\raggedright Hours $s-4,\dots$ are relative to the window start $s$. All other evaluated methods, the sources, "
      r"document vintages and the methods without results are in Supplement Table~\ref{tabS:methodsfull}. CAISO and ISO-NE unadjusted baselines "
      r"coincide (Table~\ref{tab:accuracy}).\par}"]
open(os.path.join(ROOT, "tables", "T2_compact.tex"), "w", encoding="utf-8", newline="\n").write("\n".join(c) + "\n")
print("wrote tables/T2_compact.tex,", len(keep), "rows")
