# FreeLLMAPI Omarchy Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local-only Omarchy bar-widget that shows FreeLLMAPI health and capabilities from unified-key GET endpoints, following the live Omarchy theme.

**Architecture:** python3 stdlib collector writes `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/state.json`. One `Panel.qml` reads it via FileView, paints with `Color`/`Style`, and registers IPC `open|close|toggle|refresh`. No QML network, no docker, no dashboard cookie, no generation.

**Tech Stack:** Omarchy 4.0.3 Quickshell QML, python3 stdlib, curl stdin-config, unittest.

**Spec:** `docs/superpowers/specs/2026-09-15-freellmapi-omarchy-plugin-design.md`

## Global Constraints

- Plugin id `io.github.mbot11.freellmapi` — never `omarchy.*`
- Read-only: GET `/livez`, `/readyz`, `/v1/providers`, `/v1/quota-forecast`, `/v1/models` only
- Auth: `FREELLMAPI_UNIFIED_KEY` from `~/.env`; curl `-K -`; never argv/`?key=`/QML
- Theme: bind `Color`/`Style` only — no hardcoded NuMust hex
- Active-tab text on accent fill uses `Color.background`
- Status color always paired with a text label
- Chat model list stored max 80 rows; totals remain exact
- Poll `refreshIntervalSec` default 60, min 30
- Failed poll keeps last snapshot (`stale: true`, `error` set)
- Local git only, no remote, no marketplace
- Docker/pkexec/sqlite/POST media are forbidden

## File map

- `manifest.json` — plugin metadata + schema
- `Panel.qml` — pill + popup + IPC
- `bin/collect` — fetch + normalize + atomic write
- `bin/lib/normalize.py` — pure functions, imported by collect and tests
- `tests/run.sh` — unittest + security grep
- `tests/test_normalize.py`, `tests/test_collect_write.py`, `tests/test_security.py`
- `tests/fixtures/*.json` — captured/perturbed `/v1` shapes
- `DESIGN.md` — product language (not a color table)
- `README.md`, `LICENSE`, `.gitignore`

---

### Task 1: Repo + failing normalize tests

**Files:**
- Create: `.gitignore`, `LICENSE`, `README.md`, `DESIGN.md`, `manifest.json`, `bin/lib/normalize.py`, `tests/test_normalize.py`, `tests/run.sh`, `tests/fixtures/models.json`, `tests/fixtures/providers.json`, `tests/fixtures/quota.json`, `tests/fixtures/livez.json`, `tests/fixtures/readyz.json`

**Interfaces:**
- Produces: `normalize_state(livez, readyz, providers, quota, models, previous=None, error=None, fetched_at=None) -> dict` with spec keys `gateway`, `providers`, `chat`, `fusion`, `media`, `quota`, `fetched_at`, `error`, `stale`

- [ ] **Step 1: Write failing tests** in `tests/test_normalize.py`

```python
import json, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from lib.normalize import normalize_state, MEDIA_INFER, CHAT_LIST_CAP

FIX = Path(__file__).parent / "fixtures"

class NormalizeTests(unittest.TestCase):
    def load(self, name):
        return json.loads((FIX / name).read_text())

    def test_counts_and_fusion(self):
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            self.load("providers.json"), self.load("quota.json"),
                            self.load("models.json"))
        self.assertTrue(s["gateway"]["live"])
        self.assertEqual(s["chat"]["total"], 4)
        self.assertTrue(s["fusion"]["available"])
        self.assertEqual(s["chat"]["auto_available"], True)
        self.assertTrue(s["media"]["counts_unknown"])
        self.assertLessEqual(len(s["chat"]["models"]), CHAT_LIST_CAP)

    def test_keeps_previous_on_error(self):
        prev = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                               self.load("providers.json"), self.load("quota.json"),
                               self.load("models.json"))
        s = normalize_state(None, None, None, None, None, previous=prev, error="unreachable")
        self.assertEqual(s["chat"]["total"], prev["chat"]["total"])
        self.assertTrue(s["stale"])
        self.assertEqual(s["error"], "unreachable")

    def test_media_infer_cloudflare_groq_pollinations(self):
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            self.load("providers.json"), self.load("quota.json"),
                            self.load("models.json"))
        mods = {i["modality"]: i["from"] for i in s["media"]["inferred"]}
        self.assertIn("cloudflare", mods["image"])
        self.assertIn("groq", mods["transcription"])
        self.assertIn("pollinations", mods["video"])

if __name__ == "__main__":
    unittest.main()
```

