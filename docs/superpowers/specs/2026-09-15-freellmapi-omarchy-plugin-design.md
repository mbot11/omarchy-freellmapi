# FreeLLMAPI Omarchy plugin — design spec

Date: 2026-09-15
Status: draft for user review
Plugin id: `io.github.mbot11.freellmapi`
Repo (local only): `this repo`

## Problem

FreeLLMAPI runs on this Omarchy machine at `127.0.0.1:3001` as an on-demand gateway. There is no marketplace plugin that shows its live health and capability surface. The operator currently has to open the web dashboard to know whether chat, Fusion, providers, quota, or media lanes are actually up.

## Goal

v0.0.1 is a **read-only status and capabilities tracker**: a compact bar pill and a feature-rich tabbed popup. It is a **Monitor** surface (glanceable operational state), not a generator and not a second dashboard.

It must look finished on first enable: official Omarchy `Panel` shell, painted only with live theme tokens so it tracks whichever Omarchy theme is active.

## Non-goals (v0.0.1)

- Start/stop the Docker container, pkexec, docker group membership
- Dashboard login cookie or `/api/*` session routes
- Reading container SQLite
- Chat, image, audio, video, or embedding **generation** from the bar
- Toggling models or keys
- Marketplace submission, remote git, PR
- A `service` / `keepLoaded` daemon
- Inventing media/embedding counts the unified key cannot see

## Decisions already locked

| Decision | Choice |
| --- | --- |
| Job | Read-only tracker |
| Data | Unified key only (`FREELLMAPI_UNIFIED_KEY` in `~/.env`) |
| Pill | `FLA` + status color + ready-provider count |
| Popup | Tabbed: Overview, Providers, Chat, Fusion, Media, Quota |
| Visual | Strict Omarchy plugin theming (`Color` / `Style` / first-party Panel chrome). Light NuMust brand = FLA label + accent-as-active-tab via the live theme, not a private palette |
| Scope | Local git, no remote |

## Architecture

One third-party plugin, one git repo, `manifest.json` at root.

- `kinds`: `["bar-widget"]`
- `entryPoints.barWidget`: `Panel.qml`
- `allowMultiple`: false
- `defaultSection`: right
- `category`: AI
- Schema: `refreshIntervalSec` integer, min 30, max 3600, step 30, default 60

QML never performs network I/O. A python3 stdlib collector writes `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/state.json`. QML binds through `FileView { watchChanges: true }`. Failed polls must not wipe the last good snapshot; they set `error` and leave prior fields.

IPC target equals plugin id. `manageIpc: false` with a single `IpcHandler` that implements open/close/show/hide/toggle **and** `refresh`, so the target is not registered twice.

## Collector contract

Binary: `bin/collect` (python3, stdlib only). Array-form Process command. No shell strings.

Allowed HTTP:

- Unauthenticated: `GET /livez`, `GET /readyz`
- Unified key: `GET /v1/providers`, `GET /v1/quota-forecast`, `GET /v1/models`

Auth: curl `-K -` with both `url=` and `header=` on stdin. Never argv, never `?key=`, never QML literals, never log the token.

Base URL default `http://127.0.0.1:3001`, overridable in `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/config.json` mode 0600 (`baseUrl` only). Key is **not** stored there.

On-demand `refresh` must request the **full** endpoint set. Partial writes that blank other sections are forbidden.

State JSON must stay small (well under 100 KB): chat model list truncated to 80 rows after filter metadata (totals always exact). No request bodies, no key ids, no PII.

## Normalized state

```json
{
  "fetched_at": "ISO-8601",
  "error": null,
  "stale": false,
  "gateway": {
    "version": "0.4.1",
    "uptime_s": 0,
    "live": true,
    "ready": true,
    "ready_upstreams": 12
  },
  "providers": [
    {
      "platform": "groq",
      "name": "Groq",
      "status": "healthy",
      "keys": 1,
      "resume_at": null,
      "requests_remaining_pct": null,
      "last_error": null
    }
  ],
  "chat": {
    "total": 288,
    "available": 172,
    "unavailable": 116,
    "auto_available": true,
    "fusion_available": true,
    "models": [{ "id": "auto", "name": "…", "available": true, "unavailable_reason": null }]
  },
  "fusion": {
    "available": true,
    "name": "Fusion (panel of models…)",
    "unavailable_reason": null
  },
  "media": {
    "counts_unknown": true,
    "inferred": [
      { "modality": "image", "from": ["cloudflare"] },
      { "modality": "audio", "from": ["cloudflare"] },
      { "modality": "transcription", "from": ["groq"] },
      { "modality": "video", "from": ["pollinations"] },
      { "modality": "embeddings", "from": [] }
    ]
  },
  "quota": { "generated_at": "ISO-8601", "low_balance_count": 0, "pools": [] }
}
```

