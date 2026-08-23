# F060 – Notification POST, dismiss, and cancel routes

**Status**: Shipped  
**Type**: Feature  
**Depends On**: `F050_typed_cards_shared_get_routes`  
**Description**: Mount Notification control HTTP: create, dismiss by id, and cancel by id. Discovery controls Notification. GET notification lists for the SPA remain `GET /api/cards/notifications` (F050).

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — global POST `NotificationService.create_notification`; domain subclass owns dismiss/cancel; routes import the local subclass
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — `create_notification_get_routes` (already used under `/api/cards/notifications` in F050)
- `src/services/notification_service.py` — `create_notification` (inherited), `dismiss_notification`, `cancel_notification`
- `src/server.py`
- `docs/openapi.yaml` — `POST /api/notification`, `POST /api/notification/dismiss/{notification_id}`, `POST /api/notification/cancel/{notification_id}`
- `test/e2e/e2e_auth.py`

**HTTP contract** (match F020):

| Method | Path | Service |
| --- | --- | --- |
| POST | `/api/notification` | `NotificationService.create_notification(data, token, breadcrumb)` → `201` |
| POST | `/api/notification/dismiss/<notification_id>` | `dismiss_notification` → `200` |
| POST | `/api/notification/cancel/<notification_id>` | `cancel_notification` → `200` |

Route layer: `create_flask_token`, `create_flask_breadcrumb`, `request.json` (POST create only), call service, jsonify. No payload validation beyond what the service already strips (`SYSTEM_MANAGED_FIELDS`). `handle_route_exceptions` on every handler.

Do **not** import dismiss/cancel from `api_utils.services`. Prefer including control routes on a local `create_notification_routes()` blueprint (GET list of raw Notification documents is optional and not required by OpenAPI for this issue; do not collide with `/api/cards/notifications`).

**MongoDB I/O**: mutations already go through MongoIO in the service (F030). Routes must not open collections.

If F050 projected `get_notifications` on the same class used here, confirm create/dismiss/cancel still return Notification documents (not Cards).

## Goals

- `src/routes/notification_routes.py` implements the three operations and returns Notification JSON.
- `src/server.py` registers the blueprint at `/api/notification`.
- 404 for unknown or outbound-hidden ids; 401 without bearer; 201 on create.
- Unit tests mock the local `NotificationService` methods and token helpers.
- E2E: unauthenticated POST is 401; authorized dismiss/cancel of a missing id is 404. Create/dismiss happy path if seed/configurator data allows; otherwise status-code tests are enough and must be noted in **Execution Notes**.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/routes/test_notification_routes.py` — create 201; dismiss 200; cancel 200; 401 without token; service called with id/token/breadcrumb
  - `test/test_server.py` — `/api/notification`, `/api/notification/dismiss/<id>`, `/api/notification/cancel/<id>` present
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — `test/e2e/test_notification.py`

## Outputs

- `src/routes/notification_routes.py` — create
- `src/server.py` — register `/api/notification`
- `test/routes/test_notification_routes.py` — create
- `test/test_server.py` — notification URL rules
- `test/e2e/test_notification.py` — create
- `src/services/notification_service.py` — only if F050 projection leaked into mutations and a split/wrapper is required to keep dismiss/cancel/create returning Notification

The agent must not update files outside this list.

## Execution Notes

### Plan

1. `src/routes/notification_routes.py` — new local blueprint factory
   `create_notification_routes()` with the three control handlers. Each handler
   is `@handle_route_exceptions`, reads `create_flask_token()` /
   `create_flask_breadcrumb(token)`, calls `NotificationService`
   (`src.services.notification_service`), and returns `jsonify(document)` with
   `201` for create and `200` for dismiss / cancel.
2. `src/server.py` — import the factory and register it at `/api/notification`.
   Blueprint name `notification_routes` does not collide with the F050 Card GET
   blueprint, which is registered as `notification_card_routes` under
   `/api/cards/notifications`.
3. `test/routes/test_notification_routes.py` — mount the blueprint on a
   throwaway Flask app with the token / breadcrumb helpers and the three
   `NotificationService` methods mocked.
4. `test/test_server.py` — replace `test_notification_control_routes_not_registered_yet`
   with positive URL-map assertions for the three control rules, and keep the
   `/api/cards/notifications` typed-list assertions intact.
5. `test/e2e/test_notification.py` — black-box status-code coverage.

### Decisions

- **Control service, not the Card projector.** The routes import
  `NotificationService`. F050 put the Card projection on the
  `NotificationCardService` subclass, so `create_notification` (inherited),
  `dismiss_notification`, and `cancel_notification` all still return Notification
  documents. Nothing in `src/services/notification_service.py` needed to change,
  so that file is untouched.
- **Body parsing.** `create` uses `request.get_json(silent=True)` and raises
  `HTTPBadRequest` when the body is not a JSON object, so a missing or malformed
  body is the documented `400` instead of the generic `500` that
  `handle_route_exceptions` would produce from a raw `request.json` parse error.
  This is body parsing only — no field validation is added on top of the
  service's `SYSTEM_MANAGED_FIELDS` stripping.
- **No Mongo in the route layer.** Every mutation goes through the service,
  which already owns MongoIO (F030).

### Results

- `pipenv run test` — 132 passed, 102 subtests passed (104 before this task).
- `pipenv run lint` — clean after `pipenv run format`.
- `pipenv run build` — clean.
- `pipenv run container` — image built.
- `pipenv run api` + `pipenv run e2e` — 46 passed, 2 skipped. Both skips are
  pre-existing `test_cards.py` cases with no seeded Member / Mentee documents
  for the persona; no Notification test skipped.
- **Happy path ran for real.** Create is a global POST open to any
  authenticated caller, so `test/e2e/test_notification.py` seeds its own
  Notification instead of depending on Developer Edition data. Create, dismiss,
  and cancel were all exercised end to end against the containerized stack.

### Verified against the running stack

`POST /api/notification` → `201` with the Notification document (`name`,
`message`, `profile_id`, `status`, `created` breadcrumb); `POST
/api/notification/dismiss/{id}` → `200` with the same document plus a
`dismissed` breadcrumb and no `cancelled` or `saved` field. The same document
read through `GET /api/cards/notifications` comes back as a Card (`_id`, `name`,
`description`, `type: Notification`), confirming the control routes are bound to
`NotificationService` and the Card projection stays on
`NotificationCardService`.

A dismissed Notification still appears in `GET /api/cards/notifications`. That
matches the OpenAPI description for that list — it is scoped by outbound RBAC
only. The active-only filter belongs to the composite home list `GET /api/cards`
(`get_active_notifications`), which is F040 / F050 behaviour and unchanged here.

### Follow-ups

- The e2e create tests leave a handful of dismissed / cancelled Notifications in
  the Developer Edition database (unique `e2e-control-*` names). They are inert —
  excluded from the composite home list — and there is no delete endpoint to
  clean them up, but `mh down` / a reseed clears them.
- No 403 e2e case: the inbound check only rejects a non-admin retiring a
  **global** notification, and outbound RBAC turns every other cross-target
  attempt into a 404. That 403 path is covered by the service unit tests (F030);
  the e2e suite asserts the 404 instead.
- `README.md` still describes the route surface without the control endpoints;
  F070 owns the README and packaging pass.

### Orchestrator confirmation

Re-ran `pipenv run test` (132 passed, 48 e2e deselected), `pipenv run lint`, `pipenv run build`. Control routes bind `NotificationService` at `/api/notification`; Card list remains `/api/cards/notifications`. Status set to Shipped.
