"""Optuna HPO for lgbM / lgbD / mlpM / mlpD (PREREG s3 row lgb/mlp, s5 hyperparameters, s9 assertions 4, 5, 16, 17) and the
frozen secondary evaluation with the tuned parameters.

    python -I src/secondary/hpo.py --models lgbM,lgbD,mlpM,mlpD --trials 40 --eval-years 2017 [--device cuda]
    python -I src/secondary/hpo.py --dry-run
    python -I src/secondary/hpo.py --sites Hog --trials 3 --device cpu --out results/hpo_smoke     (smoke test)

Design (everything not fixed by PREREG is marked CHOICE_AFTER_FREEZE and recorded as hpo.<m>.choice.* rows):
 * Tuning uses 2016 ONLY. Per site and per refit month (May..Sep) the model is fitted on the eligible non-event weekdays of
   2016 before the first day of the month (monthly refit as in src/run/secondary.py::lgb_site), with early stopping on the
   chronologically last 20 % of those training days (s9.16), and scored on the eligible non-event weekdays of that month
   (time-blocked, expanding window). Objective (minimise) = mean over sites of the site median over buildings of the building
   mean |pred - y| / y (y = window load / dm0 window, the frozen target). 2016 event days are not used in tuning.
 * 40 TPE trials per model, Optuna TPESampler(seed=2016), SQLite storage results/hpo/hpo_<model>.db (resumable).
 * Features, targets, offsets, refits identical to the frozen lgb_site (copied, not imported: the frozen function is a closure);
   built once per (year, site, world) and cached as float32 npz, so trials never touch the load files again.
 * Final fit: tuned parameters, frozen monthly refits on the scored year, seeds 0-4, mean over seeds reported. Worlds R1 and the
   five R3 draws. 2017 aborts unless the frozen manifest matches (secondary.common.freeze_hash).
 * lgb on 2017 trains on 2017 rows before the refit month only (frozen limitation, unchanged).
"""
import argparse
import gc
import json
import os
import site as _site
import sys
import time
from pathlib import Path

up = _site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../src (needed under python -I)

import numpy as np   # noqa: E402
import pandas as pd   # noqa: E402

from run import config as C   # noqa: E402
from run import ledger as LD   # noqa: E402
from secondary import common as CM   # noqa: E402

MODELS = ("lgbM", "lgbD", "mlpM", "mlpD")
HPO_SEED = 2016
TRIALS = 40
FINAL_SEEDS = (0, 1, 2, 3, 4)
TUNE_YEAR = 2016
TUNE_MONTHS = (5, 6, 7, 8, 9)
MIN_TRAIN_ROWS = 500          # frozen lgb_site: refit skipped below 500 training rows
INNER_FRAC = 0.8              # s5: chronologically last 20 % of the training days = early-stopping block
CAT = {"M": 4, "D": 6}        # categorical column (day of week) in the frozen feature layout
LGB_ROUNDS, LGB_PATIENCE = 3000, 50
MLP_EPOCHS, MLP_PATIENCE, MLP_BATCH = 200, 15, 256
import threading   # noqa: E402
_INIT_LOCK = threading.Lock()
WORLDS = ("R1", "R3_1", "R3_2", "R3_3", "R3_4", "R3_5")


