"""CLI: python -I src/run/main.py --year {2016,2017} --mode {dev,final} --part {core,precool,erosion,secondary,all}
(--part accepts a comma list). Final is the default mode (rule 2.4). --year 2017 refuses to run unless
research/FREEZE_MANIFEST.md5 matches (freeze.py). 2016 is the development year: it only runs in --mode dev.
Never run with --year 2017 before the controller creates the manifest."""
import argparse
import json
import os
import pickle
import site
import sys
import time

up = site.getusersitepackages()
if os.path.isdir(up) and up not in sys.path:
    sys.path.append(up)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../src, needed under python -I

from run import config as C   # noqa: E402
from run import freeze        # noqa: E402

PARTS = ("core", "precool", "erosion", "secondary")


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, choices=(2016, 2017), required=True)
    ap.add_argument("--mode", choices=("dev", "final"), default="final")
    ap.add_argument("--part", default="all")
    ap.add_argument("--boot-b", type=int, default=None, help="bootstrap replicates (default PREREG 10000)")
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true", help="dev only: keep duplicate meters (equality check with the development tables)")
    ap.add_argument("--scm-final", action="store_true", help="dev only (DEV-1): run 2016 through the final-mode SCM path, output to run_v0/finalpath")
    return ap.parse_args(argv)


def main(argv=None):
    a = parse(argv)
    parts = list(PARTS) if a.part == "all" else a.part.split(",")
    assert all(p in PARTS for p in parts), parts
    if a.year == 2017:
        fh = freeze.check_manifest()      # raises SystemExit if the manifest is missing or any entry differs
        assert a.mode == "final", "2017 runs only in final mode"
    else:
        if a.mode == "final":
            raise SystemExit("2016 is the development year: use --mode dev (final results exist for 2017 only).")
        fh = "dev-unfrozen"
    from run import analysis as AN, data as D, ledger as LD, pipeline as PL, secondary as SE
    out = C.ROOT / "results" / ("run_v0" if a.mode == "dev" else "run")
    if a.no_dedupe:
        assert a.mode == "dev", "--no-dedupe is a dev-mode check only"
        D.DEDUPE = False
        out = out / "nodedupe"
    if a.scm_final:
        assert a.mode == "dev", "--scm-final is a dev-mode check only"
        out = out / "finalpath"
    out.mkdir(parents=True, exist_ok=True)
    win = C.WINDOWS["primary"]
    timing = {}
    state_path = out / "results_state.pkl"
    state = pickle.load(open(state_path, "rb")) if state_path.exists() else {}   # self-written by this program
    scm = "grid" if (a.mode == "dev" and not a.scm_final) else (C.SCM_W, C.SCM_LAM)
    Y = None
    t0 = time.time()
    need_year = any(p in parts for p in ("core", "erosion", "secondary"))
    if need_year:
        Y = D.build_year(a.year, win)
        timing["load"] = {"time_s": time.time() - t0, "peak_gb": PL.peak_mem_gb()}
        print("loaded", a.year, "meters", Y.n_e1, round(time.time() - t0), "s", flush=True)
    frames = None
    if "core" in parts:
        t1 = time.time()
        frames, sample, tm = PL.run_core(Y, out, scm=scm)
        state["sample"] = sample
        timing["core_run"] = tm
        t1 = time.time()
        state["core"] = PL.analyse_core(frames, win, B=a.boot_b)
        timing["core_analysis"] = {"time_s": time.time() - t1, "peak_gb": PL.peak_mem_gb()}
        state["dst"] = Y.dst.to_dict("list")
        if a.year == 2016:
            Y.dst.to_csv(out / "dst_table_recomputed.csv", index=False)
    if "precool" in parts:
        t1 = time.time()
        frames = frames or PL.load_frames(out)
        state["precool"] = PL.run_precool(frames, win, B=a.boot_b, do_boot=not a.no_boot)
        timing["precool"] = {"time_s": time.time() - t1, "peak_gb": PL.peak_mem_gb()}
    if "erosion" in parts:
        t1 = time.time()
        df, tm = PL.run_erosion(Y, out)
        state["erosion"] = PL.analyse_erosion(df, win)
        timing["erosion"] = {"time_s": time.time() - t1, "peak_gb": PL.peak_mem_gb()}
    if "secondary" in parts:
        t1 = time.time()
        state["secondary"] = SE.run_secondary(Y, out, boot_b=a.boot_b)
        timing["secondary"] = {"time_s": time.time() - t1, "peak_gb": PL.peak_mem_gb()}
    state.setdefault("timing", {}).update(timing)
    with open(state_path, "wb") as fh_:
        pickle.dump(state, fh_)
    led = LD.Ledger(a.mode, a.year, freeze_hash=fh, source_default=str(out))
    holm = PL.emit_all(led, state, out)
    SE.emit_secondary(led, state.get("secondary"))
    led.add("compute.peak_mem_gb", max(v.get("peak_gb", 0) for v in state["timing"].values()), status="secondary")
    led.add("compute.gpu_hours", 0.0, status="secondary")
    path = (C.ROOT / "tables" / "summary.csv") if a.mode == "final" else (out / "summary_v0.csv")
    df = led.write(path)
    json.dump(state["timing"], open(out / "timing.json", "w"), indent=1)
    print("ledger rows", len(df), "->", path)
    print("Holm:", holm)
    print("timing:", json.dumps(state["timing"], default=str))


if __name__ == "__main__":
    main()
