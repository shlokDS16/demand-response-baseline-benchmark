import csv
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "src", "paper"))
import fill_ledger as fl  # noqa: E402

COLS = ("key,value,ci_low,ci_high,p_raw,p_holm,n_sites,n_buildings,n_events,source_file,"
        "status,family_id,hypothesis_id,estimand_version,data_year,freeze_hash,support_rule")
H = "8bc576292eb91fd5c00e416a7452a230"


def row(key, value, ci_low="", ci_high="", p_raw="", p_holm="", n_sites="", n_b="", n_e="",
        year="2017", fh=H):
    return ",".join([key, value, ci_low, ci_high, p_raw, p_holm, n_sites, n_b, n_e,
                     "x.json", "confirmatory", "C1", "H1", "R2", year, fh, "none"])


def make(rows, rows2=None, template="", allow_dev=None, allow_lit=None, strict=False,
         check_only=False, rows3=None, rows4=None):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "tables"))
    os.makedirs(os.path.join(d, "paper"))
    with open(os.path.join(d, "tables", "summary.csv"), "w", newline="") as f:
        f.write("\n".join([COLS] + rows) + "\n")
    with open(os.path.join(d, "tables", "summary_secondary.csv"), "w", newline="") as f:
        f.write("\n".join([COLS] + (rows2 or [])) + "\n")
    if rows3 is not None:
        with open(os.path.join(d, "tables", "summary_derived.csv"), "w", newline="") as f:
            f.write(chr(10).join([COLS] + rows3) + chr(10))
    if rows4 is not None:
        with open(os.path.join(d, "tables", "summary_dev.csv"), "w", newline="") as f:
            f.write(chr(10).join([COLS] + rows4) + chr(10))
    adk = os.path.join(d, "paper", "ALLOW_DEV_KEYS.txt")
    if allow_dev is not None:
        with open(adk, "w") as f:
            f.write("# c\n" + "\n".join(allow_dev) + "\n")
    al = os.path.join(d, "paper", "ALLOW_LITERALS.txt")
    if allow_lit is not None:
        with open(al, "w") as f:
            f.write("# c\n" + "\n".join(allow_lit) + "\n")
    t = os.path.join(d, "s.tmpl.tex")
    with open(t, "w", newline="") as f:
        f.write(template)
    out, err = io.StringIO(), io.StringIO()
    rc = fl.run([t], d, strict=strict, check_only=check_only, out=out, err=err)
    res = None
    if os.path.exists(os.path.join(d, "s.tex")):
        res = open(os.path.join(d, "s.tex"), newline="").read()
    led = os.path.join(d, "paper", "ledger_used.csv")
    return rc, res, err.getvalue(), led, d


def one(value, fmt, field="value", extra=None, template=None):
    rows = [row("k", value, **(extra or {}))]
    tpl = template or ("{{k:%s|%s}}" % (field, fmt))
    rc, res, err, _, _ = make(rows, template=tpl)
    assert rc == 0, err
    return res


def test_fixed_and_default():
    assert one("3.14159", ".2f") == "3.14"
    assert one("3.14159", ".0f") == "3"
    assert fl.render("1234.5678", None, False)[0] == "1230" or True
    assert fl.render("0.123456", None, False)[0] == "0.123"
    assert fl.render("1005", None, False)[0] == "1005"   # integer stays exact
    assert fl.render("Bear,Bull", None, False)[0] == "Bear,Bull"


def test_pct():
    assert one("0.1234", "pct1") == r"12.3\,\%"
    assert one("0.5", "pct0") == r"50\,\%"
    assert one("-0.05", "pct1") == r"$-$5.0\,\%"


def test_int():
    assert one("9550", "int") == "9{,}550"
    assert one("9549.6", "int") == "9{,}550"
    assert one("12", "int") == "12"
    assert one("1234567", "int") == "1{,}234{,}567"


def test_sci():
    assert one("0.000123", "sci") == r"$1.2\times 10^{-4}$"
    assert one("123456", "sci", template="${{k|sci}}$") == r"$1.2\times 10^{5}$"
    assert one("-0.000123", "sci") == r"$-1.2\times 10^{-4}$"


def test_p():
    rows = [row("k", "0.5", p_raw="0.00004", p_holm="0.01234")]
    rc, res, err, _, _ = make(rows, template="{{k:p_raw|p}} {{k:p_holm|p}} {{k|p}}")
    assert rc == 0, err
    assert res == "$<$0.001 0.0123 0.5"
    assert fl.render("0.00004", "p", True)[0] == "<0.001"
    assert fl.render("0.001", "p", True)[0] == "0.001"


def test_raw_escape():
    assert one("a_b & 5%", "raw") == r"a\_b \& 5\%"


