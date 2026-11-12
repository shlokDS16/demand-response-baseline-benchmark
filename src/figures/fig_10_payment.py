"""Figure 10: payment error ratio at c = 10 % by method on hot days (R1)."""
from common import *

style()
L = Ledger()
order = ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "isone0", "isoneA", "dm0", "dmA", "wm0", "wmA", "m3", "mid8", "cg0", "cgA", "scmR", "scmC"]
for k in ("PER_c10_median", "share_PER_gt_0_5", "relMAE_median", "bias_median"):
    assert abs(L.v("method.caiso0.R1.%s" % k) - L.v("method.isone0.R1.%s" % k)) < 1e-12
order.remove("isone0")
NAME["caiso0"] = "CAISO = ISO-NE"
per = {m: L.v("method.%s.R1.PER_c10_median" % m) for m in order}
sh = {m: L.v("method.%s.R1.share_PER_gt_0_5" % m) for m in order}
order = sorted(order, key=lambda m: per[m])   # sorted by median PER
fig, axs = plt.subplots(1, 2, figsize=(W15, 4.0), sharey=True, gridspec_kw=dict(wspace=0.1))
yy = np.arange(len(order))[::-1]
for ax, d, xl, scale, fmt in ((axs[0], per, "Median PER (c = 10 %)", 1, "%.2f"), (axs[1], sh, "Events with PER > 0.5 (%)", 100, "%.0f")):
    for y, m in zip(yy, order):
        v = d[m] * scale
        ax.hlines(y, 0, v, color=FAMILY[m], lw=1.3, alpha=0.5)
        ax.plot(v, y, "o", color=FAMILY[m], ms=5, mec="white", mew=0.4, zorder=3)
        ax.text(v + 0.012 * (max(d.values()) * scale), y, fmt % v, va="center", fontsize=7, color=INK2, bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.9), zorder=4)
    ax.axvline(0.5 * scale if scale == 1 else 50, color=INK2, lw=0.8, ls="--", zorder=0)
    ax.set_xlabel(xl); ax.set_xlim(0, max(d.values()) * scale * 1.2); ax.grid(axis="x", lw=0.4, alpha=0.7)
axs[0].set_yticks(yy); axs[0].set_yticklabels([NAME[m] for m in order])
fig.text(0.5, -0.01, "CAISO = ISO-NE: identical 10-day mean", ha="center", va="top", fontsize=7, color=INK2)
panel(axs[0], "a", dx=-0.4); panel(axs[1], "b", dx=-0.03)
L.report()
save(fig, "fig_10_payment")
