# Designing Studio — Muse Spark 1.3 (backend contract)

Designers never manage RFP binding tokens in the UI. **Muse Spark 1.3** (via `META_MODEL_SPARK`) is instructed server-side to emit HTML/CSS/JS that includes all required proposal bindings and passes validation before save.

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
