"""Figure 14: screening tree (depth 2; trained on 2016, tested on 2017 with 2016-only features): rules, class shares, site log ratio vs pjmA (secondary)."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

style()
S = Ledger("summary_secondary.csv")
SITES = ["Bear", "Bull", "Cockatoo", "Eagle", "Fox", "Hog", "Lamb", "Peacock", "Rat", "Robin", "Wolf"]
fig = plt.figure(figsize=(W15, 5.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.3, wspace=0.4, width_ratios=[1.45, 1])
# (a) tree rules, drawn as a depth-2 tree parsed from the ledger text
rules = S.v("screen.tree.rules")
ax = fig.add_subplot(gs[0, 0]); ax.axis("off")
lines = [l for l in rules.splitlines() if l.strip()]
cond = [l.split("--- ")[1] for l in lines if "class:" not in l]
leaf = [l.split("class: ")[1].strip() for l in lines if "class:" in l]
assert len(cond) == 6 and len(leaf) == 4
condL, condR = cond[1], cond[4]; cond = [cond[0], cond[1], cond[4]]
labL = ["left: " + cond[1] + " / " + condL] if False else None
cc = {"pjmA": VERM, "scmR": GREEN, "cgA": GREEN}
def box(x, y, t, c=INK, w=0.44):
    ax.text(x, y, t, ha="center", va="center", fontsize=7, color=c, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=c, lw=0.8), transform=ax.transAxes)
box(0.5, 0.88, cond[0].replace("<=", "\u2264").replace("slope_rel", "slope_rel"))
box(0.25, 0.5, cond[1].replace("<=", "\u2264")); box(0.75, 0.5, cond[2].replace("<=", "\u2264"))
for x0, x1, y0, y1 in ((0.5, 0.25, 0.8, 0.58), (0.5, 0.75, 0.8, 0.58)):
    ax.plot([x0, x1], [y0, y1], color=INK2, lw=0.7, transform=ax.transAxes)
ax.text(0.34, 0.72, "yes", fontsize=7, color=INK2, ha="right", transform=ax.transAxes); ax.text(0.66, 0.72, "no", fontsize=7, color=INK2, ha="left", transform=ax.transAxes)
for i, (x, l) in enumerate(zip((0.08, 0.36, 0.67, 0.95), leaf)):
    xp = 0.25 if i < 2 else 0.75
    ax.plot([xp, x], [0.42, 0.17], color=INK2, lw=0.7, transform=ax.transAxes)
    box(x, 0.1, NAME[l], cc[l])
ax.text(0.5, -0.12, "n = %d buildings (2016); training accuracy %.2f" % (int(S.v("screen.tree.n_train")), S.v("screen.tree.train_accuracy")), ha="center", fontsize=7, color=INK2, transform=ax.transAxes)
panel(ax, "a", dx=-0.05, dy=1.0)
# (b) class shares
b = fig.add_subplot(gs[0, 1])
cl = ["pjmA", "cgA", "scmR"]; x = np.arange(3); w = 0.36
b.bar(x - w / 2, [100 * S.v("screen.train.class_share." + m) for m in cl], w, color=[cc[m] for m in cl], alpha=0.45, edgecolor="white", label="Training best-method share (2016)")
b.bar(x + w / 2, [100 * S.v("screen.test.assigned_share." + m) for m in cl], w, color=[cc[m] for m in cl], edgecolor="white", label="Test assignment (2017)")
b.set_xticks(x); b.set_xticklabels([NAME[m] for m in cl]); b.set_ylabel("Share of buildings (%)"); b.set_ylim(0, 100)
from matplotlib.patches import Patch
b.legend(handles=[Patch(fc=INK2, alpha=0.45, label="light: 2016 train"), Patch(fc=INK2, label="dark: 2017 test")], loc="lower right", fontsize=7, bbox_to_anchor=(1.05, 1.0), ncol=2, handlelength=1.0, columnspacing=0.8, handletextpad=0.4)
b.grid(axis="y", lw=0.4, alpha=0.7); b.set_axisbelow(True)
panel(b, "b", dx=-0.32, dy=0.97)
# (c) site log ratios
c = fig.add_subplot(gs[1, :])
v = [S.v("screen.test.site." + s) for s in SITES]
xs = np.arange(len(SITES))
c.axhline(0, color=INK2, lw=0.7)
c.vlines(xs, 0, v, color=GREY, lw=1.0); c.plot(xs, v, "o", color=PURPLE, ms=5, mec="white", mew=0.5, zorder=3)
c.set_xticks(xs); c.set_xticklabels(SITES, rotation=30, ha="right", fontsize=7); c.set_ylim(-0.02, 0.005)
c.set_ylabel("Site median log ratio\n(tree choice vs PJM-adj)")
med = S.v("screen.test.logratio_site_median_of_medians"); pooled = S.v("screen.test.pooled_relMAE_chosen_over_pjmA")
c.text(0.99, 0.97, "median over %d sites = %.3f; pooled relMAE ratio = %.3f; %d of %d sites better" % (int(S.v("screen.test.logratio_site_median_of_medians.n") if False else 11), med, pooled, int(S.v("screen.test.n_sites_better")), 11), transform=c.transAxes, ha="right", va="top", fontsize=7, color=INK2)
c.grid(axis="y", lw=0.4, alpha=0.7)
panel(c, "c", dx=-0.1)
S.report()
save(fig, "fig_14_screening")
