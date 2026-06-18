# Baton v2 Schema 規格書

> 跨 Agent 的 Session 進化機制 — 讓 AI 在與人類協作中持續進化
> Council: R1+R2 兩輪三方討論（Claude Architect + Codex Dissenter + Gemini Analyst）
> Session: 2026-06-18-baton-v2-design
> Evidence: ~/Documents/agent-council/2026-06-18-baton-v2-design/
> Status: DRAFT — 待 Maki ratify 後進入實作

---

## 1. 設計理念

Baton v1 是「session 交接棒」（open_loops + follow_ups + patterns + active_decisions）。
Baton v2 的定位升級為「**跨 Agent 的持續進化狀態**」：

- **不是 CLAUDE.md 的 JSON 版**（Codex R1 警告）
- **不是 memhall 的重複**（session_bridge 是 fast path，不是替代品）
- **是所有 Agent 共用的操作記憶**（Claude / Codex / Gemini / qwen3.6 / gemma4 / Grok）
- **取代 CLAUDE.md 中約 100-150 行的 OPERATIONAL 規則**（3-6 個月驗證期後）

### 與 v1 的差異

| | v1 | v2 |
|---|---|---|
| 定位 | session 交接棒 | 跨 Agent 進化狀態 |
| Section 數 | 4（open_loops / follow_ups / patterns / active_decisions） | 10（見 §3） |
| 寫入者 | 主要 Claude | 所有 Agent（有 tool 的直接寫，無 tool 的提交 proposal） |
| 並發保護 | LWW（last-write-wins） | revision CAS（compare-and-swap） |
| 安全 | 無特別設計 | `_security` section + credential redaction 規則 |

---

## 2. 設計約束（Council 共識）

### 硬約束（全票通過）

1. **revision CAS**：寫入必帶 `expected_revision`，不符回 409。防止 latest.md 並發覆蓋翻版
2. **fail-closed for infra_state**：stale 的 infra entry 禁止用於 deploy/SSH 決策，必須先 re-verify
3. **Credentials 不進 Baton**：token / key / secret 只能用 `$ENV_VAR_NAME` 引用，禁止 inline
4. **靜態規則 fallback 不可刪除**：Baton 是「加速劑」非「替代品」，CLAUDE.md 原則層保留
5. **時間單位統一**：全部使用 `stale_after_hours`（整數），不混用 hours/days
6. **per-section size limits**：server/write-gateway 端 enforce，防止無限膨脹

### 分層讀取模型（Codex R2 ratify）

```
啟動順序：
1. Static rules（CLAUDE.md + rules/）→ 不變原則、安全紅線、bootstrap
2. Baton（if available）→ 動態操作記憶 overlay
3. memhall（按需）→ 長期知識庫搜尋

衝突時：static safety rules > Baton > memhall
Baton 不可用時：降級到 static + memhall，明確告知 Maki
```

### 寫入權限分層（Codex R2 + Gemini R2 共識）

| Section | 有 tool 的 Agent（Claude/Codex） | 無 tool 的 Agent（qwen3.6/gemma4） |
|---|---|---|
| `infra_state` | 直接寫 | **proposal only** |
| `open_loops` | 直接寫 | **proposal only** |
| `anti_patterns` | 直接寫 | 直接寫（最差多一條錯誤 pattern） |
| `follow_ups` | 直接寫 | 直接寫 |
| `session_bridge` | 直接寫 | 直接寫 |
| 其餘 section | 直接寫 | 直接寫 |

---

## 3. JSON Schema

