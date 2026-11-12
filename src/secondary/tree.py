"""Screening tree (exploratory; PREREG s6 'Secondary', Revision 2 row 14): depth 2, minimum leaf 20 buildings, no pruning,
trained on 2016 only; features fixed (use, slope of window load on Tmax, window CV, log size, correlation of the building's
daily window load with its site mean); classes pjmA, cgA, scmR; tested in 2017 against pjmA by the site-median log ratio.

CHOICE_AFTER_FREEZE (PREREG leaves these open; simplest option each):
 * Label of a training building = the method with the lowest building relMAE on the 2016 R1 events (common support of the
   three methods; ties go to pjmA, then cgA).
 * Features are computed from 2016 load only, on non-event season weekdays (the site's frozen 2016 R1 days and R3 draws
   excluded), for the training buildings AND for the 2017 buildings: no 2017 load enters the tree (assertion 4).
   slope = OLS slope of daily window load on daily Tmax divided by the mean window load (per-unit); CV = std/mean of the daily
   window load; log size = log mean daily window load; corr = Pearson correlation of the building's daily window load with the
   site mean over the buildings of that meter set; use = one indicator per primary space usage with >= 20 training buildings
   (other uses pooled in 'Other').
 * sklearn DecisionTreeClassifier(criterion='gini', max_depth=2, min_samples_leaf=20, ccp_alpha=0, random_state=2016).
 * 2016 dev run: trained on the fold-A buildings and tested on the fold-B buildings of the same year (2017 does not exist
   in a dev run); the 2017 run trains on all 2016 buildings and tests on the 2017 R1 results.
 * Test statistic: per building log(relMAE(chosen) / relMAE(pjmA)); site median; two-sided exact signed-rank over sites, HL."""
import numpy as np
import pandas as pd

from run import adjust, config as C, data as D, events as EV
from run import stats as ST
from run import analysis as AN

FEATURES = ["slope_rel", "cv", "log_size", "corr_site"]
CLASSES = ["pjmA", "cgA", "scmR"]


def window_features(Y16, win):
    """Per meter (2016 raw load after DST): relative Tmax slope, window CV, log size, correlation with site mean; days:
    season weekdays of the site that are neither frozen R1 nor R3 days; complete 24 h."""
    s, e = win
    WIN = list(range(s, e))
    ev = EV.frozen_events()
    rows = []
    cols = Y16.cols
    for name in C.SITES:
        bi = [cols.index(b) for b in Y16.aud.index[Y16.aud.site_id == name]]
        if not bi or name not in Y16.tmax.columns:
            continue
        c = D.ctry(Y16.aud.timezone[Y16.aud.site_id == name].iloc[0])
        wk = D.site_weekday_mask(Y16.days, Y16.hol[c]) & D.season_mask(Y16.days)
        ed = ev[(ev.site_id == name) & (ev.year == 2016) & ev.primary & ev.rule.isin(["R1", "R3"])].date
        evmask = Y16.days.isin(pd.DatetimeIndex(ed))
        tm = Y16.tmax[name].values
        use_d = wk & ~evmask & ~np.isnan(tm)
        X = Y16.X[:, :, bi].astype(np.float64)
        Wd = X[:, WIN, :].sum(1)                       # days x nb (NaN when any hour is missing)
        ok_d = ~np.isnan(X).any(1) & use_d[:, None]
        Wm = np.where(ok_d, Wd, np.nan)
        site_mean = np.nanmean(Wm, 1)
        for k, b in enumerate(bi):
            m = ok_d[:, k]
            if m.sum() < 30:
                continue
            y, t = Wm[m, k], tm[m]
            mu = y.mean()
            if not mu > 0:
                continue
            slope = np.polyfit(t, y, 1)[0] / mu if np.ptp(t) > 0 else 0.0
            sm = site_mean[m]
            cc = np.corrcoef(y, sm)[0, 1] if y.std() > 0 and sm.std() > 0 else np.nan
            rows.append(dict(b=cols[b], site=name, use=Y16.aud.primaryspaceusage[cols[b]], slope_rel=float(slope),
                             cv=float(y.std() / mu), log_size=float(np.log(mu)), corr_site=float(cc), n_days=int(m.sum())))
    return pd.DataFrame(rows).set_index("b")


def building_relmae(R1, s, e, methods=CLASSES):
    """Per-building relMAE of each method on the common support of all methods (frozen definitions); columns site, b + methods."""
    b = adjust.adjusted(R1, s, e)
    ok = AN.pair_events(R1, b, methods)
    out = pd.DataFrame({m: AN.bld_stat(R1, b, m, ok, "relMAE") for m in methods}).dropna()
    out.index.names = ["site", "b"]
    return out.reset_index().set_index("b")


