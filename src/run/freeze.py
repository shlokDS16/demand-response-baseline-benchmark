"""Freeze lock (T3): in --year 2017 the code refuses to run unless research/FREEZE_MANIFEST.md5 exists and every entry
matches. The manifest must list PREREG.md, every results/frozen/*.csv and every src/run/*.py (md5 over raw bytes)."""
import hashlib
from pathlib import Path

from . import config as C


def md5_file(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def parse_manifest(text):
    ent = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split(None, 1)
        assert len(parts) == 2 and len(parts[0]) == 32, "bad manifest line: " + ln
        ent[parts[1].strip().lstrip("*").replace("\\", "/")] = parts[0].lower()
    return ent


def required_paths():
    req = ["research/PREREG.md"]
    req += sorted("results/frozen/" + p.name for p in C.FROZEN.glob("*.csv"))
    req += sorted("src/run/" + p.name for p in (C.ROOT / "src" / "run").glob("*.py"))
    return req


def check_manifest(manifest=None, root=None):
    """Return the md5 of the manifest file on success; raise SystemExit otherwise."""
    manifest = Path(manifest or C.MANIFEST)
    root = Path(root or C.ROOT)
    if not manifest.exists():
        raise SystemExit("FREEZE LOCK: %s does not exist; refusing to run on 2017." % manifest)
    ent = parse_manifest(manifest.read_text(encoding="utf-8"))
    missing = [p for p in required_paths() if p not in ent]
    if missing:
        raise SystemExit("FREEZE LOCK: manifest does not list %s" % missing)
    for rel, h in ent.items():
        f = root / rel
        if not f.exists() or md5_file(f) != h:
            raise SystemExit("FREEZE LOCK: %s changed or missing (manifest %s)" % (rel, h))
    return md5_file(manifest)