```json
{
  "_meta": {
    "schema_version": "2.0",
    "namespace": "home",
    "revision": 1,
    "last_written_by": "claude",
    "last_written_at": "2026-06-18T10:30:00Z"
  },

  "_security": {
    "forbidden": [
      "No actual token/key/secret values",
      "check_command and agent_cli_commands: use $ENV_VAR_NAME only"
    ]
  },

  "infra_state": {
    "machines": {
      "mini2": {
        "alias": "mini2-ts",
        "tailscale_ip": "100.89.41.50",
        "role": "memhall-primary, embed_server",
        "verified_at": "2026-06-18T08:00:00Z",
        "verified_by": "claude",
        "status": "ok",
        "stale_after_hours": 24,
        "notes": ""
      }
    },
    "services": {
      "memhall_primary": {
        "url": "http://100.89.41.50:9100",
        "verified_at": "2026-06-18T08:00:00Z",
        "verified_by": "claude",
        "status": "ok",
        "stale_after_hours": 12,
        "check_command": "curl -sf $MEMHALL_PRIMARY_URL/health"
      }
    }
  },

  "discovery_cache": {
    "entries": [
      {
        "id": "dc-001",
        "target": "mini2:memhall",
        "discovered_at": "2026-06-10T14:00:00Z",
        "discovered_by": "claude",
        "stale_after_hours": 720,
        "findings": {
          "deployment_mode": "host (not Docker)",
          "config_path": "/etc/memory-hall/config.yaml",
          "restart_command": "systemctl restart memory-hall"
        },
        "verified_still_valid": true
      }
    ]
  },

  "anti_patterns": {
    "entries": [
      {
        "id": "ap-001",
        "pattern": "assume nginx is on the host without checking",
        "category": "infra_assumption",
        "severity": "high",
        "occurrences": 3,
        "last_occurred_at": "2026-06-12T09:00:00Z",
        "last_occurred_by": "claude",
        "context": "Tried certbot on host, nginx was in Docker. Lost 20 min.",
        "remedy": "Run docker ps | grep nginx before touching nginx config.",
        "promoted_to_rule": null,
        "source_tier": "llm_derived"
      }
    ]
  },

  "open_loops": {
    "entries": [
      {
        "id": "OL-001",
        "action": "Deployed memhall v0.4.2 to mini2",
        "created_at": "2026-06-17T18:00:00Z",
        "created_by": "claude",
        "stale_after_hours": 72,
        "verify": {
          "method": "http",
          "url": "http://100.89.41.50:9100/health",
          "expected_status": 200,
          "timeout_seconds": 5
        },
        "status": "pending",
        "source_tier": "llm_derived"
      }
    ]
  },

  "follow_ups": {
    "entries": [
      {
        "id": "FU-001",
        "title": "Implement S2.1 HMAC auth for memhall write",
        "created_at": "2026-06-10T09:00:00Z",
        "created_by": "claude",
        "priority": "high",
        "postponed_count": 2,
        "last_postponed_at": "2026-06-17T20:00:00Z",
        "blocked_by": null,
        "suggested_agent": "codex",
        "status": "open",
        "source_tier": "llm_derived"
      }
    ]
  },

  "session_bridge": {
    "last_session": {
      "session_date": "2026-06-17",
      "session_id": "2026-06-17-baton-store-design",
      "summary": "Implemented baton_cache.py with local fallback",
      "completed": ["baton_cache.py verified", "fallback path documented"],
      "in_progress": ["Baton v2 schema design"],
      "next_action": "Complete v2 schema, Codex review, then implement",
      "written_by": "claude",
      "written_at": "2026-06-17T22:00:00Z"
    }
  },

  "infra": {
    "memhall": {
      "primary_url": "http://100.89.41.50:9100",
      "backup_url": "http://100.122.171.74:9100",
      "auth_type": "Bearer",
      "auth_env_var": "MH_API_TOKEN"
    },
    "mk_council": {
      "url": "http://100.122.171.74:18792"
    },
    "agent_cli_commands": {
      "codex": "codex exec --sandbox workspace-write --skip-git-repo-check < {briefing} > {answer}",
      "gemini": "gemini -p 'Execute briefing on stdin.' < {briefing} > {answer}",
      "ollama_qwen": "ollama run qwen3.6 < {briefing} > {answer}",
      "ollama_gemma4": "ollama run gemma4:31b < {briefing} > {answer}"
    }
  },

  "governance": {
    "limits": {
      "max_files_per_commit": 10,
      "max_files_per_delegation": 5,
      "max_followup_items_surface": 3,
      "_fallback_note": "Baton unavailable → use these as current values, prefer conservative"
    }
  },

  "deprecated_patterns": [
    {
      "name": "handoff/latest.md",
      "deprecated_since": "2026-05-31",
      "reason": "Concurrent overwrite between agents",
      "replacement": "memhall"
    },
    {
      "name": "mem0",
      "deprecated_since": "2026-04-18",
      "reason": "Replaced by memhall",
      "replacement": "memhall"
    }
  ]
}
```

---

## 4. Section 詳細規格

### 4.1 `_meta`

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `schema_version` | string | Y | `"2.0"` |
| `namespace` | string | Y | `"home"` / `"project:xxx"` |
| `revision` | int | Y | 單調遞增，write 時 CAS 比對 |
| `last_written_by` | string | Y | agent stable ID |
| `last_written_at` | string | Y | ISO 8601 |

### 4.2 `infra_state`

取代 `infrastructure-quick-ref.md` 的靜態表。

**status enum**: `"ok"` / `"needs_reverify"` / `"down"` / `"unknown"`

**Staleness 語義**（reader-computed，不改 JSON）：
`now - verified_at > stale_after_hours * 3600` → 視為 `needs_reverify`

**fail-closed 規則**：status 非 `ok` → deploy/SSH 前必須先執行 check_command 驗證。

**size limit**: machines max 30, services max 30

### 4.3 `discovery_cache`

