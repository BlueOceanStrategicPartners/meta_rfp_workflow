# Admin Command Center: Development Plan

**Branch:** `develop/admin-panel` · **Base:** `main` @ `f7ad9da` · **Written:** 2026-11-03 · **Updated:** 2026-11-03 (Module 1 Map Studio dropped)
**Time box:** 60 minutes of implementation and testing
**Spec sources:**
- `Docs/Multi_Agent_Rfp_Engine_Development_Plan_2466.md`: §6.2 (the 7 admin modules), §7.2 (data model) and §9 (failure paths).
- UI rules: `Docs/Designer_Studio_UI_UX_Audit.md` and the `studio-*` component classes in `frontend/src/index.css`.

---

## 0. How to use this plan

- **Two tracks run in parallel.** Track B is the backend and Track F is the frontend. They agree on one contract, the API in §6, which is frozen before any code is written. Each track can then build and test without waiting on the other.
- **Priorities.** Every task is tagged **P0**, **P1** or **P2**:
  - **P0:** must ship within the hour.
  - **P1:** do it if you're ahead of the timeline.
  - **P2:** after the hackathon.
- **When you fall behind,** cut work in the order given in §13. Don't trade away P0 tests for P1 features.
- **Tests come first.** Write a failing test for each P0 backend behaviour before writing the view. §11 lists the exact tests.

---

## 1. Goal and scope

**Goal.** Build a working, role-protected Admin Command Center at `/admin/*`. An admin should be able to sign in and run the hotel's side of the RFP engine:
- see live RFP activity;
- inspect and override the 3-agent debate;
- set pricing policy;
- take over a negotiation;
- manage inventory and occupancy data;
- read SLA telemetry.

### In scope for the hour (P0)

| # | Module (spec §6.2) | P0 deliverable |
|---|---|---|
| — | Foundation | Admin sign-in, route guard, nested routing, layout, permission matrix test, audit log |
| — | Overview | KPI dashboard (landing page of `/admin`) |
| 2 | Live 3-Agent Debate Observatory | RFP list → debate detail (source, rounds, flags, extracted fields) → field override |
| 3 | Dynamic Pricing & XGBoost Studio | Editable pricing policy, model status, retrain, quote history. **Fixes both pricing bugs.** |
| 4 | Negotiation & Concession Playbook Monitor | Active negotiations, **human takeover** / hand back, operator message spoken in the client's orb |
| 5 | Venue, Room & Conference Inventory CMS | Create/edit/delete properties and spaces, capacity editor, release booking |
| 6 | Historical Occupancy & Dual-DB Sync Hub | CSV upload with a validation report, data table, database summary |
| 7 | 2-Minute SLA, Conversion & Token Telemetry | SLA p50/p95, within-120s rate, status funnel, debate and pricing stats |

### Out of scope for the hour

| Item | Priority | Reason |
|---|---|---|
| Module 1, AI Venue Map Studio | Dropped | Removed from the project on 3 Nov (decision by Sasidu). No admin page, route or menu item. |
| Live WebSocket push to the admin UI | P1 | P0 uses 10-second polling. The consumer role check is still P0. |
| Negotiation transcript (client turns) | P1 | This is a small hook in the voice-chat views, logged into the same audit table. |
| Token usage per Muse call | P1 | It touches `meta_client.py`, which the Designer Studio shares. |
| XLSX import | P1 | `openpyxl` isn't installed. P0 imports CSV. |
| Real SHAP waterfall | P2 | It needs a correctly trained model first. |
| Concession playbook editor | P2 | It needs negotiation logic that doesn't exist yet. |

---

## 2. Starting point (verified in the code on 3 Nov)

- **Backend.** `backend/apps/admin_command_center/` has 6 thin endpoints, all `IsAdminRole`:
  - `modules/`, `debate-observatory/`, `sla/`, `negotiations/`, `occupancy/ingest/`, `debate/<uuid>/override/`
  - `ws/admin/telemetry/` exists, but nothing sends to it and it doesn't check roles.
- **Frontend.** `frontend/src/pages/AdminPortal.tsx` is 34 lines: 7 static tiles and a JSON dump. Its fetch doesn't send the Bearer token. `App.tsx` routes `/admin` with `end`, so nested routes won't light up the nav.
- **Auth.** `POST /api/auth/login/` returns a session plus a JWT. `apiFetch` (`frontend/src/lib/apiClient.ts`) adds the Bearer token and CSRF header and refreshes on a 401. **No ADMIN account is seeded.** `AppShellContext.designerAuthed` is already `true` for ADMIN, because `isStudioRole` includes ADMIN.
- **Gaps that block admin features:**
  - `sla_completed_at` is never written.
  - `RFPStatus.ESCALATED` is never set.
  - The pricing guardrails can only be set through environment variables.
  - **Pricing bug A.** The fallback engine puts the floor above the target (`floor = base × 1.12`, `target = base × 1.10`).
  - **Pricing bug B.** Retraining uses RevPAR in currency units as the label, then treats the prediction as a multiplier, so prices come out about 150× too high.

---

## 3. Ownership and conflict rules

| Area | Owner | Rule on this branch |
|---|---|---|
| `backend/apps/admin_command_center/**`, `frontend/src/pages/admin/**`, `frontend/src/components/admin/**`, `frontend/src/lib/admin*.ts`, `frontend/src/hooks/useAdmin*.ts`, `backend/tests/test_admin_*.py` | Admin (you) | Free to change |
| `backend/apps/dynamic_pricing/**`, `backend/apps/inventory/**` | Shared | Additive changes only; existing tests must still pass |
| `backend/apps/rfp_debate/tasks.py`, `backend/apps/negotiation_agent/views.py`, `backend/apps/accounts_rbac/demo_accounts.py`, `frontend/src/App.tsx`, `frontend/src/pages/AdminPortal.tsx` | Shared | Minimal, surgical edits, each listed in §8 |
| `backend/apps/designer_studio/**`, `frontend/src/components/designer/**`, `DesignerPortal.tsx`, `useStudioPortalAuth.ts`, `AppShellContext.tsx`, `index.css` | Designer (Sasidu) | **Import only, never edit.** Reuse classes and components as they are |

---

## 4. Authentication and authorization

