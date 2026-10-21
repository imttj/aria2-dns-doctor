# aria2-dns-doctor



Diagnose and fix **aria2 / Motrix** BitTorrent and magnet downloads stuck at **0 peers / 0 connections** because aria2's asynchronous DNS resolver (c-ares) hangs on bogus DNS servers.

Pure Python 3 standard library, cross-platform (Windows, macOS, Linux), no dependencies.

## The problem

aria2 resolves tracker hostnames with c-ares, which reads the system's DNS server list itself. On Windows, disconnected or virtual adapters often advertise the deprecated IPv6 site-local DNS servers `fec0:0:0:ffff::1/2/3`. c-ares tries them, times out, and trackers never resolve — so magnets sit at "0 connections" forever while browsers work fine (they use the OS resolver).

**Fix:** make aria2 use the system resolver (`--async-dns=false`). In Motrix this is `"dnsMode": "system"` in the `engine` section of `settings.json`.

**Gotcha:** Motrix's `settings.json` must be UTF-8 **without BOM**. Editing it with Windows PowerShell 5 / Notepad may add a BOM, and Motrix will then silently **reset all your settings**. This tool always backs up first and writes without BOM.

## Install

```bash
pip install git+https://github.com/imttj/aria2-dns-doctor
# or run from a checkout without installing:
python -m aria2_dns_doctor diagnose
```

## Usage

```bash
# Check DNS servers, tracker resolution
aria2-dns-doctor diagnose

# Also inspect a running aria2 / Motrix (Motrix RPC default port is 16800)
aria2-dns-doctor diagnose --rpc http://127.0.0.1:16800/jsonrpc --secret YOURSECRET

# Fix Motrix (close Motrix first!). Default paths:
#   Windows: %APPDATA%\Motrix\settings.json
#   macOS:   ~/Library/Application Support/Motrix/settings.json
#   Linux:   ~/.config/Motrix/settings.json
aria2-dns-doctor fix --dry-run
aria2-dns-doctor fix
aria2-dns-doctor fix --settings /path/to/settings.json

# Plain aria2: prints the line to add to aria2.conf
aria2-dns-doctor fix --aria2      # -> async-dns=false

# Undo
aria2-dns-doctor restore
```

Example output on an affected Windows machine:

```
System DNS servers:
  !! fec0:0:0:ffff::1                         NO RESPONSE
       - deprecated IPv6 site-local (fec0::/10) - usually a stale default from a disconnected adapter; c-ares may hang on it
     192.168.1.1                              ok 3 ms
```

`diagnose` exits with code 1 when problems are found, 0 otherwise.

## Development

```bash
python -m pip install pytest && python -m pytest
```

## 中文说明

**aria2-dns-doctor** 用于诊断和修复 aria2 / Motrix 下载 BT/磁力链接时一直 **0 连接、0 节点** 的问题。

**原因：** aria2 默认使用异步 DNS（c-ares），会直接读取系统的 DNS 服务器列表。Windows 上已断开或虚拟网卡常带有已废弃的 IPv6 站点本地 DNS（如 `fec0:0:0:ffff::1`），c-ares 查询它们时卡住，tracker 域名解析失败，于是一直没有连接；而浏览器使用系统解析器所以正常。

**解决：** 让 aria2 使用系统 DNS（`--async-dns=false`）。Motrix 中即在 `settings.json` 的 `engine` 段设置 `"dnsMode": "system"`（Windows 路径：`%APPDATA%\Motrix\settings.json`）。

**注意：** `settings.json` 必须保存为 **无 BOM 的 UTF-8**，否则 Motrix 会重置全部设置！本工具修改前会自动备份，并以无 BOM 格式写入。

```bash
aria2-dns-doctor diagnose                 # 诊断
aria2-dns-doctor fix                      # 修复 Motrix（请先完全退出 Motrix）
aria2-dns-doctor fix --aria2              # 纯 aria2：输出 aria2.conf 配置行
aria2-dns-doctor restore                  # 从备份恢复
```

## License

MIT © 2026 Tommy (imttj)
