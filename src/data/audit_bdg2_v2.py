"""BDG2 audit v2 for B-C1 (demand-response baselines). Run: python -I audit_bdg2_v2.py
Reads data/raw/bdg2/{metadata,weather,electricity_cleaned,electricity}.csv (never written), writes results/data_audit/.
Definitions (all stated in research/DATA_PILOT_BDG2.md):
  valid day      : 24 hourly non-missing readings and day sum > 0
  usable building: >= 300 valid days in 2016 AND >= 300 valid days in 2017 (cleaned file)
  hot weekday    : Mon-Fri whose daily max airTemperature (>= 20 hourly values) is in the top 10 % of the site's
                   daily maxima over 2016-2017 pooled
  full window    : all 10 hourly readings stamped 10:00..19:00 present and their sum > 0
"""
import json
import os
import site
import sys

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "bdg2")
OUT = os.path.join(ROOT, "results", "data_audit")
os.makedirs(OUT, exist_ok=True)
DAYS = {2016: 366, 2017: 365}
HRS = {2016: 8784, 2017: 8760}


def longest_run(mask):
    T, M = mask.shape
    best = np.zeros(M, np.int32)
    cur = np.zeros(M, np.int32)
    for t in range(T):
        cur = np.where(mask[t], cur + 1, 0)
        np.maximum(best, cur, out=best)
    return best


def load(name):
    return pd.read_csv(os.path.join(RAW, name), index_col=0, parse_dates=True).astype("float32")


def valid_days(df):
    g = df.index.normalize()
    n = df.notna().groupby(g).sum()
    s = df.groupby(g).sum(min_count=1)
    return (n == 24) & (s > 0)


