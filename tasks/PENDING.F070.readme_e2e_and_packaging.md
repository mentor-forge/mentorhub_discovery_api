# F070 – README, server summary, and full e2e/packaging pass

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F060_notification_control_routes`  
**Description**: Align README and server startup logs with the Card/Notification API, fill any remaining test gaps, and run the full unit plus containerized e2e gate for F-DA02.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md` — still describes leftover Customer/Profile or 0.5.2 bootstrap notes
- `src/server.py` — route log lines
- `docs/openapi.yaml`
- `test/test_server.py`
- `test/e2e/test_cards.py`
- `test/e2e/test_notification.py`
- `test/e2e/e2e_auth.py`

This is a documentation and verification task. Add tests only for gaps found against F020’s endpoint tables. Do not invent new endpoints.

**Confirmation greps** (zero hits required except inside `tasks/`):

```bash
rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' --glob '*.py' --glob 'docs/openapi.yaml'
rg '/api/profile|/api/customer' src test docs/openapi.yaml README.md
```

## Goals

- `README.md` project structure lists Card routes/services and Notification control (not Customer/Profile infinite scroll).
- `README.md` curl examples cover:
  - `GET /api/cards` (home)
  - at least one typed list (e.g. `GET /api/cards/resources`)
  - `POST /api/notification/dismiss/<id>` (or create) with `Authorization: Bearer $TOKEN`
  - existing `/api/config` example may remain
- Token minting still uses `test/e2e/e2e_auth.py` / `pipenv run e2e` JWT settings.
- `src/server.py` startup logs list `/api/cards`, typed card prefixes (or a single “card type lists” line), `/api/notification`, plus config/docs/metrics.
- `test/test_server.py` blueprint/URL assertions match the registered surface and still forbid credential-minting routes.
- E2E coverage exists for home cards, each typed cards path from F020, and notification create/dismiss/cancel auth behavior.
- `api-utils==1.0.0` remains the Pipfile pin.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Dev e2e** (optional if container e2e is the gate; prefer both if `pipenv run dev` is already documented)
  - `pipenv run db` if the API is not already up
  - `pipenv run e2e` against a running API on port 8397
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — contains `/api/cards` and `/api/notification/dismiss/`
- Record command results in **Execution Notes**.

## Outputs

- `README.md` — current Discovery API surface and curl examples
- `src/server.py` — route registration log lines (only if they still mention Profile/Customer or omit cards/notification)
- `test/test_server.py` — only if assertions still drift from registered routes
- `test/e2e/test_cards.py` — only if typed/home coverage is incomplete
- `test/e2e/test_notification.py` — only if control coverage is incomplete
- `test/e2e/e2e_auth.py` — only if e2e tokens are missing claims required for home cards

The agent must not update files outside this list.

## Execution Notes

_Reserved for the task execution agent._