# ============================================================ feature tables (copy of frozen lgb_site features)
def build_tables(site, evset, ev_score):
    """Per variant: training candidates (every eligible non-event weekday with finite features; the refit month cut is applied
    at fit time) and the event-day rows to be scored. Same features and target as src/run/secondary.py::lgb_site."""
    from run import secondary as RS
    from run import leakage as LK
    s, nb, WIN = site.s, site.nb, site.WIN
    ND = site.Ys.shape[0]
    fold = site.fold
    base = {j: RS._roll_offset(site, evset, j)[0] for j in range(nb)}
    for d in ev_score:
        for j in range(nb):
            el = [k for k in range(d - 1, -1, -1) if site.wk[k] and site.complete[k, j] and k not in evset][:10]
            LK.a1_lookback_before(d, el)
            if len(el) == 10 and site.complete[d, j]:
                W = np.array([site.Ys[k, WIN, j].sum() for k in el])
                base[j][d] = (W.mean(), np.mean([site.Ys[k, :s - 4, j].mean() for k in el]),
                              np.mean([site.Ys[k, [s - 4, s - 3, s - 2], j].mean() for k in el]),
                              np.nanmean(site.tm[el]), W.std() / max(W.mean(), 1e-9), max(el))
    DW = np.full((ND, nb), np.nan)
    DM = np.full((ND, nb), np.nan)
    D09 = np.full((ND, nb), np.nan)
    DM09 = np.full((ND, nb), np.nan)
    for j in range(nb):
        for k, v in base[j].items():
            if site.complete[k, j]:
                DW[k, j] = site.Ys[k, WIN, j].sum()
                DM[k, j] = v[0] * len(WIN)
                D09[k, j] = site.Ys[k, :s - 4, j].mean()
                DM09[k, j] = v[1]

    def donor_feats(k, j):
        dm = np.where(fold != fold[j])[0]
        a, b = DW[k, dm], DM[k, dm]
        okk = np.isfinite(a) & np.isfinite(b)
        c, dd = D09[k, dm], DM09[k, dm]
        ok2 = np.isfinite(c) & np.isfinite(dd)
        return (a[okk].sum() / b[okk].sum() if okk.sum() >= 5 else np.nan,
                c[ok2].sum() / dd[ok2].sum() if ok2.sum() >= 5 else np.nan)

    def feats(k, j, variant):
        v = base[j].get(k)
        if v is None:
            return None
        Wm, m09o, m1012o, tmo, cv, _ = v
        tmk = site.tm[k]
        f = [tmk, tmk - tmo, site.days[k].month, site.days[k].dayofweek, j, np.log(max(Wm, 1e-9)), cv]
        if variant == "M":
            return [site.Ys[k, [s - 4, s - 3, s - 2], j].mean() / max(m1012o, 1e-9)] + f
        dw, d09 = donor_feats(k, j)
        return [site.Ys[k, :s - 4, j].mean() / max(m09o, 1e-9), dw, d09] + f

    out = dict(dates=site.days.values.astype("datetime64[D]").astype(np.int64), season=np.asarray(site.season, bool),
               meters=np.array(site.meters, dtype="U64"), year=np.int64(site.year),
               ev_days=np.array(sorted(ev_score), dtype=np.int64))
    for variant in ("M", "D"):
        Xt, yt, kt, jt = [], [], [], []
        for j in range(nb):
            for k, v in base[j].items():
                if k in evset or not site.complete[k, j]:
                    continue
                f = feats(k, j, variant)
                if f is None or not np.isfinite(f).all():
                    continue
                Xt.append(f)
                yt.append(site.Ys[k, WIN, j].sum() / (v[0] * len(WIN)))
                kt.append(k)
                jt.append(j)
        Xe, de, je, offe, Le = [], [], [], [], []
        for d in sorted(ev_score):
            for j in range(nb):
                f = feats(d, j, variant)
                if f is None or not np.isfinite(f).all():
                    continue
                Xe.append(f)
                de.append(d)
                je.append(j)
                offe.append(base[j][d][0] * len(WIN))
                Le.append(site.Ys[d, WIN, j].sum())
        out.update({
            variant + "_X": np.asarray(Xt, np.float32).reshape(-1, 8 if variant == "M" else 10), variant + "_y": np.asarray(yt, np.float32),
            variant + "_k": np.asarray(kt, np.int32), variant + "_j": np.asarray(jt, np.int32),
            variant + "_Xe": np.asarray(Xe, np.float32).reshape(-1, 8 if variant == "M" else 10), variant + "_de": np.asarray(de, np.int32),
            variant + "_je": np.asarray(je, np.int32), variant + "_offe": np.asarray(offe, np.float64),
            variant + "_Le": np.asarray(Le, np.float64)})
    return out


def cache_path(cache_dir, year, name, world):
    return Path(cache_dir) / ("%d_%s_%s.npz" % (year, name, world))


