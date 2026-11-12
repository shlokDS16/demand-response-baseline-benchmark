"""Supplementary table S_events (D29 item 4): per-site scored event days, designated days and heat episodes.
Numbers only from the ledger keys sample.event_days.*, sample.event_days_designated.*, sample.heat_episodes.*."""
import site, sys, os
_up = site.getusersitepackages()
(os.path.isdir(_up) and _up not in sys.path) and sys.path.append(_up)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

P = MultiLedger()
sites = P.v("sample.sites").split(",")
g = lambda pre, s: int(P.v("%s.%s" % (pre, s)))
rows, tot = [], [0, 0, 0, 0]
for s in sites:
    vals = [g("sample.event_days", s), g("sample.event_days_designated", s),
            g("sample.heat_episodes", s), g("sample.heat_episodes_designated", s)]
    tot = [a + b for a, b in zip(tot, vals)]
    rows.append([s + (r"\textsuperscript{a}" if s == "Lamb" else "")] + [str(x) for x in vals])
assert tot[0] == int(P.v("sample.event_days.total")), (tot, P.v("sample.event_days.total"))
rows.append(["All sites"] + [str(x) for x in tot])
lamb = [d.split(":") for d in P.v("sample.event_days_table.Lamb").split(";")]
ld = ", ".join(x[0] for x in lamb)
lb = "%d to %d" % (min(int(x[2][:-1]) for x in lamb), max(int(x[2][:-1]) for x in lamb))
hdr = ["Site", "Scored event days", "Designated days", "Heat episodes (scored)", "Heat episodes (designated)"]
note = (r"Scored event days are the hot-day (R1) days with at least one scored building-event; designated days are the %d R1 days per site "
        r"listed in the frozen event-date file. A heat episode is a run of event days at most 3 calendar days apart, so a new episode starts when "
        r"the gap to the previous event day exceeds 3 days. "
        r"\textsuperscript{a}Lamb has %d scored event days (%s; %s buildings each) in %d heat episodes, although %d days were designated; "
        r"the other designated days carry no building-event with data. At the other ten sites every designated day is scored."
        % (g("sample.event_days_designated", "Bear"), g("sample.event_days", "Lamb"), ld, lb,
           g("sample.heat_episodes", "Lamb"), g("sample.event_days_designated", "Lamb")))
write_csv(TAB / "S_events.csv", hdr, [[r[0].replace(r"\textsuperscript{a}", "*")] + r[1:] for r in rows])
write_tex(TAB / "S_events.tex", hdr, rows, r"lrrrr", [note])
print(open(TAB / "S_events.tex", encoding="utf-8").read())
P.report()
