from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceTier = Literal["raw_source", "llm_derived", "human_confirmed"]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def dump_json(data: dict[str, Any] | list) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


class VerifySpec(BaseModel):
    method: Literal["http", "file_exists", "process_running", "manual"]
    url: str | None = None
    expected_status: int | None = None
    path: str | None = None
    process_name: str | None = None
    timeout_seconds: int = 5
    note: str | None = None


class OpenLoop(BaseModel):
    id: str
    action: str
    expected_outcome: str
    verify: VerifySpec | None = None
    created_at: str
    ttl_days: int = 7
    decision_ref: str | None = None
    status: Literal["open", "verified", "failed", "escalated"] = "open"
    source_tier: SourceTier = "llm_derived"


class FollowUp(BaseModel):
    id: str
    item: str
    reason: str | None = None
    first_seen: str
    defer_count: int = 0
    last_deferred: str | None = None
    priority: Literal["normal", "elevated", "escalated"] = "normal"
    linked_pattern: str | None = None
    source_tier: SourceTier = "llm_derived"


class PatternOccurrence(BaseModel):
    session: str
    context: str


class Pattern(BaseModel):
    id: str
    what: str
    count: int = 1
    first_seen: str
    last_seen: str
    recent_occurrences: list[PatternOccurrence] = Field(default_factory=list, max_length=5)
    threshold: int = 3
    status: Literal["observing", "rule_candidate", "graduated", "dismissed"] = "observing"
    proposed_rule: str | None = None
    graduated_to: str | None = None
    source_tier: SourceTier = "llm_derived"


class ActiveDecision(BaseModel):
    id: str
    what: str
    why: str
    evidence: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    created_at: str
    status: Literal["active", "monitoring", "superseded"] = "active"
    superseded_by: str | None = None
    source_tier: SourceTier = "human_confirmed"


class Baton(BaseModel):
    schema_version: int = 1
    session_id: str
    parent_session: str | None = None
    updated_at: str
    open_loops: list[OpenLoop] = Field(default_factory=list)
    follow_ups: list[FollowUp] = Field(default_factory=list)
    patterns: list[Pattern] = Field(default_factory=list)
    active_decisions: list[ActiveDecision] = Field(default_factory=list)
    context: str = ""


class BatonReadRequest(BaseModel):
    namespace: str = Field(min_length=1)


class BatonReadResponse(BaseModel):
    baton: dict[str, Any] | None
    namespace: str
    updated_at: str | None = None


class BatonWriteRequest(BaseModel):
    namespace: str = Field(min_length=1)
    baton: dict[str, Any]


class BatonWriteResponse(BaseModel):
    ok: bool
    updated_at: str
    namespace: str
