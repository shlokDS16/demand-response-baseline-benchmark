"""Figure 9: median pre-period age (days) vs K (mechanism diagnostic, secondary)."""
from common import *

style()
L = Ledger()
Ks = [10, 20, 30, 40]
fig, ax = plt.subplots(figsize=(W1, 2.7))
for key, lab, c, mk, ls in (("pjm_lookback", "PJM lookback", VERM, "o", "-"), ("scmR_preperiod", "SCM-ridge pre-period", GREEN, "s", "--")):
    y = [L.v("H5.age_days.%s.K%d" % (key, K)) for K in Ks]
    ax.plot(Ks, y, color=c, marker=mk, ls=ls, ms=4, lw=1.4, label=lab)
ax.set_xticks(Ks); ax.set_xlabel("Dispatch count K"); ax.set_ylabel("Median age of data used (days)")
ax.set_xlim(8, 42); ax.grid(axis="y", lw=0.4, alpha=0.7)
ax.legend(loc="upper left", fontsize=7)
ax.set_title("Mechanism diagnostic (secondary)", fontsize=7.5)
L.report()
save(fig, "fig_09_age")
