"""Local baton cache for offline fallback.

Write-through: every successful remote write also writes to local cache.
Read fallback: when remote is unreachable, read from local cache.
Dirty tracking: when remote write fails, mark cache as pending_upload.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".claude" / "loop" / "batons"


def _cache_path(namespace: str) -> Path:
    safe_name = namespace.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe_name}.json"


def cache_write(namespace: str, baton: dict[str, Any], sync_status: str = "synced") -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {**baton, "_sync_status": sync_status}
    _cache_path(namespace).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def cache_read(namespace: str) -> dict[str, Any] | None:
    path = _cache_path(namespace)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_sync_status", None)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def mark_dirty(namespace: str) -> None:
    path = _cache_path(namespace)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_sync_status"] = "pending_upload"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass


def get_dirty_namespaces() -> list[str]:
    if not CACHE_DIR.exists():
        return []
    dirty = []
    for path in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("_sync_status") == "pending_upload":
                dirty.append(path.stem)
        except (json.JSONDecodeError, OSError):
            continue
    return dirty


def clear_dirty(namespace: str) -> None:
    path = _cache_path(namespace)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_sync_status"] = "synced"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass
