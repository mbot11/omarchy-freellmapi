# Security

FreeLLMAPI bar widget is a read-only monitor. This document is the trust
boundary the marketplace maintainer (or any user) can verify against the
source and `tests/`.

## Trust boundary

Omarchy shell plugins run unsandboxed with the current user's permissions.
This plugin narrows itself to:

- **Reads only**: five HTTP GETs against a loopback FreeLLMAPI gateway —
  `GET /livez`, `GET /readyz` (unauthenticated) and `GET /v1/providers`,
  `GET /v1/quota-forecast`, `GET /v1/models` (Bearer). The only other read is
  `~/.env` for `FREELLMAPI_UNIFIED_KEY`. No SQLite, no docker, no process
  inspection.
- **Credential handling**: the unified key is read once per poll from
  `~/.env`. The file must be a regular file owned by the current user, mode
  0600, and not a symlink; otherwise the collector records `key file
  unreadable` and does not send a credential. The key is passed to curl
  **only** through stdin config (`curl -K -`). Never argv, never a query
  string, never logged. Curl stderr is not stored.
- **Writes only**: `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/state.json`
  (mode 0600, unique temporary file, `flock`, then `os.replace`). An optional
  user-created `config.json` in the same directory has one recognized key,
  `baseUrl`. Removing the plugin
  directory leaves no configuration behind.

## Network egress

The only endpoint is the local gateway, default `http://127.0.0.1:3001`.
`config.json` `baseUrl` is accepted only for `http`/`https` loopback
(`127.0.0.1`, `::1`, or `localhost` resolving only to loopback). A remote or
non-HTTP value is rejected and never contacted. Curl starts with `-q`,
disables proxies, limits protocols to HTTP(S), does not follow redirects, and
inherits no proxy environment variables. There is no telemetry, update
check, or analytics. QML performs no network I/O.

## Fail-closed behavior

- A missing or unreadable unified key is recorded before any authenticated
  call. The previous snapshot is kept and marked stale.
- `/livez` and `/readyz` are collected independently. A readiness 503 is a
  gateway status, not a reason to skip provider diagnostics. Authenticated
  non-2xx responses still fail that section and keep the last good catalog.
- HTTP error bodies and curl stderr are not stored. Failures become short
  named messages.
- A failed poll never blanks the widget. `capabilities_fresh` is false when
  the catalog was not collected on this poll, and the pill count becomes `?`.

## Dangerous-pattern posture

- No `shell=True`, `os.system`, `eval`, or `exec` anywhere; the only
  subprocess is curl with a fixed argv list.
- No `/tmp` pid files; no `pkexec`/`sudo`/`docker`; no systemctl; the
  plugin cannot start, stop, or configure anything.
- No hardcoded secrets: the security-grep test
  (`tests/test_security.py`) fails the build on `?key=` query strings,
  argv Authorization headers, `/tmp` pid patterns, or `sk_`/`freellmapi-`
  literals containing digits.
- No hex colors in QML — the widget paints only through the live Omarchy
  theme (`Color`/`Style`).

## Supply chain

Python 3 stdlib only, plus `curl` and `/usr/bin/python3`. No pip installs,
no requirements files, no submodules, no vendored code, no
curl-pipe-shell. Tests use stdlib `unittest` only and never touch the live
network.

## Verification

```bash
./tests/run.sh          # normalize, collect-write, and security grep
omarchy plugin validate .
gitleaks detect --source . --no-git    # optional; expect no tracked findings
```

Audit history: a full security audit (gitleaks over the complete commit
history plus manual sweeps for secrets, personal paths, network egress,
dangerous patterns, and supply chain) was completed before publication with
the verdict SAFE FOR PUBLIC; the report is intentionally not committed.