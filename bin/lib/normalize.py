import copy
from datetime import datetime, timezone

CHAT_LIST_CAP = 80
MEDIA_INFER = {
    "cloudflare": ["image", "audio"],
    "groq": ["transcription"],
    "pollinations": ["video"],
}

_MEDIA_ORDER = ("image", "audio", "transcription", "video", "embeddings")


def _as_list(payload, key=None):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and key is not None:
        inner = payload.get(key)
        if isinstance(inner, list):
            return inner
    return []


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slim_model(row):
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "available": bool(row.get("available")),
        "unavailable_reason": row.get("unavailable_reason"),
    }


def _normalize_providers(providers):
    out = []
    for row in _as_list(providers, "providers"):
        out.append({
            "platform": row.get("platform"),
            "name": row.get("name"),
            "status": row.get("status"),
            "keys": row.get("keys"),
            "resume_at": row.get("resume_at"),
            "requests_remaining_pct": row.get("requests_remaining_pct"),
            "last_error": row.get("last_error"),
        })
    return out


def _normalize_chat_and_fusion(models):
    rows = _as_list(models, "data")
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

    pinned = []
    if auto is not None:
        pinned.append(auto)
    if fusion is not None:
        pinned.append(fusion)
    listed = (pinned + others)[:CHAT_LIST_CAP]

    chat = {
        "total": len(rows),
        "available": available,
        "unavailable": unavailable,
        "auto_available": auto_available,
        "fusion_available": fusion_available,
        "models": listed,
    }
    fusion_state = {
        "available": fusion_available,
        "name": fusion_name,
        "unavailable_reason": fusion_reason,
    }
    return chat, fusion_state


def _normalize_media(providers):
    platforms = {
        row.get("platform")
        for row in _as_list(providers, "providers")
        if row.get("platform")
    }
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
    if not isinstance(quota, dict):
        return {"generated_at": None, "low_balance_count": 0, "pools": []}
    pools = quota.get("pools") or []
    if not isinstance(pools, list):
        pools = []
    low = sum(1 for pool in pools if isinstance(pool, dict) and pool.get("low_balance"))
    return {
        "generated_at": quota.get("generated_at"),
        "low_balance_count": low,
        "pools": pools,
    }


def _normalize_gateway(livez, readyz):
    livez = livez if isinstance(livez, dict) else {}
    readyz = readyz if isinstance(readyz, dict) else {}
    return {
        "version": livez.get("version"),
        "uptime_s": livez.get("uptime_s", 0),
        "live": livez.get("status") == "ok",
        "ready": readyz.get("status") == "ok",
        "ready_upstreams": readyz.get("ready_upstreams", 0),
    }


def _rebuild_gateway_on_error(livez, readyz, previous_gateway):
    prev = previous_gateway if isinstance(previous_gateway, dict) else {}
    live = livez if isinstance(livez, dict) else None
    ready = readyz if isinstance(readyz, dict) else None
    return {
        "version": live.get("version") if live is not None and "version" in live else prev.get("version"),
        "uptime_s": live.get("uptime_s") if live is not None and "uptime_s" in live else prev.get("uptime_s", 0),
        "live": live is not None and live.get("status") == "ok",
        "ready": ready is not None and ready.get("status") == "ok",
        "ready_upstreams": (
            ready.get("ready_upstreams")
            if ready is not None and "ready_upstreams" in ready
            else prev.get("ready_upstreams", 0)
        ),
    }


def normalize_state(livez, readyz, providers, quota, models, previous=None, error=None, fetched_at=None):
    if error and previous:
        out = copy.deepcopy(previous)
        out["gateway"] = _rebuild_gateway_on_error(
            livez, readyz, previous.get("gateway") if isinstance(previous, dict) else None
        )
        out["error"] = error
        out["stale"] = True
        if fetched_at is not None:
            out["fetched_at"] = fetched_at
        return out

    stamp = fetched_at if fetched_at is not None else _iso_now()
    chat, fusion = _normalize_chat_and_fusion(models)
    return {
        "fetched_at": stamp,
        "error": error,
        "stale": bool(error),
        "gateway": _normalize_gateway(livez, readyz),
        "providers": _normalize_providers(providers),
        "chat": chat,
        "fusion": fusion,
        "media": _normalize_media(providers),
        "quota": _normalize_quota(quota),
    }
