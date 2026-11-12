"""P4 leakage spot-check, independent of src.run. Run: python -I audits/leakage_spot.py
(a) donors: for every R1 building-event, don_L / ndon must equal the sum / count of true window load of OPPOSITE-fold
    buildings with an event row on the same site-day (so no same-fold donor, no target in its own pool), and the fold in the
    frame must equal results/frozen/folds.csv.
(b) 20 random R1 building-events at CLOCK-mapped sites: pjm0 lookback re-derived from raw 2017 readings with our own code;
    reports the 4 lookback dates, checks all < event day, not an event day, weekday, not holiday; compares pjm0 and pjm0_m.
pickle note: results/run/*.pkl are produced by this project's own run (trusted)."""
import sys
sys.path.append("" + __import__("site").getusersitepackages() + "")
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R1 = pd.read_pickle(ROOT / "results" / "run" / "events_R1.pkl")
folds = pd.read_csv(ROOT / "results" / "frozen" / "folds.csv").set_index("meter_id").fold
S, E = 14, 18

# ---- (a) donors and folds ----
print("frame fold == folds.csv for all rows:", bool((R1.b.map(folds).values == R1.fold.values).all()))
g = R1.groupby(["site", "d"])
bad_n = bad_L = 0
chk = 0
for (site, d), t in g:
    for f, other in (("A", "B"), ("B", "A")):
        tt = t[t.fold == f]
        if tt.empty:
            continue
        don = t[t.fold == other]
        chk += len(tt)
        bad_n += int((tt.ndon.values != len(don)).sum())
        bad_L += int((~np.isclose(tt.don_L.values, don.L.sum(), rtol=1e-9)).sum())
print("events checked (donor identity):", chk, " ndon mismatches:", bad_n, " don_L mismatches:", bad_L)

# ---- (b) lookback re-derivation ----
CLOCK = ["Bear", "Bull", "Fox", "Hog", "Peacock"]
hol = pd.read_csv(ROOT / "results" / "frozen" / "holidays.csv", parse_dates=["date"])
ctry = {s: "US" for s in ["Bear", "Bull", "Cockatoo", "Eagle", "Fox", "Hog", "Peacock", "Rat"]}
ctry.update({"Lamb": "UK", "Robin": "UK", "Wolf": "IE"})
ev = pd.read_csv(ROOT / "results" / "frozen" / "event_dates.csv", parse_dates=["date"])
ev = ev[(ev.year == 2017) & (ev.rule == "R1") & (ev["primary"])]
cand = R1[R1.site.isin(CLOCK)].sample(20, random_state=20261111).reset_index(drop=True)
cols = sorted(cand.b.unique())
n16 = 8784
X = pd.read_csv(ROOT / "data" / "raw" / "bdg2" / "electricity_cleaned.csv", skiprows=range(1, n16 + 1), nrows=8760,
                index_col=0, parse_dates=True, usecols=lambda c: c == "timestamp" or c in set(cols))
assert X.index[0] == pd.Timestamp("2017-01-01") and len(X) == 8760
days = pd.date_range("2017-01-01", periods=365)
out = []
allok = True
for _, r in cand.iterrows():
    v = X[r.b].values.reshape(365, 24)
    d = int(r.d)
    evset = set((ev[ev.site_id == r.site].date - pd.Timestamp("2017-01-01")).dt.days.tolist())
    hs = set((hol[hol.country == ctry[r.site]].date - pd.Timestamp("2017-01-01")).dt.days.tolist())

    def flat(day):
        w = day[10:20]
        run = 1
        for i in range(1, len(w)):
            run = run + 1 if (w[i] == w[i - 1] and not np.isnan(w[i])) else 1
            if run >= 4:
                return True
        return False
    elig = []
    for k in range(d - 1, max(d - 46, -1), -1):
        if days[k].dayofweek >= 5 or k in hs or k in evset:
            continue
        if np.isnan(v[k]).any() or flat(v[k]):
            continue
        elig.append(k)
    p5 = elig[:5]
    wsum = {k: v[k, S:E].sum() for k in p5}
    m5 = np.mean(list(wsum.values()))
    keep = [k for k in p5 if wsum[k] >= 0.25 * m5]
    p4 = sorted(keep, key=lambda k: -wsum[k])[:4]
    pj = np.mean([wsum[k] for k in p4])
    prof = np.mean([v[k, S - 6:S] for k in p4], axis=0)
    prof_f = np.array(r.pjm0_m, float)
    before = all(k < d for k in p4)
    notev = all(k not in evset for k in p4)
    wkd = all(days[k].dayofweek < 5 and k not in hs for k in p4)
    match = np.isclose(pj, r.pjm0, rtol=1e-4) and np.allclose(prof, prof_f, rtol=1e-4, atol=1e-6) and len(p4) == 4
    okrow = before and notev and wkd and match
    allok &= okrow
    out.append("%-6s %-22s d=%3d (%s) lookback=%s max_age_gap_ok=%s notEvent=%s wkday_nonhol=%s pjm0 mine=%.4f frame=%.4f %s" % (
        r.site, r.b[:22], d, days[d].date(), [str(days[k].date()) for k in p4], before, notev, wkd, pj, r.pjm0, "MATCH" if match else "MISMATCH"))
print("\n".join(out))
print("ALL 20 PASS:", allok)
