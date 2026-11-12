"""Loading, DST table, flatline rules E2/E3, eligibility E1-E5, holidays E7, weather E8.
Order of transformations (T3 4.3): DST -> filters -> injection (inject.py) -> lookback/training construction -> baseline.
Year 2017 load is never read when year == 2016 (rows are taken by position: nrows / skiprows)."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from . import leakage as LK


def ctry(tz):
    return "UK" if tz == "Europe/London" else ("IE" if tz == "Europe/Dublin" else "US")


def load_holidays():
    h = pd.read_csv(C.HOLIDAYS_CSV, parse_dates=["date"])
    return {c: set(g.date) for c, g in h.groupby("country")}


def eligible_meters():
    """E1: A3 `usable` (>= 300 valid days in 2016 and 2017, flag from the earlier audit) and not all-zero."""
    aud = pd.read_csv(C.AUDIT)
    aud = aud[aud.usable & aud.site_id.isin(C.SITES) & ~aud.all_zero_meter].set_index("meter_id")
    return aud


def read_load(year, cols):
    """Read ONE year of hourly load by row position; the other year's rows are never parsed."""
    n16, n17 = C.YEAR_HOURS[2016], C.YEAR_HOURS[2017]
    keep = set(cols)
    kw = dict(index_col=0, parse_dates=True, usecols=lambda c: c == "timestamp" or c in keep)
    if year == 2016:
        df = pd.read_csv(C.RAW / "electricity_cleaned.csv", nrows=n16, **kw)
    elif year == 2017:
        df = pd.read_csv(C.RAW / "electricity_cleaned.csv", skiprows=range(1, n16 + 1), nrows=n17, **kw)
    else:
        raise ValueError(year)
    assert len(df) == C.YEAR_HOURS[year]
    assert df.index.min() >= pd.Timestamp("%d-01-01" % year) and df.index.max() < pd.Timestamp("%d-01-01" % (year + 1))
    assert (df.index.year == year).all()
    return df[cols].astype(np.float32)


def read_weather(year):
    W = pd.read_csv(C.RAW / "weather.csv", usecols=["timestamp", "site_id", "airTemperature"], parse_dates=["timestamp"])
    W = W[W.timestamp.dt.year == year].copy()
    W["date"] = W.timestamp.dt.normalize()
    return W


def daily_tmax(W, days, e8=True, rnd=True):
    """E8: a day's Tmax needs >= 20 hourly values, else NaN (not an R1 candidate). Rounded to 0.1 C (T3 1.3)."""
    g = W.groupby(["site_id", "date"]).airTemperature
    tm = g.max()
    if e8:
        tm = tm.where(g.count() >= C.MIN_TMAX_HOURS)
    if rnd:
        tm = tm.round(1)
    return tm.unstack(0).reindex(days)


def hourly_temp(W, site, days):
    s = W[W.site_id == site].groupby("timestamp").airTemperature.mean()
    idx = pd.date_range(days[0], periods=len(days) * 24, freq="h")
    return s.reindex(idx).ffill().bfill().values.reshape(len(days), 24)


# ---------------- E6 DST ----------------
def _ramp_hour(P):
    prof = np.nanmean(P, 0)
    out = np.full(prof.shape[1], np.nan)
    for j in range(prof.shape[1]):
        p = prof[:, j]
        if np.isnan(p).any() or p.max() - p.min() <= 0:
            continue
        mid = (p.min() + p.max()) / 2
        ks = np.where(p[3:] > mid)[0]
        if len(ks) == 0:
            continue
        k = ks[0] + 3
        out[j] = k - 1 + (mid - p[k - 1]) / (p[k] - p[k - 1])
    return out


