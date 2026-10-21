"""Locate and patch Motrix settings.json safely (backup + UTF-8 without BOM)."""
import json
import os
import shutil
import sys
import time

BOM = b"\xef\xbb\xbf"


def default_settings_path(platform=None, env=None):
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")
    if platform.startswith("win"):
        base = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "Motrix", "settings.json")


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    had_bom = raw.startswith(BOM)
    return json.loads(raw[len(BOM):] if had_bom else raw), had_bom


def write_no_bom(path, data):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(text.encode("utf-8"))  # never a BOM: Motrix resets settings if one is present
    os.replace(tmp, path)


def backup(path):
    dst = "%s.bak-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, dst)
    return dst


def list_backups(path):
    d, base = os.path.split(path)
    d = d or "."
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.startswith(base + ".bak-"))


def apply_fix(path, dry_run=False):
    """Set engine.dnsMode = 'system'. Returns dict describing what happened."""
    data, had_bom = load(path)
    engine = data.setdefault("engine", {}) if isinstance(data, dict) else None
    if engine is None or not isinstance(engine, dict):
        raise ValueError("unexpected settings.json structure (no 'engine' object)")
    before = engine.get("dnsMode")
    changed = before != "system" or had_bom
    result = {"path": path, "before": before, "had_bom": had_bom, "changed": changed, "backup": None}
    if changed and not dry_run:
        result["backup"] = backup(path)
        engine["dnsMode"] = "system"
        write_no_bom(path, data)
    return result


def restore(path, backup_path=None):
    if backup_path is None:
        backups = list_backups(path)
        if not backups:
            raise FileNotFoundError("no backups found next to %s" % path)
        backup_path = backups[-1]
    shutil.copy2(backup_path, path)
    return backup_path