def ensure_cache(year, worlds, sites, cache_dir, log=print):
    """Build the missing feature caches of (year, site, world). The load year is read once and only if something is missing."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    todo = [(n, w) for n in sites for w in worlds if not cache_path(cache_dir, year, n, w).exists()
            and not cache_path(cache_dir, year, n, "SKIP").exists()]
    if not todo:
        return
    from run import data as D, events as EV
    t0 = time.time()
    Y = D.build_year(year)
    log("cache: year %d loaded in %.0f s, %d (site, world) tables to build" % (year, time.time() - t0, len(todo)))
    for n in sites:
        need = [w for (nn, w) in todo if nn == n]
        if not need:
            continue
        site, _ = D.make_site(Y, n)
        if site is None:
            cache_path(cache_dir, year, n, "SKIP").write_bytes(b"")       # site fails the sample rules (E4)
            log("cache: %s skipped (not in the sample)" % n)
            continue
        r1 = EV.r1_days(site)
        r3 = EV.r3_draws(site)
        for w in need:
            ev = r1 if w == "R1" else r3[int(w.split("_")[1]) - 1]
            tb = build_tables(site, set(ev.tolist()), set(ev.tolist()))
            np.savez(cache_path(cache_dir, year, n, w), **tb)
            log("cache: %d %s %s done (%.0f s)" % (year, n, w, time.time() - t0))
        del site
        gc.collect()
    del Y
    gc.collect()


def load_cache(cache_dir, year, name, world):
    p = cache_path(cache_dir, year, name, world)
    if cache_path(cache_dir, year, name, "SKIP").exists() or not p.exists():
        return None
    z = np.load(p)
    return {k: z[k] for k in z.files}


# ============================================================ model fits
def month_first(T, month):
    """First calendar day of `month` in the site's year (index into dates). Same rule as the frozen refit."""
    mo = T["dates"].astype("datetime64[D]").astype("datetime64[M]").astype(int) % 12 + 1
    return int(np.where(mo == month)[0][0]), mo


def inner_split(kd):
    cut = np.quantile(kd, INNER_FRAC)
    return kd <= cut, kd > cut


def assert_leak_free(T, kd, first, tr, va, val_days=None, tune=False):
    """s9 assertions 1, 4, 5, 16 on the rows actually used by one fit (and, in tuning, 2016 only)."""
    assert len(kd) == 0 or kd.max() < first, "leak: fit row not before the prediction month"
    assert kd[tr].max() < kd[va].min(), "leak: early-stopping block does not follow the fitting days"
    if val_days is not None:
        assert val_days.min() >= first, "validation day before the month start"
    if tune:
        used = np.concatenate([kd] + ([val_days] if val_days is not None else []))
        yrs = T["dates"][used].astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
        assert (yrs == TUNE_YEAR).all() and int(T["year"]) == TUNE_YEAR, "2017 date entered tuning"


def lgb_params(hp, seed, threads):
    return dict(objective="l1", learning_rate=hp["learning_rate"], num_leaves=int(hp["num_leaves"]),
                min_child_samples=int(hp["min_child_samples"]), lambda_l2=hp["lambda_l2"], feature_fraction=hp["feature_fraction"],
                bagging_fraction=hp["bagging_fraction"], bagging_freq=1, seed=int(seed), deterministic=True, force_row_wise=True,
                num_threads=threads, verbose=-1)


def fit_lgb(X, y, kd, cat, hp, seed, threads):
    import lightgbm as lgb
    tr, va = inner_split(kd)
    dset = lgb.Dataset(X[tr], y[tr], categorical_feature=[cat], free_raw_data=False)
    vset = lgb.Dataset(X[va], y[va], reference=dset)
    mdl = lgb.train(lgb_params(hp, seed, threads), dset, num_boost_round=LGB_ROUNDS, valid_sets=[vset],
                    callbacks=[lgb.early_stopping(LGB_PATIENCE, verbose=False)])
    return lambda Z: mdl.predict(Z)


class MlpFit:
    """Standardiser (train rows of the refit only, s9.5), one-hot day of week, MLP, AdamW, cosine, L1, early stopping."""

    def __init__(self, X, y, kd, cat, hp, seed, device, threads=None):
        import torch
        self.torch = torch
        if threads:
            torch.set_num_threads(threads)
        tr, va = inner_split(kd)
        self.num = [i for i in range(X.shape[1]) if i != cat]
        self.cat = cat
        Xn = X[tr][:, self.num].astype(np.float64)
        self.lo, self.hi = np.percentile(Xn, 0.5, axis=0), np.percentile(Xn, 99.5, axis=0)   # CHOICE: winsorise (ratio features)
        Z = np.clip(Xn, self.lo, self.hi)
        self.mu, self.sd = Z.mean(0), Z.std(0)
        self.sd[self.sd < 1e-8] = 1.0
        dev = torch.device(device)
        self.dev = dev
        Xt = torch.tensor(self._prep(X[tr]), device=dev)
        yt = torch.tensor(y[tr], dtype=torch.float32, device=dev)
        Xv = torch.tensor(self._prep(X[va]), device=dev)
        yv = torch.tensor(y[va], dtype=torch.float32, device=dev)
        g = torch.Generator(device=dev)          # per-fit generator: shuffling and dropout never touch the global RNG (thread safe)
        g.manual_seed(int(seed))

        class GDropout(torch.nn.Module):
            def __init__(self, p):
                super().__init__()
                self.p = p

            def forward(self, x):
                if not self.training or self.p <= 0:
                    return x
                return x * (torch.rand(x.shape, generator=g, device=x.device) >= self.p).to(x.dtype) / (1.0 - self.p)

        with _INIT_LOCK:                          # weight init uses the global RNG: seed and build under a lock
            torch.manual_seed(int(seed))
            layers, d_in = [], Xt.shape[1]
            for _ in range(int(hp["depth"])):
                layers += [torch.nn.Linear(d_in, int(hp["width"])), torch.nn.ReLU(), GDropout(float(hp["dropout"]))]
                d_in = int(hp["width"])
            layers.append(torch.nn.Linear(d_in, 1))
            net = torch.nn.Sequential(*layers)
        net = net.to(dev)
        with torch.no_grad():
            net[-1].bias.fill_(float(np.median(y[tr])))                                       # train-only statistic
        opt = torch.optim.AdamW(net.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=MLP_EPOCHS)
        best, bad, state = float("inf"), 0, None
        n = Xt.shape[0]
        for ep in range(MLP_EPOCHS):
            net.train()
            perm = torch.randperm(n, device=dev, generator=g)
            for i in range(0, n, MLP_BATCH):
                idx = perm[i:i + MLP_BATCH]
                opt.zero_grad(set_to_none=True)
                loss = (net(Xt[idx]).squeeze(1) - yt[idx]).abs().mean()
                loss.backward()
                opt.step()
            sch.step()
            net.eval()
            with torch.no_grad():
                v = float((net(Xv).squeeze(1) - yv).abs().mean())
            if v < best - 1e-7:
                best, bad = v, 0
                state = {k: t.detach().clone() for k, t in net.state_dict().items()}
            else:
                bad += 1
                if bad >= MLP_PATIENCE:
                    break
        net.load_state_dict(state)
        net.eval()
        self.net = net
        self.epochs = ep + 1

    def _prep(self, X):
        Z = (np.clip(X[:, self.num].astype(np.float64), self.lo, self.hi) - self.mu) / self.sd
        oh = np.eye(7, dtype=np.float64)[np.clip(X[:, self.cat].astype(int), 0, 6)]
        return np.hstack([Z, oh]).astype(np.float32)

    def predict(self, X):
        with self.torch.no_grad():
            return self.net(self.torch.tensor(self._prep(X), device=self.dev)).squeeze(1).cpu().numpy().astype(np.float64)


def fit_model(kind, X, y, kd, cat, hp, seed, args):
    if kind == "lgb":
        return fit_lgb(X, y, kd, cat, hp, seed, fit_threads('lgb', args))
    return MlpFit(X, y, kd, cat, hp, seed, args.device, args.torch_threads).predict


# ============================================================ tuning (2016 only)
def suggest(trial, kind):
    if kind == "lgb":
        return dict(learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                    num_leaves=trial.suggest_int("num_leaves", 7, 127, log=True),
                    min_child_samples=trial.suggest_int("min_child_samples", 5, 200, log=True),
                    lambda_l2=trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
                    feature_fraction=trial.suggest_float("feature_fraction", 0.5, 1.0),
                    bagging_fraction=trial.suggest_float("bagging_fraction", 0.5, 1.0))
    return dict(depth=trial.suggest_int("depth", 1, 3), width=trial.suggest_categorical("width", [32, 64, 128, 256]),
                dropout=trial.suggest_float("dropout", 0.0, 0.3), lr=trial.suggest_float("lr", 1e-4, 3e-3, log=True),
                weight_decay=trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True))


def n_workers(kind, args):
    return args.workers or (1 if kind == "lgb" else 4)


