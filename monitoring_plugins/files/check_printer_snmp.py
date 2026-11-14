#!/usr/bin/env python3
"""check_printer_snmp - toner levels and printer status via SNMP
(Printer-MIB RFC 3805, Host-Resources-MIB RFC 2790)"""
import argparse
import subprocess
import sys

OK, WARNING, CRITICAL, UNKNOWN = 0, 1, 2, 3
STATE_TEXT = {OK: "OK", WARNING: "WARNING", CRITICAL: "CRITICAL", UNKNOWN: "UNKNOWN"}
# Severity for the summary: CRITICAL > WARNING > UNKNOWN > OK
RANK = {OK: 0, UNKNOWN: 1, WARNING: 2, CRITICAL: 3}

PRINTER_STATUS = {1: "other", 2: "unknown", 3: "idle", 4: "printing", 5: "warmup"}

# hrPrinterDetectedErrorState (RFC 2790): bit 0 is the most significant bit of the first byte
ERROR_FLAGS = [
    (0, "lowPaper"), (1, "noPaper"), (2, "lowToner"), (3, "noToner"),
    (4, "doorOpen"), (5, "jammed"), (6, "offline"), (7, "serviceRequested"),
    (8, "inputTrayMissing"), (9, "outputTrayMissing"), (10, "markerSupplyMissing"),
    (11, "outputNearFull"), (12, "outputFull"), (13, "inputTrayEmpty"),
    (14, "overduePreventMaintenance"),
]
FLAG_NAMES = [name for _, name in ERROR_FLAGS]


def die(msg):
    print(f"UNKNOWN - {msg}")
    sys.exit(UNKNOWN)


def walk(args, oid, hex_strings=False):
    """Run snmpwalk, the result is {index suffix: value}."""
    opts = "-Oqnx" if hex_strings else "-Oqn"
    cmd = ["snmpwalk", "-v", args.version, "-c", args.community,
           "-t", str(args.timeout), "-r", "1", opts, args.host, oid]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=args.timeout * 4)
    except FileNotFoundError:
        die("snmpwalk not found (install snmp or net-snmp-utils)")
    except subprocess.TimeoutExpired:
        die("SNMP timeout")
    if res.returncode != 0:
        die("SNMP error: " + (res.stderr.strip() or res.stdout.strip()))
    prefix = "." + oid + "."
    result = {}
    for line in res.stdout.splitlines():
        parts = line.split(None, 1)
        if not parts or not parts[0].startswith(prefix):
            continue
        value = parts[1].strip().strip('"') if len(parts) > 1 else ""
        result[parts[0][len(prefix):]] = value
    return result


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rate_toner(args, level, maxcap):
    """Returns (state, percent or None)."""
    if level is None or maxcap is None:
        return UNKNOWN, None
    if level == -3:          # "at least some remaining", no number
        return OK, None
    if level < 0 or maxcap <= 0:   # -1 other, -2 unknown
        return UNKNOWN, None
    pct = level * 100.0 / maxcap
    if pct < args.critical:
        return CRITICAL, pct
    if pct < args.warning:
        return WARNING, pct
    return OK, pct


