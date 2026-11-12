"""Figure 7: p* (relMAE reaches 10 %) and p-cross (equals SCM-ridge's no-injection error) by method, 4 h and 2 h shapes."""
from common import *
from matplotlib.lines import Line2D

style()
L = Ledger()
meths = ["pjm0", "pjmA", "caisoA", "nyA", "isoneA", "dmA", "wmA", "cg0", "cgA", "scmR", "scmC"]   # by information set: I-hist, I-morn, I-donor
CAPPED = {"caisoA", "nyA", "dmA", "wmA"}   # ratio rules clipped (T2 caps)
fig, axs = plt.subplots(1, 2, figsize=(W15, 4.2), sharey=True, gridspec_kw=dict(wspace=0.08))
yy = np.arange(len(meths))[::-1]


def draw(ax, key, y, c, filled):
    if not L.has(key):
        return
    r = L.row(key); v = r["value"]
    if v.startswith(">"):
        ax.annotate("", xy=(0.318, y), xytext=(0.30, y), arrowprops=dict(arrowstyle="-|>", color=c, lw=1.1, mutation_scale=7))
        return
    x = float(v)
    if r["ci_low"]:
        ax.plot([float(r["ci_low"]), float(r["ci_high"])], [y, y], color=c, lw=1.3)
    ax.plot(x, y, "o" if filled else "D", color=c if filled else "white", mec=c, mew=1.1, ms=5 if filled else 4.5, zorder=3)


for ax, sh, ttl in zip(axs, ("4h", "2h"), ("Four-hour shape", "Two-hour shape")):
    for y, m in zip(yy, meths):
        draw(ax, "pstar.%s.%s" % (m, sh), y + 0.17, FAMILY[m], True)
        if m != "scmR":
            draw(ax, "pcross.%s.%s" % (m, sh), y - 0.17, FAMILY[m], False)
    ax.axvspan(0, 0.10, color=GREY, alpha=0.10, lw=0); ax.axvline(0.10, color=INK2, lw=0.7, ls="--")
    ax.text(0.05, len(meths) - 0.35, "realistic band", ha="center", va="bottom", fontsize=7, color=INK2)
    ax.set_xlim(0, 0.33); ax.set_ylim(-0.7, len(meths) - 0.3)
    ax.set_title(ttl, fontsize=7.5, pad=14); ax.grid(axis="x", lw=0.4, alpha=0.7)
    ax.set_xticks([0, 0.1, 0.2, 0.3])
axs[0].set_yticks(yy); axs[0].set_yticklabels([NAME[m] + (" (reference)" if m == "scmR" else "") + (" (capped)" if m in CAPPED else "") for m in meths])
panel(axs[0], "a", dx=-0.45, dy=1.06); panel(axs[1], "b", dx=-0.03, dy=1.06)
h = [Line2D([0], [0], marker="o", color=INK2, lw=1.2, ls="-", ms=5, label=r"10 %-error threshold $p^{\star}$: relMAE reaches 10 %"),
     Line2D([0], [0], marker="D", color=INK2, markerfacecolor="white", lw=1.2, ms=4.5, label=r"break-even pre-event increase $p^{\times}$ (building-pooled): reaches SCM-ridge error at $p=0$"),
     Line2D([0], [0], marker=">", color=INK2, lw=0, ms=4, label="not reached up to p = 0.30")]
fig.legend(handles=h, loc="lower center", ncol=1, bbox_to_anchor=(0.5, -0.12), fontsize=7)
fig.text(0.5, 0.0, "Injected pre-event increase p (bars: 95 % interval)", ha="center", va="top", fontsize=7.5, transform=fig.transFigure) if False else None
fig.supxlabel("Injected pre-event load increase p (bars: 95 % interval)", fontsize=7.5, y=0.02)
L.report()
save(fig, "fig_07_pstar")
