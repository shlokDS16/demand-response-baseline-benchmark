"""Figure 1: study design: (a) lookback and event day, (b) hours read versus shaped, (c) information sets, (d) example building-event (pipeline panel removed in Revision 1: Algorithm 4 covers it).
Panel (d) is drawn from results/run/events_R1.pkl (read-only): the median-error building-event of PJM-adj at the middle site (by event count).
No numbers are printed on the figure."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import textwrap
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle
from common import *
from run import adjust

style()
plt.rcParams.update({"font.size": 8.3, "axes.labelsize": 8.3, "xtick.labelsize": 8.3, "ytick.labelsize": 8.3, "legend.fontsize": 8.3})
L = Ledger()
# ------------- X10: choose the example building-event -------------
R1 = pd.read_pickle(RUN / "events_R1.pkl")
cnt = R1.site.value_counts().sort_values(ascending=False)
mid = cnt.index[len(cnt) // 2]                      # middle site by number of R1 building-events (6th of 11)
S = R1[R1.site == mid].reset_index(drop=True)
bb = adjust.adjusted(S, 14, 18)
S["pjmA"] = bb["pjmA"]; S["scmR"] = bb["scmR"]
S = S[np.isfinite(S.pjmA) & np.isfinite(S.scmR) & (S.L > 0)].copy()
S["err"] = (S.pjmA - S.L).abs() / S.L
med = S.err.median()
ex = S.iloc[int((S.err - med).abs().values.argmin())]
print("X10 example: site=%s building=%s day=%s; site median |relative error| of PJM-adj = %.4f, chosen event error = %.4f (closest to the median of %d events)"
      % (mid, ex.b, ex.day, med, ex.err, len(S)))
mrn = np.array(ex.morning, float); pj_m = np.array(ex.pjm0_m, float)
nw = 4
met_w, pjA_w, scm_w = ex.L / nw, ex.pjmA / nw, ex.scmR / nw
del R1

fig = plt.figure(figsize=(W2, 9.2))


def newax(y0, h, xl=100, yl=50):
    a = fig.add_axes([0.0, y0, 1.0, h]); a.set_xlim(0, xl); a.set_ylim(0, yl); a.axis("off"); return a


def title(a, t, y=49.5):
    a.text(0, y, t, fontsize=9.3, fontweight="bold", va="top")


# ---------------- (a) timeline ----------------
ax = newax(0.775, 0.225)
title(ax, "(a) One event day and the data each baseline may use")
ax.text(1, 38, "Lookback: past non-event weekdays", fontsize=8.3, va="bottom")
removed = {2, 3, 6}   # dispatched event days are removed from the lookback (schematic)
for i in range(10):
    ax.add_patch(Rectangle((1 + 3.9 * i, 20), 3.5, 14, fc="white", ec=INK2 if i in removed else GREY, lw=0.6, hatch="////" if i in removed else None))
    ax.text(1 + 3.9 * i + 1.75, 27, "d-%d" % (i + 1), ha="center", va="center", fontsize=8.3, color=INK,
            bbox=dict(fc="white", ec="none", pad=0.3) if i in removed else None)
ax.text(1, 15.5, "hatched: earlier dispatched event\ndays, removed from the lookback;\nrepeated dispatch pushes data back", fontsize=8.3, va="top", color=INK2)
ax.annotate("", xy=(44.5, 27), xytext=(41, 27), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.8))
x0, x1 = 46, 99
hx = lambda h: x0 + (h - 6) * (x1 - x0) / 16.0
ax.text((x0 + x1) / 2, 38, "Event day: estimate in the event window", ha="center", va="bottom", fontsize=8.3)
ax.add_patch(Rectangle((x0, 20), x1 - x0, 14, fc="white", ec=INK2, lw=0.6))
ax.add_patch(Rectangle((hx(10), 20), hx(13) - hx(10), 14, fc=VERM, alpha=0.30, ec="none", hatch="\\\\\\\\"))
ax.add_patch(Rectangle((hx(10), 20), hx(14) - hx(10), 4.5, fc=VERM, alpha=0.60, ec="none", hatch="...."))
ax.add_patch(Rectangle((hx(14), 20), hx(18) - hx(14), 14, fc=BLUE, alpha=0.22, ec="none"))
for h in range(6, 23, 2):
    ax.plot([hx(h)] * 2, [20, 19], color=INK2, lw=0.6); ax.text(hx(h), 18.2, "%d" % h, ha="center", va="top", fontsize=8.3, color=INK2)
ax.text((x0 + x1) / 2, 11.5, "hour of the event day (window starts at s = 14)", ha="center", fontsize=8.3, color=INK2)
ax.text((hx(10) + hx(13)) / 2, 30, "adjustment hours" + chr(10) + "s-4 to s-2", ha="center", va="center", fontsize=8.3, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.85))
ax.text((hx(10) + hx(14)) / 2, 22.2, "pre-event 4 h", ha="center", va="center", fontsize=8.3, bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.85))
ax.text((hx(14) + hx(18)) / 2, 27, "event window\n14 to 18 h", ha="center", va="center", fontsize=8.3)
ax.text(1, 1.5, "Curtailment estimate = baseline - metered load; payment error = |error| / (value of a 10 % curtailment).", fontsize=8.3, va="top", color=INK2)

# ---------------- (b) hours read versus shaped ----------------
bx = newax(0.575, 0.19)
title(bx, "(b) Hours each baseline reads (filled) and hours a participant can shape (shaded)")
rows = [("PJM-adj", VERM, [(10, 13)]), ("CAISO-adj", VERM, [(10, 13)]), ("NYISO-adj", VERM, [(10, 12)]), ("ISO-NE-adj", VERM, [(11, 13)]),
        ("CG-adj", GREEN, [(10, 13)]), ("SCM-ridge", GREEN, [(8, 10)])]
lx0, lx1 = 14, 98
gx = lambda h: lx0 + (h - 6) * (lx1 - lx0) / 16.0
top, rh = 41, 5.0
bx.add_patch(Rectangle((gx(10), 7), gx(14) - gx(10), top - 7, fc=GREY, alpha=0.18, ec="none"))
bx.add_patch(Rectangle((gx(12), 7), gx(14) - gx(12), top - 7, fc=GREY, alpha=0.28, ec="none"))
bx.add_patch(Rectangle((gx(14), 7), gx(18) - gx(14), top - 7, fc=BLUE, alpha=0.12, ec="none"))
for i, (nm, c, segs) in enumerate(rows):
    y = top - (i + 1) * rh
    bx.text(lx0 - 1, y + (rh - 1.0) / 2, nm, ha="right", va="center", fontsize=8.3, color=INK)
    bx.add_patch(Rectangle((gx(6), y), gx(22) - gx(6), rh - 1.0, fc="white", ec=GRID, lw=0.5, zorder=1))
    for a, b_ in segs:
        bx.add_patch(Rectangle((gx(a), y), gx(b_) - gx(a), rh - 1.0, fc=c, ec="white", lw=0.5, zorder=3))
for h in range(6, 23, 2):
    bx.text(gx(h), 6, "%d" % h, ha="center", va="top", fontsize=8.3, color=INK2)
bx.text((lx0 + lx1) / 2, 0.5, "hour of the event day", ha="center", va="top", fontsize=8.3, color=INK2)
bx.text(gx(11), top + 0.8, "4 h shape", ha="center", va="bottom", fontsize=8.3, color=INK2)
bx.text(gx(13.2), top + 0.8, "2 h", ha="center", va="bottom", fontsize=8.3, color=INK)
bx.text(gx(16), top + 0.8, "event window", ha="center", va="bottom", fontsize=8.3, color=BLUE)

# ---------------- (c) information sets ----------------
cx = newax(0.355, 0.2)
title(cx, "(c) Three information sets and the methods in each")
cols = [(1, 31, "I-hist: own history only", BLUE, [("Unadjusted rules", "PJM, CAISO, NYISO, ISO-NE, DM, WM, M3, Mid8"), ("Trivial", "prev (previous weekday)")]),
        (35, 31, "I-morn: history + morning", VERM, [("Day-of adjusted rules", "PJM-adj (primary), CAISO-adj, NYISO-adj, ISO-NE-adj, DM-adj, WM-adj")]),
        (69, 30, "I-donor: other buildings", GREEN, [("Donor methods", "SCM-ridge (primary), SCM-classic, comparison group CG"), ("Donor + morning", "CG-adj (comparison group, adjusted)")])]
for x, w, t, col, items in cols:
    cx.add_patch(FancyBboxPatch((x, 2), w, 37, boxstyle="round,pad=0.0,rounding_size=1.2", fc="white", ec=col, lw=1.4))
    cx.add_patch(Rectangle((x, 32), w, 7, fc=col, alpha=0.18, ec="none"))
    cx.text(x + w / 2, 35.8, t, ha="center", va="center", fontsize=8.7, fontweight="bold")
    y = 31
    for head, body in items:
        cx.text(x + 1.2, y, head, fontsize=8.3, fontweight="bold", va="top", color=col)
        wr = "\n".join(textwrap.wrap(body, 30, break_on_hyphens=False))
        cx.text(x + 1.2, y - 3.8, wr, fontsize=8.3, va="top", color=INK)
        y -= 3.8 + 3.8 * (wr.count("\n") + 1) + 2.0

# ---------------- (d) example building-event ----------------
dx = fig.add_axes([0.08, 0.085, 0.78, 0.225])
hrs = np.arange(8, 14)
dx.plot(hrs + 0.5, mrn, color="black", lw=1.4, marker="o", ms=3, label="metered load")
dx.plot(hrs + 0.5, pj_m, color=BLUE, lw=1.0, ls="--", label="PJM profile (unadjusted)")
dx.axvspan(10, 13, color=VERM, alpha=0.18, lw=0); dx.axvspan(14, 18, color=BLUE, alpha=0.10, lw=0)
dx.hlines(met_w, 14, 18, color="black", lw=2.0); dx.hlines(pjA_w, 14, 18, color=VERM, lw=2.0); dx.hlines(scm_w, 14, 18, color=GREEN, lw=2.0)
dx.text(18.15, met_w, "metered window mean", fontsize=8.3, va="center")
dx.text(18.15, pjA_w - 0.3, "PJM-adj baseline", fontsize=8.3, va="top", color=VERM)
dx.text(18.15, scm_w + 0.3, "SCM-ridge baseline", fontsize=8.3, va="bottom", color=GREEN)
dx.annotate("", xy=(14.4, pjA_w), xytext=(14.4, met_w), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.8))
dx.text(14.55, 0.5 * (pjA_w + met_w), "baseline error", fontsize=8.3, va="center", color=INK2)
dx.text(11.5, 1.01, "adjustment hours", transform=dx.get_xaxis_transform(), fontsize=8.3, ha="center", va="bottom", color=VERM)
dx.text(16, 0.97, "event window", transform=dx.get_xaxis_transform(), fontsize=8.3, ha="center", va="top", color=BLUE)
dx.set_xlim(8, 23.5); dx.set_xticks(range(8, 19, 2)); dx.set_xlabel("hour of the event day"); dx.set_ylabel("load (kWh per hour)")
dx.legend(loc="upper right", fontsize=8.3); dx.grid(axis="y", lw=0.4, alpha=0.7)
fig.text(0.0, 0.335, "(d) One real building-event: the median-error PJM-adj event at the middle site", fontsize=9.3, fontweight="bold", va="center")
fig.text(0.0, 0.012, "No curtailment on this proxy event day: the gap is a baseline error, not a settlement amount.", fontsize=8.3, color=INK2, va="top")

L.row("sample.n_sites")
L.report()
save(fig, "fig_01_design")
