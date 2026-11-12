"""Audit of Building Data Genome 2 (BDG2) for B-C1 (DR baselines). Run: python -I audit_bdg2.py
Reads data/raw/bdg2/*.csv (never written to), writes results/data_audit/*.
Memory: one wide meter file at a time as float32 (~110 MB)."""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "data_audit")
os.makedirs(OUT, exist_ok=True)

COV_MIN = 0.80


def load_wide(name):
    df = pd.read_csv(os.path.join(RAW, name), index_col=0, parse_dates=True)
    return df.astype("float32")


def longest_run(mask):
    """Longest run of True per column; mask is (T, M) bool."""
    T, M = mask.shape
    best = np.zeros(M, dtype=np.int32)
    cur = np.zeros(M, dtype=np.int32)
    for t in range(T):
        cur = np.where(mask[t], cur + 1, 0)
        best = np.maximum(best, cur)
    return best


def meter_stats(df, meta):
    y = df.index.year
    cov16 = df[y == 2016].notna().mean()
    cov17 = df[y == 2017].notna().mean()
    covall = df.notna().mean()
    zr = longest_run((df.values == 0))
    st = pd.DataFrame({"meter_id": df.columns, "coverage_2016": cov16.values, "coverage_2017": cov17.values,
                       "coverage_all": covall.values, "missing_share": 1 - covall.values,
                       "longest_zero_run_h": zr})
    st = st.merge(meta[["building_id", "site_id", "primaryspaceusage", "sqm", "timezone", "lat"]],
                  left_on="meter_id", right_on="building_id", how="left").drop(columns="building_id")
    st["good"] = (st.coverage_2016 >= COV_MIN) & (st.coverage_2017 >= COV_MIN)
    return st


def good_days(df, cols):
    """Boolean (days, meters): all 24 hourly readings present and day sum > 0."""
    sub = df[cols]
    notna = sub.notna().groupby(sub.index.normalize()).sum()
    tot = sub.groupby(sub.index.normalize()).sum(min_count=1)
    return (notna == 24) & (tot > 0)


