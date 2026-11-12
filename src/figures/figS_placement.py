"""Supplement figure figS_placement (D29 item 5): break-even pre-event increase of PJM-adj against SCM-ridge, by site,
when the shaping covers all three adjustment hours (H4, four-hour, s-4..s-1) versus when it ends before them (early shape a,
s-7..s-4, exploratory). Numbers only from ledger keys H4.site.*, exploratory.early_shape.a.pcross_samep.site.*."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

style()
P = MultiLedger()
sites = P.v("sample.sites").split(",")
GRIDMAX = 30.0   # the grid maximum (percent); ">0.30" in the ledger marks a break-even above it
over, early, cens = {}, {}, {}
for s in sites:
    over[s] = 100 * P.v("H4.site.%s" % s)
    e = P.v("exploratory.early_shape.a.pcross_samep.site.%s" % s)
    if isinstance(e, str):
        assert e.strip() == ">0.30", e
        early[s], cens[s] = GRIDMAX, True
    else:
        early[s], cens[s] = 100 * e, False
order = sorted(sites, key=lambda s: over[s])

fig, ax = plt.subplots(figsize=(W15, 3.3))
ax.axvline(10, color=INK2, lw=0.8, ls="--", zorder=1)
ax.text(10.4, len(order) - 0.45, "10 % reference", fontsize=7, color=INK2, va="bottom", ha="left")
for i, s in enumerate(order):
    ax.plot([over[s], early[s]], [i, i], color=GRID, lw=1.4, zorder=2, solid_capstyle="round")
    ax.plot(over[s], i, "o", color=VERM, ms=5, mec="white", mew=0.5, zorder=4)
    if cens[s]:
        ax.annotate("", xy=(GRIDMAX + 1.2, i), xytext=(GRIDMAX - 0.5, i), zorder=4,
                    arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=0.9, shrinkA=0, shrinkB=0))
        ax.plot(GRIDMAX - 0.5, i, "o", color=BLUE, ms=5, mec="white", mew=0.5, zorder=3)
    else:
        ax.plot(early[s], i, "s", color=BLUE, ms=7.5, mec="white", mew=0.5, zorder=3)
ax.set_yticks(range(len(order))); ax.set_yticklabels(order)
ax.set_ylim(-0.7, len(order) - 0.1)
ax.set_xlim(-0.8, GRIDMAX + 2.5)
ax.set_xticks([0, 5, 10, 15, 20, 25, 30])
ax.set_xlabel("Break-even pre-event load increase (%)")
ax.spines["left"].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", lw=0.4, alpha=0.7, zorder=0)
h = [plt.Line2D([], [], marker="o", color=VERM, ls="", ms=5, label="Shaping covers all three adjustment hours (H4, s$-$4 to s$-$1)"),
     plt.Line2D([], [], marker="s", color=BLUE, ls="", ms=6.5, label="Shaping shifted earlier: covers only the first adjustment hour (s$-$7 to s$-$4)")]
ax.legend(handles=h, loc="lower right", fontsize=7, handletextpad=0.3, borderaxespad=0.2, frameon=True, facecolor="white", edgecolor="none", framealpha=1)
fig.tight_layout()
save(fig, "figS_placement")
nb = sum(1 for s in sites if early[s] < 10)
print("sites with early-shape break-even below 10 %:", nb, "; censored (>30 %):", [s for s in sites if cens[s]])
P.report()