### 4.1 Accounts

- **P0 demo admin.** Add `admin@demo.local` / `admin12345` with role `ADMIN`. Do it in `accounts_rbac/demo_accounts.py` by mirroring the designer helper:
  - Add `ADMIN_DEMO_EMAIL`, `ADMIN_DEMO_PASSWORD` and `ensure_admin_demo_user(reset_password=False)`.
  - In `try_resolve_studio_login`, under DEBUG only, auto-provision the admin account exactly as it does for the designer.
- **Seeding.** `seed_demo` also calls `ensure_admin_demo_user(reset_password=True)`.
- **Production.** Admins are created through Django admin (`/admin/` on :8000, where `role` can be edited) or with `manage.py shell`. Never in code.

### 4.2 Backend authorization

- **Default deny.** Every view in `admin_command_center` uses `permission_classes = [IsAdminRole]`. There are no per-view exceptions and no `permission_classes = []`.
- **Pricing admin endpoints** (`/api/pricing/admin/*`) keep `IsAdminRole`.
- **WebSocket (P0).** In `AdminTelemetryConsumer.connect`, close with code `4403` unless `self.scope["user"].is_authenticated and user.role == "ADMIN"`. WebSockets authenticate through the Django session cookie, which `/api/auth/login/` sets alongside the JWT, using `AuthMiddlewareStack`.
- **Audit (P0).** Every admin action that changes data writes an `AdminAuditEvent` row (§5.1).

### 4.3 Permission matrix (enforced by `test_admin_permissions.py`)

| Endpoint group | Anonymous | CLIENT | DESIGNER | ADMIN |
|---|---|---|---|---|
| `/api/admin-center/**` | 401 | 403 | 403 | ✔ |
| `/api/pricing/admin/**` | 401 | 403 | 403 | ✔ |
| `ws/admin/telemetry/` | closed 4403 | closed 4403 | closed 4403 | ✔ |
| `/api/designer/**` | 401 | 403 | ✔ | 403 (unchanged) |

### 4.4 Frontend auth flow

```
/admin/*  →  useAdminAuth()
             ├─ bootstrapping        → <StudioPortalBootSplash title="Admin Command Center" />
             ├─ not signed in        → <StudioPortalLogin title="Admin Command Center"
             │                             subtitle="Sign in with your admin account" … />
             ├─ signed in, not ADMIN → same login, error: "Signed in as {role}. Sign in with an admin account."
             └─ ADMIN                → <AdminLayout> + nested routes
```

- **`useAdminAuth`** (new file `frontend/src/hooks/useAdminAuth.ts`). It calls `authMe()` from `lib/designerApi.ts`. `authed` is `me.authenticated && me.role === "ADMIN"`. It exposes `{ authed, bootstrapping, role, signIn(email, password), signOut() }`.
- **`signIn`** calls the shared login, `loginDesigner()`, which is a generic `/api/auth/login/` call that stores the tokens. It then confirms the role through `authMe()`.
- **API calls.** Every admin call goes through `apiFetch`, which handles the Bearer token, CSRF and refresh-on-401. If the response is still 401 or 403 after the refresh, `adminApi` throws `AdminAuthError` and the guard returns to the login view.
- **Logout** reuses the header logout in `App.tsx`. See the edit in §8.

---

## 5. Data model changes

Each new model gets its own migration. There are only two.

### 5.1 `admin_command_center.AdminAuditEvent` (P0)

Migration: `admin_command_center/migrations/0001_initial.py`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `actor` | FK `CustomUser`, null | `null` for system events |
| `action` | CharField(64), indexed | e.g. `debate.override`, `pricing.policy.update`, `pricing.retrain`, `negotiation.takeover`, `negotiation.release`, `negotiation.message`, `inventory.space.create/update/delete/release`, `inventory.property.*`, `occupancy.upload`, `negotiation.turn` (P1) |
| `target_type` | CharField(32) | `rfp`, `space`, `property`, `policy`, `occupancy` |
| `target_id` | CharField(64), indexed | |
| `payload_json` | JSONField | Before/after values, previous status, message text |
| `created_at` | DateTimeField(auto_now_add), indexed | |

Helper: `admin_command_center/audit.py → record(actor, action, target_type, target_id, **payload)`.

### 5.2 `dynamic_pricing.PricingPolicy` (P0, singleton with `pk=1`)

Migration: `dynamic_pricing/migrations/0002_pricingpolicy.py`

| Field | Type | Default |
|---|---|---|
| `walk_away_floor_margin_pct` | FloatField | `settings.WALK_AWAY_FLOOR_MARGIN_PCT` (0.12) |
| `max_autonomous_discount_pct` | FloatField | `settings.MAX_AUTONOMOUS_DISCOUNT_PCT` (0.15) |
| `target_markup_pct` | FloatField | 0.18 |
| `anchor_markup_pct` | FloatField | 0.08 |
| `event_multiplier` | FloatField | 1.0 |
| `seasonality_json` | JSONField | `{"6":1.15,"7":1.15,"11":1.15,"12":1.15}`; months not listed default to 1.0 |
| `updated_by` | FK `CustomUser`, null | |
| `updated_at` | DateTimeField(auto_now) | |

Helpers:
- `PricingPolicy.get_solo()` gets or creates `pk=1` with the defaults above.
- `policy.season(month) -> float`

**Validation.** The serializer enforces:
- `0 ≤ walk_away_floor_margin_pct ≤ 1`
- `0 ≤ max_autonomous_discount_pct ≤ 0.5`
- `target_markup_pct > walk_away_floor_margin_pct`. This is what keeps the target above the floor.
- every seasonality value between 0.5 and 3.0, with keys `"1"`…`"12"`.

### 5.3 No other schema changes

- **Takeover state.** Takeover uses `RFPStatus.ESCALATED`, which is already defined. The previous status is stored in the audit payload.
- **SLA.** The SLA uses the existing `sla_completed_at` field.

---

## 6. API contract

This contract is frozen for both tracks. Everything is under `/api/admin-center/`, needs `IsAdminRole`, and uses JSON. Lists are not paginated unless noted. Money values are decimal strings and percentages are fractions (`0.12`). On every error the response body is `{"detail": "<human sentence>"}`, plus `"errors"` for validation.

