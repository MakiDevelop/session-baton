# Baton Store 實作規格書 v1.0

> Session-Level Loop Engineering 的跨 session 狀態交棒系統
> Council ratified: 2026-06-17, DEC-BATON-001~004
> ACA compliant: L1 Memory / L2 Trust / Anti-Ouroboros / L5 Decision

---

## 1. 系統定位

```
memhall (mini2:9100)
├── /v1/memory/*     ← 既有：模糊搜尋知識（Warm tier）
├── /v1/baton/read   ← 新增：精確讀取 baton state（Hot tier）
└── /v1/baton/write  ← 新增：atomic upsert baton state（Hot tier）
```

Baton ≠ Memory。Baton 是「進行中的交接棒」，Memory 是「已結案的知識庫」。
同一個 process、同一個 SQLite（WAL mode）、不同 table、不同 endpoint。

---

## 2. SQLite Schema

```sql
-- 在 _create_schema() 裡加（alongside entries table）
CREATE TABLE IF NOT EXISTS batons (
    namespace TEXT PRIMARY KEY,        -- "claude-home" / "claude-work"（每 ns 一筆）
    updated_at TEXT NOT NULL,          -- ISO 8601
    data TEXT NOT NULL                 -- JSON string, 完整 baton object
);
```

**設計決策（Risk Review #1 修正）**：
- 每個 namespace 只有一筆 baton → namespace 本身就是 PK，不需要額外 id
- 移除 version 欄位（Risk Review #2）：MVP 接受 LWW，Phase 1 補 optimistic lock
- **不做 FTS**：baton 是精確讀寫，不需要全文搜尋

---

## 3. Baton JSON Schema（存在 `data` 欄位裡）

```json
{
  "schema_version": 1,
  "session_id": "2026-06-17-003",
  "parent_session": "2026-06-17-002",
  "updated_at": "2026-06-17T18:30:00+08:00",

  "open_loops": [
    {
      "id": "OL-007",
      "action": "部署 dx-chatbot 到 chiba.tw",
      "expected_outcome": "service responds 200 on /health",
      "verify": {
        "method": "http",
        "url": "https://dx.chiba.tw/health",
        "expected_status": 200,
        "timeout_seconds": 5
      },
      "created_at": "2026-06-17",
      "ttl_days": 7,
      "decision_ref": "DEC-021",
      "status": "open",
      "source_tier": "llm_derived"
    }
  ],

  "follow_ups": [
    {
      "id": "FU-012",
      "item": "重構 mk-brain weight formula",
      "reason": "目前公式對新書籤過度偏好",
      "first_seen": "2026-06-10",
      "defer_count": 5,
      "last_deferred": "2026-06-17",
      "priority": "escalated",
      "linked_pattern": "PAT-003",
      "source_tier": "llm_derived"
    }
  ],

  "patterns": [
    {
      "id": "PAT-005",
      "what": "沒讀 docker-compose.yml 就假設架構",
      "count": 3,
      "first_seen": "2026-06-12",
      "last_seen": "2026-06-17",
      "recent_occurrences": [
        {"session": "2026-06-17", "context": "以為用 alpine image，其實是 debian"}
      ],
      "threshold": 3,
      "status": "rule_candidate",
      "proposed_rule": "部署前必須 cat docker-compose.yml",
      "graduated_to": null,
      "source_tier": "llm_derived"
    }
  ],

  "active_decisions": [
    {
      "id": "DEC-021",
      "what": "Cloud Run 部署一律用 --update-env-vars",
      "why": "--set-env-vars 會清掉既有變數",
      "evidence": ["2026-06-12 incident", "GCP 文件確認"],
      "rejected": ["--set-env-vars", "手動 env backup script"],
      "created_at": "2026-06-15",
      "status": "active",
      "superseded_by": null,
      "source_tier": "human_confirmed"
    }
  ],

  "context": "本週重心在 Home AI Center 穩定性。"
}
```

### ACA 合規欄位

| 欄位 | ACA 層 | 說明 |
|---|---|---|
| `source_tier` | L1 Memory + L2 Trust | `raw_source` / `llm_derived` / `human_confirmed` |
| `namespace` | L2 Trust | 繼承 memhall namespace 隔離規則 |
| `status: rule_candidate → graduated` | Anti-Ouroboros | graduation 需要 `source_tier` 從 `llm_derived` 升級為 `human_confirmed`（= Maki 批准） |
| `active_decisions.status` | L5 Decision | `active` → `monitoring` → `superseded`，對齊 ACA decision lifecycle |

