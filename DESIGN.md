# FreeLLMAPI plugin — product language

A glanceable **Monitor** for the local FreeLLMAPI gateway. Not a second dashboard, not a generator.

## Information architecture

1. **Pill** — always present. Label `FLA`, ready-upstream count, status as color **and** a text label (Ready / Degraded / Down). Never hide an empty slot.
2. **Overview** — one operational sentence (Ready / Degraded / Down), version, uptime, poll age, four stats, last-error banner when present.
3. **Providers** — one row per upstream: name, status chip with a text label, key count, `resume_at` while cooling, remaining % when the gateway reported it. Sort down → cooling → healthy.
4. **Chat** — exact totals; stored list capped at 80. Pin `auto` and `fusion` first, then available, then unavailable. Filter is local. Unavailable rows keep `unavailable_reason` in a tooltip.
5. **Fusion** — public catalog row only (available + name). Saved panel k/judge is dashboard-session and out of scope; say so once, plainly.
6. **Media** — inferred chips from a closed provider map. Always say counts are unknown. Do not claim a video count.
7. **Quota** — pools from `/v1/quota-forecast`, or “No numeric quotas reported yet”.

Empty tabs use those sentences. Never a blank panel.

## Density

Command-workspace density: compact pill, tabbed popup, short operational copy. One accent signal — the active tab — using the live Omarchy theme (`Color.accent` fill, `Color.background` text). No logos, no second chrome, no plugin-local palette.

## Brand

The `FLA` label is the brand. Theme tokens do the rest. When the desktop theme is NuMust, accent is already NuMust; other themes restyle the same bindings. Do not special-case a theme in QML. This file is not a color table.

## Voice

Plain claims. Named errors. Age of stale data. No hype, no “AI-powered”, no marketing adjectives.