### 6.1 Overview

**`GET overview/`**
```json
{
  "rfps": { "total": 12, "by_status": { "NEGOTIATING": 4, "BOOKED": 2, "ESCALATED": 1, "...": 0 } },
  "sla": { "target_seconds": 120, "measured": 9, "p50_seconds": 14.2, "p95_seconds": 41.0, "within_target_pct": 1.0 },
  "debate": { "rounds": 21, "avg_consensus": 0.93, "partial_rate": 0.08 },
  "pricing": { "quotes": 30, "fallback_rate": 1.0, "model_trained": false },
  "inventory": { "properties": 1, "spaces": 2, "booked": 0 },
  "occupancy": { "rows": 10, "from": "2026-06-01", "to": "2026-06-10" },
  "attention": [ { "rfp_id": "…", "company_name": "Acme", "reason": "escalated|amber_fields" } ],
  "recent_activity": [ { "action": "pricing.policy.update", "actor": "admin@demo.local", "target_type": "policy", "target_id": "1", "created_at": "…" } ]
}
```

### 6.2 Module 2: Debate Observatory

- **`GET rfps/?status=NEGOTIATING&q=acme`.** `q` matches company name or id prefix. Returns the newest 100.
```json
[ { "id": "uuid", "company_name": "Acme", "client_email": "demo-client@local", "status": "NEGOTIATING",
    "rounds": 2, "latest_consensus": 1.0, "amber_fields": [], "created_at": "…", "updated_at": "…" } ]
```
- **`GET rfps/<uuid>/`**
```json
{ "id": "uuid", "status": "NEGOTIATING", "client_email": "…", "source_document_text": "…",
  "cards": { "event_overview": {}, "room_block": {}, "meeting_space": {}, "catering_av": {}, "live_quote": {} },
  "amber_fields": ["total_room_nights"],
  "sla": { "started_at": "…", "completed_at": "…", "duration_seconds": 13.9 },
  "rounds": [ { "iteration": 1, "extractor_model_id": "muse-wonder", "critic_model_id": "muse-spark-1.3",
                "consensus": 0.0, "duration_ms": 412,
                "flags": [ { "field_path": "total_room_nights", "severity": "high", "message": "…", "expected": "120", "actual": "110" } ],
                "extraction": { "company_name": { "value": "Acme", "source_citation": { "page_number": 1, "verbatim_quote": "…" } } } } ],
  "quotes": [ { "id": "uuid", "floor": "28560.00", "target": "30090.00", "anchor": "32497.20", "agreed": null, "used_fallback": true, "created_at": "…" } ],
  "audit": [ { "action": "debate.override", "actor": "admin@demo.local", "payload": {}, "created_at": "…" } ] }
```
- **`POST rfps/<uuid>/override/`** with body `{"fields": {...}, "note": "Confirmed by phone"}`.
  - Allowed `fields` keys: `company_name`, `event_type`, `check_in_date`, `check_out_date`, `total_room_nights`, `headcount`, `seating_style`.
  - The keys are mapped onto card sections, the overridden keys are removed from the `amber_fields` lists, and the result is applied with the existing `validate_card_mutation(rfp_id, payload)`. That call validates capacity and dates, reprices, and broadcasts `cards_patch` to the client.
  - Responses: `200 {"ok": true, "quote": {...}}`, or `400 {"detail": "...", "alternatives": [...]}` on `CardMutationValidationError`.
  - Writes the audit event `debate.override`.
  - The old path `debate/<uuid>/override/` stays as an alias.

### 6.3 Module 3: Pricing

- **`GET pricing/policy/`** returns the policy fields from §5.2 plus `updated_by` (email) and `updated_at`.
- **`PUT pricing/policy/`** takes the full policy body. Returns 200 with the saved policy, or 400 with `errors`. Writes `pricing.policy.update` with before and after values.
- **`GET pricing/model/`** returns `{"artifact_exists": false, "trained_at": null, "occupancy_rows": 10, "min_rows_required": 5}`.
- **`POST pricing/retrain/`** returns `{"status": "ok"|"skipped_insufficient_data", "trained_at": "…"}`. It wraps `train_and_save_model` and writes `pricing.retrain`. The old `/api/pricing/admin/retrain/` is kept.
- **`GET pricing/quotes/?rfp=<uuid>`** returns the newest 100 quotes, shaped like `quotes[]` in §6.2 plus `rfp_id` and `company_name`.

### 6.4 Module 4: Negotiations

- **`GET negotiations/`** lists RFPs with status `NEGOTIATING`, `ESCALATED`, `PRICING` or `PROPOSAL_RENDERED`. This replaces the old ID-only response.
```json
[ { "id": "uuid", "company_name": "Acme", "status": "ESCALATED", "taken_over": true, "taken_over_by": "admin@demo.local",
    "check_in_date": "2026-12-01", "check_out_date": "2026-12-04", "headcount": 200,
    "latest_quote": { "floor": "…", "target": "…", "anchor": "…", "agreed": null, "used_fallback": true },
    "updated_at": "…" } ]
```
- **`POST negotiations/<uuid>/takeover/`.**
  - Allowed only from `AWAITING_USER_CARD_EDIT`, `PRICING`, `NEGOTIATING` or `PROPOSAL_RENDERED`. Anything else returns `409`.
  - Sets `ESCALATED` and writes `negotiation.takeover` with `{previous_status}`.
  - Broadcasts `agent_utterance` with the text *"A member of our events team is joining the conversation now."*
- **`POST negotiations/<uuid>/release/`.**
  - Returns `409` unless the RFP is `ESCALATED`.
  - Restores the previous status from the latest takeover event, or `NEGOTIATING` if none is found.
  - Writes `negotiation.release` and broadcasts *"Thanks for waiting. I'll pick things up from here."*
- **`POST negotiations/<uuid>/message/`** with body `{"text": "…"}`.
  - The text is 1–500 characters after trimming. Returns `409` unless `ESCALATED`.
  - Broadcasts `agent_utterance {text}`; the client speaks it through TTS. Writes `negotiation.message`.
