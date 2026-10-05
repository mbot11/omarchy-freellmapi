import copy
import math
from datetime import datetime, timezone

CHAT_LIST_CAP = 80
PROVIDER_CAP = 64
QUOTA_CAP = 40
TEXT_CAP = 240
STATE_BUDGET = 100_000
MEDIA_INFER = {
    "cloudflare": ["image", "audio"],
    "groq": ["transcription"],
    "pollinations": ["video"],
}
_MEDIA_ORDER = ("image", "audio", "transcription", "video", "embeddings")
_QUOTA_FIELDS = (
    "platform",
    "pool",
    "used",
    "remaining",
    "limit",
    "remaining_pct",
    "reset_at",
    "low_balance",
    "seconds_until_reset",
    "rate_per_min",
    "estimated_exhaustion_at",
)


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("text field must be a string")
    return value[:TEXT_CAP]


def _bool(value, label):
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _number(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _require_rows(payload, key):
    if payload is None:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"{key} payload missing {key}")
    return payload[key]


def _slim_model(row):
    if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
        raise ValueError("model row must include an id")
    return {
        "id": _text(row.get("id")),
        "name": _text(row.get("name")),
        "available": _bool(row.get("available"), "available"),
        "unavailable_reason": _text(row.get("unavailable_reason")),
    }


def _normalize_providers(providers):
    rows = _require_rows(providers, "providers")
    if rows is None:
        return []
    out = []
    for row in rows[:PROVIDER_CAP]:
        if not isinstance(row, dict):
            raise ValueError("provider row must be an object")
        out.append({
            "platform": _text(row.get("platform")),
            "name": _text(row.get("name")),
            "status": _text(row.get("status")),
            "keys": _number(row.get("keys"), "keys"),
            "resume_at": _text(row.get("resume_at")),
            "requests_remaining_pct": _number(row.get("requests_remaining_pct"), "requests_remaining_pct"),
            "last_error": _text(row.get("last_error")),
        })
    return out


def _normalize_chat_and_fusion(models):
    rows = _require_rows(models, "data")
    if rows is None:
        rows = []
    auto = None
    fusion = None
    others = []
    available = 0
    unavailable = 0
    auto_available = False
    fusion_available = False
    fusion_name = None
    fusion_reason = None

    for row in rows:
        slim = _slim_model(row)
        if slim["available"]:
            available += 1
        else:
            unavailable += 1
        mid = slim["id"]
        if mid == "auto":
            auto = slim
            auto_available = slim["available"]
        elif mid == "fusion":
            fusion = slim
            fusion_available = slim["available"]
            fusion_name = slim["name"]
            fusion_reason = slim["unavailable_reason"]
        else:
            others.append(slim)

    others.sort(key=lambda row: (not row["available"], row["id"] or ""))
    pinned = []
    if auto is not None:
        pinned.append(auto)
    if fusion is not None:
        pinned.append(fusion)
    ranked = pinned + others
    listed = ranked[:CHAT_LIST_CAP]
    chat = {
        "total": len(rows),
        "available": available,
        "unavailable": unavailable,
        "auto_available": auto_available,
        "fusion_available": fusion_available,
        "models": listed,
        "listed": len(listed),
        "truncated": len(ranked) > CHAT_LIST_CAP,
    }
    fusion_state = {
        "available": fusion_available,
        "name": fusion_name,
        "unavailable_reason": fusion_reason,
    }
    return chat, fusion_state


def _normalize_media(providers):
    rows = _require_rows(providers, "providers") or []
    platforms = {row.get("platform") for row in rows if isinstance(row, dict) and row.get("platform")}
    from_map = {mod: [] for mod in _MEDIA_ORDER}
    for platform, modalities in MEDIA_INFER.items():
        if platform not in platforms:
            continue
        for mod in modalities:
            if mod in from_map and platform not in from_map[mod]:
                from_map[mod].append(platform)
    inferred = [{"modality": mod, "from": from_map[mod]} for mod in _MEDIA_ORDER]
    return {"counts_unknown": True, "inferred": inferred}


