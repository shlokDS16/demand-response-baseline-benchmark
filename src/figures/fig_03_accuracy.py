"""Figure 3: hot-day (R1) relative MAE by method, building level distribution plus site medians."""
import sys
import pandas as pd
sys.path.insert(0, str(ROOT_SRC := __import__("pathlib").Path(__file__).resolve().parents[1]))
from common import *
from run import adjust, analysis as AN, config as C   # read-only import of the frozen package

style()
L = Ledger()
R1 = pd.read_pickle(RUN / "events_R1.pkl")
s, e = C.WINDOWS["primary"]
b = adjust.adjusted(R1, s, e)
order = ["prev", "pjm0", "pjmA", "caiso0", "caisoA", "ny0", "nyA", "isone0", "isoneA", "dm0", "dmA", "wm0", "wmA", "m3", "mid8",
         "cg0", "cgA", "scmR", "scmC"]
order = [m for m in order if m in b and np.isfinite(b[m]).any()]
vals, sitem, bvals = {}, {}, {}
for m in order:
    ok = AN.pair_events(R1, b, [m])
    rel = AN.bld_stat(R1, b, m, ok, "relMAE")
    vals[m] = rel.values
    sitem[m] = rel.groupby(level=0).median().values
    bias = AN.bld_stat(R1, b, m, ok, "bias")
    bvals[m] = bias.values
    key = "method.%s.R1.relMAE_median" % m
    assert abs(np.median(rel.values) - L.v(key)) < 1e-9, (m, np.median(rel.values), L.v(key))
    assert abs(np.median(bias.values) - L.v("method.%s.R1.bias_median" % m)) < 1e-9, m
    L.v("method.%s.R1.support_share" % m)
assert np.allclose(vals["caiso0"], vals["isone0"], rtol=0, atol=1e-12), "CAISO and ISO-NE differ"
n_dm = int((np.abs(b["caiso0"] - b["dm0"]) > 1e-12).sum()); n_ev = len(R1)
print("caiso0 == isone0 (atol 1e-12): True; dm0 differs from caiso0 in %d of %d events" % (n_dm, n_ev))
order.remove("isone0")
fam_rank = lambda m: 0 if m == "prev" else (1 if FAMILY[m] == BLUE else (2 if FAMILY[m] == VERM else 3))
order = sorted(order, key=lambda m: (fam_rank(m), np.median(vals[m])))
NAME["caiso0"] = "CAISO = ISO-NE"
del R1, b
fig, axs = plt.subplots(1, 2, figsize=(W2, 4.6), sharey=True, gridspec_kw=dict(width_ratios=[1.25, 1], wspace=0.06))
ax, bx = axs
yy = np.arange(len(order))[::-1]
rng = np.random.default_rng(1)
import matplotlib.ticker as mt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
for y, m in zip(yy, order):
    col = FAMILY[m]; hatch = "////" if col == GREEN else None
    v = np.clip(vals[m], 1e-3, None)
    bp = ax.boxplot(v, positions=[y], vert=False, widths=0.55, whis=(5, 95), showfliers=False, patch_artist=True,
                    medianprops=dict(color="black", lw=1.2), boxprops=dict(facecolor=col, alpha=0.35, edgecolor=col, lw=0.8, hatch=hatch),
                    whiskerprops=dict(color=col, lw=0.8), capprops=dict(color=col, lw=0.8))
    ax.scatter(sitem[m], y + rng.uniform(-0.18, 0.18, len(sitem[m])), s=9, color=col, edgecolor="white", linewidth=0.4, zorder=3)
    bv = bvals[m]
    bp2 = bx.boxplot(bv, positions=[y], vert=False, widths=0.55, whis=(5, 95), showfliers=False, patch_artist=True,
                     medianprops=dict(color="black", lw=1.2), boxprops=dict(facecolor=col, alpha=0.35, edgecolor=col, lw=0.8, hatch=hatch),
                     whiskerprops=dict(color=col, lw=0.8), capprops=dict(color=col, lw=0.8))
ax.set_xscale("log"); ax.set_xlim(0.011, 0.55)
ax.set_yticks(yy); ax.set_yticklabels([NAME[m] for m in order])
tk = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
ax.set_xticks(tk); ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: "%g" % v)); ax.xaxis.set_minor_formatter(mt.NullFormatter())
ax.set_xlabel("Relative MAE per building (log scale)")
ax.axvline(0.10, color=INK2, lw=0.7, ls="--")
bx.axvline(0, color=INK2, lw=0.8); bx.set_xlim(-0.3, 0.4)
bx.set_xlabel("Signed relative bias per building")
h = [Patch(fc=GREY, alpha=0.5, label="trivial (prev)"), Patch(fc=BLUE, alpha=0.5, label="own history (I-hist)"),
     Patch(fc=VERM, alpha=0.5, label="own history + morning (I-morn)"), Patch(fc=GREEN, alpha=0.5, hatch="////", label="donors (I-donor)"),
     Line2D([0], [0], color="black", lw=1.2, label="median of buildings"),
     Line2D([0], [0], marker="o", color="w", markerfacecolor=INK2, markersize=4, label="site median (11 sites)")]
ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.62, -0.13), ncol=3, fontsize=7)
for a_ in axs: a_.grid(axis="x", lw=0.4, alpha=0.7)
panel(ax, "a", dx=-0.3); panel(bx, "b", dx=-0.02)
L.report()
save(fig, "fig_03_accuracy")
