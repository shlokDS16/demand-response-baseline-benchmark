"""Tables S2 (screening tree, exploratory null result) and S3 (fallback rates by K, from the old Fig. 8b).
Values only from tables/summary.csv and tables/summary_secondary.csv; the ledger key is a CSV column and a TeX comment."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

P = Ledger(); S = Ledger("summary_secondary.csv")
f = lambda v, d=3: ("%." + str(d) + "f") % v
esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def emit(stem, hdr, rows, colspec):
    write_csv(TAB / (stem + ".csv"), hdr + ["Ledger key"], rows)
    L = [r"\begin{tabular}{%s}" % colspec, r"\toprule", " & ".join(esc(h) for h in hdr) + " " + chr(92) * 2, r"\midrule"]
    for r in rows:
        L.append(" & ".join(esc(c) for c in r[:-1]) + " " + chr(92) * 2 + " % key: " + r[-1])
    L += [r"\bottomrule", r"\end{tabular}"]
    (TAB / (stem + ".tex")).write_text(chr(10).join(L) + chr(10), encoding="utf-8", newline=chr(10))


# ---------------- S2 screening tree ----------------
rows = []
def add(q, key, val, d=3, ci=False):
    c = ""
    if ci:
        lo, hi = S.ci(key); c = "[%s, %s]" % (f(lo, d), f(hi, d))
    rows.append([q, f(val, d) if not isinstance(val, str) else val, c, key])
add("Training buildings (2016)", "screen.tree.n_train", int(S.v("screen.tree.n_train")), 0)
add("Training accuracy", "screen.tree.train_accuracy", S.v("screen.tree.train_accuracy"), 2)
for m in ("pjmA", "cgA", "scmR"):
    add("Training best-method share, %s" % NAME[m], "screen.train.class_share." + m, S.v("screen.train.class_share." + m), 2)
for m in ("pjmA", "cgA", "scmR"):
    add("Test assignment share, %s" % NAME[m], "screen.test.assigned_share." + m, S.v("screen.test.assigned_share." + m), 3)
add("Test buildings (2017)", "screen.test.n_buildings", int(S.v("screen.test.n_buildings")), 0)
add("Site-median log ratio vs PJM-adj (median over sites)", "screen.test.logratio_site_median_of_medians", S.v("screen.test.logratio_site_median_of_medians"), 3)
add("Hodges-Lehmann log ratio vs PJM-adj", "screen.test.logratio_vs_pjmA", S.v("screen.test.logratio_vs_pjmA"), 3, ci=True)
add("Sites where the tree is better", "screen.test.n_sites_better", int(S.v("screen.test.n_sites_better")), 0)
add("Pooled relMAE ratio, tree choice over PJM-adj", "screen.test.pooled_relMAE_chosen_over_pjmA", S.v("screen.test.pooled_relMAE_chosen_over_pjmA"), 3)
emit("S2_screening", ["Quantity", "Value", "Interval", "Ledger key"][:3], rows, "lrl")
# ---------------- S3 fallback rates ----------------
rows = []
for K in (10, 20, 30, 40):
    r = [str(K)]
    for lab, k in (("PJM", "H5.fallback.PJM.K%d"), ("CAISO", "H5.fallback.CAISO.K%d"), ("CAISO_lt10", "H5.fallback.CAISO_lt10.K%d")):
        r.append(f(100 * P.v(k % K), 2))
    r.append("H5.fallback.{PJM,CAISO,CAISO_lt10}.K%d" % K)
    rows.append(r)
emit("S3_fallback", ["K", "PJM fallback (%)", "CAISO fallback (%)", "CAISO with < 10 days (%)"], rows, "rrrr")
P.report(); S.report()
