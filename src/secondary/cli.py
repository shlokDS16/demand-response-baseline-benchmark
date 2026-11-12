"""CLI: python -I src/secondary/cli.py --year {2016,2017} --part h6,tree,abl,nonevent,flat,hpo,gscm,mlp [--collect]
2016 (dev) runs first, keys carry _v0. 2017 aborts unless run.freeze.check_manifest() passes (called first)."""
import argparse
import os
import site
import sys

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../src, needed under python -I

from run import config as C   # noqa: E402
from secondary import common as CM   # noqa: E402

PARTS = ("h6", "tree", "abl", "donor", "nonevent", "flat", "hpo", "gscm", "mlp")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, choices=(2016, 2017), required=True)
    ap.add_argument("--part", default="")
    ap.add_argument("--boot-b", type=int, default=None)
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args(argv)
    fh = CM.freeze_hash(a.year)          # 2017: SystemExit if the manifest does not match
    parts = [p for p in a.part.split(",") if p]
    assert all(p in PARTS for p in parts), parts
    s, e = C.WINDOWS["primary"]
    for part in parts:
        tm = CM.Timer()
        led = CM.SecLedger(a.year, fh)
        if part == "h6":
            from secondary import h6
            R1 = CM.load_R1(a.year)
            res = h6.run_h6(R1, s, e)
            h6.emit(led, res)
        elif part == "tree":
            from secondary import tree
            res = tree.run_tree(a.year, led)
        elif part in ("abl", "donor"):
            from secondary import ablations
            res = ablations.run(a.year, led, part)
        elif part in ("nonevent", "flat"):
            from secondary import variants
            res = variants.run(a.year, led, part, boot_b=a.boot_b)
        elif part == "hpo":
            from secondary import hpo
            res = hpo.run(a.year, led)
        elif part == "gscm":
            from secondary import gscm
            res = gscm.run(a.year, led)
        elif part == "mlp":
            from secondary import mlp
            res = mlp.run(a.year, led)
        t = tm.stop()
        led.add("compute.%s.time_s" % part, t["time_s"])
        led.add("compute.%s.peak_mem_gb" % part, t["peak_gb"])
        p = led.save(a.year, part)
        CM.log_timing(a.year, part, t)
        print(part, "done", t, "->", p, flush=True)
    if a.collect or parts:
        df = CM.collect()
        print("summary_secondary rows:", None if df is None else len(df))


if __name__ == "__main__":
    main()
