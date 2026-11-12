"""Figure 12: H6 portfolio aggregation (secondary, 2017): payment error share PER at n = 1, n = 20 and load-matched random portfolios, and the cgA-minus-pjmA contrasts."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

style()
S = Ledger("summary_secondary.csv")
SITES = ["Bear", "Bull", "Cockatoo", "Eagle", "Fox", "Hog", "Lamb", "Peacock", "Rat", "Robin", "Wolf"]
cols = [("pjmA", VERM, "o", "PJM-adj"), ("cgA", GREEN, "D", "CG-adj")]
cats = [("n1", "n1", "n = 1"), ("nbig", "n20", "n = 20"), ("rand", "rand", "random\nmatched")]
fig, axs = plt.subplots(2, 1, figsize=(W15, 4.8), gridspec_kw=dict(height_ratios=[0.8, 1], hspace=0.9))
ax = axs[0]
mk = {"n1": ("o", "n = 1"), "nbig": ("s", "n = 20"), "rand": ("^", "load-matched random")}
yrow = {"pjmA": 1, "cgA": 0}
for m, c, _, nm in cols:
    y0 = yrow[m]
    v = {k: S.v("H6.%s.PER.site_median_%s" % (m, k)) for k, _, _ in cats}
    ax.hlines(y0, min(v.values()), max(v.values()), color=c, lw=1.6, alpha=0.6, zorder=1)
    for k, (m_, lab) in mk.items():
        ax.plot(v[k], y0, m_, color=c, ms=7, mec="white", mew=0.6, zorder=3, mfc=c if k != "rand" else "white", mew2=None) if False else ax.plot(v[k], y0, m_, color=c, ms=7, mec=c if k == "rand" else "white", mew=1.0 if k == "rand" else 0.6, zorder=3, mfc=c if k != "rand" else "white")
        ax.text(v[k] + {"n1": 0.0, "nbig": -0.004, "rand": 0.004}[k], y0 + (0.2 if m == "pjmA" else -0.22), "%.2f" % v[k], fontsize=7, color=c, ha={"n1": "center", "nbig": "right", "rand": "left"}[k], va="bottom" if m == "pjmA" else "top")
ax.set_yticks([1, 0]); ax.set_yticklabels(["PJM-adj", "CG-adj"]); ax.set_ylim(-0.7, 1.7); ax.set_xlim(0.08, 0.46)
ax.set_xlabel("Median over sites of portfolio payment error" + chr(10) + "|sum B - sum L| / (0.10 sum L)")
ax.grid(axis="x", lw=0.4, alpha=0.7)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker=m_, ls="", color=INK2, mfc=INK2 if k != "rand" else "white", ms=6, label=lab) for k, (m_, lab) in mk.items()], loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=7, ncol=3, frameon=False, columnspacing=1.5)
panel(ax, "a", dx=-0.12)
b = axs[1]
items = [("level_n1", "Level at n = 1"), ("level_big", "Level at n = 20"),
         ("delta_big", "Change n = 1 to 20"), ("delta_rand", "Change n = 1 to random"),
         ("big_minus_rand_cgA_minus_pjmA", "n = 20 minus random")]
yy = np.arange(len(items))[::-1]
for y, (k, lab) in zip(yy, items):
    key = "H6.contrast." + k
    v = S.v(key); lo, hi = S.ci(key)
    nneg = int(S.v(key + ".n_negative_sites")); nst = int(float(S.row(key)["n_sites"]))
    b.hlines(y, lo, hi, color=GREEN, lw=1.4)
    b.plot(v, y, "D", color=GREEN, ms=5, mec="white", mew=0.5, zorder=3)
    b.text(0.135, y, "%d/%d sites < 0" % (nneg, nst), va="center", ha="left", fontsize=7, color=INK2)
b.axvline(0, color=INK2, lw=0.7)
b.set_yticks(yy); b.set_yticklabels([l for _, l in items]); b.set_xlim(-0.17, 0.25)
b.set_xlabel("CG-adj minus PJM-adj, PER difference\n(site Hodges-Lehmann, 95 % CI)")
b.grid(axis="x", lw=0.4, alpha=0.7)
panel(b, "b", dx=-0.3)
fig.text(0.5, -0.01, "Secondary analysis, 2017; {:,} load-matched random portfolios; no multiplicity adjustment; descriptive".format(int(S.v("H6.n_portfolios.rand"))),
         ha="center", va="top", fontsize=7, color=INK2)
S.report()
save(fig, "fig_12_portfolio")
