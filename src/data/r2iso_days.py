"""R2-ISO: external, ex-ante event-day rule for BDG2 sites (no building data used).

For each BDG2 site mapped to a US balancing authority (BA), rank the weekdays 15 May - 30 Sep of
2016 and 2017 by the BA's day-ahead DEMAND FORECAST peak (EIA-930 'Demand Forecast (MW)', daily max
over the local-date hours). Output: results/r2iso/r2iso_days.csv (ranks 1..40) and
results/r2iso/r2iso_summary.json (coverage, missing forecast share, Jaccard with R1 at K=10).

R1 = the 10 hottest weekdays by the site's daily max airTemperature (data/raw/bdg2/weather.csv),
same window. Run:  python -I src/data/r2iso_days.py   (from paper_B)
"""
import glob
import json
import os
import site
import sys

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import pandas as pd  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EIA = os.path.join(ROOT, "data", "raw", "eia930")
WEATHER = os.path.join(ROOT, "data", "raw", "bdg2", "weather.csv")
OUT = os.path.join(ROOT, "results", "r2iso")
AUDIT = os.path.join(ROOT, "results", "data_audit", "bdg2_audit_summary.json")
KMAX, K = 40, 10
MIN_HOURS = 20  # a day needs >= 20 of 24 forecast hours to be rankable

# site -> (BA, confidence, source)
MAP = {
    "Bear": ("CISO", "high", "BDG2 Table 1: UC Berkeley, Berkeley CA (doi:10.1038/s41597-020-00712-x); CAISO area"),
    "Bull": ("ERCO", "high", "BDG2 Table 1: Univ. of Texas - Austin; ERCOT"),
    "Cockatoo": ("NYIS", "high", "BDG2 Table 1: Cornell University, Ithaca NY; NYISO"),
    "Fox": ("SRP", "medium", "metadata lat/lng 33.42,-111.93 = Tempe AZ (ASU); Tempe is served by SRP and APS, SRP chosen; AZPS is the alternative"),
    "Hog": ("MISO", "medium", "BDG2 site anonymous; metadata lat/lng 44.98,-93.26 = Minneapolis MN; MISO (Xcel NSP)"),
    "Peacock": ("PJM", "high", "BDG2 Table 1: Princeton University, NJ; PJM"),
    "Rat": ("PJM", "high", "metadata lat/lng 38.90,-77.01 = Washington DC (Pepco); PJM"),
}
UNMAPPED = {
    "Bobcat": "anonymous site, no lat/lng (US/Mountain, climate 5B): grid area unknown",
    "Eagle": "anonymous site, no lat/lng (US/Eastern, climate 4A): grid area unknown",
    "Gator": "anonymous site, no lat/lng (US/Eastern, climate 2A): grid area unknown",
    "Lamb": "Cardiff UK: GB national day-ahead forecast for 2016-17 not obtained (see DATA_EIA930.md)",
    "Robin": "London UK (UCL): as Lamb",
    "Wolf": "UCD Dublin, Ireland: EirGrid day-ahead forecast for 2016-17 not obtained",
    "Moose": "Ottawa, Canada (IESO): not in EIA-930, IESO source not obtained",
}


def load_eia(bas):
    fr = []
    for f in sorted(glob.glob(os.path.join(EIA, "EIA930_BALANCE_201[67]_*.csv"))):
        d = pd.read_csv(f, usecols=["Balancing Authority", "Data Date", "Hour Number",
                                    "Demand Forecast (MW)"], low_memory=False)
        fr.append(d[d["Balancing Authority"].isin(bas)])
    d = pd.concat(fr, ignore_index=True)
    d["date"] = pd.to_datetime(d["Data Date"], format="%m/%d/%Y")
    d["fc"] = pd.to_numeric(d["Demand Forecast (MW)"].astype(str).str.replace(",", ""), errors="coerce")
    return d.rename(columns={"Balancing Authority": "ba"})[["ba", "date", "Hour Number", "fc"]]


def window_weekdays(year):
    r = pd.date_range(f"{year}-05-15", f"{year}-09-30", freq="D")
    return r[r.dayofweek < 5]


def main():
    os.makedirs(OUT, exist_ok=True)
    sites = json.load(open(AUDIT))["sites_donor_ge5_nontarget"]
    eia = load_eia({v[0] for v in MAP.values()})
    w = pd.read_csv(WEATHER, usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
    w["date"] = w["timestamp"].dt.normalize()
    rows, summ = [], {}
    for s in sites:
        if s not in MAP:
            summ[s] = {"mapped": False, "reason": UNMAPPED.get(s, "not mapped")}
            continue
        ba, conf, src = MAP[s]
        summ[s] = {"mapped": True, "ba": ba, "confidence": conf, "source": src, "years": {}}
        for y in (2016, 2017):
            wd = window_weekdays(y)
            e = eia[(eia.ba == ba) & eia.date.isin(wd)]
            exp_hours = len(wd) * 24
            n_fc = int(e["fc"].notna().sum())
            g = e.groupby("date")["fc"].agg(forecast_peak_MW="max", n_forecast_hours="count").reset_index()
            g = g[g.n_forecast_hours >= MIN_HOURS].sort_values(
                ["forecast_peak_MW", "date"], ascending=[False, True])
            g["rank"] = range(1, len(g) + 1)
            g = g[g["rank"] <= KMAX]
            for r in g.itertuples():
                rows.append((s, y, r.date.date().isoformat(), ba, r.forecast_peak_MW, r.rank, r.n_forecast_hours))
            r2 = set(g[g["rank"] <= K].date)
            ww = w[(w.site_id == s) & w.date.isin(wd)]
            dm = ww.groupby("date")["airTemperature"].max().dropna().sort_values(ascending=False)
            r1 = set(dm.index[:K])
            inter, uni = len(r1 & r2), len(r1 | r2)
            summ[s]["years"][str(y)] = {
                "weekdays_in_window": len(wd),
                "rankable_days": int(e.groupby("date")["fc"].count().ge(MIN_HOURS).sum()),
                "forecast_hours_missing_share": round(1 - n_fc / exp_hours, 5),
                "r1_days": len(r1), "r2_days": len(r2), "overlap": inter,
                "jaccard_K10": round(inter / uni, 3) if uni else None,
            }
    out = pd.DataFrame(rows, columns=["site_id", "year", "date", "ba", "forecast_peak_MW", "rank", "n_forecast_hours"])
    out.drop(columns="n_forecast_hours").to_csv(os.path.join(OUT, "r2iso_days.csv"), index=False)
    json.dump(summ, open(os.path.join(OUT, "r2iso_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1)[:6000])
    print(out.shape)


if __name__ == "__main__":
    main()