取代 `discovery-phase.md` 的每次 7 步從零開始。有 cache 且 `verified_still_valid` → 跳過已探索的步驟。

**size limit**: max 50 entries

### 4.4 `anti_patterns`

取代 `no-guessing.md` 的靜態 checklist。v2 新增 `category` + `severity`。

**category enum**: `"infra_assumption"` / `"scope_creep"` / `"tool_misuse"` / `"deprecated_path"` / `"guessing"`

**severity enum**: `"high"` / `"medium"` / `"low"`

**升級路徑**（OPERATIONAL → CONSTITUTIONAL）：
1. New: entry 建立，`occurrences=1`
2. Candidate: `occurrences >= 2` OR `severity=high` → agent 在 session 開場 surface
3. Proposed: Maki 指示起草 rule
4. Promoted: 寫入 `rules/`，`promoted_to_rule` 填 file path

**size limit**: max 50 entries。`promoted_to_rule` 已填的可 archive。

### 4.5 `open_loops`

延續 v1，verify 結構不變（http / file_exists / process_running / manual）。

**status enum**: `"pending"` / `"verified"` / `"failed"` / `"stale"` / `"escalated"`

**size limit**: max 20 entries，operational target < 10

### 4.6 `follow_ups`

持久化的 scope-discipline follow-up。

**priority enum**: `"high"` / `"medium"` / `"low"`

**size limit**: max 30 entries

### 4.7 `session_bridge`

上次 session 的快速索引。每次 wrap-up 覆寫（不 append）。

**硬性 cap**:
- `summary`: ≤50 words
- `completed`: max 5 items
- `in_progress`: max 3 items
- `next_action`: 1 sentence

**定位**: memhall 的 pre-computed fast path，不是替代品。>7 天未更新時額外搜 memhall 補充。

### 4.8 `infra`

靜態基礎設施參考（memhall endpoint、CLI 指令）。取代 CLAUDE.md §5 / §6 的 URL 和 CLI 指令表。

**安全規則**: `auth_env_var` 存 env var 名稱，禁止存 token 值。

### 4.9 `governance`

Council ratified 的量化限制。靜態規則保留「有上限」原則，具體數字存這裡。

Baton 不可用時 → 偏保守（選小數字）。

### 4.10 `deprecated_patterns`

已廢棄系統/方案的警告，防止 agent 回頭走廢棄路徑。

---

## 5. Write API Contract（v1 → v2 變更）

### `POST /v1/baton/write`（v2 新增 CAS）

```
Request:
  Authorization: Bearer $MH_API_TOKEN
  Content-Type: application/json
  {
    "namespace": "home",
    "expected_revision": 12,      ← v2 新增必填
    "baton": { ...完整 JSON }
  }

Response 200:
  { "ok": true, "revision": 13, "updated_at": "..." }

Response 409 (revision mismatch):
  { "error": "revision_conflict", "current_revision": 15, "baton": { ...當前版本 } }
```

409 時 client 行為：read 當前版本 → merge 本地 change → retry write。

### `POST /v1/baton/read`（不變）

```
Request:
  { "namespace": "home" }

Response 200:
  { "baton": { ... }, "namespace": "home", "updated_at": "..." }

Response 404:
  { "error": "baton not found" }
```

---

## 6. Patch Proposal 格式（無 tool Agent 用）

qwen3.6 / gemma4 等無 tool Agent 不直接呼叫 Baton API，
而是在 answer.md 輸出 patch proposal，由有 tool 的 Agent review + apply：

```json
{
  "_patch_proposal": {
    "submitted_by": "qwen3.6",
    "submitted_at": "2026-06-18T12:00:00Z",
    "patches": [
      {
        "op": "increment",
        "path": "anti_patterns.entries[id=ap-001].occurrences",
        "by": 1
      },
      {
        "op": "append",
        "path": "follow_ups.entries",
        "value": { "id": "FU-003", "title": "...", "created_by": "qwen3.6", "..." : "..." }
      },
      {
        "op": "update",
        "path": "session_bridge.last_session",
        "value": { "..." : "..." }
      }
    ]
  }
}
```

v2.0：Claude 人工 apply。v2.1+：考慮 server-side 自動 apply。

---

## 7. Lifecycle

### 7.1 Session 開場

```
1. POST /v1/baton/read → 取得 JSON
2. 判斷可用性：200 → 繼續 / 404 → 空白開始 / 失敗 → fallback
3. 讀 session_bridge → 輸出接續 summary
4. 掃 open_loops（status=pending）→ 提醒 Maki
5. 掃 follow_ups（priority=high, postponed_count>=3）→ surface
6. 掃 infra_state → 標出 stale entries
7. 掃 anti_patterns（occurrences>=2, promoted_to_rule=null）→ 提醒
8. 輸出 summary
```

### 7.2 Session 中