### Anti-Ouroboros Gate（硬約束）

```
pattern.status == "rule_candidate"
  AND pattern.source_tier == "llm_derived"
  → 禁止自動 graduate
  → 必須 Maki 在 ORIENT 階段批准
  → 批准後 source_tier 改為 "human_confirmed"
  → 才能寫入 rules/ + pattern.graduated_to = "rules/xxx.md"
```

### Patterns 增長 Cap

- `recent_occurrences`: 最多 5 筆（FIFO）
- `count`: 持續累加（不 cap）
- 超過 5 筆時，最舊的自動移除，count 繼續計

### Verify 結構（取代 bash command）

```json
{
  "method": "http",          // http | file_exists | process_running | manual
  "url": "https://...",      // method=http 時
  "expected_status": 200,    // method=http 時
  "path": "/tmp/flag",       // method=file_exists 時
  "process_name": "memhall", // method=process_running 時
  "timeout_seconds": 5,
  "note": "手動確認 X"       // method=manual 時
}
```

**禁止 bash command**。所有 verify 走 structured method。

### ID Convention

| Type | Format | Auto-increment |
|---|---|---|
| Open Loop | OL-NNN | 掃 baton 內 max ID + 1 |
| Follow-up | FU-NNN | 同上 |
| Pattern | PAT-NNN | 同上 |
| Decision | DEC-NNN | 沿用既有 DEC 編號系統 |

---

## 4. API Endpoints

### `POST /v1/baton/read`

```
Request:
  Authorization: Bearer $MH_API_TOKEN
  Content-Type: application/json
  { "namespace": "claude-home" }

Response 200:
  { "baton": { ...完整 baton JSON }, "version": 1 }

Response 404:
  { "error": "baton not found", "namespace": "claude-home" }
```

### `POST /v1/baton/write`

```
Request:
  Authorization: Bearer $MH_API_TOKEN
  Content-Type: application/json
  {
    "namespace": "claude-home",
    "baton": { ...完整 baton JSON }
  }

Response 200:
  { "ok": true, "updated_at": "2026-06-17T18:30:00+08:00", "version": 2 }
```

Atomic upsert：`INSERT INTO batons ... ON CONFLICT(id) DO UPDATE SET ...`
Transaction：`BEGIN IMMEDIATE` 防 concurrent write（WAL 下只允許 1 writer）。

---

## 4.5 Edge Case 處理（Maki Review 補強）

### A. /start baton read 失敗時的行為

```
BOOT 時讀 baton：
  ├─ 200 OK → 正常顯示 ORIENT summary
  ├─ 404 Not Found → 第一次使用，顯示「尚無 baton，本 session 結束時將建立第一份」
  ├─ Network Error（mini2 不可達）→ 讀本機 cache
  │   ├─ Cache 存在 → 顯示「⚠️ 離線模式：baton 來自本機 cache（{updated_at}）」
  │   └─ Cache 也不存在 → 顯示「⚠️ memhall 不可達且無本機 cache，本 session 無 baton 狀態」
  └─ 任何情況都不阻擋 session 開始（baton 是增強，不是 prerequisite）
```

### B. Local Cache Fallback 邏輯（gemma4 建議 + Maki 補強）

```
位置：~/.claude/loop/batons/{namespace}.json

Write-through（正常狀態）：
  1. POST /v1/baton/write 成功
  2. 同步寫一份到 local cache（同內容）
  3. 兩邊永遠一致

Read fallback（memhall down）：
  1. POST /v1/baton/read 失敗（timeout / connection refused）
  2. 讀 local cache
  3. 顯示 ⚠️ 離線標記

離線寫入（memhall down 時的 /wrap-up）：
  1. 嘗試 POST /v1/baton/write → 失敗
  2. 寫入 local cache（保證本次進度不丟）
  3. 標記 local cache 為 dirty（加 "sync_status": "pending_upload"）
  4. 下次 /start 時如果 memhall 恢復 → 自動推送 dirty cache 到 remote
  5. 顯示「⚠️ 上次 session 的 baton 為離線寫入，已同步到 memhall」
```

