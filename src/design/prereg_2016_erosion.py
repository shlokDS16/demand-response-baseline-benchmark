"""Repeated-dispatch (erosion) pilot, DEVELOPMENT YEAR 2016 ONLY (_v0).
Reuses the data loading, DST table, flatline rule and run_rule() of prereg_2016.py (executed up to the main loop).
Scenario: per site, dispatch on the K hottest season weekdays (K in 10, 20, 30, 40) with a 10 % window curtailment on
every dispatched day; the lookbacks see the curtailed load; rule fallbacks apply. Scored days are always the 10
hottest days, so K changes only the contamination and displacement of the lookbacks.
Usage: python -I prereg_2016_erosion.py <W> <lam>   (SCM config chosen by prereg_2016_analyse.py)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "prereg_2016.py"), encoding="utf-8").read()
src = src.split("all_rows = {")[0]
W_SCM, LAM_SCM = int(sys.argv[1]), float(sys.argv[2])
exec(compile(src, "prereg_2016.py", "exec"))
C = 0.10
rows = []
EVF = pd.read_csv(os.path.join(ROOT, "results", "frozen", "event_dates.csv"), parse_dates=["date"])
EVF = EVF[(EVF.year == 2016) & (EVF.rule == "R1")]
FOLD = pd.read_csv(os.path.join(ROOT, "results", "frozen", "folds.csv")).set_index("meter_id").fold
didx = {d: i for i, d in enumerate(days)}
for s in SITES:
    bi_all = [cols.index(b) for b in aud.index[aud.site_id == s] if b in keepb]
    if len(bi_all) < 12 or s not in tmax.columns:
        continue
    c = ctry(aud.timezone[aud.site_id == s].iloc[0]); hol = set(pd.to_datetime(HOL[c]))
    wk = np.array([(d.dayofweek < 5) and (d not in hol) for d in days])
    Ytrue = X[:, :, bi_all]
    complete = ~np.isnan(Ytrue).any(1) & ~flat_mask(Ytrue, FH, 4)
    tm = tmax[s].values
    e_s = EVF[EVF.site_id == s].sort_values("rank")
    order = np.array([didx[d] for d in e_s.date])          # frozen R1 ranks 1..40
    assert len(order) == 40
    fl = np.array([FOLD[cols[b]] for b in bi_all])
    A_, B_ = np.where(fl == "A")[0], np.where(fl == "B")[0]
    score = order[:10]
    for K in [10, 20, 30, 40]:
        disp = order[:K]
        evset = set(disp.tolist())
        for part, dpool in [(A_, B_), (B_, A_)]:
            # only participants (this fold's targets) curtail; donors are non-participants and stay uncurtailed
            Ys = Ytrue.copy()
            for d in disp:
                Ys[np.ix_([d], WIN, part)] *= (1 - C)
            Lc = np.where(complete, Ys[:, WIN, :].sum(1), np.nan)
            rr = run_rule(evset, score, s, bi_all, wk, complete, Ys, None, part, dpool, tm, do_scm=True,
                          scm_cfg={"W": W_SCM, "lam": LAM_SCM})
            for r in rr:
                r["K"] = K
            rows += rr
    print(s, "done", round(time.time() - T0), "s"); sys.stdout.flush()
df = pd.DataFrame(rows)
df.to_pickle(os.path.join(OUT, "events_erosion.pkl"))  # self-written intermediate (trusted)
print("saved", len(df))
