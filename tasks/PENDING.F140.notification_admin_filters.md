# F140 – Admin-only Notification card filters

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F130_member_mentee_card_content`  
**Description**: `GET /api/cards/notifications` must let **admin** callers filter by `name` and/or `status`. Non-admin callers keep the outbound-scoped unfiltered list and receive `403` if they send those query params. Notification cards already have `link` from F120. Home `GET /api/cards` stays pagination-only (no name/status filters).

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md` — routes parse HTTP only; RBAC in the service layer
- `tasks/_PLANNING.md` — MongoIO only; do not change `api_utils`
- `README.md`
- `docs/openapi.yaml` — F100 `/api/cards/notifications` `name` contains, `status` in_list, admin `403`
- `src/server.py` — currently `create_notification_get_routes(NotificationCardService)` at `/api/cards/notifications`
- `src/routes/card_routes.py` — home factory + `register_list_only_blueprint`; `_auth_context` / `_json_ok`
- `src/services/notification_service.py` — `NotificationCardService.get_notifications` calls shared `get_notifications` then projects Cards. Shared method accepts `match=` but **not** parsed filters. Shared `NOTIFICATION_LIST_ORDER` has no `NOTIFICATION_LIST_FILTERS`.
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — `create_notification_get_routes` calls `parse_list_request(request, {}, order_spec)` and **drops filters**
- `../mentorhub_api_utils/api_utils/flask_utils/list_request.py` — `parse_list_request`
- `../mentorhub_api_utils/api_utils/services/rbac.py` — `is_admin`
- `../mentorhub_api_utils/api_utils/mongo_utils/list_query.py` — `build_match_filter`, `and_match`
- `test/routes/test_card_routes.py`
- `test/services/test_notification_service.py`
- `test/test_server.py`

**Why a local factory:** the shared Notification GET factory cannot apply filters without changing `api_utils`. Do **not** bump `Pipfile`. Add a local list-only factory (same HTTP style as home: token, breadcrumb, `parse_list_request`, service, jsonify) and register it **instead of** `create_notification_get_routes` for `/api/cards/notifications`.

**Filter spec** (local, on `NotificationCardService` or a module constant):

```python
NOTIFICATION_CARD_LIST_FILTERS = {
    "name": {"type": "contains", "field": "name"},
    "status": {"type": "in_list", "field": "status"},
}
```

Order remains shared `NOTIFICATION_LIST_ORDER` (`created.at_time` desc).

**RBAC:**

- Admin (`is_admin(token)` / `Config.ROLE_ADMIN` in roles): apply parsed `name` / `status` filters AND shared outbound (admin outbound is unrestricted `{}`).
- Non-admin: if the request includes `name` or `status` query params (present, even empty), raise `HTTPForbidden`. Otherwise call the existing unfiltered list (outbound still applies: own `profile_id` / `customer_id` / `mentor_id` plus global).
- Home `get_home_cards` / `get_active_notifications` is unchanged (no filters).
- Create / dismiss / cancel still return Notification documents, not Cards.

**Service:** `NotificationCardService.get_notifications` should accept `filters=` (and keep `match=`). Translate filters through `build_match_filter` AND’d onto outbound + optional match, then `execute_list_query` / `super().get_notifications(..., match=...)`. If shared `get_notifications` cannot take a filter-built match without double-encoding, override the list in the Discovery subclass using MongoIO / `execute_list_query` the same way shared does. Encode id fields with `encode_document` before MongoIO.

Do not register a by-id GET. The Notification factory is already list-only; the local replacement must stay list-only.

## Goals

- `GET /api/cards/notifications?name=Invite` as admin returns only name-matching Cards (`contains`).
- `GET /api/cards/notifications?status=active` (and `archived`, comma-separated `in_list`) as admin filters `status`.
- Combined `name` + `status` AND together.
- Non-admin GET without those params still `200` + Card array (outbound scoped).
- Non-admin GET with `name` or `status` → `403`.
- Unauthenticated still `401`.
- Cards still include F120 `type: Notification` and `link` `discovery/notification/{id}`.
- URL map still has `/api/cards/notifications` and no by-id rule.

### Craftsmanship Expectations

- RBAC belongs in `NotificationCardService` (or `NotificationService`), not in the route beyond parsing query params.
- Do not patch `api_utils`. Local factory is the intended Discovery override.
- Do not let a non-admin filter leak through by applying filters after an unrestricted query.
- Least privilege: a Coordinator/Mentor/Mentee token must not search another user’s notifications via `name`/`status`.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_notification_service.py` — admin + name filter match; admin status filter; non-admin with filters raises `HTTPForbidden`; non-admin without filters still lists; projection still Cards with `link`
  - `test/routes/test_card_routes.py` (or a dedicated notification-card route test) — mocked service receives parsed filters for admin; `403` when token is non-admin and query has `name` or `status`; `401` without bearer
  - `test/test_server.py` — `/api/cards/notifications` still registered; no ` /<id>` rule
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — add focused cases if cheap (admin filter 200, mentee persona `?name=x` → 403). Broader persona rewrite is F150; keep existing notification e2e green.
  - `curl -s http://localhost:8397/docs/openapi.yaml` — F100 spec

## Outputs

- `src/routes/card_routes.py` — local `GET /api/cards/notifications` factory (list-only)
- `src/server.py` — register the local factory; stop using `create_notification_get_routes` for Cards
- `src/services/notification_service.py` — admin filter RBAC + `filters` on `NotificationCardService.get_notifications`
- `test/services/test_notification_service.py`
- `test/routes/test_card_routes.py` — and/or new `test/routes/test_notification_card_routes.py` if split is clearer
- `test/test_server.py` — only if registration assertions drift
- `test/e2e/test_cards.py` — only if needed to keep e2e green (full coverage in F150)

The agent must not update files outside this list. Do not change OpenAPI. Do not change home composite content.

## Execution Notes
