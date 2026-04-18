from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_text(stable_json_dumps(payload))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()
    return cleaned


def split_sentences(value: str) -> list[str]:
    cleaned = normalize_text(value)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    return [part.strip(" -•") for part in parts if part.strip(" -•")]


def iso_after_days(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
