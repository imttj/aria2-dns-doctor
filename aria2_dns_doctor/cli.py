import argparse
import os
import sys

from . import __version__, dns, motrix, rpc

ARIA2_LINE = "async-dns=false"


def cmd_diagnose(a):
    problems = 0
    servers = dns.system_dns_servers()
    print("System DNS servers:")
    if not servers:
        print("  (none found)")
    for s in servers:
        warns = dns.classify(s)
        rtt = None if a.no_probe else dns.probe_udp53(s, a.timeout)
        status = "skipped" if a.no_probe else ("ok %.0f ms" % (rtt * 1000) if rtt is not None else "NO RESPONSE")
        flag = "!!" if warns or (rtt is None and not a.no_probe) else "  "
        print("  %s %-40s %s" % (flag, s, status))
        for w in warns:
            print("       - " + w)
        if flag == "!!":
            problems += 1
    print("\nResolving tracker hostnames (system resolver):")
    for h in a.host or dns.DEFAULT_TRACKERS:
        addrs, secs = dns.resolve(h, a.timeout)
        if addrs:
            print("  ok   %-32s %.0f ms  %s" % (h, secs * 1000, ", ".join(addrs[:3])))
        else:
            print("  FAIL %-32s %.0f ms" % (h, secs * 1000))
            problems += 1
    if a.rpc:
        print("\naria2 RPC %s:" % a.rpc)
        try:
            opt = rpc.global_option(a.rpc, a.secret)
            print("  async-dns = %s" % opt.get("async-dns", "?"))
            tasks = rpc.active_tasks(a.rpc, a.secret)
            if not tasks:
                print("  no active tasks")
            for t in tasks:
                print("  [%s] %s  conns=%d seeders=%d speed=%d B/s" % (
                    t["status"], t["name"], t["connections"], t["seeders"], t["speed"]))
            stuck = [t for t in tasks if t["bt"] and t["connections"] == 0]
            if stuck and opt.get("async-dns") == "true":
                print("  !! %d BitTorrent task(s) with 0 connections while async-dns=true" % len(stuck))
                problems += 1
        except Exception as e:  # noqa: BLE001
            print("  RPC error: %s" % e)
            problems += 1
    print()
    if problems:
        print("Found %d potential problem(s). Try: aria2-dns-doctor fix" % problems)
        return 1
    print("No obvious DNS problems found.")
    return 0


def cmd_fix(a):
    if a.aria2:
        print("Add this line to your aria2.conf (or pass --%s on the command line):" % ARIA2_LINE)
        print(ARIA2_LINE)
        return 0
    path = a.settings or motrix.default_settings_path()
    if not os.path.exists(path):
        print("Motrix settings not found at %s\nUse --settings PATH, or --aria2 for plain aria2." % path,
              file=sys.stderr)
        return 2
    print("Close Motrix completely before fixing, or it may overwrite the file on exit.")
    r = motrix.apply_fix(path, dry_run=a.dry_run)
    if not r["changed"]:
        print("Already fixed: engine.dnsMode is 'system' (%s)" % path)
        return 0
    print("engine.dnsMode: %r -> 'system'%s" % (r["before"], " (BOM will be removed)" if r["had_bom"] else ""))
    if a.dry_run:
        print("Dry run: nothing written.")
    else:
        print("Backup: %s\nWritten (UTF-8, no BOM): %s\nRestart Motrix." % (r["backup"], path))
    return 0


def cmd_restore(a):
    path = a.settings or motrix.default_settings_path()
    try:
        used = motrix.restore(path, a.backup)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    print("Restored %s from %s" % (path, used))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="aria2-dns-doctor",
                                description="Diagnose/fix aria2 & Motrix torrents stuck at 0 peers due to async DNS.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diagnose", help="check system DNS servers, tracker resolution, aria2 RPC")
    d.add_argument("--rpc", help="aria2 RPC URL, e.g. http://127.0.0.1:16800/jsonrpc (Motrix default)")
    d.add_argument("--secret", help="aria2 RPC secret")
    d.add_argument("--host", action="append", help="hostname to test (repeatable)")
    d.add_argument("--timeout", type=float, default=3.0)
    d.add_argument("--no-probe", action="store_true", help="don't send UDP probes to DNS servers")
    d.set_defaults(func=cmd_diagnose)
    f = sub.add_parser("fix", help="set Motrix dnsMode=system (with backup) or print aria2.conf line")
    f.add_argument("--settings", help="path to Motrix settings.json")
    f.add_argument("--aria2", action="store_true", help="plain aria2: print the aria2.conf line")
    f.add_argument("--dry-run", action="store_true")
    f.set_defaults(func=cmd_fix)
    r = sub.add_parser("restore", help="restore Motrix settings.json from latest (or given) backup")
    r.add_argument("--settings")
    r.add_argument("--backup", help="specific backup file")
    r.set_defaults(func=cmd_restore)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    return a.func(a)
