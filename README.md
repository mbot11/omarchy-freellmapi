# FreeLLMAPI

Read-only Omarchy bar widget for a local [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) gateway: live health, providers, chat/Fusion availability, inferred media lanes, and quota. One plugin. Monitor surface only — it does not start Docker, generate content, or toggle keys.

## About FreeLLMAPI

This widget is a companion for — and requires — [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) (MIT): a self-hosted gateway that puts 34 free LLM providers and 635 free model endpoints behind one OpenAI-compatible `/v1` with smart routing, automatic failover, and encrypted keys. This plugin is not affiliated with that project; it just monitors your local instance. Install and configure FreeLLMAPI first (its docs cover Docker setup and dashboard keys), add your provider keys there, and this widget surfaces what your instance can actually do.

## Requirements

1. **FreeLLMAPI itself** — install it first: https://github.com/tashfeenahmed/freellmapi (Docker one-liner in its README). It must be listening on `127.0.0.1:3001` (override with `baseUrl` in this plugin's config).
2. Omarchy (Hyprland + omarchy-shell)
3. `python3` (stdlib only) and `curl`
4. Your FreeLLMAPI unified key as `FREELLMAPI_UNIFIED_KEY` in `~/.env` (mode 0600). The plugin never stores the key. The dashboard shows it under Keys.

## Install

From a local clone of this repo (no public remote yet):

```bash
omarchy plugin add "$(pwd)" --enable
```

Or symlink the clone to `~/.config/omarchy/plugins/io.github.mbot11.freellmapi` and enable it from bar settings. The pill lands on the right section. Do not enable until you intend to load it in the live shell.

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

Removing the widget does not stop or uninstall the FreeLLMAPI gateway.

## Settings

| Key | Default | Meaning |
| --- | --- | --- |
| `refreshIntervalSec` | 60 | Collector poll interval (min 30, max 3600) |
| `baseUrl` | `http://127.0.0.1:3001` | Gateway URL override. File `config.json` (mode 0600) in the plugin state dir: `${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/io.github.mbot11.freellmapi/config.json` |

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

## Security

Read-only by construction: five GET endpoints, unified key passed to curl via stdin only, writes limited to a 0600 state file. See [docs/SECURITY.md](docs/SECURITY.md) for the full trust boundary.

## License

MIT, see [LICENSE](LICENSE).