def label_from_relmae(rel):
    """Lowest relMAE; ties to pjmA, then cgA (column order CLASSES; idxmin returns the first minimum)."""
    return rel[CLASSES].idxmin(axis=1)


def design_matrix(feat, uses):
    X = feat[FEATURES].copy()
    for u in uses:
        X["use_" + u] = (feat["use"] == u).astype(float)
    return X


def fit_tree(X, y):
    from sklearn.tree import DecisionTreeClassifier
    t = DecisionTreeClassifier(criterion="gini", max_depth=2, min_samples_leaf=20, ccp_alpha=0.0, random_state=2016)
    t.fit(X.values, y.values)
    return t


def run_tree(year, led):
    from sklearn.tree import export_text
    s, e = C.WINDOWS["primary"]
    Y16 = D.build_year(2016)
    feat = window_features(Y16, (s, e))
    R16 = pd.read_pickle(C.ROOT / "results" / "run_v0" / "events_R1.pkl")   # 2016 R1 frame (self-written by run_core, trusted)
    rel16 = building_relmae(R16, s, e)
    lab16 = label_from_relmae(rel16)
    fold16 = R16.drop_duplicates("b").set_index("b").fold
    if year == 2016:
        train_b = [b for b in rel16.index if fold16[b] == "A" and b in feat.index]
        test_b = [b for b in rel16.index if fold16[b] == "B" and b in feat.index]
        rel_test = rel16
    else:
        train_b = [b for b in rel16.index if b in feat.index]
        rel_test = building_relmae(CM_load_R1(2017), s, e)
        test_b = [b for b in rel_test.index if b in feat.index]
    ftr = feat.loc[train_b]
    uses = [u for u, n in ftr.use.value_counts().items() if n >= 20]
    Xtr = design_matrix(ftr, uses)
    mask = Xtr[FEATURES].notna().all(axis=1).values
    train_b = list(np.array(train_b)[mask])
    Xtr, ytr = Xtr[mask], lab16.loc[train_b]
    tree = fit_tree(Xtr, ytr)
    rules = export_text(tree, feature_names=list(Xtr.columns))
    Xte = design_matrix(feat.loc[test_b], uses)
    okt = Xte[FEATURES].notna().all(axis=1).values
    tb = list(np.array(test_b)[okt])
    pred = pd.Series(tree.predict(Xte.values[okt]), index=tb)
    rt = rel_test.loc[tb]
    chosen = np.array([rt.loc[b, pred[b]] for b in tb], float)
    lr = pd.Series(np.log(chosen / rt.pjmA.values), index=pd.MultiIndex.from_arrays([rt.site.values, tb]))
    lr = lr.replace([np.inf, -np.inf], np.nan).dropna()
    sv = lr.groupby(level=0).median()
    sr = ST.signed_rank(sv.values, "two")
    est, lo, hi, conf = ST.hl_ci(sv.values)
    ledger_rows(led, year, rules, tree, Xtr, ytr, pred, lr, sv, sr, est, lo, hi, uses, len(train_b))
    return dict(rules=rules, est=est, ci=(lo, hi), p=sr["p"])


def CM_load_R1(year):
    from secondary import common as CM
    return CM.load_R1(year)


def ledger_rows(led, year, rules, tree, Xtr, ytr, pred, lr, sv, sr, est, lo, hi, uses, n_train):
    led.add("screen.tree.rules", rules, status="secondary")
    led.add("screen.tree.n_train", int(len(ytr)), status="secondary")
    led.add("screen.tree.train_accuracy", float((tree.predict(Xtr.values) == ytr.values).mean()), status="secondary")
    led.add("screen.tree.uses", ",".join(uses), status="secondary")
    for c in CLASSES:
        led.add("screen.train.class_share.%s" % c, float((ytr == c).mean()), status="secondary")
        led.add("screen.test.assigned_share.%s" % c, float((pred == c).mean()), status="secondary")
    led.add("screen.test.n_buildings", int(len(lr)), n_sites=int(len(sv)), status="secondary")
    led.add("screen.test.logratio_vs_pjmA", est, ci_low=lo, ci_high=hi, p_raw=sr["p"], n_sites=int(sr["n"]),
            n_buildings=int(len(lr)), status="secondary")
    led.add("screen.test.logratio_site_median_of_medians", float(np.median(sv.values)), n_sites=int(len(sv)), status="secondary")
    led.add("screen.test.n_sites_better", int((sv < 0).sum()), n_sites=int(len(sv)), status="secondary")
    for site, v in sv.items():
        led.add("screen.test.site.%s" % site, float(v), status="secondary")
    led.add("screen.test.pooled_relMAE_chosen_over_pjmA", float(np.exp(lr.mean())), status="secondary")