def fit_threads(kind, args):
    return max(1, args.threads // n_workers(kind, args)) if kind == "lgb" else args.threads


def pmap(fn, items, workers):
    """Thread pool (LightGBM and torch release the GIL); results in input order, so every run is reproducible."""
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


def _month_tune(kind, variant, name, T, mo, hp, args, seed):
    X, y, kk, jj = T[variant + "_X"], T[variant + "_y"], T[variant + "_k"], T[variant + "_j"]
    first, months = month_first(T, mo)
    trm = kk < first
    vam = (months[kk] == mo) & T["season"][kk]
    if trm.sum() < MIN_TRAIN_ROWS or vam.sum() == 0:
        return None
    kd = kk[trm]
    tr, va = inner_split(kd)
    assert_leak_free(T, kd, first, tr, va, kk[vam], tune=True)         # every fit, every trial: 2016 dates only, train < month <= val
    pred = fit_model(kind, X[trm], y[trm], kd, CAT[variant], hp, seed, args)
    pv = pred(X[vam])
    yv = y[vam].astype(np.float64)
    ok = yv > 1e-3
    return name, pd.DataFrame({"j": jj[vam][ok], "e": np.abs(pv[ok] - yv[ok]) / yv[ok]}), int(T["dates"][kk[vam]].max()), int(ok.sum())


def tune_score(kind, variant, tables, hp, args, seed):
    """Mean over sites of the site median over buildings of the building mean relative error on the validation months.
    The (site, month) fits are independent and run on a thread pool."""
    tasks = [(n, T, mo) for n, T in tables.items() for mo in TUNE_MONTHS]
    res = [r for r in pmap(lambda t: _month_tune(kind, variant, t[0], t[1], t[2], hp, args, seed), tasks, n_workers(kind, args)) if r]
    site_scores = []
    for n in tables:
        rr = [r[1] for r in res if r[0] == n]
        if rr:
            site_scores.append(float(pd.concat(rr).groupby("j").e.mean().median()))
    assert site_scores, "no site produced a validation score"
    return float(np.mean(site_scores)), dict(max_val_date=str(np.datetime64(max(r[2] for r in res), "D")), n_fits=len(res),
                                             n_val_rows=sum(r[3] for r in res), n_sites=len(site_scores))


def storage_url(hpo_dir, model):
    return "sqlite:///" + str((Path(hpo_dir) / ("hpo_%s.db" % model)).resolve()).replace("\\", "/")


def tune(model, args, sites, log=print):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    kind, variant = model[:3], model[3]
    ensure_cache(TUNE_YEAR, ["R1"], sites, args.cache_dir, log)
    tables = {n: load_cache(args.cache_dir, TUNE_YEAR, n, "R1") for n in sites}
    tables = {n: T for n, T in tables.items() if T is not None}
    assert tables and all(int(T["year"]) == TUNE_YEAR for T in tables.values()), "tuning tables must be 2016"
    st0 = optuna.create_study(study_name="hpo_%s" % model, storage=storage_url(args.hpo_dir, model), load_if_exists=True, direction="minimize")
    n0 = len([t for t in st0.trials if t.state == optuna.trial.TrialState.COMPLETE])
    # seed = 2016 for a fresh study; after an interruption the sampler is re-seeded with 2016 + completed trials, otherwise the
    # random start-up trials would repeat the earlier ones (a resumed TPESampler restarts its random stream)
    study = optuna.create_study(study_name="hpo_%s" % model, storage=storage_url(args.hpo_dir, model), load_if_exists=True,
                                direction="minimize", sampler=optuna.samplers.TPESampler(seed=HPO_SEED + n0))
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    seed = HPO_SEED if kind == "lgb" else 0

    def objective(trial):
        hp = suggest(trial, kind)
        t0 = time.time()
        v, info = tune_score(kind, variant, tables, hp, args, seed)
        for k_, v_ in dict(info, time_s=round(time.time() - t0, 1)).items():
            trial.set_user_attr(k_, v_)
        log("  %s trial %d score %.5f (%.0f s, rss peak %.2f GB)" % (model, trial.number, v, time.time() - t0, CM.peak_gb()))
        return v

    todo = max(0, args.trials - len(done))
    log("%s: %d/%d trials complete, running %d more" % (model, len(done), args.trials, todo))
    t0 = time.time()
    if todo:
        study.optimize(objective, n_trials=todo, gc_after_trial=True)
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    return study, dict(time_s=round(time.time() - t0, 1), peak_gb=round(CM.peak_gb(), 3), n_done=len(done),
                       max_val_date=max((t.user_attrs.get("max_val_date", "") for t in done), default=""))


# ============================================================ final evaluation (frozen refits, tuned parameters)
def eval_world(model, hp, year, world, name, args):
    """Predictions (site, meter, day, seed, pred) for one site and one world. Resumable per file."""
    kind, variant = model[:3], model[3]
    f = Path(args.hpo_dir) / "eval" / ("%s_%d_%s_%s.pkl" % (model, year, world, name))
    if f.exists():
        return pd.read_pickle(f)
    T = load_cache(args.cache_dir, year, name, world)
    if T is None:
        return None
    assert int(T["year"]) == year
    X, y, kk = T[variant + "_X"], T[variant + "_y"], T[variant + "_k"]
    Xe, de, je, offe = T[variant + "_Xe"], T[variant + "_de"], T[variant + "_je"], T[variant + "_offe"]
    rows = []
    for mo in sorted({int(m) for m in month_first(T, 1)[1][np.unique(de)]}):
        first, months = month_first(T, mo)
        trm = kk < first
        if trm.sum() < MIN_TRAIN_ROWS:
            continue
        kd = kk[trm]
        tr, va = inner_split(kd)
        assert_leak_free(T, kd, first, tr, va)
        em = months[de] == mo
        for seed in args.seeds:
            pred = fit_model(kind, X[trm], y[trm], kd, CAT[variant], hp, seed, args)
            p = pred(Xe[em]) * offe[em]
            rows.append(pd.DataFrame({"site": name, "b": T["meters"][je[em]], "day": [str(np.datetime64(int(T["dates"][d]), "D")) for d in de[em]],
                                      "world": world, "seed": seed, "pred": p}))
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["site", "b", "day", "world", "seed", "pred"])
    f.parent.mkdir(parents=True, exist_ok=True)
    out.to_pickle(f)
    return out


