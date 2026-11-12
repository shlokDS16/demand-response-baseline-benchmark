"""Figure 4: hot-day (R1) vs random-weekday (R3) bias per rule, site medians connected."""
import sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import *
from run import adjust, analysis as AN, config as C

style()
L = Ledger()
st = load_pkl("results_state.pkl")
s, e = C.WINDOWS["primary"]
rules = [("pjm0", "PJM (primary)", "H1.delta_bias.pjm0", st["core"]["H1"]["R1_bias_site"]),
         ("ny0", "NYISO", "H1s.delta_bias.ny", st["core"]["secondary_rules"]["H1s.ny"]["R1_bias_site"]),
         ("caiso0", "CAISO", "H1s.delta_bias.caiso", st["core"]["secondary_rules"]["H1s.caiso"]["R1_bias_site"]),
         ("isone0", "ISO-NE", "H1s.delta_bias.isone", st["core"]["secondary_rules"]["H1s.isone"]["R1_bias_site"])]
del st
R3 = pd.read_pickle(RUN / "events_R3.pkl")
draws = []
for _, g in R3.groupby("draw"):
    g = g.reset_index(drop=True)
    bb = adjust.adjusted(g, s, e)
    d = {}
    for m, *_ in rules:
        ok = AN.pair_events(g, bb, [m])
        d[m] = AN.bld_stat(g, bb, m, ok, "bias")
    draws.append(d)
del R3
r3 = {m: AN.site_median(pd.concat([d[m] for d in draws], axis=1).mean(axis=1, skipna=True)) for m, *_ in rules}
sites = L.v("sample.sites").split(",")
assert all(abs(r3["caiso0"][x] - r3["isone0"][x]) < 1e-12 for x in sites)
assert abs(L.v("H1s.delta_bias.caiso") - L.v("H1s.delta_bias.isone")) < 1e-12
rules = [r for r in rules if r[0] != "isone0"]
rules[2] = ("caiso0", "CAISO = ISO-NE", rules[2][2], rules[2][3])
fig, axs = plt.subplots(1, 3, figsize=(W15, 2.9), sharey=True, gridspec_kw=dict(wspace=0.12))
for ax, (m, title, key, r1) in zip(axs, rules):
    delta = L.v(key); lo, hi = L.ci(key)
    for si in sites:
        a, b = r3[m][si], r1[si]
        ax.plot([0, 1], [a, b], color=BLUE if b < a else GREY, lw=0.8, alpha=0.8, marker="o", ms=3, mec="white", mew=0.3)
    ax.plot([0, 1], [np.median([r3[m][x] for x in sites]), np.median([r1[x] for x in sites])], color="black", lw=1.8, marker="D", ms=4, zorder=4)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_ylim(-0.17, 0.30)
    for si in sites:
        top = max(r3[m][si], r1[si])
        if top > 0.30:
            ax.annotate("R3 %.2f" % r3[m][si] if r3[m][si] > 0.30 else "R1 %.2f" % r1[si], xy=(min(1, max(0, (r3[m][si] - 0.30) / (r3[m][si] - r1[si]))), 0.30), xytext=(0.45, 0.28), fontsize=7, color=INK2, ha="center", va="top",
                        arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
    ax.set_xlim(-0.35, 1.35); ax.set_xticks([0, 1]); ax.set_xticklabels(["random\nweekday", "hot\nday"])
    ax.set_title(title + chr(10) + "H1 = %.3f" % delta, fontsize=7.5)
axs[0].set_ylabel("Median relative bias")
axs[0].annotate("", xy=(-0.25, -0.15), xytext=(-0.25, -0.02), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9), annotation_clip=False)
axs[0].text(-0.2, -0.125, "under-prediction" + chr(10) + "(e = B - L < 0)", fontsize=7, color=INK2, va="center", ha="left")
axs[0].annotate("", xy=(-0.25, 0.29), xytext=(-0.25, 0.04), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9), annotation_clip=False)
axs[0].text(-0.2, 0.275, "over-prediction", fontsize=7, color=INK2, va="center", ha="left")
note = "Lines: 11 sites (blue = more negative on hot days); black: median over sites." + chr(10) + "H1 = hot-day minus random-weekday bias; e = B - L (Granderson et al. use the opposite sign)." + chr(10) + "Arrow at the top: value of the point above the axis"
fig.text(0.5, -0.11, note, ha="center", va="top", fontsize=7, color=INK2)
L.report()
save(fig, "fig_04_h1_bias")
