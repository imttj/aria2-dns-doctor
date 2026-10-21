# Changelog

## [0.1.0] - 2026-10-21
### Added
- `diagnose`: list system DNS servers (Windows/macOS/Linux), flag fec0::/10 site-local and link-local servers, UDP/53 probe, tracker hostname resolution, optional aria2 RPC check (`--rpc`, `--secret`).
- `fix`: set Motrix `engine.dnsMode = "system"` with timestamped backup, written as UTF-8 without BOM; `--aria2` prints `async-dns=false`; `--dry-run`.
- `restore`: restore latest or a specific backup.