def compute_dst_table(Xstamp, days, aud, cols, hol, year):
    """Development year only (2016). Xstamp: days x 24 x B on stamps."""
    rows = []
    for s in C.SITES:
        bi = [cols.index(b) for b in aud.index[aud.site_id == s]]
        if not bi:
            continue
        c = ctry(aud.timezone[aud.site_id == s].iloc[0])
        h = hol[c]
        row = {"site": s, "country": c, "n_b": len(bi)}
        for name, t0 in zip(["spring", "autumn"], C.DST_DATES[year][c]):
            t0 = pd.Timestamp(t0)
            bef = [i for i, d in enumerate(days) if t0 - pd.Timedelta(days=14) <= d < t0 and d.dayofweek < 5 and d not in h]
            aft = [i for i, d in enumerate(days) if t0 <= d < t0 + pd.Timedelta(days=14) and d.dayofweek < 5 and d not in h]
            sh = _ramp_hour(Xstamp[aft][:, :, bi]) - _ramp_hour(Xstamp[bef][:, :, bi])
            sh = sh[~np.isnan(sh)]
            row[name + "_median_shift_h"] = round(float(np.median(sh)), 2) if len(sh) else np.nan
            row[name + "_share_lt_m05"] = round(float((sh < -0.5).mean()), 3) if len(sh) else np.nan
            row[name + "_share_gt_p05"] = round(float((sh > 0.5).mean()), 3) if len(sh) else np.nan
            row[name + "_n"] = int(len(sh))
        sp, au = row["spring_median_shift_h"], row["autumn_median_shift_h"]
        if sp <= C.DST_STD_SHIFT[0] and au >= C.DST_STD_SHIFT[1]:
            row["convention"] = "STD"
        elif abs(sp) < C.DST_CLOCK_ABS and abs(au) < C.DST_CLOCK_ABS:
            row["convention"] = "CLOCK"
        else:
            row["convention"] = "AMBIGUOUS"
        rows.append(row)
    return pd.DataFrame(rows)


def apply_dst(X0, ts, aud, cols, table, year, alt=False):
    """Shift STD sites by one stamp inside the DST period (clock[t] = stamp[t-1]). alt=True is the reported sensitivity
    mapping (AMBIGUOUS sites treated as STD). Returns days x 24 x B."""
    X = X0.copy()
    for _, r in table.iterrows():
        conv = r.convention
        if conv == "AMBIGUOUS" and alt:
            conv = "STD"
        if conv != "STD":
            continue
        a, b_ = C.DST_DATES[year][r.country]
        inside = (ts >= pd.Timestamp(a) + pd.Timedelta(hours=2)) & (ts < pd.Timestamp(b_) + pd.Timedelta(hours=2))
        bi = [cols.index(b) for b in aud.index[aud.site_id == r.site]]
        idx = np.where(inside)[0]
        X[np.ix_(idx, bi)] = X[np.ix_(idx - 1, bi)]
    return X.reshape(-1, 24, X.shape[1])


# ---------------- E2/E3 flat ----------------
def flat_hours(win):
    s, e = win
    return list(range(s - 4, e + 2))


def flat_mask(Xs, hours, r=None):
    r = r or C.FLAT_RUN
    dz = (np.diff(Xs[:, hours, :], axis=1) == 0)
    flat = np.zeros((Xs.shape[0], Xs.shape[2]), bool)
    cur = np.zeros_like(flat, int)
    for h in range(dz.shape[1]):
        cur = np.where(dz[:, h, :], cur + 1, 0)
        flat |= cur >= r - 1
    return flat


def find_duplicates(Xs):
    """s9.12: identical series or correlation > 0.999 over the year (pairwise complete); returns (kept, dropped) pairs.
    Xs: days x 24 x B."""
    T = Xs.shape[0] * 24
    M = Xs.reshape(T, -1).astype(np.float64)
    m = ~np.isnan(M)
    Z = np.where(m, M, 0.0)
    mf = m.astype(np.float64)
    n = mf.T @ mf
    sx = Z.T @ mf
    sxx = (Z * Z).T @ mf
    sxy = Z.T @ Z
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy - sx * sx.T / n
        vx = sxx - sx ** 2 / n
        corr = cov / np.sqrt(vx * vx.T)
    pairs = []
    dropped = set()
    for i in range(M.shape[1]):
        for j in range(i + 1, M.shape[1]):
            if j in dropped or i in dropped or n[i, j] < 24 * 30:
                continue
            if corr[i, j] > 0.999:
                pairs.append((i, j))
                dropped.add(j)
    return pairs


@dataclass
class Year:
    year: int
    days: pd.DatetimeIndex
    aud: pd.DataFrame
    cols: list
    X: np.ndarray                 # days x 24 x B float32, clock hours, after DST
    tmax: pd.DataFrame
    weather: pd.DataFrame
    hol: dict
    dst: pd.DataFrame
    folds: pd.Series              # meter -> 'A'/'B' (frozen)
    flat_share: pd.Series = None  # per meter share of flat warm-season weekdays (E3), scored year
    n_e1: int = 0
    dst_applied: bool = False
    info: dict = field(default_factory=dict)


def site_weekday_mask(days, hol_set):
    return np.array([(d.dayofweek < 5) and (d not in hol_set) for d in days])


def season_mask(days):
    y = days[0].year
    return np.asarray((days >= "%d-%s" % (y, C.SEASON[0])) & (days <= "%d-%s" % (y, C.SEASON[1])))


