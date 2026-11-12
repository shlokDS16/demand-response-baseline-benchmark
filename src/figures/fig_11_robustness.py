"""Figure 11: robustness of H1-H5: leave-one-site-out range and p-values by test."""
from common import *

style()
L = Ledger()
H = [("H1", "H1.delta_bias.pjm0", "H1.loso_min", "H1.loso_max", "H1.p_signedrank", "H1.p_wcb", "H1.p_holm", "hot minus random bias"),
     ("H2", "H2.logratio.pjmA_pjm0", "H2.loso_min", "H2.loso_max", "H2.p_signedrank", "H2.p_wcb", "H2.p_holm", "log ratio of rel. MAE"),
     ("H3", "H3.logratio.cgA_pjmA", "H3.loso_min", "H3.loso_max", "H3.p_tost", None, "H3.p_holm", "log ratio of rel. MAE"),
     ("H4", "H4.median_site_pcross", "H4.loso_min", "H4.loso_max", "H4.p_signedrank", "H4.p_wcb", "H4.p_holm", "median site\nbreak-even"),
     ("H5", "H5.eta_diff", "H5.loso_min", "H5.loso_max", "H5.p_signedrank", "H5.p_wcb", "H5.p_holm", "error growth\nper dispatch")]
fig = plt.figure(figsize=(W2, 3.0))
gs = fig.add_gridspec(2, 5, height_ratios=[0.7, 1.3], hspace=0.9, wspace=0.55)
for i, (h, est, lo, hi, psr, pw, ph, unit) in enumerate(H):
    ax = fig.add_subplot(gs[0, i])
    e = L.v(est); a, b = L.v(lo), L.v(hi)
    ck = {"H3": "H3.ci_boot_conditional"}.get(h, est)
    cl, ch = L.ci(ck)
    ax.plot([cl, ch], [0, 0], color="black", lw=1.0, solid_capstyle="butt", zorder=1)
    ax.plot([cl, cl], [-0.15, 0.15], color="black", lw=1.0); ax.plot([ch, ch], [-0.15, 0.15], color="black", lw=1.0)
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((a, -0.3), max(b - a, 1e-12), 0.6, fc=BLUE, ec=BLUE, lw=0.8, alpha=0.85, zorder=2))
    ax.plot(e, 0, "D", mfc="white", mec="black", mew=1.2, ms=5, zorder=5)
    lo_, hi_ = min(cl, a, e), max(ch, b, e); pad = (hi_ - lo_) * 0.08
    ax.set_xlim(lo_ - pad, hi_ + pad); ax.set_ylim(-1, 1); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_title(h, fontsize=7.5)
    ax.set_xlabel(unit, fontsize=7)
    ax.tick_params(axis="x", labelsize=7)
    ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=2, steps=[1, 2, 5, 10]))
    if i == 0:
        panel(ax, "a", dx=-0.2, dy=1.2)
bx = fig.add_subplot(gs[1, :])
xs = np.arange(len(H))
for i, (h, est, lo, hi, psr, pw, ph, unit) in enumerate(H):
    p1 = L.v(psr); bx.plot(i - 0.12, p1, "o", color=BLUE, ms=5)
    if pw:
        bx.plot(i + 0.12, L.v(pw), "s", color=VERM, ms=5)
    bx.plot(i, L.v(ph), "_", color="black", ms=14, mew=1.5)
nS = int(L.v("sample.n_sites")); floor = 0.5 ** nS
bx.set_yscale("log"); bx.set_xticks(xs); bx.set_xticklabels([h[0] + (" (TOST)" if h[0] == "H3" else "") for h in H])
bx.set_xlim(-0.6, len(H) - 0.4); bx.set_ylim(floor * 0.3, 0.3); bx.set_ylabel("p-value (log scale)")
nS = int(L.v("sample.n_sites")); floor = 0.5 ** nS
bx.axhline(floor, color=GREY, lw=0.8, ls=":"); bx.text(-0.55, floor, "exact p floor, %d sites (1/%d)" % (nS, 2 ** nS), fontsize=7, color=INK2, va="bottom", ha="left")
bx.axhline(0.05, color=INK2, lw=0.6, ls="--"); bx.text(len(H) - 0.42, 0.05, "0.05", fontsize=7, color=INK2, va="bottom", ha="right")
bx.grid(axis="y", lw=0.4, alpha=0.7)
from matplotlib.lines import Line2D
bx.legend(handles=[Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, ms=5, label="exact test (signed-rank; sign test for H4; TOST for H3)"),
                   Line2D([0], [0], marker="s", color="w", markerfacecolor=VERM, ms=5, label="wild cluster bootstrap (tests the site mean, a different estimand)"),
                   Line2D([0], [0], marker="_", color="black", ms=10, mew=1.5, ls="", label="Holm-adjusted (primary)")],
          loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.22), columnspacing=1.2, handletextpad=0.4, fontsize=7)
panel(bx, "b", dx=-0.06)
L.report()
save(fig, "fig_11_robustness")