Media inference map (v0.0.1, closed list):

- cloudflare → image, audio
- groq → transcription
- pollinations → video
- huggingface → (no video row claimed unless `/v1/providers` shows it **and** we still label counts unknown)

Do not POST to `/v1/images/generations` or siblings to “probe” — that spends quota.

## UI

**Pill.** `FLA · {ready_upstreams}` with a status dot. Never hidden.

- Green (`#10b981`): live and ready, no rate-limited providers
- Amber (`#f59e0b`): live but degraded (any `rate_limited`, or ready count dropped) **or** unified key missing while livez is ok
- Red (`#ef4444`): livez failed or readyz unavailable
- Count `?` when providers were not fetched (missing key)

**Popup tabs.** 1 Overview, 2 Providers, 3 Chat, 4 Fusion, 5 Media, 6 Quota.

- Overview: Playfair title (`Ready` / `Degraded` / `Down`), version, uptime, poll age, four stats, last error banner
- Providers: rows sorted down → cooling → healthy; chips with text labels; `resume_at` when cooling; remaining % when present
- Chat: local filter, `auto` and `fusion` pinned at top, then available then unavailable; tooltip for `unavailable_reason`
- Fusion: public catalog row only (available + name). Explicit note that saved panel k/judge is dashboard-session and out of scope
- Media: inferred chips + “counts unknown” / “not in /v1/models”
- Quota: `/v1/quota-forecast` pools or “No numeric quotas reported yet”

## Visual identity (Omarchy theme rules + light NuMust brand)

Do not violate Omarchy plugin theming. Use first-party surfaces and tokens only:

- `qs.Ui.Panel`, `WidgetButton`, `KeyboardPanel`, `PanelKeyCatcher`
- `Color.background`, `Color.foreground`, `Color.accent`, `Color.urgent`, `Color.muted`
- `Color.bar.*` / `Color.popups.*`
- `Style.*` fills, borders, spacing, radii, type

No plugin-local palette, no bundled Playfair/JetBrains requirement, no hex in QML.

Light NuMust branding is **through the theme**, not a paint-over:

- The desktop theme `numust` already maps NuMust DESIGN.md into `colors.toml` (`accent = #ff5f19`, etc.). When that theme is active, `Color.accent` **is** NuMust orange.
- Brand touch in the plugin: the `FLA` pill label, tabbed command-workspace density, one accent signal (active tab uses `Color.accent` with `Color.background` text for contrast), operational copy. That is the branding. Do not add logos, orange fills on the bar, or a second chrome.
- Other Omarchy themes (`molllz`, `mena-botrous`, stock): the same bindings restyle automatically. Do not special-case NuMust in QML.

`DESIGN.md` in the repo is product language (IA, density, no hype). It is not a QML color table.

## States

- Happy: last snapshot, `stale: false`
- Degraded banner: named provider + resume time
- Down: keep snapshot, show age, “No process on 127.0.0.1:3001”
- Auth: livez may be green; providers/models explain `FREELLMAPI_UNIFIED_KEY` in `~/.env` mode 0600
- Empty tabs use the designed sentences in the UI section, never a blank panel
- Collector writes `{ ...previous, error, stale: true }` on failure

## Keyboard and IPC

- Click / Space: toggle
- Esc: close
- 1–6: tabs
- r: refresh
- `/`: focus chat filter when on Chat
- `omarchy-shell io.github.mbot11.freellmapi open|close|toggle|refresh`
- Invalid IPC argument: nonzero exit, named reason, no file write

## Tests and QA (definition of done)

1. `omarchy plugin validate <dir>` green
2. Collector tests on fixtures (no live network); assert JSON shape and size cap
3. Security audit test: no `?key=`, no argv secrets, no `/tmp` pid files, no 24+ char tokens with a digit in source
4. Enable locally; IPC verbs + refusal path
5. grim visual QA of pill + each tab + down/auth banners on the live bar
6. Journal clean of `scene:` errors after load

## Files (implementation, after spec approval)

- `manifest.json`
- `Panel.qml`
- `bin/collect`
- `tests/run.sh` + fixtures
- `DESIGN.md` (product language; colors come from the live Omarchy theme)
- `README.md` (install and removal)
- `LICENSE` MIT
- `.gitignore` including `.superpowers/`

## Risks

- Theme swap: FileView/collector data is theme-agnostic; QML must recolor instantly via `Color` bindings with no restart.
- `/v1/models` is 288 rows today; always truncate the stored list.
- Catalog overlay for Nova Reel is independent of this plugin; Media tab must not claim a video **count**.

## Next

User reviews this file. After explicit approval, write an implementation plan (`writing-plans`), then implement. No plugin QML/collector until that approval.
