"""Figure 8: repeated-dispatch stress test: (a) absolute estimation error vs K, (b) signed rho vs K, (c) per-site slope differences.
Panel (a) site medians are recomputed from events_erosion.pkl (read-only) and asserted against the stored state; slopes and the other numbers come from the ledgers."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import *
from run import adjust, config as C

style()
L = Ledger(); S = Ledger("summary_secondary.csv"); D = Ledger("summary_derived.csv")
Ks = [10, 20, 30, 40]
meths = [("pjmA", VERM, "-", "o"), ("caisoA", VERM, "-", "s"), ("cgA", GREEN, "-", "D"), ("scmR", GREEN, "-", "^"), ("pjm0", BLUE, "-", "v")]
fig = plt.figure(figsize=(W2, 6.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.5, wspace=0.95, width_ratios=[1.3, 1])
ax = fig.add_subplot(gs[0, 0]); bx = fig.add_subplot(gs[0, 1]); cx = fig.add_subplot(gs[1, :])
ER = pd.read_pickle(RUN / "events_erosion.pkl")      # frozen run output, read-only
st = load_pkl("results_state.pkl")["erosion"]
sw, ew = C.WINDOWS["primary"]
base = {}
for K, g in ER.groupby("K"):
    g = g.reset_index(drop=True); base[K] = (g, adjust.adjusted(g, sw, ew))
del ER
key = lambda g: g.site + "|" + g.b + "|" + g.day
sets = []
for K in Ks:
    g, bb = base[K]; ok = np.isfinite(bb["pjmA"]) & np.isfinite(bb["scmR"]); sets.append(set(key(g)[ok]))
common = set.intersection(*sets)
sitemed = {}
for m, *_ in meths:
    rows_ = []
    for K in Ks:
        g, bb = base[K]
        ok = key(g).isin(common).values
        rho = (bb[m] - g.Lobs.values) / (C.C_PRIMARY * g.L.values)
        t = pd.DataFrame({"site": g.site, "b": g.b, "rho": rho})[ok]
        rows_.append(t.groupby(["site", "b"]).rho.mean().rename(K))
    tab = pd.concat(rows_, axis=1)
    assert np.allclose(tab.values, st["tab"][m].reindex(tab.index).values, atol=1e-9, equal_nan=True), m
    sitemed[m] = (tab - 1).abs().groupby(level=0).median().median(axis=0)
del base
# ---------------- (a) absolute error ----------------
ax.axvspan(19.5, 43, color=YELLOW, alpha=0.12, lw=0)
ends = []
for m, c, ls, mk in meths:
    y = sitemed[m].values
    ax.plot(Ks, y, color=c, ls=ls, marker=mk, ms=4.5, lw=1.3, zorder=3, mfc="white" if m in ("cgA", "pjm0") else c)
    ends.append((y[-1], m))
ends.sort(); lab = [e[0] for e in ends]
for _ in range(200):
    mv = False
    for i in range(1, len(lab)):
        d = lab[i] - lab[i - 1]
        if d < 0.075 - 1e-9:
            lab[i] += (0.075 - d) / 2; lab[i - 1] -= (0.075 - d) / 2; mv = True
    if not mv: break
for (y0, m), yl in zip(ends, lab):
    sl = S.v("H5.eta_abs.median_of_site_slopes.%s" % m)
    ax.plot([40.4, 41.5], [y0, yl], color=INK2, lw=0.5, zorder=1)
    ax.text(41.7, yl, ("%s (slope %+.4f)" % (NAME[m], sl)).replace("-0", "\u22120"), va="center", fontsize=7, color=INK)
ax.text(10, 0.84, chr(10).join(["$K=10$: upper end of", "documented annual", "event counts"]), fontsize=7, color=INK2, va="top", ha="left")
ax.text(30, 0.075, r"$K\geq 20$: stress", fontsize=7, color=INK2, va="bottom", ha="center")
ax.set_xlim(8, 43); ax.set_xticks(Ks); ax.set_xlabel("Dispatch count $K$ (stress test)")
ax.set_ylabel("Absolute estimation error\nmedian over sites of $|\\rho-1|$")
ax.set_ylim(0.05, 0.85)
ax.grid(axis="y", lw=0.4, alpha=0.7)
panel(ax, "a", dx=-0.17)
# ---------------- (b) signed rho ----------------
bx.axhline(1, color=INK2, lw=0.7)
bends = []
for m, c, ls, mk in meths:
    y = [L.v("H5.rho.%s.K%d" % (m, K)) for K in Ks]
    bx.plot(Ks, y, color=c, marker=mk, ms=4.5, lw=1.3, mfc="white" if m in ("cgA", "pjm0") else c)
    bends.append((y[-1], m))
bends.sort(); blab = [e[0] for e in bends]
for _ in range(200):          # spread end labels so that none overlap (REVISION_1)
    mv = False
    for i in range(1, len(blab)):
        d = blab[i] - blab[i - 1]
        if d < 0.045 - 1e-9:
            blab[i] += (0.045 - d) / 2; blab[i - 1] -= (0.045 - d) / 2; mv = True
    if not mv: break
for (y0, m), yl in zip(bends, blab):
    bx.plot([40.3, 41.2], [y0, yl], color=INK2, lw=0.5, zorder=1, clip_on=False)
    bx.text(41.4, yl, NAME[m], fontsize=7, va="center", color=INK)
bx.axvspan(19.5, 43, color=YELLOW, alpha=0.12, lw=0)
bx.set_xlim(8, 43); bx.set_xticks(Ks); bx.set_xlabel("Dispatch count $K$ (stress test)")
bx.set_ylabel("Signed ratio $\\rho$ (1 = unbiased)\nbuilding-pooled median")
bx.grid(axis="y", lw=0.4, alpha=0.7)
panel(bx, "b", dx=-0.25)
# ---------------- (c) per-site slope differences ----------------
sites = L.v("sample.sites").split(",")
vals = {s_: L.v("H5.site.%s" % s_) for s_ in sites}
order = sorted(sites, key=lambda x: vals[x])
xs = np.arange(len(order))
cx.axhline(0, color=INK2, lw=0.7)
cx.plot(xs, [vals[s_] for s_ in order], "o", color=GREEN, ms=5, mec="white", mew=0.5, zorder=3)
est = L.v("H5.eta_diff"); lo, hi = L.ci("H5.eta_diff")
cx.axhspan(lo, hi, color=GREY, alpha=0.2, lw=0)
cx.axhline(est, color="black", lw=1.0)
cx.text(2.0, hi + 0.0003, ("HL estimate %.4f [%.4f, %.4f]" % (est, lo, hi)).replace("-", "\u2212"), fontsize=7, va="bottom", ha="left", color=INK)
cx.set_xticks(xs); cx.set_xticklabels(order, rotation=30, ha="right")
cx.set_ylabel("Site slope difference\n(PJM-adj minus SCM-ridge, per dispatch)")
cx.grid(axis="y", lw=0.4, alpha=0.7)
n_faster = int(D.v("derived.H5.n_sites_scmR_faster"))
cx.text(0.01, 0.97, "SCM-ridge absolute error grows faster at %d of %d sites" % (n_faster, int(L.v("sample.n_sites"))), transform=cx.transAxes, fontsize=7, color=INK2, va="top")
panel(cx, "c", dx=-0.07)
L.report(); S.report(); D.report()
save(fig, "fig_08_dispatch")