- **Gate in the shared voice-chat views (P0).** When the RFP is `ESCALATED`, `POST /api/negotiation/voice-chat/` and `voice-chat/stream/` return the fixed reply *"A member of our team has joined and will reply shortly."* with `"human_takeover": true`. The stream version sends this as one `done` event. Neither calls the agent.

### 6.5 Module 5: Inventory

- **Properties.** `GET|POST inventory/properties/` and `GET|PATCH|DELETE inventory/properties/<uuid>/`.
  - Fields: `id`, `name`, `timezone`, `space_count`.
  - `DELETE` returns `409` if the property has spaces or occupancy rows.
- **Spaces.** `GET|POST inventory/spaces/?property=<uuid>` and `GET|PATCH|DELETE inventory/spaces/<uuid>/`.
  - Fields: `id`, `property`, `name`, `space_type` (`ROOM_BLOCK|BALLROOM|BOARDROOM|OUTDOOR`), `capacities_json` (`{banquet, classroom, theater, u_shape, cocktail}`, non-negative ints), `rack_rate`, `base_floor_cost` (must be `≤ rack_rate`), `av_capabilities_json`, `is_booked` (read-only).
  - `DELETE` returns `409` when `is_booked`.
- **`POST inventory/spaces/<uuid>/release/`** sets `is_booked=false` and `booking_idempotency_key=null`. Writes `inventory.space.release`.

### 6.6 Module 6: Occupancy

- **`GET occupancy/?property=<uuid>&from=YYYY-MM-DD&to=YYYY-MM-DD`** returns rows ordered by date, at most 366.
- **`POST occupancy/upload/`** takes multipart fields `file` (CSV) and `property`.
  - Required columns: `target_date`, `room_occupancy_pct`, `adr`, `revpar`.
  - Optional columns: `hall_utilization_pct`, `is_peak_season`, `local_event_multiplier`.
  - Rows are upserted on `(property, target_date)`. Bad rows are skipped and reported; the request never fails as a whole because of row errors.
```json
{ "created": 28, "updated": 2, "skipped": 1, "errors": [ { "row": 7, "error": "room_occupancy_pct must be between 0 and 1" } ] }
```
  Returns `400` only when the file is missing, isn't a CSV, or lacks a required column. Writes `occupancy.upload`.
- **`GET occupancy/summary/`** returns `{"engine": "sqlite"|"azuresql", "vendor": "sqlite", "tables": {"rfp": 12, "quotes": 30, "occupancy": 40, "spaces": 2}, "occupancy_range": {"from": "…", "to": "…"}}`. This is the honest form of "Dual-DB sync": it shows which engine is active, because no sync mechanism exists.
- **`occupancy/ingest/`** (JSON rows) is kept as it is.

### 6.7 Module 7: Telemetry

**`GET telemetry/`**
```json
{ "sla": { "target_seconds": 120, "p50_seconds": 14.2, "p95_seconds": 41.0, "within_target_pct": 1.0,
           "recent": [ { "rfp_id": "…", "company_name": "…", "status": "…", "duration_seconds": 13.9, "started_at": "…" } ] },
  "funnel": [ { "status": "EXTRACTING", "count": 0 }, "… in RFPStatus order …", { "status": "BOOKED", "count": 2 } ],
  "conversion": { "booked": 2, "total": 12, "rate": 0.17 },
  "debate": { "avg_rounds": 1.6, "avg_consensus": 0.93, "partial_rate": 0.08, "avg_critic_ms": 380 },
  "pricing": { "quotes": 30, "fallback_rate": 1.0 },
  "tokens": null }
```
`tokens` stays `null` until P1 (`ModelCallLog`). The UI says "Not recorded yet".

### 6.8 Audit

**`GET audit/?limit=50&target_type=rfp&target_id=<uuid>`** returns the newest events first.

---

## 7. Backend implementation (Track B)

### 7.1 Files

```
backend/apps/admin_command_center/
  models.py              AdminAuditEvent                          (new)
  audit.py               record(...)                               (new)
  serializers.py         RFP list/detail, round, quote, property, space, occupancy row, audit, policy (new)
  services/
    overview.py          build_overview()                         (new)
    telemetry.py         build_telemetry(), percentile()          (new)
    occupancy_import.py  import_csv(file, property) -> report     (new)
    negotiation.py       takeover(), release(), send_message()    (new)
  views.py               keep existing views; add new APIViews/ViewSets
  urls.py                existing paths + DefaultRouter for inventory/*
  consumers.py           role check on connect (4403)
  management/commands/seed_admin_demo.py   (P0, demo data, §12)
  migrations/0001_initial.py
```

### 7.2 Shared-file edits

These are the exhaustive list of edits outside the admin app.

| File | Edit | Priority |
|---|---|---|
| `dynamic_pricing/models.py` + `migrations/0002_pricingpolicy.py` | Add `PricingPolicy` (§5.2) | P0 |
| `dynamic_pricing/rule_fallback.py` | Read the policy: `base = rack × nights × policy.season(month) × policy.event_multiplier`; `floor = max(base × (1+margin), space.base_floor_cost)`; `target = base × (1+target_markup)`; `anchor = target × (1+anchor_markup)`; then `_enforce_ladder`. **Fixes bug A.** | P0 |
| `dynamic_pricing/services.py` | (1) Use `PricingPolicy` instead of `settings.WALK_AWAY_FLOOR_MARGIN_PCT`. (2) Train on `label = revpar / mean(revpar)`, a demand index around 1.0, and clamp the prediction to `[0.8, 1.5]` at inference. **Fixes bug B.** (3) Add `_enforce_ladder(floor, target, anchor)` so `target ≥ floor × 1.05` and `anchor ≥ target × 1.03`. (4) Write the training timestamp next to the artifact (`xgboost_pricing.meta.json`). | P0 |
| `dynamic_pricing/views.py` | `AdminPricingGuardrailView.get` reads `PricingPolicy.get_solo()` | P0 |
| `rfp_debate/tasks.py` | In `_apply_quote_to_cards`, set `sla_completed_at = now()` if it's empty | P0 |
| `negotiation_agent/views.py` | ESCALATED gate in both voice-chat views (§6.4) | P0 |
| `accounts_rbac/demo_accounts.py`, `inventory/management/commands/seed_demo.py` | Demo admin account (§4.1) | P0 |
| `negotiation_agent/views.py` | Log `negotiation.turn` audit events `{message, reply}`. This is the transcript | P1 |
| `rfp_debate/meta_client.py` | `ModelCallLog` (model, fixture_kind, prompt/completion tokens from `usage`, elapsed_ms). Additive only | P1 |
| `rfp_debate/tasks.py`, `ui_card_validator/services.py` | `broadcast_admin(event, payload)` to group `admin_telemetry` | P1 |

