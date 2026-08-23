# F060 – Notification POST, dismiss, and cancel routes

**Status**: Pending  
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

_Reserved for the task execution agent._