def _normalize_quota(quota):
    if quota is None:
        return {"generated_at": None, "low_balance_count": 0, "pools": []}
    if not isinstance(quota, dict) or not isinstance(quota.get("pools"), list):
        raise ValueError("quota payload missing pools")
    pools = []
    for row in quota["pools"][:QUOTA_CAP]:
        if not isinstance(row, dict):
            raise ValueError("quota pool must be an object")
        item = {}
        for field in _QUOTA_FIELDS:
            if field not in row:
                continue
            if field == "low_balance":
                item[field] = _bool(row[field], "low_balance")
            elif field in {"platform", "pool", "reset_at", "estimated_exhaustion_at"}:
                item[field] = _text(row[field])
            else:
                item[field] = _number(row[field], field)
        pools.append(item)
    low = sum(1 for pool in pools if pool.get("low_balance"))
    return {
        "generated_at": _text(quota.get("generated_at")),
        "low_balance_count": low,
        "pools": pools,
    }


def _normalize_gateway(livez, readyz):
    livez = livez if isinstance(livez, dict) else {}
    readyz = readyz if isinstance(readyz, dict) else {}
    ready_count = readyz.get("ready_upstreams", 0) if readyz else 0
    if ready_count is not None:
        ready_count = _number(ready_count, "ready_upstreams")
    return {
        "version": _text(livez.get("version")) if livez else None,
        "uptime_s": _number(livez.get("uptime_s", 0), "uptime_s") if livez else 0,
        "live": bool(livez) and livez.get("status") == "ok",
        "ready": bool(readyz) and readyz.get("status") == "ok",
        "ready_upstreams": 0 if ready_count is None else ready_count,
        "readiness_observed": bool(readyz),
    }


def _rebuild_gateway_on_error(livez, readyz, previous_gateway):
    prev = previous_gateway if isinstance(previous_gateway, dict) else {}
    live = livez if isinstance(livez, dict) else None
    ready = readyz if isinstance(readyz, dict) else None
    observed = ready is not None and "ready_upstreams" in ready
    count = ready.get("ready_upstreams") if ready is not None and observed else prev.get("ready_upstreams", 0)
    return {
        "version": live.get("version") if live is not None and "version" in live else prev.get("version"),
        "uptime_s": live.get("uptime_s") if live is not None and "uptime_s" in live else prev.get("uptime_s", 0),
        "live": live is not None and live.get("status") == "ok",
        "ready": ready is not None and ready.get("status") == "ok",
        "ready_upstreams": count if count is not None else 0,
        "readiness_observed": observed,
    }


def _enforce_budget(state):
    blob = __import__("json").dumps(state, separators=(",", ":"), ensure_ascii=True)
    if len(blob.encode("utf-8")) >= STATE_BUDGET:
        raise ValueError("normalized state exceeds 100 KB")
    return state


def normalize_state(livez, readyz, providers, quota, models, previous=None, error=None, fetched_at=None):
    if error and previous:
        out = copy.deepcopy(previous)
        out["gateway"] = _rebuild_gateway_on_error(
            livez, readyz, previous.get("gateway") if isinstance(previous, dict) else None
        )
        out["error"] = _text(error) or "request failed"
        out["stale"] = True
        out["capabilities_fresh"] = False
        if fetched_at is not None:
            out["fetched_at"] = fetched_at
        return _enforce_budget(out)

    stamp = fetched_at if fetched_at is not None else _iso_now()
    chat, fusion = _normalize_chat_and_fusion(models)
    state = {
        "fetched_at": stamp,
        "error": _text(error) if error else None,
        "stale": bool(error),
        "capabilities_fresh": not bool(error),
        "gateway": _normalize_gateway(livez, readyz),
        "providers": _normalize_providers(providers),
        "chat": chat,
        "fusion": fusion,
        "media": _normalize_media(providers),
        "quota": _normalize_quota(quota),
    }
    return _enforce_budget(state)