def main():
    meta = pd.read_csv(os.path.join(RAW, "metadata.csv"))
    wx = pd.read_csv(os.path.join(RAW, "weather.csv"), parse_dates=["timestamp"])
    summary = {}

    # site table
    site_tz = meta.groupby("site_id").agg(timezone=("timezone", "first"), lat=("lat", "mean"), lng=("lng", "mean"),
                                           n_buildings=("building_id", "count")).reset_index()
    wxs = wx.groupby("site_id").agg(temp_missing_share=("airTemperature", lambda s: s.isna().mean()),
                                    n_hours=("airTemperature", "size")).reset_index()
    site = site_tz.merge(wxs, on="site_id", how="outer")

    # daily max temp per site
    wx["date"] = wx.timestamp.dt.normalize()
    g = wx.groupby(["site_id", "date"]).airTemperature
    dmax = pd.DataFrame({"tmax": g.max(), "n": g.count()}).reset_index()
    dmax = dmax[dmax.n >= 20]

    results = {}
    for kind, fname in [("electricity", "electricity_cleaned.csv"), ("chilledwater", "chilledwater_cleaned.csv")]:
        if not os.path.exists(os.path.join(RAW, fname)) or os.path.getsize(os.path.join(RAW, fname)) < 1000:
            summary[f"{kind}_status"] = "FILE MISSING (download blocked)"
            continue
        df = load_wide(fname)
        summary[f"{kind}_n_meters"] = int(df.shape[1])
        summary[f"{kind}_span"] = [str(df.index.min()), str(df.index.max())]
        diffs = pd.Series(df.index[1:] - df.index[:-1]).value_counts()
        summary[f"{kind}_timestep_counts"] = {str(k): int(v) for k, v in diffs.items()}
        st = meter_stats(df, meta)
        st["site_id"] = st["site_id"].fillna(st["meter_id"].str.split("_").str[0])
        st.to_csv(os.path.join(OUT, f"bdg2_{kind}_meter_stats.csv"), index=False)
        q = st.missing_share.quantile([0, .1, .25, .5, .75, .9, 1]).round(4)
        summary[f"{kind}_missing_share_quantiles"] = {str(k): float(v) for k, v in q.items()}
        summary[f"{kind}_n_good_meters"] = int(st.good.sum())
        summary[f"{kind}_n_cov80_2016"] = int((st.coverage_2016 >= COV_MIN).sum())
        summary[f"{kind}_n_cov80_2017"] = int((st.coverage_2017 >= COV_MIN).sum())
        summary[f"{kind}_zero_run_ge24h_share"] = float((st.longest_zero_run_h >= 24).mean())
        summary[f"{kind}_zero_run_ge168h_share"] = float((st.longest_zero_run_h >= 168).mean())
        summary[f"{kind}_zero_run_quantiles"] = {str(k): float(v) for k, v in
                                                st.longest_zero_run_h.quantile([.5, .75, .9, .99, 1]).items()}
        # per site
        ps = st.groupby("site_id").agg(n_meters=("meter_id", "count"), n_good=("good", "sum")).reset_index()
        use = (st[st.good].groupby(["site_id", "primaryspaceusage"]).size().unstack(fill_value=0))
        ps["primary_use_mix_good"] = ps.site_id.map(lambda s: json.dumps(
            {k: int(v) for k, v in use.loc[s].items() if v > 0}) if s in use.index else "{}")
        ps = ps.merge(site, on="site_id", how="left")

        # good building-days, summer and hot days
        gcols = list(st.loc[st.good, "meter_id"])
        gd = good_days(df, gcols)  # days x meters
        sid = st.set_index("meter_id").loc[gcols, "site_id"]
        rows = []
        for s, cols in sid.groupby(sid).groups.items():
            lat = site.loc[site.site_id == s, "lat"].mean()
            months = [6, 7, 8, 9] if (pd.isna(lat) or lat >= 0) else [12, 1, 2, 3]
            d = gd[list(cols)]
            summer = d[d.index.month.isin(months)]
            dm = dmax[dmax.site_id == s].set_index("date").tmax
            if len(dm) > 0:
                thr = dm.quantile(0.9)
                hot_days = dm.index[dm >= thr]
                top10 = dm.groupby(dm.index.year).nlargest(10).reset_index(level=0, drop=True).index
                hot_bd = int(d.reindex(hot_days).fillna(False).values.sum())
                top10_bd = int(d.reindex(top10).fillna(False).values.sum())
                n_hot = len(hot_days)
                hot_share = hot_bd / max(int(d.values.sum()), 1)
            else:
                hot_bd = top10_bd = n_hot = 0
                hot_share = np.nan
            rows.append({"site_id": s, "good_meters": len(cols), "good_building_days_all": int(d.values.sum()),
                         "good_building_days_summer": int(summer.values.sum()),
                         "summer_months": "".join(f"{m:02d}-" for m in months)[:-1],
                         "n_hot_days_top10pct": n_hot, "good_building_days_on_hot_days": hot_bd,
                         "hot_share_of_good_bd": hot_share, "good_building_days_on_top10_per_year": top10_bd})
        bd = pd.DataFrame(rows)
        ps = ps.merge(bd, on="site_id", how="left")
        ps.to_csv(os.path.join(OUT, f"bdg2_{kind}_per_site.csv"), index=False)
        summary[f"{kind}_sites_with_good_ge10"] = int((ps.n_good >= 10).sum())
        summary[f"{kind}_sites_with_good_ge20"] = int((ps.n_good >= 20).sum())
        summary[f"{kind}_sites_with_good_ge5"] = int((ps.n_good >= 5).sum())
        summary[f"{kind}_total_good_bd_summer"] = int(ps.good_building_days_summer.sum())
        summary[f"{kind}_total_good_bd_hot_top10pct"] = int(ps.good_building_days_on_hot_days.sum())
        summary[f"{kind}_total_good_bd_top10_per_year"] = int(ps.good_building_days_on_top10_per_year.sum())
        results[kind] = st
        del df, gd
        print(kind, "done", flush=True)

    # combined coverage CSV (electricity, as asked)
    if "electricity" not in results:
        return 1
    e = results["electricity"][["meter_id", "site_id", "primaryspaceusage", "sqm", "coverage_2016", "coverage_2017"]]
    e.to_csv(os.path.join(OUT, "bdg2_meter_coverage.csv"), index=False)
    site.to_csv(os.path.join(OUT, "bdg2_site_weather.csv"), index=False)
    with open(os.path.join(OUT, "bdg2_audit_summary.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