### 7.3 Implementation notes

- **Percentiles.** Use nearest-rank over the sorted durations; return `null` when there are none. Don't add numpy to the request path.
- **CSV import.** Use the `csv` module with `io.TextIOWrapper(file, encoding="utf-8-sig")`, which handles the Excel BOM. Validate each cell, and do all upserts inside `transaction.atomic()`.
- **Audit.** Every write view calls `audit.record(request.user, …)` after it succeeds.
- **Performance.** List views use `select_related("client")`, `annotate(rounds=Count("debate_logs"))`, and slicing. Keep 100-row caps.
- **Serializers.** Never `fields = "__all__"`. List fields explicitly. The admin may see floor prices; client-facing serializers are unchanged.

---

## 8. Frontend implementation (Track F)

### 8.1 Routing

| Path | Page | Module |
|---|---|---|
| `/admin` | `OverviewPage` | Overview |
| `/admin/debates` | `DebatesPage` | 2 |
| `/admin/debates/:rfpId` | `DebateDetailPage` | 2 |
| `/admin/pricing` | `PricingPage` | 3 |
| `/admin/negotiations` | `NegotiationsPage` (`?rfp=<id>` selects a row) | 4 |
| `/admin/inventory` | `InventoryPage` | 5 |
| `/admin/occupancy` | `OccupancyPage` | 6 |
| `/admin/telemetry` | `TelemetryPage` | 7 |
| `/admin/*` (unknown) | Redirect to `/admin` | — |

**`App.tsx` edits** (shared file; these three changes only):
1. `<Route path="/admin/*" element={<AdminPortal />} />`
2. NavLink `end`: change `end={to !== "/client"}` to `end={to === "/designer"}`, so the Admin tab stays active on sub-routes.
3. Logout button:
   - Show it when `(onStudio || onAdmin) && designerAuthed`, where `onAdmin = location.pathname.startsWith("/admin")`.
   - After logout, navigate to `onAdmin ? "/admin" : "/designer"`.

### 8.2 Files

```
frontend/src/pages/AdminPortal.tsx            replaced: auth guard + <AdminLayout> + nested <Routes>
frontend/src/pages/admin/
  OverviewPage.tsx  DebatesPage.tsx  DebateDetailPage.tsx  PricingPage.tsx
  NegotiationsPage.tsx  InventoryPage.tsx  OccupancyPage.tsx  TelemetryPage.tsx
frontend/src/components/admin/
  AdminLayout.tsx        module rail (aside) + content panel
  AdminPanel.tsx         studio-panel-header (kicker/title/subtitle/actions) + studio-panel-body
  AdminIcons.tsx         SVG icons per module (no emoji)
  StatTile.tsx           label, value, sub-label (tabular-nums)
  StatusChip.tsx         RFPStatus → label + tone
  AdminTable.tsx         columns config, row click, empty/loading/error states
  PriceLadder.tsx        floor · target · anchor mini bar (P1; P0 = three numbers)
  SpaceFormDialog.tsx    create/edit space, capacity grid
  LoadState.tsx          spinner / error with "Try again"
frontend/src/lib/adminApi.ts                  typed client for §6 (uses apiFetch); throws AdminAuthError on 401/403
frontend/src/lib/adminFormat.ts               money, pct, duration, relative time, status meta
frontend/src/lib/adminFormat.test.ts          Vitest
frontend/src/hooks/useAdminAuth.ts
frontend/src/hooks/usePolling.ts              (fn, intervalMs=10000) → {data, error, loading, reload}; pauses when tab hidden
frontend/e2e/admin.spec.ts                    Playwright (P1)
```

### 8.3 Page specifications

Each page is wrapped in `AdminPanel`, so it gets one header (kicker = module name, title, one-line subtitle) and actions on the right. Each page also handles all four states: **loading**, **empty**, **error** (with "Try again") and **data**.

**Overview** (`/admin`)
- 6 `StatTile`s: Active RFPs, SLA p50 (target 120 s), Within SLA %, Avg consensus, Fallback pricing %, Spaces booked.
- A status funnel (a horizontal bar per status, scaled to the maximum count).
- A **Needs attention** list (escalated RFPs and RFPs with amber fields), linking to the debate detail or negotiation.
- **Recent activity** (the last 10 audit events). The page polls every 10 seconds.

**Debates** (`/admin/debates`)
- A status filter (select) and a search field (`studio-field`).
- Table columns: RFP (short id), Company, Status chip, Rounds, Consensus, Amber, Updated.
- Clicking a row opens the detail page.
- Empty state: *"No RFPs yet. Submit one from the Client workspace and it will appear here."*

**Debate detail** (`/admin/debates/:rfpId`)
- **Left: Source.** The source text in a `studio-scroll` `<pre>`, with each `verbatim_quote` highlighted (`<mark>`).
- **Right, top: Rounds.** A timeline: iteration, model ids, consensus, duration and the flags list (field, severity, expected → actual).
- **Right, middle: Extracted fields.** Columns: field, value, citation quote. Amber fields are outlined amber.
- **Right, bottom: Override** form with company, event type, check-in/out, room nights, headcount and seating style, plus a note.
  - Clicking **Save override** opens a `ConfirmDialog`: *"Override these fields? The client's cards and quote will update."*
  - The result is shown as a snackbar: *"Override saved. Client cards updated."* or the 400 detail.
- **Footer:** quote history and audit trail for this RFP.

**Pricing** (`/admin/pricing`)
- **Policy form.** Inputs:
  - Floor margin %, Max autonomous discount %, Target markup %, Anchor markup %
  - Event multiplier
  - Seasonality: a 12-month grid of multipliers
  - The form shows inline validation, and **Save policy** is disabled while the form is invalid.
