"""Table T5: secondary and sensitivity summary (2017). Values only from tables/summary.csv and tables/summary_secondary.csv; key per row in CSV and as a TeX comment."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

P = Ledger(); S = Ledger("summary_secondary.csv")
f = lambda v, d=3: ("%." + str(d) + "f") % v
rows = []   # analysis, quantity, estimate, interval, n, key
def pt(led, an, q, key, d=3, n=""):
    rows.append([an, q, f(led.v(key), d), "", n, key])
def ci(led, an, q, key, d=3, n=""):
    lo, hi = led.ci(key); rows.append([an, q, f(led.v(key), d), "[%s, %s]" % (f(lo, d), f(hi, d)), n, key])
# H6 portfolio
ci(S, "H6 portfolio", "CG-adj minus PJM-adj PER, level at n = 1", "H6.contrast.level_n1", n="11 sites")
ci(S, "H6 portfolio", "CG-adj minus PJM-adj PER, level at n = 20", "H6.contrast.level_big", n="8 sites")
ci(S, "H6 portfolio", "Change n = 1 to 20, CG-adj minus PJM-adj", "H6.contrast.delta_big", n="8 sites")
ci(S, "H6 portfolio", "n = 20 minus load-matched random, CG-adj minus PJM-adj", "H6.contrast.big_minus_rand_cgA_minus_pjmA", n="8 sites")
pt(S, "H6 portfolio", "Pooled PER, PJM-adj, n = 1", "H6.pjmA.PER.n1", n="11 sites")
pt(S, "H6 portfolio", "Pooled PER, PJM-adj, n = 20", "H6.pjmA.PER.nbig", n="11 sites")
pt(S, "H6 portfolio", "Pooled PER, CG-adj, n = 1", "H6.cgA.PER.n1", n="11 sites")
pt(S, "H6 portfolio", "Pooled PER, CG-adj, n = 20", "H6.cgA.PER.nbig", n="11 sites")
# screening
pt(S, "Screening tree", "Pooled relMAE of tree choice over PJM-adj", "screen.test.pooled_relMAE_chosen_over_pjmA", n="11 sites")
pt(S, "Screening tree", "Site median log ratio vs PJM-adj", "screen.test.logratio_site_median_of_medians", n="11 sites")
pt(S, "Screening tree", "Share of test buildings assigned to PJM-adj", "screen.test.assigned_share.pjmA", n="1001 buildings")
# event-rule and window sensitivity (method medians)
for m in ("pjmA", "cgA", "scmR"):
    for c, lab in (("R1", "primary R1"), ("R2ISO", "R2-ISO (7 US sites)"), ("w1620", "16:00 to 20:00 window")):
        pt(P, "Sensitivity: relMAE", "%s, %s" % (NAME[m], lab), "method.%s.%s.relMAE_median" % (m, c), 4)
# non-event baseline days and flatline filter
for tag, lab in (("nonevent", "Non-event E3 days"), ("flatoff", "Flatline filter off")):
    for h in ("H1", "H2", "H3"):
        ci(S, lab, "%s estimate" % h, "%s.%s.est" % (tag, h), 3)
# ablations
pt(S, "Ablation", "PJM-adj relMAE, adjustment on", "ablation.adjustment.pjmA.on.relMAE_median", 4)
pt(S, "Ablation", "PJM-adj relMAE, adjustment off", "ablation.adjustment.pjmA.off.relMAE_median", 4)
pt(S, "Ablation", "PJM-adj relMAE, cap on", "ablation.cap.pjmA.on.relMAE_median", 4)
ci(S, "Ablation", "CG-adj with 5 donors, log ratio vs whole pool", "ablation.donor.k5.logratio_vs_wholepool", 3)
ci(S, "Ablation", "CG-adj, same-use donors, log ratio vs whole pool", "ablation.donor.pool_same_use.logratio_vs_wholepool", 3)
hdr = ["Analysis", "Quantity", "Estimate", "Interval", "Sample", "Ledger key"]
write_csv(TAB / "T5_secondary.csv", hdr, rows)
esc = tex_text
# REVISION_1: p-column so that the table fits the supplement text width
L = [r"\begin{tabular}{@{}l>{\raggedright\arraybackslash}p{6.4cm}rll@{}}", r"\toprule", " & ".join(esc(h) for h in hdr[:5]) + r" \\", r"\midrule"]
prev = None
for r in rows:
    if prev is not None and r[0] != prev:
        L.append(r"\midrule")
    prev = r[0]
    L.append(" & ".join(esc(c) for c in r[:5]) + r" \\ % key: " + r[5])
L += [r"\bottomrule", r"\end{tabular}"]
(TAB / "T5_secondary.tex").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
print("rows", len(rows))
P.report(); S.report()
