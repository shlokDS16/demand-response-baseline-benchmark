"""Generate frozen, load-free inputs for Paper B (PREREG Revision 2, DECISIONS T3 1.3 and 4.1).
Outputs (results/frozen/):
  holidays.csv     country, date (US federal; England and Wales bank holidays; Ireland public holidays), 2016-2017
  event_dates.csv  site_id, year, rule (R1 | R3), draw (0 for R1, 1-5 for R3), rank (R1: 1-40 by Tmax; R3: 1-10),
                   date, tmax_c (rounded 0.1 C), primary (R1 rank <= 10, or R3)
  folds.csv        meter_id, site_id, fold (A | B)
Reads ONLY data/raw/bdg2/weather.csv, data/raw/bdg2/metadata.csv (timezone) and results/data_audit/bdg2_meter_audit.csv
(E1 flags). An audit hook aborts the run if any file whose name contains "electricity" is opened.
Run: python -I freeze_inputs.py   (from src/design)
"""
import sys

OPENED = []
def _audit(event, args):
    if event == "open":
        path = str(args[0])
        OPENED.append(path)
        if "electricity" in path.lower():
            raise RuntimeError("freeze_inputs.py must not open electricity files: " + path)
sys.addaudithook(_audit)

import os, site
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "frozen")
os.makedirs(OUT, exist_ok=True)
SITES = sorted(["Bear", "Bobcat", "Bull", "Cockatoo", "Eagle", "Fox", "Gator", "Hog", "Lamb", "Moose", "Peacock", "Rat", "Robin", "Wolf"])
# Holidays. 2016 lists as used in the 2016 development scripts; 2017 lists entered from the official calendars as
# known to the author: VERIFY against US OPM, gov.uk and gov.ie before the freeze (PREREG E7).
HOL = {
    "US": ["2016-01-01", "2016-01-18", "2016-02-15", "2016-05-30", "2016-07-04", "2016-09-05", "2016-10-10", "2016-11-11", "2016-11-24", "2016-12-26",
           "2017-01-02", "2017-01-16", "2017-02-20", "2017-05-29", "2017-07-04", "2017-09-04", "2017-10-09", "2017-11-10", "2017-11-23", "2017-12-25"],
    "UK": ["2016-01-01", "2016-03-25", "2016-03-28", "2016-05-02", "2016-05-30", "2016-08-29", "2016-12-26", "2016-12-27",
           "2017-01-02", "2017-04-14", "2017-04-17", "2017-05-01", "2017-05-29", "2017-08-28", "2017-12-25", "2017-12-26"],
    "IE": ["2016-01-01", "2016-03-17", "2016-03-28", "2016-05-02", "2016-06-06", "2016-08-01", "2016-10-31", "2016-12-26", "2016-12-27",
           "2017-01-02", "2017-03-17", "2017-04-17", "2017-05-01", "2017-06-05", "2017-08-07", "2017-10-30", "2017-12-25", "2017-12-26"]}
pd.DataFrame([(c, d) for c, v in HOL.items() for d in v], columns=["country", "date"]).to_csv(os.path.join(OUT, "holidays.csv"), index=False)
ctry = lambda tz: "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")
meta = pd.read_csv(os.path.join(RAW, "metadata.csv"), usecols=["site_id", "timezone"])
site_tz = meta.dropna().groupby("site_id").timezone.first()

W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
W = W[W.site_id.isin(SITES)]
W["date"] = W.timestamp.dt.normalize()
g = W.dropna(subset=["airTemperature"]).groupby(["site_id", "date"]).airTemperature
daily = pd.DataFrame({"tmax": g.max(), "n": g.size()}).reset_index()
rows = []
for si, s in enumerate(SITES):
    c = ctry(site_tz[s]); hol = set(pd.to_datetime(HOL[c]))
    for year in [2016, 2017]:
        dd = daily[(daily.site_id == s) & (daily.date >= f"{year}-05-15") & (daily.date <= f"{year}-09-30")].copy()
        dd = dd[(dd.n >= 20) & (dd.date.dt.dayofweek < 5) & ~dd.date.isin(hol)]          # E8, weekdays, E7
        dd["tmax_c"] = dd.tmax.round(1)
        r1 = dd.sort_values(["tmax_c", "date"], ascending=[False, True]).head(40).reset_index(drop=True)  # ties: earlier
        for k, r in r1.iterrows():
            rows.append(dict(site_id=s, year=year, rule="R1", draw=0, rank=k + 1, date=r.date.date(), tmax_c=r.tmax_c, primary=k < 10))
        pool = dd[~dd.date.isin(r1.date.head(10))].sort_values("date").reset_index(drop=True)
        for draw in range(1, 6):
            rng = np.random.default_rng([year, si, draw])
            pick = pool.iloc[np.sort(rng.choice(len(pool), 10, replace=False))]
            for k, (_, r) in enumerate(pick.iterrows()):
                rows.append(dict(site_id=s, year=year, rule="R3", draw=draw, rank=k + 1, date=r.date.date(), tmax_c=r.tmax_c, primary=True))
ev = pd.DataFrame(rows)
ev.to_csv(os.path.join(OUT, "event_dates.csv"), index=False)

aud = pd.read_csv(os.path.join(ROOT, "results", "data_audit", "bdg2_meter_audit.csv"),
                  usecols=["meter_id", "site_id", "usable", "all_zero_meter"])
e1 = aud[aud.usable & ~aud.all_zero_meter & aud.site_id.isin(SITES)]
frows = []
for si, s in enumerate(SITES):
    ids = sorted(e1.meter_id[e1.site_id == s])
    perm = np.random.default_rng(20171 + si).permutation(len(ids))
    half = len(ids) // 2
    for k, i in enumerate(perm):
        frows.append(dict(meter_id=ids[i], site_id=s, fold="A" if k < half else "B"))
folds = pd.DataFrame(frows).sort_values(["site_id", "meter_id"])
folds.to_csv(os.path.join(OUT, "folds.csv"), index=False)

assert not any("electricity" in p.lower() for p in OPENED)
print("event_dates rows", len(ev), ev.groupby(["year", "rule"]).size().to_dict())
print("R1 primary rows", int((ev.rule.eq("R1") & ev.primary).sum()), "site-years with < 40 R1 candidates",
      ev[ev.rule == "R1"].groupby(["site_id", "year"]).size().lt(40).sum())
print("folds rows", len(folds), folds.groupby("fold").size().to_dict())
print("holidays rows", sum(len(v) for v in HOL.values()))
print("files opened containing 'electricity':", [p for p in OPENED if "electricity" in p.lower()])
