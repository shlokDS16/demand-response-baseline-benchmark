"""Supplementary bridge table S_bridge (X1, D22): NMBE (Granderson sign) and relative RMSE next to our signed bias.
No new computation: values are existing ledger keys method.<m>.R1.nmbe_granderson / rmse_median / bias_median."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

P = Ledger()
NAME.update({"m3A": "M3-adj", "towt70": "TOWT-70", "towt70A": "TOWT-70-adj", "towt7": "TOWT-7",
             "lgbM": "LightGBM-morn", "lgbD": "LightGBM-donor"})
order = ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "isone0", "isoneA", "dm0", "dmA", "wm0", "wmA", "m3",
         "m3A", "mid8", "towt70", "towt70A", "towt7", "cg0", "cgA", "scmR", "scmC", "lgbM", "lgbD"]
f = lambda v, d=3: ("%." + str(d) + "f") % v
rows, missing = [], []
for m in order:
    if m == "isone0":
        continue
    ks = ["method.%s.R1.%s" % (m, x) for x in ("relMAE_median", "bias_median", "nmbe_granderson", "rmse_median")]
    if not P.has(ks[0]):
        continue
    nm = NAME[m] if m != "caiso0" else "CAISO / ISO-NE (identical)"
    if m == "caiso0":
        for x in ("nmbe_granderson", "rmse_median", "bias_median"):
            assert P.v("method.caiso0.R1.%s" % x) == P.v("method.isone0.R1.%s" % x)
    have = [P.has(k) for k in ks]
    if not (have[2] and have[3]):
        missing.append(NAME[m])
    rows.append([nm, f(P.v(ks[1])), f(P.v(ks[2])) if have[2] else "n/a", f(P.v(ks[3])) if have[3] else "n/a"])
hdr = ["Method", "Bias (ours)", "NMBE (Granderson sign)", "Relative RMSE"]   # signs explained in the note (REVISION_1: was 169 pt too wide)
write_csv(TAB / "S_bridge.csv", hdr, rows)
note = ("Hot-day building-events (R1); medians over buildings. Our bias is positive for over-payment; NMBE is positive for under-prediction. NMBE is the sum of (actual minus baseline) over the sum of actual load, "
        "the sign used by LBNL studies; our bias has the opposite sign convention, so NMBE and bias are not equal. "
        "NMBE and relative RMSE are not in the ledger for TOWT and LightGBM (n/a).")
write_tex(TAB / "S_bridge.tex", hdr, rows, r"lrrr", [note])
print("rows", len(rows), "missing nmbe/rmse:", missing)
P.report()
