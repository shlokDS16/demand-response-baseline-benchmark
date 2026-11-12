import sys
sys.path.append("" + __import__("site").getusersitepackages() + "")
import numpy as np, pandas as pd
R1 = pd.read_pickle("results/run/events_R1.pkl")
for (site, d), t in R1.groupby(["site", "d"]):
    for f, o in (("A", "B"), ("B", "A")):
        tt = t[t.fold == f]; don = t[t.fold == o]
        if tt.empty: continue
        if not np.isclose(tt.don_L.values, don.L.sum(), rtol=1e-9).all():
            print(site, d, f, "frame", tt.don_L.iloc[0], "sum", don.L.sum(), "rel", (tt.don_L.iloc[0]-don.L.sum())/don.L.sum(), "ndon", tt.ndon.iloc[0], len(don), "Lobs-L max", float((don.Lobs-don.L).abs().max()))
