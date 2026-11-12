"""Figure 13: sensitivity of method accuracy to the event rule (R2-ISO, 7 US sites) and the 16:00-20:00 window, against the primary R1 (2017; secondary)."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

style()
L = Ledger()
order = ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "cgA", "scmR"]   # methods with all three conditions in the ledger
conds = [("R1", "Primary (R1, 14:00 to 18:00)", "o", 1.0), ("R2ISO", "R2-ISO (7 US sites)", "s", 0.85), ("w1620", "16:00 to 20:00 window", "^", 0.85)]
fig, axs = plt.subplots(1, 2, figsize=(W2, 3.4), sharey=True, gridspec_kw=dict(wspace=0.32))
yy = np.arange(len(order))[::-1]
for ax, stat, xl, fmt in ((axs[0], "relMAE_median", "Median relative MAE", "%.3f"), (axs[1], "bias_median", "Median relative bias", "%.3f")):
    for y, m in zip(yy, order):
        vals = [L.v("method.%s.%s.%s" % (m, c, stat)) for c, *_ in conds]
        ax.hlines(y, min(vals), max(vals), color=FAMILY[m], lw=1.0, alpha=0.45, zorder=1)
        for (c, lab, mk, a), v in zip(conds, vals):
            ax.plot(v, y, mk, ms=5.2 if c == "R1" else 4.6, mfc=FAMILY[m] if c == "R1" else "white", mec=FAMILY[m], mew=1.0, zorder=3)
    ax.set_xlabel(xl); ax.grid(axis="x", lw=0.4, alpha=0.7); ax.set_axisbelow(True)
axs[1].axvline(0, color=INK2, lw=0.7)
axs[0].set_yticks(yy); axs[0].set_yticklabels([NAME[m] for m in order]); axs[1].set_yticks(yy); axs[1].set_yticklabels([NAME[m] for m in order])
axs[0].set_xlim(0.03, 0.15)
axs[0].set_title("Relative MAE", fontsize=7.5, pad=22, loc="left"); axs[1].set_title("Relative bias", fontsize=7.5, pad=22, loc="left")
for y, m in zip(yy, order):
    v1, v2, v3 = [L.v("method.%s.%s.relMAE_median" % (m, c)) for c in ("R1", "R2ISO", "w1620")]
    axs[0].text(0.112, y, ("%+.3f  %+.3f" % (v2 - v1, v3 - v1)).replace("-", "\u2212"), fontsize=7, va="center", ha="left", color=INK2, clip_on=False)
axs[0].text(0.112, len(order) - 0.15, "R2-ISO  16:00 window", fontsize=7, va="bottom", ha="left", color=INK2)
axs[0].text(0.112, len(order) + 0.2, "difference from primary", fontsize=7, va="bottom", ha="left", color=INK2)
from matplotlib.lines import Line2D
h = [Line2D([], [], marker=mk, ls="", color=INK2, mfc=INK2 if c == "R1" else "white", mew=1.0, ms=5, label=lab) for c, lab, mk, a in conds]
fig.legend(handles=h, loc="lower center", ncol=3, fontsize=7, handletextpad=0.3, bbox_to_anchor=(0.5, -0.1))
panel(axs[0], "a", dx=-0.3, dy=1.17); panel(axs[1], "b", dx=-0.12, dy=1.17)
fig.text(0.5, -0.14, "Secondary sensitivity analyses, 2017; filled circle = primary rule. H4 and H5 sensitivity not computed.", ha="center", va="top", fontsize=7, color=INK2)
L.report()
save(fig, "fig_13_sensitivity")
