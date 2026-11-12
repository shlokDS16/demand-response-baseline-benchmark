"""Table T_h5windows (D29 item 1): H5 levels and slope contrast, 14:00-18:00 (confirmatory) beside 16:00-20:00
(pre-specified secondary). Numbers only from tables/summary*.csv."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

P = MultiLedger()
sites = P.v("sample.sites").split(",")
f3 = lambda v: "%.3f" % v


def absd(m, k, w):
    key = ("derived.H5.absdev_sitemedian.%s.K%d" if w == "1418" else "derived.H5.absdev_sitemedian_w1620.%s.K%d") % (m, k)
    return P.v(key)


def sg(v, d=2):
    """Signed value x 1e3 with TeX minus/plus signs."""
    t = ("%." + str(d) + "f") % (1e3 * v)
    return ("$-$" + t[1:]) if t.startswith("-") else ("$+$" + t)


ci = lambda e, l, h: "%s [%s, %s]" % (sg(e), sg(l), sg(h))

rows = []
for k in (10, 40):
    for m, nm in (("pjmA", "PJM-adj"), ("scmR", "SCM-ridge")):
        rows.append([r"Site-median $|\rho-1|$, $K = %d$, %s" % (k, nm), f3(absd(m, k, "1418")), f3(absd(m, k, "1620"))])
nl = {w: int(P.v("derived.H5.levels_pjmA_lower_all_K.w" + w)) for w in ("1418", "1620")}
rows.append(["$K$ (of 4) where PJM-adj is lower", "%d of 4" % nl["1418"], "%d of 4" % nl["1620"]])

e14, (l14, h14) = P.v("H5.eta_diff"), P.ci("H5.eta_diff")
k20 = "exploratory.h5_win1620.eta_diff.pjmA_minus_scmR"
e20, (l20, h20) = P.v(k20), P.ci(k20)
rows.append([r"Slope contrast, HL [95 % CI] ($\times 10^{{-}3}$ per $K$)", ci(e14, l14, h14), ci(e20, l20, h20)])
rows.append([r"$p$-value (exact signed-rank)", "%.4f (Holm)" % P.v("H5.p_holm"),
             "%.3f (unadjusted)" % P.v("exploratory.h5_win1620.p_signedrank_two_sided_unadjusted")])
n14 = int(P.v("derived.H5.n_sites_scmR_faster.w1418"))
n20 = int(P.v("derived.H5.n_sites_scmR_faster.w1620"))
assert n14 == int(P.v("derived.H5.n_sites_scmR_faster"))   # the w1418 key equals the original ledger key
rows.append(["Sites with SCM-ridge's error growing faster", "%d of %d" % (n14, len(sites)), "%d of %d" % (n20, len(sites))])

hdr = ["", "14:00-18:00 (confirmatory)", "16:00-20:00 (pre-specified secondary)"]
xk = "exploratory.h5_window_contrast.eta_diff_1418_minus_1620"
xc, (xl, xh) = P.v(xk), P.ci(xk)
xp = P.v("exploratory.h5_window_contrast.p_signedrank_two_sided_unadjusted")
note = (r"PJM-adj, PJM rule with same-day adjustment; SCM-ridge, ridge synthetic control from other buildings; HL, Hodges-Lehmann estimate; "
        r"CI, confidence interval; $K$, number of dispatched days. Site-median values are medians over the %d sites of each site's median absolute error "
        r"$|\rho-1|$. The slope contrast is the per-site slope of the site-median error over $K$ for PJM-adj minus SCM-ridge; negative means SCM-ridge's error grows faster. "
        r"The 14:00-18:00 window is the confirmatory test (Holm-adjusted within the confirmatory family); 16:00-20:00 is a pre-specified secondary rerun "
        r"with no adjustment. The windows are not pooled. Exploratory cross-window contrast (14:00-18:00 minus 16:00-20:00, per-site paired): "
        r"HL %s ($\times 10^{{-}3}$ per $K$), 95\,\%% CI [%s, %s], unadjusted $p=%.2f$." %
        (len(sites), sg(xc), sg(xl), sg(xh), xp))
write_tex(TAB / "T_h5windows.tex", hdr, rows, r"lrr", [note])
print(open(TAB / "T_h5windows.tex", encoding="utf-8").read())
P.report()
