"""Figure 5 (REVISION_1): H3 site log ratios in the main text (fig_05_h3_forest) and the H2 replication panel moved to the
supplement (fig_15_h2_forest). Same data and drawing as the earlier two-panel fig_05_h2_h3_forest."""
from common import *

style()
L = Ledger()
D = Ledger("summary_derived.csv")
sites = L.v("sample.sites").split(",")
MINUS = "−"


def forest(ax, prefix, est_key, ci, color, xlabel, margin=None, pooled_label="Pooled (median of sites)"):
    vals = {s_: L.v("%s.site.%s" % (prefix, s_)) for s_ in sites}
    order = sorted(sites, key=lambda x: vals[x])
    ys = np.arange(len(order) + 2)[::-1]
    if margin is not None:
        ax.axvspan(-margin, margin, color=color, alpha=0.12, lw=0)
        ax.axvline(-margin, color=color, lw=0.7, ls="--"); ax.axvline(margin, color=color, lw=0.7, ls="--")
    ax.axvline(0, color=INK2, lw=0.7)
    for y, s_ in zip(ys[2:], order):
        v = vals[s_]
        inside = margin is None or abs(v) <= margin
        ax.plot(v, y, "o", color=color if inside else "white", mec=color, mew=1.2, ms=5)
    est = L.v(est_key); lo, hi = ci
    ax.errorbar(est, ys[0], xerr=[[est - lo], [hi - est]], fmt="D", color="black", ms=5, capsize=3, lw=1.2)
    ax.axhline(ys[1], color=GRID, lw=0.6)
    ax.set_yticks(list(ys[2:]) + [ys[0]]); ax.set_yticklabels(order + [pooled_label])
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", lw=0.4, alpha=0.7)
    return vals, est


# ---------------- main text: H3 ----------------
fig, ax = plt.subplots(figsize=(W1 * 1.25, 3.5))
margin = L.v("H3.margin")
v3, e3 = forest(ax, "H3", "H3.logratio.cgA_pjmA", L.ci("H3.ci90"), GREEN,
                "Log ratio of relative MAE, CG-adj / PJM-adj", margin=margin, pooled_label="Location of site log ratios")
n_out = sum(abs(v) > margin for v in v3.values())
assert n_out == int(D.v("derived.H3.n_sites_outside_margin")), n_out
share_in = D.v("derived.H3.share_sites_inside_margin"); s_lo, s_hi = D.ci("derived.H3.share_sites_inside_margin")
ticks = [-0.2, -0.1, 0, 0.1, 0.2]
ax.set_xticks(ticks)
ax.set_xticklabels([("%g" % t).replace("-", MINUS) for t in ticks])
ax.text(0.98, 1.02, "share of sites inside margin: %.2f [%.2f, %.2f]" % (share_in, s_lo, s_hi), transform=ax.transAxes,
        ha="right", va="bottom", fontsize=7, color=INK2)
ax.set_xlabel(ax.get_xlabel() + chr(10) + "band: ±log(1.10) margin; bar: 90 % interval" + chr(10)
              + "open markers: outside margin ({} of {})".format(n_out, int(L.v("sample.n_sites"))))
save(fig, "fig_05_h3_forest")

# ---------------- supplement: H2 ----------------
fig, ax = plt.subplots(figsize=(W1 * 1.25, 3.4))
forest(ax, "H2", "H2.logratio.pjmA_pjm0", L.ci("H2.logratio.pjmA_pjm0"), VERM,
       "Log ratio of relative MAE, PJM-adj / PJM (< 0: adjustment helps)", pooled_label="Location of site log ratios")
tk = [-0.8, -0.6, -0.4, -0.2, 0]
ax.set_xticks(tk); ax.set_xticklabels([("%g" % t).replace("-", MINUS) for t in tk])
ax.set_xlabel(ax.get_xlabel() + chr(10) + "bar: 95 % Hodges-Lehmann interval")
L.report(); D.report()
save(fig, "fig_15_h2_forest")