- **Live example line.** Computed client-side from the policy and the highest rack rate: *"3 nights at 8,500 → floor 28,560 · target 30,090 · anchor 32,497"*. This makes the ladder visible.
- **Model** card: trained yes/no, trained at, rows used. The **Retrain model** button opens a confirm dialog and shows the result in a snackbar.
- **Quotes** table: RFP, Company, Floor, Target, Anchor, Agreed, Engine (`Fallback` / `XGBoost`), Created.

**Negotiations** (`/admin/negotiations`)
- **Left list:** company, status chip, dates, latest anchor and agreed price. Taken-over rows show a *"You're live"* chip.
- **Right detail:**
  - A card summary and the price ladder.
  - **Take over** (primary) or **Hand back** (secondary), each behind a confirm dialog.
  - An **operator message** box. It's enabled only while the RFP is taken over, the button says **Send to client**, and the placeholder reads *"Typed messages are spoken to the client in the agent's voice."*
  - **Activity:** audit events for this RFP. Once P1 lands, these include the transcript turns.

**Inventory** (`/admin/inventory`)
- A property selector with **Add property** and **Rename**.
- Spaces table: Name, Type, Banquet/Classroom/Theater, Rack rate, Floor cost, Status (`Booked`/`Available`).
- Row actions: **Edit**, **Release booking** (only when booked) and **Delete** (danger, disabled when booked). Destructive actions go through `ConfirmDialog` with `confirmVariant="danger"`.
- `SpaceFormDialog` has a capacity grid for banquet, classroom, theater, U-shape and cocktail, and validates that floor cost ≤ rack rate.

**Occupancy** (`/admin/occupancy`)
- A property selector and an upload zone (file input plus drag and drop, CSV only). It shows the expected header as copyable text.
- After an upload, an **Import report** shows created, updated and skipped counts and the row errors.
- A date-range filter and a table: Date, Occupancy %, Hall %, ADR, RevPAR, Peak, Event multiplier.
- A **Database** card (engine, row counts, date range) and a **Retrain model** link to Pricing.

**Telemetry** (`/admin/telemetry`)
- Tiles for SLA p50, p95, within-120s % and conversion rate.
- An SLA table for recent RFPs. Durations over 120 s are shown in red text with the word *"Over"*.
- The funnel, a debate stats tile row and the pricing fallback rate.
- **Token usage:** *"Not recorded yet"* with one line saying it arrives with model call logging (P1).

### 8.4 State and data rules

- **One fetch layer.** All requests go through `adminApi.ts`. Components never call `fetch` directly.
- **Polling.** `usePolling` runs every 10 s on Overview, Debates and Negotiations. Other pages fetch on mount and after each mutation.
- **After a mutation:** refetch the affected list, then show a snackbar. There are no optimistic updates in P0.
- **Remembered selection.** The selected property is kept in `localStorage` (`rfp-admin-property`), wrapped in try/catch.
- **Formatting.** Money uses `Intl.NumberFormat("en-US", { maximumFractionDigits: 0 })` with no currency symbol, because the backend has no currency field. Percentages show one decimal place.

---

## 9. UI/UX rules (from `Docs/Designer_Studio_UI_UX_Audit.md` and `index.css`)

The admin panel must look like part of the same product as the Designer Studio. These rules are binding.