def build_year(year, win=C.WINDOWS["primary"], dst_alt=False, e8=True, rnd=True):
    days = pd.date_range("%d-01-01" % year, "%d-12-31" % year, freq="D")
    ND = len(days)
    hol = load_holidays()
    aud = eligible_meters()
    cols = aud.index.tolist()
    E = read_load(year, cols)
    X0 = E.values.astype(np.float64)
    del E
    W = read_weather(year)
    tmax = daily_tmax(W, days, e8=e8, rnd=rnd)
    if year == 2016:
        dst = compute_dst_table(X0.reshape(ND, 24, -1), days, aud, cols, hol, 2016)
    else:
        dst = pd.read_csv(C.DST_TABLE_2016)  # table fixed from 2016 (E6), applied to 2017
    ts = pd.date_range("%d-01-01" % year, periods=ND * 24, freq="h")
    X = apply_dst(X0, ts, aud, cols, dst, year, alt=dst_alt)
    del X0
    LK.a11_dst_before_windows(True)
    folds = pd.read_csv(C.FOLDS_CSV).set_index("meter_id").fold
    assert set(cols) <= set(folds.index), "meters without a frozen fold"
    folds = folds.reindex(cols)
    Y = Year(year, days, aud, cols, X.astype(np.float32), tmax, W, hol, dst, folds, n_e1=len(cols), dst_applied=True)
    FH = flat_hours(win)
    share = {}
    for s in C.SITES:
        bi = [cols.index(b) for b in aud.index[aud.site_id == s]]
        if not bi:
            continue
        c = ctry(aud.timezone[aud.site_id == s].iloc[0])
        m = site_weekday_mask(days, hol[c]) & season_mask(days)
        f = flat_mask(Y.X[:, :, bi].astype(np.float64), FH)
        for k, b in enumerate(bi):
            share[cols[b]] = float(f[m, k].mean())
    Y.flat_share = pd.Series(share)
    return Y


@dataclass
class Site:
    name: str
    index: int
    year: int
    days: pd.DatetimeIndex
    meters: list
    use: list
    Ys: np.ndarray          # days x 24 x nb, float64, clock hours, raw (pre-injection)
    complete: np.ndarray    # days x nb: 24 h present and not flat (E2); computed on raw readings
    wk: np.ndarray
    season: np.ndarray
    tm: np.ndarray
    fold: np.ndarray        # 'A'/'B' per building
    win: tuple              # (s, e)
    hol: set
    dup_dropped: list = field(default_factory=list)
    excl: dict = field(default_factory=dict)

    @property
    def s(self):
        return self.win[0]

    @property
    def WIN(self):
        return list(range(self.win[0], self.win[1]))

    @property
    def nb(self):
        return len(self.meters)

    def part_idx(self, f):
        return np.where(self.fold == f)[0]


DEDUPE = True   # s9.12; switched off only by `--no-dedupe` (dev mode) to show equality with the development tables


def make_site(Y, name, win=C.WINDOWS["primary"], dedupe=None, min_meters=C.MIN_METERS_SITE):
    """E1-E5: eligible meters of the site minus E3 flat meters (and duplicates), E4 >= 12 meters. None if it fails."""
    dedupe = DEDUPE if dedupe is None else dedupe
    cols = Y.cols
    bi_site = [cols.index(b) for b in Y.aud.index[Y.aud.site_id == name]]
    n_e1 = len(bi_site)
    keep = [b for b in bi_site if Y.flat_share[cols[b]] <= C.FLAT_METER_SHARE]
    excl = {"e1": n_e1, "e3_flat_meter": n_e1 - len(keep)}
    c = ctry(Y.aud.timezone[Y.aud.site_id == name].iloc[0])
    dropped = []
    if dedupe and len(keep) > 1:
        pr = find_duplicates(Y.X[:, :, keep].astype(np.float64))
        jd = {j for _, j in pr}
        dropped = [cols[keep[j]] for j in sorted(jd)]
        keep = [b for k, b in enumerate(keep) if k not in jd]
    excl["dup_dropped"] = len(dropped)
    excl["n_after"] = len(keep)
    if len(keep) < min_meters or name not in Y.tmax.columns:
        return None, excl
    Ys = Y.X[:, :, keep].astype(np.float64)
    wk = site_weekday_mask(Y.days, Y.hol[c])
    complete = ~np.isnan(Ys).any(1) & ~flat_mask(Ys, flat_hours(win), C.FLAT_RUN)
    site = Site(name, C.SITES.index(name), Y.year, Y.days, [cols[b] for b in keep],
                [Y.aud.primaryspaceusage[cols[b]] for b in keep], Ys, complete, wk, season_mask(Y.days),
                Y.tmax[name].values, Y.folds.iloc[keep].values, win, Y.hol[c], dropped, excl)
    return site, excl