def score_year(model, hp, year, worlds, sites, args, log=print):
    """Returns {'R1': {seed: tab}, 'R3': {seed: tab}} with the frozen method_table-style summary of the model column."""
    from run import adjust, config as CC
    from run import secondary as RS
    s, e = CC.WINDOWS["primary"]
    ensure_cache(year, worlds, sites, args.cache_dir, log)
    preds = []
    jobs = [(w, n) for w in worlds for n in sites]

    def one(job):
        p = eval_world(model, hp, year, job[0], job[1], args)
        log("  eval %s %d %s %s done (rss peak %.2f GB)" % (model, year, job[0], job[1], CM.peak_gb()))
        return p

    for p in pmap(one, jobs, n_workers(model[:3], args)):
        if p is not None and len(p):
            preds.append(p)
    P = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame(columns=["site", "b", "day", "world", "seed", "pred"])
    res = {}
    for rule in ("R1", "R3"):
        fr = CM.frames_dir(year) / ("events_%s.pkl" % rule)
        F = pd.read_pickle(fr)
        F = F[F.site.isin(sites)].reset_index(drop=True)
        if rule == "R1":
            Pw = P[P.world == "R1"]
            key = ["site", "b", "day"]
        else:
            Pw = P[P.world.str.startswith("R3")].copy()
            Pw["draw"] = Pw.world.str.split("_").str[1].astype(int)
            key = ["site", "b", "day", "draw"]
        if not len(Pw) or not len(F):
            continue
        base = None
        res[rule] = {}
        for sd in args.seeds:
            q = Pw[Pw.seed == sd][key + ["pred"]]
            Fl = F.merge(q, on=key, how="left")
            if base is None:
                base = adjust.adjusted(Fl, s, e)
            base[model] = Fl["pred"].values
            res[rule][sd] = RS._method_tab_from(Fl, base, [model]).get(model)
    return res


# ============================================================ ledger
class HLed(CM.SecLedger):
    def __init__(self, year, fh, mode):
        self.year = year
        self.L = LD.Ledger(mode, year, freeze_hash=fh, source_default="src/secondary/hpo.py")