操作完立即更新對應 section（不等 wrap-up）：
- SSH 驗證成功 → 更新 infra_state.verified_at
- 發現新佈局 → 新增 discovery_cache entry
- 執行 deploy → 新增 open_loop
- 踩到失誤 → 新增/更新 anti_pattern
- 發現 scope 外改善 → 新增 follow_up

### 7.3 Session 收尾

```
1. 覆寫 session_bridge.last_session
2. 確認新 open_loops / anti_patterns / follow_ups 已寫入
3. POST /v1/baton/write（帶 expected_revision）
4. 同步寫本機 cache（~/.claude/loop/batons/{namespace}.json）
5. 走 memhall 4-question gate 寫 episode（Baton 之外的獨立流程）
```

### 7.4 Fallback

```
mini2 primary → mini1 backup → 本機 cache → static rules
每層降級明確告知 Maki，不靜默跳過
```

---

## 8. v1 → v2 Migration

既有 v1 baton（schema_version: 1）在 session 開場時觸發一次性 migration：

1. 保留 `open_loops` / `follow_ups` / `patterns`（改名 → `anti_patterns`）
2. `active_decisions` 保留但不在 v2 core（可放 `governance` 或 separate）
3. 新增 `_meta`（含 revision: 1）、`_security`、`infra`、`governance`、`deprecated_patterns`、`session_bridge`、`infra_state`、`discovery_cache`
4. `context` 欄位內容移到 `session_bridge.last_session.summary`
5. v1 的 `patterns` 欄位 mapping：`what` → `pattern`、`count` → `occurrences`、`graduated_to` → `promoted_to_rule`、新增 `category` + `severity`（default `"medium"` / `"infra_assumption"`）

Migration 由 agent 在第一次 read 到 v1 baton 時自動執行，write 回 v2。

---

## 9. CLAUDE.md 精簡路徑

Baton v2 穩定運行 3-6 個月後，可精簡的靜態規則（需逐條驗證 Baton 覆蓋率）：

| 來源 | 可精簡內容 | 估計行數 | 前提 |
|---|---|---|---|
| infrastructure-quick-ref.md | IP/Port/SSH alias 靜態表 | -50 行 | infra_state 覆蓋且 fallback 可靠 |
| no-guessing.md | 具體 checklist 案例 | -30 行 | anti_patterns 累積足夠案例 |
| session-memory.md | 開場步驟細節 | -20 行 | session_bridge 證明為有效 fast path |
| CLAUDE.md §5 | CLI 指令表 | -15 行 | infra.agent_cli_commands 穩定 |
| CLAUDE.md §6 | memhall endpoint | -10 行 | infra.memhall 穩定 |
| safe-operations.md | 量化數字（保留原則） | -5 行 | governance.limits 穩定 |

**總計: 約 -130 行（450 → ~320 行）**

**不動的**（CONSTITUTIONAL，見 gemini-answer.md 完整清單）：
- §0 紅線、§7 安全、Council Presets、北極星、ACE、memhall gate、禁 git add .

---

## 10. 待 Maki 裁量

### T1：CAS 需要 memhall server 端改動
`/v1/baton/write` 目前不支援 `expected_revision`。需要改 memory-hall repo 的 storage + routes。

### T2：preferences.maki 和 doc_routing defer 到 v2.1
核心 10 section 先跑起來，Maki 偏好和 doc 映射等 Baton 證明價值後再擴。

### T3：anti_patterns 額外欄位 defer
v2.0 加 `category` + `severity`。Gemini 建議的 `trigger_conditions` / `agents_involved` / `promotion_candidate` / `review_at` defer 到 v2.1。

### T4：governance.limits 的 fallback
Baton 掛掉時 agent 不知確切數字。目前設計：靜態規則保留「有上限」原則 + `_fallback_note` 說偏保守。是否需要在靜態規則中保留具體數字作為 hard fallback？

---

## 11. 實作計畫

### Phase 1：Server 端（memory-hall repo）
- `batons` table 加 `revision INTEGER DEFAULT 1`
- `/v1/baton/write` 支援 `expected_revision` + 409 conflict
- 預估：Codex 30-40 min

### Phase 2：Client 端（session-baton repo）
- `models.py` 升級為 v2 schema（Pydantic models）
- `storage.py` / `server.py` 支援 CAS
- `cache.py` 支援 write-through + dirty sync
- 預估：Codex 40-60 min

### Phase 3：Skill 整合
- `/start` skill：讀 v2 Baton 開場流程
- `/wrap-up` skill：寫 v2 Baton 收尾流程
- 預估：Claude 20-30 min

### Phase 4：Dogfood
- 跑 3-5 個 session 驗證完整 lifecycle
- 確認 anti_patterns 累積行為
- 確認 infra_state fail-closed 正常運作