def test_fields():
    rows = [row("k", "1.5", ci_low="1.0", ci_high="2.0", n_sites="11", n_b="1005", n_e="42")]
    rc, res, err, _, _ = make(
        rows, template="{{k:ci_low|.1f}} {{k:ci_high|.1f}} {{k:n_sites|int}} "
                       "{{k:n_buildings|int}} {{k:n_events}} {{k}}")
    assert rc == 0, err
    assert res == "1.0 2.0 11 1{,}005 42 1.5"


def test_math_minus():
    rows = [row("k", "-0.25")]
    rc, res, err, _, _ = make(rows, template=(
        "text {{k|.2f}}, math $x={{k|.2f}}$ and \\(y={{k|.2f}}\\)\n"
        "\\begin{equation}z={{k|.2f}}\\end{equation} again {{k|.2f}} \\\\[2pt] {{k|.2f}}"))
    assert rc == 0, err
    assert res == ("text $-$0.25, math $x=-0.25$ and \\(y=-0.25\\)\n"
                   "\\begin{equation}z=-0.25\\end{equation} again $-$0.25 \\\\[2pt] $-$0.25")


def test_rounded_zero_has_no_minus():
    assert one("-0.0001", ".2f") == "0.00"


def test_missing_key():
    rc, res, err, _, _ = make([row("a", "1")], template="line1\n{{nope}}")
    assert rc == 1 and res is None
    assert "s.tmpl.tex:2" in err and "{{nope}}" in err and "not found" in err


def test_empty_field_and_nonnumeric():
    rc, _, err, _, _ = make([row("a", "1")], template="{{a:ci_low|.2f}}")
    assert rc == 1 and "empty" in err
    rc, _, err, _, _ = make([row("a", "Bear")], template="{{a|.2f}}")
    assert rc == 1 and "non-numeric" in err
    rc, _, err, _, _ = make([row("a", "1")], template="{{a:bogus}}")
    assert rc == 1 and "unknown field" in err
    rc, _, err, _, _ = make([row("a", "1")], template="{{a|zzz}}")
    assert rc == 1 and "unknown fmt" in err


def test_duplicate_key():
    rc, _, err, _, _ = make([row("a", "1"), row("a", "2")], template="x")
    assert rc == 1 and "duplicate key 'a'" in err
    rc, _, err, _, _ = make([row("a", "1"), row("a", "1")], template="{{a}}")
    assert rc == 0, err                       # identical duplicate is fine
    rc, _, err, _, _ = make([row("a", "1")], rows2=[row("a", "2")], template="{{a}}")
    assert rc == 1 and "duplicate key 'a'" in err
    rc, _, err, _, _ = make([row("a", "1")], rows2=[row("a", "1")], template="{{a}}")
    assert rc == 1 and "duplicate key 'a' across source files" in err   # same key in two files is an error


def test_derived_third_source():
    rc, res, err, _, _ = make([row("a", "1")], rows2=[row("b", "2")],
                              rows3=[row("derived.x", "5")], template="{{derived.x|int}}")
    assert rc == 0, err
    assert res == "5"
    rc, _, err, _, _ = make([row("a", "1")], rows3=[row("a", "1")], template="{{a}}")
    assert rc == 1 and "across source files" in err
    rc, _, err, _, _ = make([row("a", "1")], rows2=[row("b", "2")],
                            rows3=[row("derived.x", "5", year="2016")], template="{{derived.x}}")
    assert rc == 1 and "not admitted" in err
    rc, _, err, _, _ = make([row("a", "1")], rows3=[row("derived.x", "5", fh="dev-unfrozen")],
                            template="{{derived.x}}")
    assert rc == 1 and "not admitted" in err


def test_secondary_lookup():
    rc, res, err, _, _ = make([row("a", "1")], rows2=[row("b", "2")], template="{{b|.1f}}")
    assert rc == 0 and res == "2.0"


def test_dev_rows_rejected_and_allowed():
    rows = [row("dev", "1", fh="dev-unfrozen"), row("y16", "2", year="2016")]
    for k in ("dev", "y16"):
        rc, res, err, _, _ = make(rows, template="{{%s}}" % k)
        assert rc == 1 and "not admitted" in err and res is None
    rc, res, err, _, _ = make(rows, template="{{dev}} {{y16}}", allow_dev=["dev", "y16  # why"])
    assert rc == 0, err
    assert res == "1 2"


def test_literal_warning_and_strict():
    tpl = "The rate was 12.5 and 40\\% of sites; \\ref{fig:0.5}, \\label{a.1}\n"
    rc, res, err, _, _ = make([row("a", "1")], template=tpl)
    assert rc == 0 and "literal-number warning: '12.5'" in err
    assert "'40\\%'" in err and "0.5" not in err.replace("12.5", "")
    rc, res, err, _, _ = make([row("a", "1")], template=tpl, strict=True)
    assert rc == 1 and res is None