def emit_tune(led, model, study, tm):
    import optuna
    kind = model[:3]
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    led.add("hpo.%s.trials" % model, len(done), status="secondary")
    led.add("hpo.%s.seed" % model, HPO_SEED, status="secondary")
    led.add("hpo.%s.tune_year" % model, TUNE_YEAR, status="secondary")
    led.add("hpo.%s.best_inner_score" % model, float(study.best_value), status="secondary")
    led.add("hpo.%s.best_trial" % model, int(study.best_trial.number), status="secondary")
    for k, v in study.best_params.items():
        led.add("hpo.%s.best.%s" % (model, k), float(v) if not isinstance(v, (int, np.integer)) else int(v), status="secondary")
    led.add("hpo.%s.max_val_date_any_trial" % model, tm["max_val_date"], status="secondary")
    led.add("hpo.%s.choice.objective" % model,
            "CHOICE_AFTER_FREEZE: mean over sites of site median over buildings of building mean |pred-y|/y on non-event "
            "weekdays of the refit months May-Sep 2016, expanding window, refit before each month, inner early stopping on the last 20 % of the training days",
            status="secondary")
    if kind == "mlp":
        led.add("hpo.%s.choice.preproc" % model, "CHOICE_AFTER_FREEZE: inputs winsorised at the 0.5/99.5 percentiles of the inner-training rows, standardised, day of week one-hot, output bias = median target", status="secondary")
    led.add("compute.hpo.%s.time_s" % model, tm["time_s"], status="secondary")
    led.add("compute.hpo.%s.peak_rss_gb" % model, tm["peak_gb"], status="secondary")


def method_id(model):
    """Ledger method id of the tuned rows: lgbM/lgbD get _hpo (tables/summary.csv already holds method.lgbM.* with fixed parameters)."""
    return model + "_hpo" if model.startswith("lgb") else model


def emit_eval(led, model, res, t_eval, n_seeds):
    for rule, per in res.items():
        tabs = [v for v in per.values() if v]
        if not tabs:
            continue
        for stat in ("relMAE_median", "bias_median", "support_share"):
            vals = np.array([t[stat] for t in tabs])
            led.add("method.%s.%s.%s" % (method_id(model), rule, stat), float(vals.mean()), n_buildings=tabs[0]["n_b"], n_events=tabs[0]["n_events"],
                    status="secondary")
        led.add("method.%s.%s.relMAE_seed_sd" % (method_id(model), rule), float(np.std([t["relMAE_median"] for t in tabs])), status="secondary")
        led.add("method.%s.%s.n_seeds" % (method_id(model), rule), len(tabs), status="secondary")
    led.add("compute.eval.%s.time_s" % model, t_eval["time_s"], status="secondary")
    led.add("compute.eval.%s.peak_rss_gb" % model, t_eval["peak_gb"], status="secondary")


# ============================================================ driver
def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--trials", type=int, default=TRIALS)
    ap.add_argument("--sites", default="", help="comma list (default: all frozen sites)")
    ap.add_argument("--eval-years", default="2017", help="comma list of 2016 (dev, _v0 keys) and 2017 (frozen, manifest checked)")
    ap.add_argument("--worlds", default="R1,R3", help="R1, R3 (five draws) or both")
    ap.add_argument("--phase", default="both", choices=("tune", "eval", "both"))
    ap.add_argument("--device", default="cuda", choices=("cuda", "cpu"), help="MLP device")
    ap.add_argument("--threads", type=int, default=6, help="LightGBM threads per fit (4 to 8 measured equal on this data; 20 is 10x slower)")
    ap.add_argument("--torch-threads", type=int, default=1, help="intra-op threads per MLP fit (the fits themselves run on --workers threads)")
    ap.add_argument("--workers", type=int, default=0, help="parallel sites (default: 1 for lgb, 4 for mlp; measured: python threads over LightGBM fits are slower than one fit with 4-8 OpenMP threads)")
    ap.add_argument("--seeds", default="0,1,2,3,4", help="final seeds")
    ap.add_argument("--out", default="", help="smoke-test directory: ALL outputs go here, tables/summary_secondary.csv is not touched")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    a.models = [m for m in a.models.split(",") if m]
    assert all(m in MODELS for m in a.models), a.models
    a.seeds = tuple(int(x) for x in a.seeds.split(","))
    a.eval_years = [int(x) for x in a.eval_years.split(",") if x]
    a.sites = [x for x in a.sites.split(",") if x] or list(C.SITES)
    assert all(x in C.SITES for x in a.sites), a.sites
    w = a.worlds.split(",")
    a.worlds = (["R1"] if "R1" in w else []) + (list(WORLDS[1:]) if "R3" in w else [])
    root = Path(a.out).resolve() if a.out else C.ROOT / "results" / "hpo"
    a.hpo_dir, a.cache_dir = root, root / "cache"
    return a


