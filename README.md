# FreeLLMAPI

Read-only Omarchy bar widget for a local [FreeLLMAPI](https://github.com/mbot11/freellmapi) gateway: live health, providers, chat/Fusion availability, inferred media lanes, and quota. One plugin. Monitor surface only — it does not start Docker, generate content, or toggle keys.

## Requirements

- Omarchy (Hyprland + omarchy-shell)
- `python3` (stdlib only) and `curl`
- FreeLLMAPI listening on `127.0.0.1:3001` (override with `baseUrl` in the plugin config)
- Unified key as `FREELLMAPI_UNIFIED_KEY` in `~/.env` (mode 0600). The plugin never stores the key.

## Install

From this local clone (no public remote yet):

```bash
omarchy plugin add $(pwd) --enable
```

Or copy/symlink the repo under `~/.config/omarchy/plugins/io.github.mbot11.freellmapi` and enable it from bar settings. The pill lands on the right section.

Optional hotkey in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + F", "FreeLLMAPI panel", "omarchy-shell io.github.mbot11.freellmapi toggle")
```

## Remove

```bash
omarchy plugin remove io.github.mbot11.freellmapi --yes
# optional leftover state:
# rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/io.github.mbot11.freellmapi"
```

Removing the plugin does not stop the FreeLLMAPI gateway.

## Settings

| Key | Default | Meaning |
| --- | --- | --- |
| `refreshIntervalSec` | 60 | Collector poll interval (min 30, max 3600) |

## What it shows

- **Bar pill** — `FLA` plus ready-upstream count and a labeled status (ready / degraded / down). Never hidden.
- **Panel tabs** — Overview, Providers, Chat, Fusion, Media, Quota.
- **IPC** — `omarchy-shell io.github.mbot11.freellmapi open|close|toggle|refresh`

Failed polls keep the last snapshot and mark it stale. Media counts are never invented; the Media tab only infers lanes from known providers.

## Tests

```bash
./tests/run.sh
omarchy plugin validate .
```

## License

MIT, see [LICENSE](LICENSE).