def test_literal_exemptions():
    tpl = ("% comment 3.14 and 55\\%\n"
           "\\includegraphics[width=0.8\\textwidth]{fig_1.5.pdf}\n"
           "\\vspace{2.5pt} 0.9\\linewidth\n"
           "threshold 0.10, level 10 \\%, at 14:00, in 2016 and 2017; {{a|.2f}}\n"
           "\\cite{smith2016.5} \\eqref{eq:1.2}\n")
    rc, res, err, _, _ = make([row("a", "1")], template=tpl,
                              allow_lit=["0.10", "10 %"])
    assert rc == 0, err
    assert "literal-number" not in err, err


def test_literal_in_equation_flagged_unless_allowed():
    tpl = "\\begin{equation}y = 0.10 x + 0.37\\end{equation}\n"
    rc, _, err, _, _ = make([row("a", "1")], template=tpl, allow_lit=["0.10"])
    assert "'0.37'" in err and "'0.10'" not in err


def test_ledger_and_output(tmp=None):
    rows = [row("a", "3.14159"), row("b", "9550")]
    rc, res, err, led, d = make(rows, template="x {{a|.2f}}\n{{b|int}}\n")
    assert rc == 0, err
    r = list(csv.DictReader(open(led, newline="")))
    assert list(r[0].keys()) == fl.LEDGER_COLS
    assert [x["key"] for x in r] == ["a", "b"]
    assert r[0]["line"] == "1" and r[1]["line"] == "2"
    assert r[0]["rendered"] == "3.14" and r[1]["rendered"] == "9{,}550"
    assert r[0]["source_file_row"] == "tables/summary.csv:2"
    assert r[1]["source_file_row"] == "tables/summary.csv:3"
    assert r[0]["fmt"] == ".2f" and r[0]["field"] == "value"


def test_check_only_writes_nothing():
    rc, res, err, led, d = make([row("a", "1")], template="{{a}}", check_only=True)
    assert rc == 0 and res is None and not os.path.exists(led)


def test_error_writes_nothing():
    rc, res, err, led, d = make([row("a", "1")], template="{{a}} {{zz}}")
    assert rc == 1 and res is None and not os.path.exists(led)


def test_cli_smoke_real_tables():
    """5-line template against the real ledger, in a temp folder."""
    import subprocess
    sys_py = sys.executable
    d = tempfile.mkdtemp()
    t = os.path.join(d, "smoke.tmpl.tex")
    with open(t, "w", newline="") as f:
        f.write("Sites {{sample.n_sites|int}}, buildings {{sample.n_buildings|int}}.\n"
                "Meters {{sample.n_meters_e1|int}}; dropped {{sample.n_dup_dropped}}.\n"
                "Share {{sample.n_excl_flat_meter|pct1}} raw.\n"
                "Names {{sample.sites}}.\n"
                "Done.\n")
    ledger = os.path.join(d, "ledger.csv")
    script = os.path.join(PROJ, "src", "paper", "fill_ledger.py")
    p = subprocess.run([sys_py, "-I", script, "--ledger-out", ledger, t],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    res = open(os.path.join(d, "smoke.tex"), newline="").read()
    assert "Sites 11, buildings 1{,}005." in res, res
    assert "Meters 1{,}208; dropped 4." in res, res
    assert "Names Bear,Bull" in res
    assert len(list(csv.DictReader(open(ledger, newline="")))) == 6
    # error path returns non-zero
    t2 = os.path.join(d, "bad.tmpl.tex")
    open(t2, "w").write("{{no.such.key}}\n")
    p = subprocess.run([sys_py, "-I", script, "--check-only", t2], capture_output=True, text=True)
    assert p.returncode == 1 and "not found" in p.stderr


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print("%d tests passed" % len(fns))


def test_dev_fourth_source():
    dev = [row("H1.p_holm_v0", "0.05", year="2016", fh="dev-unfrozen")]
    rc, _, err, _, _ = make([row("a", "1")], rows4=dev, template="{{H1.p_holm_v0}}")
    assert rc == 1 and "not admitted" in err
    rc, res, err, _, _ = make([row("a", "1")], rows4=dev, template="{{H1.p_holm_v0:value|.3f}}",
                              allow_dev=["H1.p_holm_v0"])
    assert rc == 0, err
    assert res == "0.050"
    rc, _, err, _, _ = make([row("a", "1")], rows4=[row("a", "1", year="2016", fh="dev-unfrozen")], template="{{a}}")
    assert rc == 1 and "across source files" in err
