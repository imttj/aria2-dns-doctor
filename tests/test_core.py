import json
import os

from aria2_dns_doctor import cli, dns, motrix, rpc

IPCONFIG = """
Ethernet adapter Ethernet 2:

   Media State . . . . . . . . . . . : Media disconnected
   DNS Servers . . . . . . . . . . . : fec0:0:0:ffff::1%1
                                       fec0:0:0:ffff::2%1
                                       192.168.1.1
   NetBIOS over Tcpip. . . . . . . . : Enabled
"""


def test_parse_ipconfig():
    assert dns.parse_ipconfig(IPCONFIG) == ["fec0:0:0:ffff::1", "fec0:0:0:ffff::2", "192.168.1.1"]


def test_parse_resolv_conf():
    assert dns.parse_resolv_conf("# c\nnameserver 1.1.1.1\nnameserver bogus\nnameserver ::1\n") == ["1.1.1.1", "::1"]


def test_parse_scutil():
    t = "resolver #1\n  nameserver[0] : 8.8.8.8\n  nameserver[1] : 8.8.8.8\n"
    assert dns.parse_scutil(t) == ["8.8.8.8"]


def test_classify():
    assert dns.classify("fec0:0:0:ffff::1")
    assert dns.classify("fe80::1")
    assert dns.classify("1.1.1.1") == []


def _write(p, data, bom=False):
    raw = json.dumps(data).encode()
    p.write_bytes((motrix.BOM if bom else b"") + raw)


def test_fix_removes_bom_and_backs_up(tmp_path):
    p = tmp_path / "settings.json"
    _write(p, {"engine": {"dnsMode": "async", "x": "中文"}, "user": {}}, bom=True)
    r = motrix.apply_fix(str(p))
    assert r["changed"] and r["had_bom"] and os.path.exists(r["backup"])
    raw = p.read_bytes()
    assert not raw.startswith(motrix.BOM)
    data = json.loads(raw)
    assert data["engine"]["dnsMode"] == "system" and data["engine"]["x"] == "中文"
    assert motrix.load(r["backup"])[1] is True


def test_fix_idempotent_and_dry_run(tmp_path):
    p = tmp_path / "settings.json"
    _write(p, {"engine": {}})
    assert motrix.apply_fix(str(p), dry_run=True)["changed"]
    assert "dnsMode" not in json.loads(p.read_bytes())["engine"]
    motrix.apply_fix(str(p))
    assert not motrix.apply_fix(str(p))["changed"]


def test_restore(tmp_path):
    p = tmp_path / "settings.json"
    _write(p, {"engine": {"dnsMode": "async"}})
    motrix.apply_fix(str(p))
    motrix.restore(str(p))
    assert json.loads(p.read_bytes())["engine"]["dnsMode"] == "async"


def test_default_paths():
    assert motrix.default_settings_path("win32", {"APPDATA": "C:\\A"}).endswith(os.path.join("Motrix", "settings.json"))
    assert "Application Support" in motrix.default_settings_path("darwin", {"HOME": "/h"})
    assert motrix.default_settings_path("linux", {"HOME": "/h"}) == os.path.join("/h", ".config", "Motrix", "settings.json")


def test_summarize_tasks():
    t = rpc.summarize_tasks([{"gid": "1", "status": "active", "connections": "0",
                              "numSeeders": "0", "downloadSpeed": "0",
                              "bittorrent": {"info": {"name": "ubuntu.iso"}}}])
    assert t[0]["name"] == "ubuntu.iso" and t[0]["bt"] and t[0]["connections"] == 0


def test_cli_fix_aria2(capsys):
    assert cli.main(["fix", "--aria2"]) == 0
    assert "async-dns=false" in capsys.readouterr().out


def test_cli_fix_and_restore(tmp_path, capsys):
    p = tmp_path / "settings.json"
    _write(p, {"engine": {"dnsMode": "async"}})
    assert cli.main(["fix", "--settings", str(p)]) == 0
    assert cli.main(["restore", "--settings", str(p)]) == 0
    assert cli.main(["fix", "--settings", str(tmp_path / "nope.json")]) == 2
