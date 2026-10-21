"""System DNS server discovery and health checks (stdlib only)."""
import ipaddress
import os
import re
import socket
import subprocess
import sys
import time

DEFAULT_TRACKERS = [
    "tracker.opentrackr.org",
    "open.stealth.si",
    "tracker.torrent.eu.org",
    "exodus.desync.com",
]

_IP_RE = re.compile(r"([0-9a-fA-F:.%]+)")


def _clean(addr):
    addr = addr.strip().strip("[]")
    return addr.split("%", 1)[0]


def _valid_ip(addr):
    try:
        ipaddress.ip_address(_clean(addr))
        return True
    except ValueError:
        return False


def parse_resolv_conf(text):
    servers = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver" and _valid_ip(parts[1]):
            servers.append(_clean(parts[1]))
    return _dedupe(servers)


def parse_ipconfig(text):
    """Parse `ipconfig /all` output (English locale best-effort, any locale for continuation lines)."""
    servers = []
    in_dns = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            in_dns = False
            continue
        if ":" in line and ". ." in line:
            label, _, value = line.partition(" : ")
            in_dns = "DNS Servers" in label or "DNS 服务器" in label
            if in_dns and _valid_ip(value.strip()):
                servers.append(_clean(value))
        elif in_dns and raw.startswith(" ") and _valid_ip(line.strip()):
            servers.append(_clean(line))
        else:
            in_dns = False
    return _dedupe(servers)


def parse_scutil(text):
    servers = []
    for line in text.splitlines():
        m = re.match(r"\s*nameserver\[\d+\]\s*:\s*(\S+)", line)
        if m and _valid_ip(m.group(1)):
            servers.append(_clean(m.group(1)))
    return _dedupe(servers)


def _dedupe(items):
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                              errors="replace").stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def system_dns_servers(platform=None):
    platform = platform or sys.platform
    if platform.startswith("win"):
        return parse_ipconfig(_run(["ipconfig", "/all"]))
    if platform == "darwin":
        s = parse_scutil(_run(["scutil", "--dns"]))
        if s:
            return s
    try:
        with open("/etc/resolv.conf", encoding="utf-8", errors="replace") as f:
            return parse_resolv_conf(f.read())
    except OSError:
        return []


def classify(addr):
    """Return a list of warning strings for a DNS server address (empty = looks fine)."""
    warnings = []
    ip = ipaddress.ip_address(_clean(addr))
    if ip.version == 6:
        if ip in ipaddress.ip_network("fec0::/10"):
            warnings.append("deprecated IPv6 site-local (fec0::/10) - usually a stale default from a "
                            "disconnected adapter; c-ares may hang on it")
        elif ip.is_link_local:
            warnings.append("IPv6 link-local address; often unusable by c-ares")
    if ip.is_unspecified:
        warnings.append("unspecified address")
    return warnings


def probe_udp53(addr, timeout=2.0):
    """Send a minimal DNS query for '.' NS to addr:53; return RTT seconds or None."""
    ip = ipaddress.ip_address(_clean(addr))
    fam = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
    query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x01"
    try:
        with socket.socket(fam, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            t0 = time.monotonic()
            s.sendto(query, (str(ip), 53))
            data, _ = s.recvfrom(512)
            if data[:2] == b"\x12\x34":
                return time.monotonic() - t0
    except OSError:
        pass
    return None


def resolve(host, timeout=5.0):
    """Resolve host with the system resolver; return (addresses, seconds) or (None, seconds)."""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    t0 = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, None)
        return sorted({i[4][0] for i in infos}), time.monotonic() - t0
    except OSError:
        return None, time.monotonic() - t0
    finally:
        socket.setdefaulttimeout(old)
