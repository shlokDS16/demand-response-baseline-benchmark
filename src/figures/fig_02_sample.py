"""Figure 2: sample composition and eligibility funnel (2017)."""
import pandas as pd
from common import *

style()
L = Ledger()
sites = L.v("sample.sites").split(",")
cols = ["site", "b", "use"]
R1 = pd.read_pickle(RUN / "events_R1.pkl", )[cols].drop_duplicates()
n_check = len(R1)
assert n_check == int(L.v("sample.n_buildings")), (n_check, L.v("sample.n_buildings"))
ct = R1.groupby(["site", "use"]).size().unstack(fill_value=0).reindex(sites)
top = ct.sum().sort_values(ascending=False).index[:6].tolist()
ct["Other uses"] = ct.drop(columns=top).sum(axis=1)
ct = ct[top + ["Other uses"]]
pal = [BLUE, VERM, GREEN, ORANGE, SKY, PURPLE, GREY]
fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 3.3), gridspec_kw=dict(width_ratios=[1.25, 1], wspace=0.55))
left = np.zeros(len(sites))
y = np.arange(len(sites))[::-1]
for c, col in zip(ct.columns, pal):
    a.barh(y, ct[c].values, left=left, color=col, edgecolor="white", linewidth=0.6, height=0.72, label=c)
    left += ct[c].values
for yi, tot in zip(y, left):
    a.text(tot + 3, yi, "%d" % tot, va="center", fontsize=7, color=INK2)
a.set_yticks(y); a.set_yticklabels(sites); a.set_xlabel("Buildings with R1 events (n)")
a.set_xlim(0, left.max() * 1.12)
a.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.62, -0.17), fontsize=7, handlelength=1.0, columnspacing=0.8, labelspacing=0.3)
panel(a, "a", dx=-0.22)
# funnel
e1 = L.v("sample.n_meters_e1"); fl = L.v("sample.n_excl_flat_meter"); dup = L.v("sample.n_dup_dropped")
nb = L.v("sample.n_buildings"); ne = L.v("sample.n_events.R1")
after_e3 = e1 - fl - dup
stages = [("E1: usable meters\n(14 sites)", e1), ("E3: after flat-meter\nand duplicate filters", after_e3),
          ("E4: sites with >= 12\nmeters (11 sites)", nb)]
yy = np.arange(len(stages))[::-1] + 1
for yi, (lab, v) in zip(yy, stages):
    b.barh(yi, v, color=BLUE, height=0.6, edgecolor="white")
    b.text(v + 15, yi, "%d" % v, va="center", fontsize=7.5)
b.set_yticks(yy); b.set_yticklabels([s[0] for s in stages]); b.set_xlim(0, e1 * 1.18)
b.set_xlabel("Meters / buildings (n)")
b.set_ylim(-0.2, 3.6)
b.text(0.04*e1, 0.35, "R1 hot-day events: %d building-events\nfrom %d buildings" % (ne, nb), fontsize=7.5, va="center", color=INK)
panel(b, "b", dx=-0.55)
L.report()
save(fig, "fig_02_sample")