**衝突處理**：dirty cache 推送時，如果 remote 的 `updated_at` 比 cache 新（代表另一台機器有寫過），顯示 warning 讓 Maki 決定保留哪份。MVP 不自動 merge。

### C. CAS Check 預留（Phase 1 補）

MVP 的 write 是 LWW（last-write-wins）。Phase 1 補：

```json
// write request 加 optional 欄位
{
  "namespace": "claude-home",
  "expected_updated_at": "2026-06-17T18:30:00+08:00",  // optional
  "baton": { ... }
}
```

Server side：如果 `expected_updated_at` 存在且不等於 DB 裡的 `updated_at` → 回 409 Conflict + 當前 baton 內容。Client 決定 merge 或 force write。

---

## 5. 改動檔案清單

| 檔案 | 改什麼 | 行數估計 |
|---|---|---|
| `src/memory_hall/storage/sqlite_store.py` | `_create_schema()` 加 batons table + `baton_read()` / `baton_write()` 兩個方法 | ~60 行 |
| `src/memory_hall/server/app.py` | 加 `/v1/baton/read` + `/v1/baton/write` 兩個 route | ~50 行 |
| `src/memory_hall/models.py` | 加 `BatonReadRequest` / `BatonWriteRequest` / `BatonResponse` Pydantic models | ~30 行 |
| `~/.claude/skills/start/SKILL.md` | Step 0.5：BOOT 讀 baton + 顯示 open items | ~30 行 |
| `~/.claude/skills/wrap-up/SKILL.md` | 新增 Step：PERSIST 收集 + 寫 baton | ~40 行 |
| `~/.claude/loop/batons/` | 本機 cache 目錄（write-through） | mkdir |

**總計 ~210 行新 code + ~70 行 skill 修改。**

---

## 6. 實作分工（全員動員）

| 成員 | 任務 | 產出 | 預估時間 |
|---|---|---|---|
| **Codex** | 寫 memhall 三個檔案（models + storage + routes） | PR-ready Python code | 30-40 min |
| **Claude** | 寫 /start 和 /wrap-up skill 修改 + local cache 邏輯 | Skill 改動 | 20-30 min |
| **Gemini** | Review Codex 產出的 ACA 合規性（source_tier / Anti-Ouroboros gate） | Review report | 10 min |
| **Grok** | 寫端到端測試腳本（curl 測 read/write + 跨 session 驗證） | test.sh | 15 min |
| **gemma4** | 寫 local cache fallback 的 Python snippet | cache.py | 10 min |

### 依賴順序

```
Phase 1（平行）: Codex 寫 code + gemma4 寫 cache + Grok 寫 test
Phase 2（序列）: Claude 整合 + Gemini review
Phase 3（序列）: 部署到 mini2 + 跑 Grok 的 test
Phase 4（序列）: 改 skill + dogfooding
```

---

## 7. 部署計畫

1. 在 MBP 開發 + 本機測試
2. `git commit` 到 memory-hall repo
3. SSH 到 mini2，`git pull` + 重啟 memhall service
4. `curl` 驗證 `/v1/baton/read` + `/v1/baton/write`
5. 改 /start + /wrap-up skill
6. 開新 session 測試完整 loop

---

## 8. Rollback Plan

- 刪 batons table：`DROP TABLE IF EXISTS batons;`
- 移除 baton routes：git revert
- /start + /wrap-up skill：git revert
- 風險等級：**YELLOW（可逆）**

---

## 9. Success Criteria

MVP 成功 = 以下全部通過：

1. ✅ `curl POST /v1/baton/write` 寫入一筆 baton（帶 open_loop + follow_up）
2. ✅ `curl POST /v1/baton/read` 讀回完整 baton，內容一致
3. ✅ 寫入第二次（update），讀回是新版本
4. ✅ /start 時顯示 baton 的 open items
5. ✅ /wrap-up 時收集並寫入 baton
6. ✅ 新開一個 session，/start 能讀到上一個 session 寫的 baton
7. ✅ 每個 item 都帶 `source_tier` 欄位
8. ✅ patterns 的 `recent_occurrences` 不超過 5 筆