def plan(a):
    print("models", a.models, "trials", a.trials, "sites", a.sites, "eval years", a.eval_years, "worlds", a.worlds, "seeds", a.seeds)
    print("storage", a.hpo_dir, "| ledger", "NOT written (smoke)" if a.out else CM.SEC_LEDGER, "| mlp device", a.device)
    for y, ws in [(TUNE_YEAR, ["R1"])] + [(y, a.worlds) for y in a.eval_years]:
        have = sum(cache_path(a.cache_dir, y, n, w).exists() for n in a.sites for w in ws)
        print("cache %d: %d/%d tables present" % (y, have, len(a.sites) * len(ws)))
    for m in a.models:
        try:
            import optuna
            st = optuna.load_study(study_name="hpo_%s" % m, storage=storage_url(a.hpo_dir, m))
            n = len([t for t in st.trials if t.state == optuna.trial.TrialState.COMPLETE])
        except Exception:
            n = 0
        print("study %s: %d/%d trials complete" % (m, n, a.trials))
    print("n fits per trial (upper bound): %d sites x %d months x 1 variant; final: %d sites x ~5 months x %d seeds x %d worlds per model"
          % (len(a.sites), len(TUNE_MONTHS), len(a.sites), len(a.seeds), len(a.worlds)))


def main(argv=None):
    a = parse(argv)
    Path(a.hpo_dir).mkdir(parents=True, exist_ok=True)
    plan(a)
    if a.dry_run:
        print("dry run: nothing fitted")
        return
    fh_by_year = {y: CM.freeze_hash(y) for y in a.eval_years}      # 2017: SystemExit if the manifest does not match
    t_all = time.time()
    for m in a.models:
        # one ledger file per model (a later run with other --models must not overwrite this one)
        led_tune = HLed(TUNE_YEAR, fh_by_year.get(2017, "dev-unfrozen"), "final")
        led_eval = {y: HLed(y, fh_by_year[y], CM.mode_of(y)) for y in a.eval_years}
        hp, study = None, None
        if a.phase in ("tune", "both"):
            study, tm = tune(m, a, a.sites)
            emit_tune(led_tune, m, study, tm)
            hp = study.best_params
        else:
            import optuna
            study = optuna.load_study(study_name="hpo_%s" % m, storage=storage_url(a.hpo_dir, m))
            hp = study.best_params
        if a.phase in ("eval", "both"):
            assert len([t for t in study.trials if t.state.name == "COMPLETE"]) >= a.trials, "tuning incomplete for %s" % m
            for y in a.eval_years:
                t0 = time.time()
                res = score_year(m, hp, y, a.worlds, a.sites, a)
                emit_eval(led_eval[y], m, res, dict(time_s=round(time.time() - t0, 1), peak_gb=round(CM.peak_gb(), 3)), len(a.seeds))
                print(m, y, json.dumps({r: {k: (v["relMAE_median"] if v else None) for k, v in per.items()} for r, per in res.items()}), flush=True)
        _save(a, m, led_tune, led_eval)          # persist after every model (resume safety)
    print("hpo done in %.0f s" % (time.time() - t_all))


def _save(a, m, led_tune, led_eval):
    out = Path(a.out) if a.out else None
    if led_tune.L.rows:
        (led_tune.L.to_frame().to_csv(out / ("hpo_tune_%s.rows.csv" % m), index=False) if out
         else led_tune.L.to_frame().to_csv(CM.out_dir(TUNE_YEAR) / ("hpo_tune_%s.rows.csv" % m), index=False))
    for y, l in led_eval.items():
        if not l.L.rows:
            continue
        if out:
            l.L.to_frame().to_csv(out / ("hpo_eval_%s_%d.rows.csv" % (m, y)), index=False)
        else:
            l.save(y, "hpo_eval_%s" % m)
    if not out:
        CM.collect()


def run(year, led, models=("lgbM", "lgbD", "mlpM", "mlpD")):
    """Entry for `secondary/cli.py --part hpo`: tune on 2016, evaluate `year`. Rows go to `led`; defaults of the CLI above."""
    a = parse(["--models", ",".join(models), "--eval-years", str(year)])
    study_res = {}
    for m in models:
        study, tm = tune(m, a, a.sites)
        emit_tune(led, m, study, tm)
        t0 = time.time()
        res = score_year(m, study.best_params, year, a.worlds, a.sites, a)
        emit_eval(led, m, res, dict(time_s=round(time.time() - t0, 1), peak_gb=round(CM.peak_gb(), 3)), len(a.seeds))
        study_res[m] = res
    return study_res


if __name__ == "__main__":
    main()