def check_toner(args):
    base = "1.3.6.1.2.1.43.11.1.1."
    cls = walk(args, base + "4")    # prtMarkerSuppliesClass (3 = consumed)
    typ = walk(args, base + "5")    # prtMarkerSuppliesType (3 = toner)
    desc = walk(args, base + "6")
    cap = walk(args, base + "8")
    lvl = walk(args, base + "9")

    supplies = [(idx, name) for idx, name in desc.items()
                if cls.get(idx) == "3" and typ.get(idx) == "3"]
    if not supplies:
        die("no toner cartridges found")

    if args.toner.lower() != "all":
        selected = [s for s in supplies if args.toner.lower() in s[1].lower()]
        if not selected:
            die("no toner matches '%s', available: %s"
                % (args.toner, ", ".join(n for _, n in supplies)))
        supplies = selected

    labels = [n.split()[0] for _, n in supplies]
    if len(set(labels)) != len(labels):      # not unique, use the full description
        labels = [n for _, n in supplies]

    states, texts, perf = [], [], []
    for (idx, _), label in zip(supplies, labels):
        state, pct = rate_toner(args, to_int(lvl.get(idx)), to_int(cap.get(idx)))
        states.append(state)
        if pct is None:
            shown = "unknown" if state == UNKNOWN else "some remaining"
        else:
            shown = "%.0f%%" % pct
            perf.append("'%s'=%.0f%%;%s:;%s:;0;100"
                        % (label, pct, args.warning, args.critical))
        suffix = "" if state == OK else " (%s)" % STATE_TEXT[state]
        texts.append("%s %s%s" % (label, shown, suffix))

    worst = max(states, key=lambda s: RANK[s])
    return worst, "TONER %s - %s" % (STATE_TEXT[worst], ", ".join(texts)), perf


def parse_flags(text, option):
    names = [t.strip() for t in text.split(",") if t.strip()]
    for n in names:
        if n not in FLAG_NAMES:
            die("%s: unknown flag '%s', valid: %s"
                % (option, n, ", ".join(FLAG_NAMES)))
    return set(names)


def check_status(args):
    crit_flags = parse_flags(args.status_critical, "--status-critical")
    ignore_flags = parse_flags(args.status_ignore, "--status-ignore")

    status = walk(args, "1.3.6.1.2.1.25.3.5.1.1")
    errors = walk(args, "1.3.6.1.2.1.25.3.5.1.2", hex_strings=True)
    if not errors:
        die("hrPrinterDetectedErrorState not available")

    flags = set()
    for value in errors.values():
        try:
            data = [int(t, 16) for t in value.replace(":", " ").split()]
        except ValueError:
            die("hrPrinterDetectedErrorState not readable: %r" % value)
        for bit, name in ERROR_FLAGS:
            byte, mask = bit // 8, 0x80 >> (bit % 8)
            if byte < len(data) and data[byte] & mask:
                flags.add(name)
    flags -= ignore_flags

    state = OK
    for f in flags:
        state = max(state, CRITICAL if f in crit_flags else WARNING)

    st = to_int(next(iter(status.values()), None))
    st_text = PRINTER_STATUS.get(st, "unknown")
    active = [n for n in FLAG_NAMES if n in flags]
    detail = "errors: " + ", ".join(active) if active else "no errors"
    return state, "STATUS %s - printer %s, %s" % (STATE_TEXT[state], st_text, detail), []


def main():
    p = argparse.ArgumentParser(description="Check the toner and the status of a printer via SNMP")
    p.add_argument("-H", "--host", required=True)
    p.add_argument("-C", "--community", default="public")
    p.add_argument("-v", "--version", default="2c", choices=["1", "2c"])
    p.add_argument("-t", "--timeout", type=int, default=5)
    p.add_argument("--check", required=True, choices=["toner", "status"])
    p.add_argument("--toner", default="all",
                   help="'all' (the worst level wins) or a part of the name, e.g. black")
    p.add_argument("-w", "--warning", type=float, default=10.0,
                   help="toner WARNING below x percent")
    p.add_argument("-c", "--critical", type=float, default=5.0,
                   help="toner CRITICAL below x percent")
    p.add_argument("--status-critical", default="",
                   help="comma separated error flags causing CRITICAL (default: none)")
    p.add_argument("--status-ignore", default="",
                   help="comma separated error flags to ignore")
    args = p.parse_args()

    if args.critical > args.warning:
        die("--critical must not be greater than --warning")

    if args.check == "toner":
        state, text, perf = check_toner(args)
    else:
        state, text, perf = check_status(args)

    print(text + (" | " + " ".join(perf) if perf else ""))
    sys.exit(state)


if __name__ == "__main__":
    main()