| # | Rule | How the admin panel applies it |
|---|---|---|
| U1 | **Shared horizontal inset.** Panels use `var(--studio-inset-x)` and never mix `px-3` with `px-5` | `AdminPanel` uses `studio-panel-header` and `studio-panel-body` only. Page content never sets its own side padding |
| U2 | **Panel rhythm.** Content starts below the header with `pt-5`, and footers use `pb-6` (`studio-panel-body` / `studio-panel-footer`) | Same classes. Footer actions (Save policy, Save override) live in `studio-panel-footer` |
| U3 | **Panels are `studio-shell-panel`** (rounded-2xl, `border-white/10`) | Module rail `<aside className="studio-shell-panel …">` (like DesignerPortal's `sm:w-64` aside), plus one content panel |
| U4 | **Themed scrollbars:** `.studio-scroll` on every scroll area | Tables, source text, lists and the rail |
| U5 | **Consistent buttons**, all controls aligned at `min-h-[2.75rem]` | Secondary: `studio-btn-secondary`. Destructive: `studio-btn-secondary studio-btn-danger`. Icon-only: `TemplateIconButton` with a `label` (aria) |
| U6 | **Clear action labels** (the audit renamed "Validate (Spark)" to "Check template") | Verb + object: *Save policy*, *Retrain model*, *Take over*, *Hand back*, *Send to client*, *Upload CSV*, *Release booking*. No model jargon in buttons |
| U7 | **No Muse/Fixture badges in the UI chrome** | Model ids appear only as data in the debate rounds, never as header badges |
| U8 | **Logout and theme live in the app nav only** | No sub-header logout. Reuse the `App.tsx` header button (§8.1 edit 3) |
| U9 | **Confirm before destructive or customer-visible actions** (`ConfirmDialog`, as for Clear chat and Log out) | Delete space/property, release booking, retrain, take over, hand back, override |
| U10 | **Feedback by toast** (`StudioSnackbar`; the audit's follow-up asks for toasts) | Every mutation ends in a success or error snackbar. Use `inferSnackbarTone` or an explicit tone |
| U11 | **Empty states** use `studio-empty-list` (dashed) | Every empty state says what will appear and how to make the first one |
| U12 | **SVG icons, not emoji** (open audit follow-up) | `AdminIcons.tsx`, in the same style as `AppNavIcons.tsx` |
| U13 | **Focus rings and reduced motion are global** (`*:focus-visible` violet ring; the `prefers-reduced-motion` block) | Never remove an outline. framer-motion transitions under 200 ms, none that loop |
| U14 | **Screen reader live region** (`aria-live`) | One `aria-live="polite"` region in `AdminLayout` announces snackbar text and polling errors |
| U15 | **Both themes.** Dark is the default; light uses `html[data-theme="light"]` plus the `designer-shell-light` wrapper | Wrap the admin root in `designer-shell-light` when `theme === "light"`, as DesignerPortal does. Check both themes in QA |
| U16 | **Kicker / title / subtitle header** (`studio-panel-kicker`, `studio-panel-subtitle`) | Kicker = module name (for example "Module 3 · Pricing"), title = page, subtitle = one sentence |
| U17 | **Login screen reuse** | `StudioPortalLogin` with `title="Admin Command Center"` and `subtitle="Sign in with your admin account"`. Leave out `onMockSso` |

**Admin-specific rules.** These follow the same spirit as the audit.
- **Status chips.** Each status has one fixed mapping in `adminFormat.ts`, so the same status looks the same everywhere:
  - `EXTRACTING`/`DEBATING`: violet, "In debate"
  - `AWAITING_USER_CARD_EDIT`: sky, "Awaiting client"
  - `PRICING`/`NEGOTIATING`: emerald, "Negotiating"
  - `PROPOSAL_RENDERED`: indigo, "Proposal sent"
  - `BOOKED`: green, "Booked"
  - `ESCALATED`: amber, "Human takeover"
- **Numbers** use `tabular-nums` and are right-aligned in tables.
- **Severity colour always comes with a word** ("Over", "High", "Booked"), never colour alone.
- **Phone width.** The rail collapses to a horizontal scroller below `sm` (`max-h-[32vh]`, same pattern as DesignerPortal), and tables scroll inside their panel, never the page.

---

## 10. Failure handling (spec §9 style)

| Flow | Happy path | Edge case | Worst case and handling |
|---|---|---|---|
| Sign-in | ADMIN signs in and lands on Overview | A DESIGNER or CLIENT session opens `/admin` | Access token expires mid-session: `apiFetch` refreshes once. If that still fails, `AdminAuthError` → login view with *"Your session ended. Sign in again."* |
| Debate override | Fields saved, client cards update live | The client is offline; the cards persist and are delivered as the snapshot on reconnect | Headcount is over capacity: 400 with alternatives, shown in the form error as *"Over capacity for {space}. Try: {names}."* |
| Pricing policy | Saved, and the next quote uses it | Two admins edit at once: last write wins, and `updated_by`/`updated_at` show who saved last | Invalid ladder (target ≤ floor): 400 from the serializer. Save stays disabled client-side |
| Retrain | Model trained, the "trained at" time updates | Fewer than 5 occupancy rows → `skipped_insufficient_data` with the hint *"Import at least 5 days of occupancy."* | Training throws → 500 caught → snackbar error. The quote path keeps the fallback, which can't crash |
| Takeover | Client hears the hand-over line, and the agent stops answering | The RFP was already booked → 409 *"This RFP is booked; there is nothing to take over."* | Admin leaves while taken over: the RFP stays ESCALATED and is listed under **Needs attention** until handed back |
| Space delete | Deleted, audit recorded | The space is booked → 409, and the button is disabled in the UI | The FK is used by future zones (P2): use PROTECT later |
| CSV upload | All rows imported | Mixed valid and invalid rows → partial import plus row errors | Wrong file or missing column → 400 that names the missing column |
| Telemetry | Real durations | No completed RFPs → tiles show "—" with *"No completed RFPs yet"* | Clock skew/negative duration → excluded from the percentiles |

---

## 11. Testing plan

### 11.1 Backend (pytest, `backend/tests/`, uses the existing `conftest.py` fixtures)

Add `admin_user` and `seeded_rfp` fixtures to `tests/conftest.py`. `seeded_rfp` runs `run_debate_pipeline` in fixture mode.

| File | Tests (P0 unless marked) |
|---|---|
| `test_admin_permissions.py` | Gets every URL pattern from `apps.admin_command_center.urls` (UUID kwargs filled with `uuid4()`); for each, anonymous → 401/403, CLIENT → 403, DESIGNER → 403, ADMIN → not 401/403. Plus `/api/pricing/admin/*`. **Write this first; it covers every future endpoint automatically.** |
| `test_admin_auth.py` | Demo admin login returns role ADMIN and a JWT; `/api/auth/me/` with that token says ADMIN; telemetry WS rejects non-admin (`channels.testing.WebsocketCommunicator`, P1) |
| `test_admin_overview.py` | Overview counts match the seeded data; SLA percentiles ignore null durations; `sla_completed_at` is set after the pipeline |
| `test_admin_debates.py` | List filter by status; detail includes rounds/flags/quotes; override updates cards, clears amber for overridden keys, creates a quote and an audit event; over-capacity override → 400 with alternatives |
| `test_admin_pricing.py` | **Ladder invariant:** `floor ≤ target ≤ anchor` for the fallback and after retrain with seeded occupancy (regression for bugs A and B); policy PUT validation rejects `target_markup ≤ margin`; policy change alters the next quote; GET guardrails reads the policy; audit event recorded |
| `test_admin_negotiations.py` | Takeover sets ESCALATED and records previous status; takeover on BOOKED → 409; voice-chat returns `human_takeover: true` while escalated; message requires ESCALATED and broadcasts `agent_utterance` (capture with the in-memory channel layer); release restores previous status |
| `test_admin_inventory.py` | Create/update/delete space; `base_floor_cost > rack_rate` → 400; delete booked → 409; release clears the booking; property delete with spaces → 409 |
| `test_admin_occupancy.py` | CSV with BOM and mixed rows → created/updated/skipped counts and row errors; missing column → 400; upsert on the same date updates; summary reports the engine |
| `test_admin_telemetry.py` | Funnel in RFPStatus order; conversion rate; `tokens` is `null` |

Existing suites must stay green: `test_rbac_and_templates.py`, `test_card_validator.py`, `test_inventory_locking.py`, `test_guardrails.py`, and all designer tests.

### 11.2 Frontend

| Check | Command | Priority |
|---|---|---|
| Type check and build | `npm run build` (`tsc -b && vite build`) | P0 |
| Unit: `adminFormat.test.ts` covers status meta for every RFPStatus, money/pct/duration formatting, the ladder example maths | `npm test` | P0 |
| Unit: `adminApi` throws `AdminAuthError` on 401/403 (mock `fetch`) | `npm test` | P1 |
| E2E: `e2e/admin.spec.ts` covers the sign-in form shown at `/admin`, demo admin login, visiting each module via the rail, and a designer login rejected at `/admin` | `npm run test:e2e` (needs both servers) | P1 |

### 11.3 Manual QA checklist (5 minutes, before the demo)

- [ ] `/admin` signed out → login; designer account → rejected with role message; admin → Overview
- [ ] Every rail link loads with no console errors, in **dark and light** themes
- [ ] Phone width (~400 px): the rail scrolls horizontally and the page never scrolls sideways
- [ ] Keyboard only: tab through the rail, a table row, a form and a dialog; focus ring visible; Esc closes dialogs
- [ ] Submit an RFP in `/client` (second tab) → it appears in Debates within 10 s
- [ ] Override headcount → client cards update live
- [ ] Change floor margin → new quote reflects it; ladder floor < target < anchor
- [ ] Take over → client hears the hand-over line; operator message is spoken; Hand back works
- [ ] Upload `backend/artifacts/sample_occupancy.csv` (from `seed_admin_demo --write-csv`) → report shows counts
- [ ] Telemetry shows a non-null p50 after one completed RFP

### 11.4 Commands

```powershell
cd backend
.\.venv\Scripts\pytest tests/test_admin_*.py -q          # fast loop
.\.venv\Scripts\pytest -q                                # full suite before commit
cd ..\frontend
npm run build; npm test
npm run test:e2e                                          # P1, servers running
```

---

## 12. Demo data and demo script

**`manage.py seed_admin_demo`** (P0, `admin_command_center/management/commands/`):
- Runs `seed_demo`, then adds:
  - a Boardroom and a Room-block space;
  - 60 days of occupancy;
  - 4 RFPs pushed through `run_debate_pipeline` synchronously in fixture mode, with varied text. One is left with amber fields, one is moved to `BOOKED`, and one to `ESCALATED` via the service.
- Idempotent.
- `--write-csv` writes `backend/artifacts/sample_occupancy.csv` for the upload demo.

**Two-minute demo script:**
1. Sign in as `admin@demo.local` → Overview: KPIs, the funnel and the **Needs attention** list.
2. In a second tab, submit an RFP from `/client` → it appears in **Debates**. Open it to show the source quotes, the rounds and the flags.
3. Override the headcount → the client tab's cards and quote update.
4. **Pricing:** raise the floor margin from 12% to 15% → the example ladder updates → save → a new quote shows the new floor.
5. **Negotiations:** **Take over** → the client hears the hand-over → **Send to client** "We can include the AV package at no charge" → **Hand back**.
6. **Telemetry:** the SLA p50 is well under 120 s.
7. **Inventory:** add a space and release a booking. **Occupancy:** upload the CSV → import report → **Retrain model**.

---

## 13. 60-minute timeline

| Time | Track B (backend) | Track F (frontend) | Gate |
|---|---|---|---|
| 0:00–0:05 | `.env`, migrate, `seed_demo`, start the servers | `npm install`, start Vite | Both servers up; this contract frozen |
| 0:05–0:15 | `test_admin_permissions.py` (red) → `AdminAuditEvent`, `PricingPolicy`, migrations, demo admin, consumer role check | `adminApi.ts` types from §6, `useAdminAuth`, guard + login, `App.tsx` edits, `AdminLayout`, rail, `AdminPanel` | Admin can sign in to an empty layout |
| 0:15–0:30 | Inventory CRUD, overview, rfps list/detail/override, pricing policy/model/retrain/quotes + **ladder fixes**, `sla_completed_at` | Overview, Inventory (with dialog), Debates, Debate detail | Permission test green |
| 0:30–0:40 | Negotiation takeover/release/message + voice-chat gate, occupancy upload/list/summary, telemetry, audit | Pricing, Negotiations, Occupancy, Telemetry | All §11.1 test files written |
| 0:40–0:48 | `seed_admin_demo`; full `pytest` green | `adminFormat.test.ts`; `npm run build` green | Both suites green |
| 0:48–0:56 | Integration and manual QA (§11.3), both together; fix what breaks | | Checklist ticked |
| 0:56–1:00 | Commit, push `develop/admin-panel`, open PR | Rehearse the demo script | PR open |

**If you're behind, cut in this order:** the PriceLadder visual (keep the numbers), then Occupancy date filter, then Telemetry funnel bars (keep the counts), then Inventory property rename. **Never cut:** the permission matrix test, the ladder invariant test, the takeover gate, or the sign-in guard.

---

## 14. Definition of done

- [ ] Every `/api/admin-center/**` endpoint rejects non-admins (the matrix test proves it)
- [ ] Every admin action that changes data writes an `AdminAuditEvent`
- [ ] Pricing ladder `floor ≤ target ≤ anchor` holds for the fallback and XGBoost paths (tested)
- [ ] `sla_completed_at` is written, and Telemetry and Overview show real durations
- [ ] Takeover stops the assistant, and operator messages reach the client's voice
- [ ] All P0 pages handle the loading, empty, error and data states in both themes, with no console errors
- [ ] UI rules U1–U17 are followed (reviewer checks §9 line by line)
- [ ] `pytest` (full) and `npm run build && npm test` are green; no Designer Studio files changed
- [ ] `designer_langgraph_checkpoints.sqlite*` and `db.sqlite3` are **not** committed
- [ ] PR description lists the shared-file edits from §7.2 and §8.1 for Sasidu's review

---

## 15. Follow-ups after the hackathon (P1/P2)

- **Live admin feed:** `broadcast_admin` from the debate loop, card validation and quote creation; `useAdminTelemetry` switches to WebSocket and polling stays as the fallback.
- **Transcript:** `negotiation.turn` audit events from the voice-chat views, shown in Negotiations.
- **`ModelCallLog`** for token usage and latency per Muse call, which fills Telemetry's `tokens`.
- **Concession playbook:** a model with ranked perks that the negotiation agent reads, and an editor in Module 4.
- **Enforce `max_autonomous_discount_pct`** in `/api/negotiation/offer/`.
- **Security clean-ups outside admin scope:**
  - Stop sending `floor_price`/`target_price` to the client cards.
  - Add auth to the RFP cards snapshot and the voice-chat endpoints.
  - Add role checks to the RFP WebSocket.
- **Housekeeping:** fix `.github/workflows/ci.yml`, which points at the old `hospitality-rfp-engine/` path.
