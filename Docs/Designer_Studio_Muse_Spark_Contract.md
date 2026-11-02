# Designing Studio — Muse Spark 1.3 (backend contract)

Designers never manage RFP binding tokens in the UI. **Muse Spark 1.3** (via `META_MODEL_SPARK`) is instructed server-side to emit HTML/CSS/JS that includes all required proposal bindings and passes validation before save.

## Muse structured output (Meta Model API)

All JSON Muse calls use Chat Completions **structured output** (`response_format.type = json_schema`).

| Module | `fixture_kind` | Schema name |
|--------|----------------|-------------|
| Tool loop | `designer_tool_loop` / `_repair` | `DesignerToolLoopStep` |
| Execution plan | `designer_execution_plan` | `DesignerExecutionPlan` |
| Work plan labels | `designer_work_plan` | `DesignerWorkPlanLabels` |
| Full-document chat | `designer_chat` | `DesignerChatTemplate` |
| Validate / save | `designer_validate`, `designer_save_validate` | `DesignerValidationResult` |
| Agent rules | `designer_rule_validate` | `DesignerRuleConflict` |
| Media upload | `designer_asset_meta` | `DesignerAssetMeta` |
| Map studio | `map_chat`, `map_validate` | `MapInteractiveResponse`, `MapValidationResult` |
| RFP debate | `rfp_extraction`, `rfp_critique` | `RfpExtractionPayload`, `RfpCritiqueResult` |
| Voice assistant | `voice_reply` | `VoiceAssistantReply` |

Schemas: `backend/apps/rfp_debate/muse_structured_schemas.py`  
Post-decode validation (Checkmate terminal states): `backend/apps/rfp_debate/muse_completion.py`  
Client: `MetaModelClient` — HTTP errors, JSON parse, and validation failures log with explicit codes; designer tool loop uses `allow_fixture_fallback=False`.

Docs: [Structured output](https://dev.meta.ai/docs/structured-output)

## What the frontend sends

| Endpoint | Purpose | Body (key fields) |
|----------|---------|-------------------|
| `POST /api/designer/chat/` | Design turn | `message`, `chat_history_json`, `html_markup`, `css_stylesheet`, `js_script`, `attachment_ids[]` |
| `POST /api/designer/validate/` | Pre-save check | Same markup fields as template |
| `POST /api/designer/templates/` | Create | `name`, markup fields, `chat_history_json` |
| `PATCH /api/designer/templates/:id/` | Update | Same |
| `POST /api/designer/assets/upload/` | Media | `file`, optional `template_id` |

The frontend **does not** send placeholder lists or Muse model IDs. Attachments are uploaded first; IDs and URLs are included in the chat payload so Spark can embed media.

## What the backend returns (chat)

```json
{
  "assistant_message": "string",
  "html_markup": "string",
  "css_stylesheet": "string",
  "js_script": "string",
  "clarification_options": ["optional quick replies"],
  "chat_history_json": [],
  "used_fixture": false
}
```

Spark system instructions (in `design_agent.py`) require:

- JSON-only responses with the keys above
- Every mandatory RFP binding token present exactly once in `html_markup` (list maintained in `REQUIRED_PLACEHOLDERS` on the server)
- Interactivity in `js_script` (no unsafe inline handlers)
- Uploaded asset URLs embedded when provided
- Clarification options when the request is ambiguous

## Save path

1. Deterministic checks (`deterministic_template_checks`) — placeholder presence, basic safety
2. Spark validation pass (`VALIDATION_SYSTEM_PROMPT`) — layout, CTA visibility, JS safety
3. On failure: HTTP 400 with human-readable `detail` (no need to expose raw token list in the studio chrome)

## Frontend responsibilities

- Chat, preview, media upload, template library, save/export
- Surface validation/save errors from API messages
- **Do not** display binding token cheat-sheets or model badges; the agent owns schema compliance