Fixture `models.json` object list of four rows: `auto` available, `fusion` available, one other available, one unavailable. `providers.json` includes groq/cloudflare/pollinations healthy plus one rate_limited. `livez.json` `{status:ok,version,uptime_s}`. `readyz.json` `{status:ok,ready_upstreams:12}`.

- [ ] **Step 2: Run tests — expect FAIL** (`ModuleNotFoundError` or missing function)

```bash
python3 tests/test_normalize.py -v
```

- [ ] **Step 3: Implement `bin/lib/normalize.py`**

```python
CHAT_LIST_CAP = 80
MEDIA_INFER = {
    "cloudflare": ["image", "audio"],
    "groq": ["transcription"],
    "pollinations": ["video"],
}

def normalize_state(livez, readyz, providers, quota, models, previous=None, error=None, fetched_at=None):
    ...
```

Rules: pin `auto`/`fusion` first in `chat.models`; truncate to 80 after that; `stale=bool(error)`; if error and previous, copy previous then overlay error/stale/fetched_at.

- [ ] **Step 4: Run tests — expect PASS**

```bash
python3 tests/test_normalize.py -v
```

- [ ] **Step 5: `omarchy plugin validate` stub**

`manifest.json` schemaVersion 1, id `io.github.mbot11.freellmapi`, kinds `["bar-widget"]`, entryPoints `{barWidget: Panel.qml}`, barWidget schema `refreshIntervalSec` min 30 max 3600 default 60. Minimal `Panel.qml`: `import QtQuick; Item { visible: false; property var settings: ({}) }`.

```bash
omarchy plugin validate "$(pwd)"
```

Expected: pass (entry point exists).

- [ ] **Step 6: Commit**

```bash
cd "$(pwd)"  # repo root
git init
git add -A
git commit -m "test: normalize FreeLLMAPI gateway state"
```

No remote.

---

### Task 2: Collector fetch + atomic write

**Files:**
- Create: `bin/collect`, `tests/test_collect_write.py`, `tests/test_security.py`
- Modify: `tests/run.sh`

**Interfaces:**
- Consumes: `normalize_state`
- Produces: `main(argv)` writes state JSON atomically to `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/state.json`; `load_key()` reads `FREELLMAPI_UNIFIED_KEY` from `~/.env` without printing it; `http_get(url, key=None)` uses curl `-K -`

- [ ] **Step 1: Failing tests**

`test_collect_write.py`: monkeypatch `http_get` to return fixtures; tmp `XDG_STATE_HOME`; assert file exists, mode not world-readable if possible, JSON has `gateway.live`. Second test: `http_get` raises; previous file remains and new JSON has `stale: true`.

`test_security.py`: grep repo (exclude fixtures/.superpowers) for `?key=`, `/tmp` pid files, `Authorization: Bearer ` concatenated with a variable in argv (command lists must be arrays). Fail if `sk_` or `freellmapi-` literals with a digit appear.

- [ ] **Step 2: Run — expect FAIL**

```bash
python3 tests/test_collect_write.py -v
```

- [ ] **Step 3: Implement `bin/collect`**

- Shebang `#!/usr/bin/python3`
- Default base `http://127.0.0.1:3001`
- Optional config `$XDG_STATE_HOME/omarchy/io.github.mbot11.freellmapi/config.json` key `baseUrl` only
- curl argv: `["curl","-sS","-m","8","-K","-"]` with stdin `url=...\nheader = "Authorization: Bearer ${key}"\n` — key only on stdin
- Unauthenticated livez/readyz: curl without header
- Atomic write: write `state.json.tmp` then `os.replace`
- On any fetch failure, load previous JSON if present and call `normalize_state(..., previous=..., error=str)`

- [ ] **Step 4: Run full suite**

```bash
chmod +x bin/collect tests/run.sh
./tests/run.sh
```

Expected: all unittest PASS, security grep PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/collect tests
git commit -m "feat: collect FreeLLMAPI status without leaking the unified key"
```

---

### Task 3: Panel pill + FileView + theme bindings

**Files:**
- Modify: `Panel.qml`

**Interfaces:**
- Consumes: state JSON
- Produces: bar pill `FLA · N` (or `?`), status dot from live/ready/degraded, click toggles popup

- [ ] **Step 1: Replace stub `Panel.qml`** with Memorix-shaped Panel:

```qml
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.mbot11.freellmapi"
  ipcTarget: "io.github.mbot11.freellmapi"
  manageIpc: false
  readonly property int refreshIntervalSec: setting("refreshIntervalSec", 60)
  readonly property string statePath: Quickshell.env("XDG_STATE_HOME")
                    ? Quickshell.env("XDG_STATE_HOME") + "/omarchy/io.github.mbot11.freellmapi/state.json"
                    : Quickshell.env("HOME") + "/.local/state/omarchy/io.github.mbot11.freellmapi/state.json"
  property var snap: ({})
  // pill uses Color.foreground / Color.accent / Color.urgent / Color.muted only
}
```

`FileView { path: root.statePath; watchChanges: true; onLoaded: parse }`

`WidgetButton` text from snap. Timer interval `Math.max(30, refreshIntervalSec)*1000` runs `collectProc.command = ["python3", collectorPath]`.

Status: if `!gateway.live` → urgent; else if any provider rate_limited or `error` → accent; else foreground/success via muted vs accent.

Never `#ff5f19` or other hex.

