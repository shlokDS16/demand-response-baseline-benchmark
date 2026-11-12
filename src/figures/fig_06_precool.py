"""Figure 6: median relative MAE vs injected pre-event increase p (stress test), four-hour and two-hour shapes."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

style()
L = Ledger()
sites = L.v("sample.sites").split(",")
P = ["0", "0.02", "0.05", "0.1", "0.2", "0.3"]
px = [float(p) for p in P]
# (key, colour, linestyle, marker, linewidth, markersize, zorder, hollow)
meths = [("nyA", VERM, ":", "^", 1.3, 6.5, 2, True), ("caisoA", VERM, "-.", "s", 1.3, 3.5, 3, False), ("scmR", GREEN, "-", "o", 1.3, 3.5, 4, False),
         ("cgA", GREEN, "--", "D", 1.0, 4.0, 5, True), ("pjmA", VERM, "-", "o", 2.4, 3.5, 6, False)]
fig, axs = plt.subplots(1, 2, figsize=(W2, 3.5), sharey=True, gridspec_kw=dict(wspace=0.08))
prev = L.v("method.prev.R1.relMAE_median")
for ax, sh, ttl in zip(axs, ("4h", "2h"), ("Four-hour shape", "Two-hour shape")):
    ax.axvspan(-0.01, 0.10, color=GREY, alpha=0.10, lw=0)
    ax.axvspan(0.10, 0.31, color=YELLOW, alpha=0.10, lw=0)
    ax.text(0.05, 1.005, "realistic band", transform=ax.get_xaxis_transform(), fontsize=7, color=INK2, ha="center", va="bottom")
    ax.text(0.205, 1.005, "stress tail", transform=ax.get_xaxis_transform(), fontsize=7, color=INK2, ha="center", va="bottom")
    ys = {}
    for m, c, ls, mk, lw, ms, zo, hol in meths:
        y = [L.v("precool.relMAE.%s.%s.p%s" % (m, sh, p)) for p in P]
        ys[m] = y
        ax.plot(px, y, color=c, ls=ls, marker=mk, ms=ms, lw=lw, zorder=zo, mfc="white" if hol else c)
    ax.hlines(prev, -0.01, 0.31, color=GREY, lw=0.8, zorder=1)
    ax.axvline(0.10, color=INK2, lw=0.7, ls="--")
    ax.set_xlim(-0.01, 0.56); ax.set_xlabel("Injected pre-event load increase p (stress test)")
    ax.set_xticks([0, 0.1, 0.2, 0.3])
    ax.set_title(ttl, fontsize=7.5, pad=16)
    ax.grid(axis="y", lw=0.4, alpha=0.7)
    # direct line-end labels (pjmA and cgA coincide; nyA overlays scmR in the two-hour panel)
    ends = [("pjmA", "PJM-adj = CG-adj", ys["pjmA"][-1], VERM), ("caisoA", "CAISO-adj", ys["caisoA"][-1], VERM),
            ("scmR", ("SCM-ridge: immune by" + chr(10) + "construction") if sh == "4h" else "SCM-ridge = NYISO-adj", ys["scmR"][-1], GREEN), ("prev", "prev (no injection effect)", prev, INK2)]
    if sh == "4h":
        ends.append(("nyA", "NYISO-adj", ys["nyA"][-1], VERM))
    ends.sort(key=lambda e: e[2]); lab = [e[2] for e in ends]
    for i in range(1, len(lab)):
        lab[i] = max(lab[i], lab[i - 1] + (0.034 if "immune" in ends[i - 1][1] or "immune" in ends[i][1] else 0.018))
    for (m, t, y0, c), yl in zip(ends, lab):
        ax.text(0.315, yl, t, fontsize=7, color=c, va="center", ha="left")
axs[0].set_ylabel("Median building relative MAE (hot days)")
axs[0].text(0.105, 0.93, "p = 0.10", transform=axs[0].get_xaxis_transform(), fontsize=7, color=INK2, va="top", ha="left")
axs[0].set_ylim(0.035, 0.315)
ymin = 0.035
for s_ in sites:
    v = L.v("H4.site.%s" % s_)
    axs[0].plot([v, v], [ymin, ymin + 0.008], color="black", lw=1.0, clip_on=False)
axs[0].text(0.08, ymin + 0.001, "ticks: %d site break-evens" % len(sites), ha="left", va="bottom", fontsize=7, color=INK2)
pc = L.v("H4.median_site_pcross"); lo, hi = L.ci("H4.median_site_pcross")
axs[0].text(0.02, 0.80, chr(10).join(["median of site", "break-evens = %.3f" % pc, "[%.3f, %.3f]" % (lo, hi), "(site-level estimand)"]), transform=axs[0].transAxes, fontsize=7, color=INK, va="top", bbox=dict(fc="white", ec="none", pad=1.5), zorder=5)
p2 = L.v("pcross.pjmA.2h"); l2, h2 = L.ci("pcross.pjmA.2h")
axs[1].text(0.02, 0.93, chr(10).join(["building-pooled break-even (PJM-adj)", "= %.3f [%.3f, %.3f]:" % (p2, l2, h2), "interval includes the threshold 0.10;", "no site-level test"]), transform=axs[1].transAxes, fontsize=7, color=INK, va="top", bbox=dict(fc="white", ec="none", pad=1.5), zorder=5)
fig.text(0.5, 1.0, "Stress test: injected increase, not observed behavior; curves are building-pooled medians", ha="center", va="bottom", fontsize=7.5, fontweight="bold")
panel(axs[0], "a", dx=-0.12, dy=1.0); panel(axs[1], "b", dx=-0.1, dy=1.0)
L.report()
save(fig, "fig_06_precool")
