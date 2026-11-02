# Attachment context (Designer chat)

When the user **pastes a screenshot** to explain a layout/preview bug, the file is still stored as a normal `DesignerMediaAsset`. Without explicit intent, Muse metadata and agent prompts treat it as **proposal gallery/hero media** — the model embeds `pasted-screenshot-*.png` in cards or `<img>` tags.

## Roles (set in `attachment_context.py`)

| Role | When | Agent must |
|------|------|------------|
| `layout_reference` | Filename `pasted-screenshot-*`, or message describes preview/layout/issue | Use only to **locate and fix HTML/CSS** — **never** `<img src="…">` in the proposal |
| `floorplan` | User asks for map/floorplan + image | Use for `.venue-map-proposal` / map section only |
| `proposal_media` | Brand photos, property shots, explicit “use this image in the proposal” | May embed with absolute URL |

## Context “rotting” (where instructions disappear)

1. **`_build_context_prefix`** used to join map + attachments + audit + rules, then **`trim_context_block` (4k)** on the **whole** string — attachment and audit text dropped first when map/audit are large.
2. **`truncate_history_turn_for_tool_loop` (900 chars)** — older user turns lose detail; only `[Attachments: name]` survives in saved history, not role hints.
3. **`condense_tool_loop_messages`** — after 10 tool pairs or 72k chars, early steps become one-line summaries; screenshot intent from turn 1 is gone unless restated.
4. **Default user text** `(attachments only)` → backend substitutes *“Use the attached media in the proposal design.”*
5. **`format_assets_for_agent`** — all files say “embed using absolute URLs” + Muse `suggested_placement=gallery`.
6. **`floorplan_urls`** — every `[IMAGE]` attachment URL was passed to map knowledge, nudging map/floorplan embedding.

## Editing behavior

- Update **`guidance/attachment_context.md`** for model-facing rules.
- Adjust heuristics in **`attachment_context.py`** (filename + message phrases).
- Tune limits in **`context_budget.py`** / `DESIGNER_MAX_*` settings.

After MD/code changes, restart Django to clear guidance cache.
