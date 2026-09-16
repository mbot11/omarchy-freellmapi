# Security

FreeLLMAPI bar widget is a read-only monitor. This document is the trust
boundary the marketplace maintainer (or any user) can verify against the
source and `tests/`.

## Trust boundary

Omarchy shell plugins run unsandboxed with the current user's permissions.
This plugin narrows itself to:

- **Reads only**: five HTTP GETs against the local FreeLLMAPI gateway —
  `GET /livez`, `GET /readyz` (unauthenticated) and `GET /v1/providers`,
  `GET /v1/quota-forecast`, `GET /v1/models` (Bearer). Nothing else. No
  filesystem reads outside its own state directory, no SQLite, no docker,
  no process inspection.
- **Credential handling**: the unified key is read once per poll from
  `~/.env` (`FREELLMAPI_UNIFIED_KEY`, mode 0600, read via `bin/collect:23-38`).
  The plugin never opens `auth.json`, the dashboard, browser profiles, or any
  other credential store. The key is passed to curl **only** through stdin
  config (`curl -K -`, `header = "Authorization: Bearer …"`,
  `bin/collect:55-65`) — never argv, never a query string, never logged, and
  a regression test pins this (`tests/test_collect_write.py`,
  `test_http_get_puts_key_on_stdin_not_argv`).
- **Writes only**: `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/state.json`
  (mode 0600, written atomically via `os.open(..., 0o600)` + `os.replace`,
  `bin/collect:85-100`) and an optional user-created `config.json` in the
  same directory whose only recognized key is `baseUrl`. Removing the plugin
  directory leaves no configuration behind.

## Network egress

The only endpoint is the local gateway, default `http://127.0.0.1:3001`
(`bin/collect:11`), overridable to another loopback address via the local
`config.json` `baseUrl` (documented user opt-in, README Settings table).
There is no telemetry, no update check, no analytics, no external stream of
any kind. QML performs zero network I/O — `Panel.qml` reads local state
through `FileView` and spawns the local collector through `Process`.

## Fail-closed behavior

- A missing unified key raises **before** any authenticated call
  (`bin/collect:106-107`): the previous snapshot is kept, `stale: true` is
  set, and the UI explains the fix. Tested by
  `test_missing_key_keeps_previous_and_marks_stale`.
- HTTP 401/503 JSON bodies can never be mistaken for success: curl runs
  with `-f` and non-2xx raises (`bin/collect:12,66-72`), tested by
  `test_http_get_raises_on_401_json` and `test_collect_marks_stale_on_non_2xx`.
- A failed poll never blanks the widget: the last good snapshot is retained
  with `stale: true` (`normalize_state` error path), and the gateway
  live/ready flags are recomputed from the actual probes so a dead gateway
  renders the Down state even when older data exists.

## Dangerous-pattern posture

- No `shell=True`, `os.system`, `eval`, or `exec` anywhere; the only
  subprocess is curl with a fixed argv list (`bin/collect:12`).
- No `/tmp` pid files; no `pkexec`/`sudo`/`docker`; no systemctl; the
  plugin cannot start, stop, or configure anything.
- No hardcoded secrets: the security-grep test
  (`tests/test_security.py`) fails the build on `?key=` query strings,
  argv Authorization headers, `/tmp` pid patterns, or `sk_`/`freellmapi-`
  literals containing digits.
- No hex colors in QML — the widget paints only through the live Omarchy
  theme (`Color`/`Style`).

## Supply chain

Python 3 stdlib only (`json`, `os`, `subprocess`, `sys`, `pathlib`,
`datetime`, `copy`) plus `curl` and `python3` on the host. No pip installs,
no requirements files, no submodules, no vendored code, no
curl-pipe-shell. Tests use stdlib `unittest` only and never touch the live
network.

## Verification

```bash
./tests/run.sh          # 12 tests: normalize, collect-write, security grep
omarchy plugin validate .
gitleaks detect --source . --no-git    # optional; expect no tracked findings
```

Audit history: a full security audit (gitleaks over the complete commit
history plus manual sweeps for secrets, personal paths, network egress,
dangerous patterns, and supply chain) was completed before publication with
the verdict SAFE FOR PUBLIC; the report is intentionally not committed.