- [ ] **Step 2: `omarchy plugin validate` still green**

- [ ] **Step 3: Commit**

```bash
git commit -am "feat: theme-following FLA pill bound to collector state"
```

---

### Task 4: Tabbed popup (six tabs)

**Files:**
- Modify: `Panel.qml` (KeyboardPanel content)

**Interfaces:**
- Produces: tabs Overview, Providers, Chat, Fusion, Media, Quota; keys 1–6, `r`, `/`, Esc

- [ ] **Step 1: Implement KeyboardPanel**

- `contentWidth`: `panel.fittedContentWidth(Style.space(620))`
- Active tab background `Color.accent`, text `Color.background`
- Inactive tab text `Color.muted`
- Overview Playfair is **not** required — use Style font; title string `Ready`/`Degraded`/`Down`
- Chat: TextField filter, show `snap.chat.models` locally filtered
- Media: `counts unknown` copy from spec
- Fusion: `snap.fusion` plus session-out-of-scope note
- Empty strings exactly as spec
- `PanelKeyCatcher`: 1–6, r, /, Esc
- Custom `IpcHandler` with open/close/show/hide/toggle/refresh (refresh starts collectProc)

- [ ] **Step 2: Journal sanity after save** (once enabled in Task 5)

- [ ] **Step 3: Commit**

```bash
git commit -am "feat: six-tab FreeLLMAPI capabilities popup"
```

---

### Task 5: Local enable, IPC, visual QA

**Files:** none in repo except README install/remove

- [ ] **Step 1: Enable without `plugin add` from git**

Copy or symlink `this repo` → `~/.config/omarchy/plugins/io.github.mbot11.freellmapi` if Omarchy requires the plugin dir (do **not** `plugin add` a remote). Prefer:

```bash
ln -sfn "$(pwd)" ~/.config/omarchy/plugins/io.github.mbot11.freellmapi
export OMARCHY_SHELL_IPC_TIMEOUT=25s
omarchy plugin enable io.github.mbot11.freellmapi right
```

If enable needs a bar placement, use `omarchy plugin enable io.github.mbot11.freellmapi` then `omarchy bar plugin add` only if first-party docs require it. Re-read `shell.json` after a pause.

- [ ] **Step 2: IPC**

```bash
omarchy-shell io.github.mbot11.freellmapi refresh
omarchy-shell io.github.mbot11.freellmapi open
omarchy-shell io.github.mbot11.freellmapi close
omarchy-shell io.github.mbot11.freellmapi toggle
```

Expected: exit 0. Invalid method: nonzero, no state write.

- [ ] **Step 3: grim QA**

Capture pill, each tab, then stop the gateway briefly **only if user approves** — otherwise simulate down by pointing config `baseUrl` at a dead port `http://127.0.0.1:3099` for one refresh, grim the red/amber banner, restore config. Do not `docker compose down`.

- [ ] **Step 4: Theme check**

With current theme (likely `numust`), pill/popup must pick up `Color.accent`. No hex in `Panel.qml` (`grep -n '#[0-9a-fA-F]\{3,8\}' Panel.qml` empty except comments).

- [ ] **Step 5: Commit README**

Install: symlink + enable. Remove: `omarchy plugin disable` then unlink. State files live under XDG_STATE_HOME.

```bash
git commit -am "docs: local install and removal for FreeLLMAPI bar widget"
```

---

## Spec coverage

| Spec section | Task |
| --- | --- |
| Architecture / FileView / IPC | 3, 4 |
| Collector endpoints + curl stdin | 2 |
| Normalized state + media infer + 80-cap | 1 |
| Pill + six tabs + copy | 3, 4 |
| Omarchy theme bindings | 3, 4, 5 |
| States stale/auth/down | 1, 2, 5 |
| Keyboard | 4 |
| Tests + grim | 1, 2, 5 |
| Local only | all commits, no remote |

## Placeholder scan

None: endpoints, ids, paths, and test names are concrete.
