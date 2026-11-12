"""Graphical abstract (SUSCOM): trade-off across two stress tests. Numbers only from tables/summary*.csv."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from matplotlib.patches import FancyBboxPatch

style()
L = Ledger("summary.csv")
D = MultiLedger()
sites = L.v("sample.sites").split(",")
be = {s: L.v("H4.site.%s" % s) for s in sites}
med = L.v("H4.median_site_pcross")
absd = {(m, k): D.v("derived.H5.absdev_sitemedian.%s.K%d" % (m, k)) for m in ("pjmA", "scmR") for k in (10, 40)}

NL = chr(10)
GE = chr(0x2265)
WCM = 13 / 2.54
PX_W, PX_H = 2656, 1600
fig = plt.figure(figsize=(WCM, WCM * PX_H / PX_W), dpi=PX_W / WCM)
FS = 7.2
fig.text(0.5, 0.95, "Baseline choice trades shaping sensitivity" + NL + "against error growth under repeated dispatch",
         ha="center", va="center", fontsize=8, fontweight="bold", color=INK, linespacing=1.15)

# ---- left
axl = fig.add_axes([0.125, 0.37, 0.30, 0.39])
order = sorted(sites, key=lambda s: be[s])
for i, s in enumerate(order):
    axl.plot(be[s], i, "o", color=VERM, ms=4.2, mec="white", mew=0.5, zorder=3, clip_on=False)
    axl.hlines(i, 0, be[s], color=GRID, lw=0.6, zorder=1)
axl.set_yticks(range(len(order))); axl.set_yticklabels(order, fontsize=7)
axl.set_ylim(-0.7, len(order) - 0.3)
axl.set_xlim(-0.002, 0.075)
axl.set_xticks([0, 0.025, 0.05, 0.075]); axl.set_xticklabels(["0", "2.5", "5.0", "7.5"], fontsize=FS)
axl.axvline(med, color=INK, lw=0.8, ls="--", zorder=2)
axl.text(med + 0.001, 0.2, "median" + NL + "%.1f%%" % (100 * med), fontsize=FS, color=INK, va="bottom", ha="left")
axl.set_xlabel("Break-even pre-event load increase (%)", fontsize=FS, labelpad=2)
axl.tick_params(length=2, pad=1.5)
axl.spines["left"].set_visible(False)
axl.tick_params(axis="y", length=0)
fig.text(0.275, 0.855, "Stress test 1: pre-event shaping", ha="center", fontsize=7.6, fontweight="bold", color=INK)
fig.text(0.275, 0.805, "PJM-adj stops beating SCM-ridge at this increase", ha="center", fontsize=FS, color=INK2)
fig.text(0.275, 0.215, "SCM-ridge is immune by construction" + NL + "to the specified four-hour injection", ha="center", va="center",
         fontsize=FS, color=GREEN, fontweight="bold", linespacing=1.2)

# ---- divider
fig.add_artist(plt.Line2D([0.515, 0.515], [0.19, 0.83], color=GRID, lw=0.8))

# ---- right
axr = fig.add_axes([0.645, 0.37, 0.30, 0.39])
xs = {10: 0.0, 40: 1.0}
bw = 0.36
for m, off, col in (("pjmA", -bw / 2, VERM), ("scmR", bw / 2, GREEN)):
    for k in (10, 40):
        v = absd[(m, k)]
        axr.bar(xs[k] + off, v, bw, color=col, zorder=2)
        axr.text(xs[k] + off, v + 0.012, "%.2f" % v, ha="center", va="bottom", fontsize=FS, color=INK)
axr.set_xticks([0, 1]); axr.set_xticklabels(["K = 10", "K = 40"], fontsize=FS)
axr.set_xlim(-0.55, 1.55); axr.set_ylim(0, 0.8)
axr.set_yticks([0, 0.2, 0.4, 0.6]); axr.set_yticklabels(["0", "0.2", "0.4", "0.6"], fontsize=FS)
axr.set_ylabel("Site-median $|\\rho - 1|$" + NL + "(absolute estimation error)", fontsize=FS, labelpad=2)
axr.set_xlabel("Dispatch events K, 14:00-18:00", fontsize=FS, labelpad=2)
axr.text(-0.5, 0.79, "K " + GE + " 20: stress level" + NL + "beyond documented" + NL + "annual event counts",
         fontsize=FS, color=INK2, va="top", ha="left", linespacing=1.2, zorder=5, bbox=dict(fc="white", ec="none", pad=1))
axr.grid(axis="y", lw=0.4, alpha=0.7, zorder=0); axr.tick_params(length=2, pad=1.5)
fig.text(0.795, 0.855, "Stress test 2: repeated dispatch", ha="center", fontsize=7.6, fontweight="bold", color=INK)
fig.text(0.795, 0.805, "SCM-ridge error grows faster with K", ha="center", fontsize=FS, color=INK2)
# 16-20 caveat (same ordering at all K in both windows; growth contrast inconclusive)
assert int(D.v("derived.H5.levels_pjmA_lower_all_K.w1620")) == 4 and int(D.v("derived.H5.levels_pjmA_lower_all_K.w1418")) == 4
lo, hi = D.ci("exploratory.h5_win1620.eta_diff.pjmA_minus_scmR")
assert lo < 0 < hi   # interval includes zero: growth contrast inconclusive at 16:00-20:00
fig.text(0.795, 0.138, "16:00-20:00 rerun: same ordering;" + NL + "growth contrast inconclusive", ha="center", va="center",
         fontsize=6.6, color=INK2, style="italic", linespacing=1.15)
# legend
for x, col, nm in ((0.64, VERM, "PJM-adj"), (0.76, GREEN, "SCM-ridge")):
    fig.patches.append(FancyBboxPatch((x, 0.2), 0.014, 0.03, boxstyle="square,pad=0", fc=col, ec="none", transform=fig.transFigure))
    fig.text(x + 0.02, 0.215, nm, fontsize=FS, va="center", color=INK)
fig.text(0.04, 0.125, "PJM-adj: PJM rule with same-day adjustment;" + NL + "SCM-ridge: ridge synthetic control from other buildings",
         ha="left", va="center", fontsize=FS, color=INK2, linespacing=1.2)

# takeaway
fig.add_artist(plt.Line2D([0.04, 0.96], [0.068, 0.068], color=GRID, lw=0.8))
fig.text(0.5, 0.034, "Takeaway: choose and monitor a baseline by its information set" + NL + "and the expected shaping and dispatch pattern.",
         ha="center", va="center", fontsize=FS, color=INK, fontweight="bold", linespacing=1.2)

out = ROOT / "submission"
fig.savefig(out / "graphical_abstract.pdf")
fig.savefig(out / "graphical_abstract.png", dpi=PX_W / WCM)
fig.savefig(out / "graphical_abstract.tiff", dpi=PX_W / WCM, pil_kwargs={"compression": "tiff_lzw"})
print("size px", PX_W, PX_H)
print("ledger keys used:", sorted(set(L.used + D.used)))
