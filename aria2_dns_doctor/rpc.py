"""Minimal aria2 JSON-RPC client."""
import json
import urllib.request


def call(url, method, params=None, secret=None, timeout=5.0):
    params = list(params or [])
    if secret:
        params.insert(0, "token:" + secret)
    body = json.dumps({"jsonrpc": "2.0", "id": "dnsdoc", "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data["result"]


def summarize_tasks(tasks):
    out = []
    for t in tasks:
        bt = t.get("bittorrent") or {}
        name = (bt.get("info") or {}).get("name") or t.get("gid")
        out.append({
            "gid": t.get("gid"),
            "name": name,
            "status": t.get("status"),
            "connections": int(t.get("connections", 0) or 0),
            "seeders": int(t.get("numSeeders", 0) or 0),
            "speed": int(t.get("downloadSpeed", 0) or 0),
            "bt": bool(bt) or str(name).startswith("[METADATA]"),
        })
    return out


def active_tasks(url, secret=None):
    keys = ["gid", "status", "connections", "numSeeders", "downloadSpeed", "bittorrent"]
    return summarize_tasks(call(url, "aria2.tellActive", [keys], secret))


def global_option(url, secret=None):
    return call(url, "aria2.getGlobalOption", [], secret)
