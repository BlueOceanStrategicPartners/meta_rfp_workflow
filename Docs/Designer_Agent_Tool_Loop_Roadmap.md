# Designer Agent — Tool-Loop Architecture Roadmap

> **Goal:** Replace “regenerate full HTML/CSS/JS every turn” with a **Harness-style tool loop**: locate issues, patch only relevant spans/lines, validate, repeat until done.

**Status:** Phases 1–5 implemented (tool loop default, repair loop, SSE tool UX, legacy full-document gated).

---

## Problem statement (current architecture)

| Issue | Where it hurts |
|--------|----------------|
| **Full-document regen** | Legacy `full_document` mode in `design_agent.py` (gated behind `DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT`). |
| **Context truncation** | `context_budget.trim_template_fields` still applies to legacy mode only. |
| **Slow, brittle edits** | Mitigated by `tool_loop` + scoped tools. |
| **Repair loop doubles cost** | **Fixed:** `_repair_turn` uses `DesignerToolLoopRunner.run_repair` in tool mode. |
| **No “grip” on structure** | **Fixed:** symbol index + hybrid `search_template` + `read_template_symbol`. |
| **False progress UX** | **Fixed:** SSE `tool` events + sub-step list in `DesignerAgentProgress`. |

---

## Target architecture

```text
User message + attachments + rules
        │
        ▼
┌───────────────────────────────┐
│  TemplateWorkspace (3 files)   │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│  Tool loop (edit phase)        │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│  Self-check + tool repair loop │
└───────────────────────────────┘
        │
        ▼
Frontend: html/css/js + work_plan + tool_trace + live tool steps
```

---

## Execution paths (Checkmate)

| Operation | Happy path | Edge | Failure / terminal |
|-----------|------------|------|---------------------|
| **LangGraph `planner_agent`** | One-shot Muse plan → `PLAN_READY` → executor | Muse schema error → `PLAN_FALLBACK` (heuristic todos) | Empty plan → `plan_abort` node (`PLAN_FAILED`) |
| **LangGraph `executor_agent`** | Tool loop finishes | Turn budget exhausted | `EXECUTOR_PARTIAL` / `EXECUTOR_FAILED` (`model_api_error`) |
| **LangGraph checkpoints** | One `thread_id` per template (`ProposalTemplate.langgraph_thread_id` or `designer-{user}-{template}`); SQLite checkpointer stores `executor_session` (tool trace digest, edit ledger) between turns; in-loop condense keeps more recent tool pairs when checkpoint thread is active (`DESIGNER_TOOL_LOOP_CHECKPOINT_KEEP_RECENT_PAIRS`, default 14) | `DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND=memory` in tests; disable per-template threads with `DESIGNER_LANGGRAPH_THREAD_PER_TEMPLATE=false` | Missing `thread_id` → LangGraph error; use `resolve_template_langgraph_thread_id` |
| `read_template_lines` | Returns numbered slice | Out-of-range → tool error JSON | Agent retries with overview |
| `replace_exact` | 1..N replacements | 0 matches / ambiguous | Tool error; agent searches first |
| `replace_lines` | Lines replaced | Invalid range | Tool error |
| `validate_template` | `ok: true` | Issues listed | Repair loop or `validation_warnings` |
| Edit tool loop budget | `kind: finish` | Max steps | Partial completion message + **Continue** chips (`tool_loop_exhausted`, `remaining_items`) |
| Tool loop context | Recent pairs full detail | Long sessions | `condense_tool_loop_messages` summarizes older steps |
| User says Continue | Bonus steps added | — | `DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_STEPS` |
| Repair tool loop | Issues fixed | Max repair steps | Remaining issues in `self_check` |
| Legacy `full_document` | Allowed if flag set | Flag off | Forced `tool_loop` + log warning |
| SSE `tool` event | UI appends step | Malformed event | Ignored (stream parser) |

---

## Implementation phases

### Phase 1 — Workspace & tools ✅

- `template_workspace.py`, `template_agent_tools.py`, `test_template_agent_tools.py`

### Phase 2 — Tool-loop agent + integration ✅

- `design_agent_tool_loop.py`, `DESIGNER_AGENT_MODE`, dispatch in `design_agent.py`

### Phase 3 — Targeted repair loop ✅

- `template_repair_hints.py` — issue → search hints
- `run_repair()` + `_repair_turn` tool path
- `DESIGNER_TOOL_LOOP_REPAIR_MAX_STEPS` (default 12)
- Save-path repair uses same `_repair_turn`

### Phase 4 — UX & observability ✅

- SSE event `tool` from `designer_chat_service.py`
- `DesignerAgentProgress` tool sub-steps
- API `tool_trace`, `tool_steps`, `agent_mode` on chat `done`

### Phase 5 — Deprecate full-document mode ✅

- `DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=false` (default) blocks `full_document`
- Opt-in: set `DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=true` + `DESIGNER_AGENT_MODE=full_document`
- Deprecation logged; removal tracked for a future release

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `DESIGNER_AGENT_MODE` | `tool_loop` | Requested mode (`full_document` needs legacy flag) |
| `DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT` | `false` | Opt-in legacy whole-file JSON |
| `DESIGNER_TOOL_LOOP_MAX_STEPS` | `24` | Edit loop cap |
| `DESIGNER_TOOL_LOOP_REPAIR_MAX_STEPS` | `12` | Repair loop cap |
| `DESIGNER_TOOL_LOOP_MESSAGE_BUDGET_CHARS` | `48000` | Condense when context exceeds budget |
| `DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_STEPS` | `12` | Extra steps when user says Continue |

---

## Verification checklist

- [x] `pytest tests/test_template_agent_tools.py tests/test_design_agent_tool_loop.py tests/test_designer_studio.py`
- [x] Tool repair pass (`run_repair`, self-check integration)
- [x] Legacy mode blocked without flag
- [x] SSE tool events wired to UI
- [x] Map stage + chat orchestration unchanged (`designer_chat_service.py`)

---

## Key files

| File | Role |
|------|------|
| `template_repair_hints.py` | Repair brief + search hints |
| `design_agent_tool_loop.py` | Edit + repair loops, tool events |
| `design_agent.py` | Mode resolution, repair dispatch, trace merge |
| `designer_chat_service.py` | SSE `tool` events |
| `DesignerAgentProgress.tsx` | Tool sub-step UI |
| `designerChatStream.ts` | `onTool` handler |