def main():
    meta = pd.read_csv(os.path.join(RAW, "metadata.csv"))
    wx = pd.read_csv(os.path.join(RAW, "weather.csv"), parse_dates=["timestamp"])
    summ = {}
    df = load("electricity_cleaned.csv")
    raw = load("electricity.csv")
    summ["n_meters_cleaned"] = int(df.shape[1])
    summ["n_meters_raw"] = int(raw.shape[1])
    summ["index_span"] = [str(df.index.min()), str(df.index.max())]
    summ["n_hours"] = int(len(df))
    summ["timestep_counts"] = {str(k): int(v) for k, v in
                               pd.Series(df.index[1:] - df.index[:-1]).value_counts().items()}
    summ["index_identical_raw_cleaned"] = bool(df.index.equals(raw.index))
    summ["duplicate_timestamps"] = int(df.index.duplicated().sum())
    assert (df.columns == raw.columns).all() or set(df.columns) == set(raw.columns)
    raw = raw[df.columns]

    m = meta.set_index("building_id")
    cols = pd.DataFrame({"meter_id": df.columns})
    cols["site_id"] = cols.meter_id.map(m.site_id)
    cols["primaryspaceusage"] = cols.meter_id.map(m.primaryspaceusage)
    cols["sqm"] = cols.meter_id.map(m.sqm)
    cols["timezone"] = cols.meter_id.map(m.timezone)
    summ["meters_not_in_metadata"] = int(cols.site_id.isna().sum())
    summ["meters_electricity_flag_mismatch"] = int((m.loc[cols.meter_id.dropna(), "electricity"].isna()).sum())

    y = df.index.year
    for tag, d in [("", df), ("raw_", raw)]:
        for yr in (2016, 2017):
            cols[f"{tag}coverage_{yr}"] = d[y == yr].notna().mean().values
        cols[f"{tag}longest_zero_run_h"] = longest_run(d.values == 0)
        v = d.values
        same = (v[1:] == v[:-1]) & ~np.isnan(v[1:]) & ~np.isnan(v[:-1])
        cols[f"{tag}longest_constant_run_h"] = longest_run(same) + 1  # n equal diffs -> n+1 readings
    # constant-nonzero run (flat-lined meter), cleaned
    v = df.values
    sameNZ = (v[1:] == v[:-1]) & (v[1:] != 0) & ~np.isnan(v[1:]) & ~np.isnan(v[:-1])
    cols["longest_constant_nonzero_run_h"] = longest_run(sameNZ) + 1
    cols["all_zero_meter"] = (np.nan_to_num(v).sum(0) == 0)

    vd = valid_days(df)
    for yr in (2016, 2017):
        cols[f"valid_days_{yr}"] = vd[vd.index.year == yr].sum().values
    cols["usable"] = (cols.valid_days_2016 >= 300) & (cols.valid_days_2017 >= 300)
    cols["ge300_2016"] = cols.valid_days_2016 >= 300
    cols["ge300_2017"] = cols.valid_days_2017 >= 300
    cols.to_csv(os.path.join(OUT, "bdg2_meter_audit.csv"), index=False)
    print("meters done", flush=True)

    # usage counts per site
    uc = cols.groupby(["site_id", "primaryspaceusage"]).size().unstack(fill_value=0)
    uc["TOTAL"] = uc.sum(1)
    uc.to_csv(os.path.join(OUT, "bdg2_meters_by_site_and_use.csv"))
    uu = cols[cols.usable].groupby(["site_id", "primaryspaceusage"]).size().unstack(fill_value=0)
    uu["TOTAL"] = uu.sum(1)
    uu.to_csv(os.path.join(OUT, "bdg2_usable_meters_by_site_and_use.csv"))
    summ["pooled_use_counts"] = {k: int(v) for k, v in cols.primaryspaceusage.value_counts(dropna=False).items()}
    summ["pooled_use_counts_usable"] = {k: int(v) for k, v in cols[cols.usable].primaryspaceusage.value_counts().items()}

    # weather completeness per site-year and daily max
    wx["year"] = wx.timestamp.dt.year
    wc = wx.groupby(["site_id", "year"]).agg(rows=("airTemperature", "size"),
                                              temp_valid=("airTemperature", "count"),
                                              dup_ts=("timestamp", lambda s: int(s.duplicated().sum()))).reset_index()
    wc["temp_completeness_vs_expected"] = wc.temp_valid / wc.year.map(HRS)
    wcw = wc.pivot(index="site_id", columns="year", values=["temp_completeness_vs_expected", "rows", "dup_ts"])
    wcw.columns = [f"{a}_{b}" for a, b in wcw.columns]
    wcw = wcw.reset_index()
    wx["date"] = wx.timestamp.dt.normalize()
    g = wx.groupby(["site_id", "date"]).airTemperature
    dmax = pd.DataFrame({"tmax": g.max(), "n": g.count()}).reset_index()
    dmax = dmax[dmax.n >= 20]
    dmax["year"] = dmax.date.dt.year
    dmax["weekday"] = dmax.date.dt.dayofweek < 5

    # hot weekdays
    hrs = df.index.hour
    win_mask = (hrs >= 10) & (hrs <= 19)
    dfw = df[win_mask]
    gday = dfw.index.normalize()
    win_full = (dfw.notna().groupby(gday).sum() == 10) & (dfw.groupby(gday).sum(min_count=1) > 0)  # days x meters
    hot_rows = []
    for s in sorted(cols.site_id.dropna().unique()):
        dm = dmax[dmax.site_id == s]
        if dm.empty:
            continue
        thr = dm.tmax.quantile(0.9)
        hot = dm[(dm.tmax >= thr) & dm.weekday]
        mcols = list(cols.loc[cols.site_id == s, "meter_id"])
        ucols = list(cols.loc[(cols.site_id == s) & cols.usable, "meter_id"])
        for yr in (2016, 2017):
            hd = hot[hot.year == yr].date
            alln = win_full.reindex(hd)[mcols].fillna(False)
            usn = win_full.reindex(hd)[ucols].fillna(False) if ucols else pd.DataFrame(index=hd)
            per_day_all = alln.sum(1)
            per_day_us = usn.sum(1) if ucols else pd.Series(0, index=hd)
            hot_rows.append({"site_id": s, "year": yr, "tmax_threshold_C": round(float(thr), 2),
                             "n_days_with_tmax": int((dm.year == yr).sum()),
                             "n_hot_weekdays": int(len(hd)),
                             "hot_wd_with_ge1_full_window_meter": int((per_day_all >= 1).sum()),
                             "hot_wd_with_ge5_full_window_meters": int((per_day_all >= 5).sum()),
                             "hot_wd_with_ge5_full_window_usable": int((per_day_us >= 5).sum()),
                             "building_days_full_window_all": int(per_day_all.sum()),
                             "building_days_full_window_usable": int(per_day_us.sum()),
                             "median_meters_per_hot_wd": float(per_day_all.median()) if len(hd) else np.nan})
    hot = pd.DataFrame(hot_rows)
    hot.to_csv(os.path.join(OUT, "bdg2_hot_weekdays_by_site_year.csv"), index=False)
    print("hot done", flush=True)

    # per-site table
    sc = cols.groupby("site_id")
    ps = sc.agg(n_meters=("meter_id", "count"),
                timezone=("timezone", "first"),
                n_ge300_2016=("ge300_2016", "sum"), n_ge300_2017=("ge300_2017", "sum"),
                n_usable=("usable", "sum"),
                cov2016_median=("coverage_2016", "median"), cov2017_median=("coverage_2017", "median"),
                cov2016_lt50=("coverage_2016", lambda s: int((s < .5).sum())),
                cov2017_lt50=("coverage_2017", lambda s: int((s < .5).sum())),
                raw_cov2016_median=("raw_coverage_2016", "median"), raw_cov2017_median=("raw_coverage_2017", "median"),
                zero_run_ge24=("longest_zero_run_h", lambda s: int((s >= 24).sum())),
                zero_run_ge168=("longest_zero_run_h", lambda s: int((s >= 168).sum())),
                const_nz_run_ge24=("longest_constant_nonzero_run_h", lambda s: int((s >= 24).sum())),
                const_nz_run_ge168=("longest_constant_nonzero_run_h", lambda s: int((s >= 168).sum())),
                all_zero=("all_zero_meter", "sum")).reset_index()
    tzm = meta.groupby("site_id").timezone.agg(lambda s: "|".join(sorted(s.dropna().unique())))
    ps["metadata_timezones"] = ps.site_id.map(tzm)
    ps["lat"] = ps.site_id.map(meta.groupby("site_id").lat.mean())
    ps["lng"] = ps.site_id.map(meta.groupby("site_id").lng.mean())
    ps = ps.merge(wcw, on="site_id", how="left")
    ps["usable_use_mix"] = ps.site_id.map(lambda s: json.dumps(
        {k: int(v) for k, v in uu.drop(columns="TOTAL").loc[s].items() if v > 0}) if s in uu.index else "{}")
    ps["donor_site_ge5_nontarget"] = ps.n_usable >= 6  # one target + >= 5 usable non-target buildings
    ps["donor_site_ge5_usable"] = ps.n_usable >= 5
    hp = hot.pivot(index="site_id", columns="year",
                   values=["n_hot_weekdays", "hot_wd_with_ge5_full_window_usable", "building_days_full_window_usable"])
    hp.columns = [f"{a}_{b}" for a, b in hp.columns]
    ps = ps.merge(hp.reset_index(), on="site_id", how="left")
    ps.to_csv(os.path.join(OUT, "bdg2_per_site.csv"), index=False)

    # office-specific donor view: site-level usable by use for target use categories
    summ["n_sites"] = int(ps.shape[0])
    summ["n_usable_total"] = int(cols.usable.sum())
    summ["n_ge300_2016_total"] = int(cols.ge300_2016.sum())
    summ["n_ge300_2017_total"] = int(cols.ge300_2017.sum())
    summ["sites_donor_ge5_nontarget"] = ps.loc[ps.donor_site_ge5_nontarget, "site_id"].tolist()
    summ["sites_usable_ge5"] = ps.loc[ps.donor_site_ge5_usable, "site_id"].tolist()
    summ["zero_run_ge24_share_cleaned"] = float((cols.longest_zero_run_h >= 24).mean())
    summ["zero_run_ge168_share_cleaned"] = float((cols.longest_zero_run_h >= 168).mean())
    summ["const_nz_ge24_share_cleaned"] = float((cols.longest_constant_nonzero_run_h >= 24).mean())
    summ["const_nz_ge168_share_cleaned"] = float((cols.longest_constant_nonzero_run_h >= 168).mean())
    summ["zero_run_ge168_share_raw"] = float((cols.raw_longest_zero_run_h >= 168).mean())
    summ["all_zero_meters"] = int(cols.all_zero_meter.sum())
    summ["cov_missing_overall_cleaned"] = float(df.isna().mean().mean())
    summ["cov_missing_overall_raw"] = float(raw.isna().mean().mean())
    summ["hot_weekday_totals"] = {str(yr): {
        "n_hot_weekdays_sum_over_sites": int(hot[hot.year == yr].n_hot_weekdays.sum()),
        "site_hotdays_with_ge5_usable_full_window": int(hot[hot.year == yr].hot_wd_with_ge5_full_window_usable.sum()),
        "building_days_usable": int(hot[hot.year == yr].building_days_full_window_usable.sum())} for yr in (2016, 2017)}
    summ["weather_completeness_min_by_year"] = {str(yr): float(wc[wc.year == yr].temp_completeness_vs_expected.min())
                                                for yr in (2016, 2017)}
    summ["weather_sites_below_95pct_any_year"] = wc[wc.temp_completeness_vs_expected < .95].site_id.unique().tolist()
    with open(os.path.join(OUT, "bdg2_audit_summary.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
