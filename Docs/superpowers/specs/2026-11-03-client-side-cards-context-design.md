# Client side cards & session context

Spec for phased delivery (2026-11-03). Plan: `docs/superpowers/plans/2026-11-03-client-side-cards-context.md`.

## Delivered (all phases)

### Phase 1 — UI + live save
- Themed `AgentCardDeck` with motion, editable fields, save indicator.
- Debounced WebSocket `card_mutation_submit`.
- `agent_utterance` after successful card mutation.
- WS validation errors surfaced on deck (`cardValidationError` banner).
- Consumer catches validation and generic errors.

### Phase 2 — Session memory
- `RFPSubmission.client_session_json` + migration `0002`.
- `client_session_memory.py`: events, card summary, voice context block.
- `client_agent_context.py`: `read_cards_snapshot`, `format_cards_for_prompt`.
- Voice assistant injects memory into Muse user content; records user + **assistant** turns.
- **Transcript** (30 turns) in session JSON included in agent context block.

### Phase 3 — Clarifications & UX
- `sync_clarifications_from_cards` → todos + clarification chips (two-pass done marking).
- Deck “Needs your input” panel; chips focus relevant fields.
- `client_session_patch` on pipeline, mutations, snapshot load.
- **ClientSessionTimeline** (events + transcript).
- **Catering & AV** editable card section.
- `card_normalize` syncs clarifications after sparse extraction.

## Execution paths (Checkmate)

See plan file for card mutation happy/edge/worst branches; consumer catches `CardMutationValidationError` and generic `Exception`.

## Verification

```bash
cd backend && python -m pytest tests/test_client_session_memory.py tests/test_voice_*.py -q
cd frontend && npm run build
python manage.py migrate rfp_debate  # if not applied
```
