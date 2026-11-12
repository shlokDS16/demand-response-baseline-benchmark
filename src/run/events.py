"""Event rules R1, R3 (5 draws), R2-ISO, R2-LOO (PREREG s2). R1 and R3 dates are READ from the frozen file
results/frozen/event_dates.csv (T3 1.3, generated from weather and holidays only) and never recomputed here.
Folds are read from results/frozen/folds.csv (data.py)."""
import numpy as np
import pandas as pd

from . import config as C
from . import leakage as LK

_EV = None


def frozen_events():
    global _EV
    if _EV is None:
        _EV = pd.read_csv(C.EVENTS_CSV, parse_dates=["date"])
    return _EV


def day_index(site, dates):
    pos = site.days.get_indexer(pd.DatetimeIndex(dates))
    assert (pos >= 0).all()
    return np.array(pos)


def _check_candidates(site, idx):
    """Sanity: event days are non-holiday weekdays inside the season with a valid Tmax (no load involved)."""
    assert site.wk[idx].all() and site.season[idx].all(), "frozen event day not a season weekday"
    assert not np.isnan(site.tm[idx]).any()


def r1_days(site):
    ev = frozen_events()
    e = ev[(ev.site_id == site.name) & (ev.year == site.year) & (ev.rule == "R1") & ev.primary].sort_values("rank")
    LK.a8_event_selection_no_load("frozen_file")
    idx = day_index(site, e.date)
    assert len(idx) == C.K_EVENTS, (site.name, len(idx))
    _check_candidates(site, idx)
    return idx


def r3_draws(site):
    """List of 5 index arrays (draws 1..5), R1 days excluded from the candidate set (checked)."""
    ev = frozen_events()
    r1 = set(r1_days(site).tolist())
    out = []
    for dr in C.R3_DRAWS:
        e = ev[(ev.site_id == site.name) & (ev.year == site.year) & (ev.rule == "R3") & (ev.draw == dr) & ev.primary]
        idx = day_index(site, e.date)
        assert len(idx) == C.K_EVENTS
        assert not (set(idx.tolist()) & r1), "R3 draw overlaps R1 days"
        _check_candidates(site, idx)
        out.append(idx)
    LK.a8_event_selection_no_load("frozen_file")
    return out


def r2iso_days(site):
    """Top-ranked weekdays by day-ahead forecast BA peak, after removing E7 holidays; US sites only."""
    d = pd.read_csv(C.R2ISO_CSV, parse_dates=["date"])
    d = d[(d.site_id == site.name) & (d.year == site.year)]
    if d.empty:
        return None
    d = d[d.date.isin(site.days)]
    ix = site.days.get_indexer(d.date)
    d = d.assign(ix=ix)
    d = d[[bool(site.wk[i]) for i in d.ix]].sort_values("rank")  # weekday and not E7 holiday
    d = d.head(C.K_EVENTS)
    LK.a8_event_selection_no_load("r2iso_forecast")
    return d.ix.values if len(d) == C.K_EVENTS else None


def r2loo_groups(site):
    """R2-LOO (exploratory): per target the K weekdays with the highest site window load excluding the target.
    Targets sharing an identical event set are grouped. Returns list of (frozenset-of-days array, [building idx])."""
    LK.a8_event_selection_no_load("r2loo_exploratory")
    cand = np.where(site.wk & site.season)[0]
    own = np.where(site.complete, site.Ys[:, site.WIN, :].sum(1), 0.0)
    Wl = own.sum(1)
    groups = {}
    for j in range(site.nb):
        tot = Wl - own[:, j]
        top = cand[np.argsort(-tot[cand], kind="stable")][:C.K_EVENTS]
        groups.setdefault(tuple(sorted(top.tolist())), []).append(j)
    return [(np.array(k), v) for k, v in groups.items()]


def heatwave_days(site, thr_tmax):
    """Every weekday of each run of >= 3 consecutive weekdays above the site's 2016 80th percentile of season Tmax."""
    ok = np.where(site.wk & site.season & ~np.isnan(site.tm) & (np.nan_to_num(site.tm, nan=-99) > thr_tmax))[0]
    wk_idx = np.where(site.wk)[0]
    pos = {d: i for i, d in enumerate(wk_idx)}
    out, run = [], []
    for d in ok:
        if run and pos[d] == pos[run[-1]] + 1:
            run.append(d)
        else:
            if len(run) >= C.HEATWAVE_MIN_RUN:
                out += run
            run = [d]
    if len(run) >= C.HEATWAVE_MIN_RUN:
        out += run
    return np.array(sorted(out), int)


def r1_order(site):
    """Frozen R1 ranks 1..40 (dispatch order for H5); never recomputed from weather here."""
    ev = frozen_events()
    e = ev[(ev.site_id == site.name) & (ev.year == site.year) & (ev.rule == "R1")].sort_values("rank")
    idx = day_index(site, e.date)
    assert len(idx) == 40 and e["rank"].tolist() == list(range(1, 41))
    LK.a8_event_selection_no_load("frozen_file")
    return idx
