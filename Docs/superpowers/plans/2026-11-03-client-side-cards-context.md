# Client Side Cards & Session Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: executing-plans / subagent-driven-development. **Stateful work:** checkmate-logic execution paths below.

**Goal:** Polish client RFP side cards with live save, theme-aware UI, and designer-parity session memory so the voice assistant always sees card edits and clarifications.

**Architecture:** Single mutation path (`validate_card_mutation`) appends to `client_session_json`, broadcasts `cards_patch`, `agent_utterance`, and `client_session_patch`. Voice assistant injects a compact memory block. Frontend debounces WS submits.

**Tech Stack:** Django, Channels WS, React, Framer Motion, Tailwind.

## Execution paths (Checkmate)

| Operation | Happy | Edge | Worst |
|-----------|-------|------|-------|
| `card_mutation_submit` | validate → save → broadcast | validation error → `validation_error` WS | exception → `validation_error`, DB unchanged |
| Debounced UI save | merge patch, skip if unchanged | empty patch no-op | WS closed → local error state |
| Session append | cap events at 40 | duplicate hash skip noisy log | corrupt JSON → reset to `{}` |

## Tasks

- [x] Phase 1: Backend ack + consumer error handling + frontend deck + CSS + debounced WS
- [x] Phase 2: `client_session_json` model + memory module + voice context injection + tests
- [x] Phase 3: Clarifications/todos sync + UI surfaces + snapshot/WS patch
- [x] Phase 2b: Transcript + assistant reply persistence + `client_agent_context.py`
- [x] Phase 3b: Timeline UI, catering/AV card, inline validation errors, clarification focus

**Status:** Complete (2026-11-03). Backend: 19 related tests passing. Frontend: `npm run build` passing.
