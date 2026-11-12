"""E3 design profile of BDG2 electricity (cleaned) for B-C1. Run: python -I e3_profile.py
Reads data/raw/bdg2/{metadata,weather,electricity_cleaned}.csv (read only). Writes results/e3_profile/.
Development-year (2016) pilot only for error magnitudes; 2017 is touched only for coverage counts.
"""
import json, os, site, sys
up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np
import pandas as pd

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "e3_profile")
os.makedirs(OUT, exist_ok=True)
summ = {}

meta = pd.read_csv(os.path.join(RAW, "metadata.csv"))
# electricity in float32, chunked
chunks = []
for ch in pd.read_csv(os.path.join(RAW, "electricity_cleaned.csv"), chunksize=2000, index_col=0, parse_dates=True):
    chunks.append(ch.astype(np.float32))
E = pd.concat(chunks); del chunks
summ["elec_shape"] = list(E.shape)
summ["ts_first_last"] = [str(E.index[0]), str(E.index[-1])]
summ["ts_unique_step_h"] = sorted(set((np.diff(E.index.values).astype("timedelta64[m]").astype(int) // 60).tolist()))[:5]

W = pd.read_csv(os.path.join(RAW, "weather.csv"), usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
summ["sites_weather"] = int(W.site_id.nunique())

m = meta.set_index("building_id").reindex(E.columns)
m["year16_cov"] = E.loc["2016"].notna().mean().values
m["year17_cov"] = E.loc["2017"].notna().mean().values
m["zero16"] = (E.loc["2016"] == 0).mean().values
m["zero17"] = (E.loc["2017"] == 0).mean().values
# longest NaN-or-zero run (hours) per year
def longest_bad(X):
    bad = (X.isna() | (X == 0)).values
    out = np.zeros(bad.shape[1], dtype=int)
    run = np.zeros(bad.shape[1], dtype=int)
    for r in bad:
        run = np.where(r, run + 1, 0)
        out = np.maximum(out, run)
    return out
m["run16"] = longest_bad(E.loc["2016"]); m["run17"] = longest_bad(E.loc["2017"])
ok = (m.year16_cov >= 0.9) & (m.year17_cov >= 0.9) & (m.zero16 < 0.05) & (m.zero17 < 0.05)
m["eligible_v0"] = ok
summ["n_buildings_with_elec"] = int(E.shape[1])
summ["eligible_v0_rule"] = "coverage>=0.90 in both years, zero share<0.05 in both years"
summ["n_eligible_v0"] = int(ok.sum())
summ["eligible_by_site"] = m[ok].groupby("site_id").size().sort_values(ascending=False).to_dict()
summ["eligible_by_use"] = m[ok].groupby("primaryspaceusage").size().sort_values(ascending=False).to_dict()
summ["timezones"] = m[ok].groupby("timezone").size().to_dict()
summ["site_tz"] = m[ok].groupby("site_id").timezone.first().to_dict()
summ["run_gt24_among_eligible"] = int(((m.run16 > 24) | (m.run17 > 24))[ok].sum())

# timestamp convention check: hour of max of mean diurnal profile, temp and site load, summer weekdays 2016
Wp = W.pivot_table(index="timestamp", columns="site_id", values="airTemperature")
summ["weather_missing_share_by_site_2016"] = Wp.loc["2016"].isna().mean().round(3).to_dict()
tz_check = {}
for s in summ["eligible_by_site"]:
    cols = m.index[ok & (m.site_id == s)]
    load = E.loc["2016-06-01":"2016-08-31", cols]
    load = load[load.index.dayofweek < 5]
    prof = load.div(load.mean()).mean(axis=1).groupby(load.index.hour).mean()
    if s in Wp.columns:
        t = Wp.loc["2016-06-01":"2016-08-31", s]
        tprof = t.groupby(t.index.hour).mean()
        th = int(tprof.idxmax()) if tprof.notna().any() else None
    else:
        th = None
    tz_check[s] = {"load_peak_hour": int(prof.idxmax()), "temp_peak_hour": th,
                   "load_min_hour": int(prof.idxmin())}
summ["diurnal_peak_hours_JJA2016"] = tz_check

with open(os.path.join(OUT, "profile_part1.json"), "w") as f:
    json.dump(summ, f, indent=1, default=str)
m[["site_id", "primaryspaceusage", "sqm", "timezone", "year16_cov", "year17_cov", "zero16", "zero17", "run16", "run17", "eligible_v0"]].to_csv(os.path.join(OUT, "building_coverage.csv"))
print(json.dumps({k: summ[k] for k in ["elec_shape", "ts_first_last", "ts_unique_step_h", "n_eligible_v0", "eligible_by_site", "eligible_by_use", "timezones", "run_gt24_among_eligible"]}, indent=1))
print(json.dumps(tz_check))
print(json.dumps(summ["weather_missing_share_by_site_2016"]))
