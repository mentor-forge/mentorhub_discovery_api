# F020 – OpenAPI for Card lists and Notification control

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F010_pin_api_utils_1_0_0`  
**Description**: Replace Discovery OpenAPI with the Card-list and Notification-control contract. Component schemas come from the running configurator (Card and Notification). No Python route implementation in this task.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — list GET is a JSON **array**; pagination is request headers `offset` (default `0`) and `size` (default `20`, max `100`); query `contains` / `in_list` filters plus `sort_by` / `order`; no cursor envelope; no `X-Pagination-*` response headers
- `docs/openapi.yaml` — current spec after F010 (config, metrics, errors only)

**Definitive schemas** must be fetched from the running MongoDB configurator. Start the backing database if needed (`pipenv run db`), then:

```bash
curl -X GET "http://localhost:8383/api/configurations/json_schema/Card.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Notification.yaml/latest/" -H "accept: application/json"
```

If the configurator is unavailable, set **Status** to `Blocked` and stop — do not fall back to dictionary YAML in another repository.

Card is a **configurator-only projection schema** (not a persisted Mongo collection). Every `GET /api/cards*` response is an array of Card. Notification is a persisted collection that Discovery **controls**.

**Endpoint map** (universal landing nav → Discovery API). Home is the default cards list; every other nav item has a typed cards list:

| Nav item | Method and path | Response |
| --- | --- | --- |
| home | `GET /api/cards` | `Card[]` — composite home list (see Goals) |
| customer | `GET /api/cards/customer` | `Card[]` |
| members (`customerMembers`) | `GET /api/cards/members` | `Card[]` |
| mentees | `GET /api/cards/mentees` | `Card[]` |
| resources | `GET /api/cards/resources` | `Card[]` |
| paths | `GET /api/cards/paths` | `Card[]` |
| plans | `GET /api/cards/plans` | `Card[]` |
| products | `GET /api/cards/products` | `Card[]` |
| notifications | `GET /api/cards/notifications` | `Card[]` |
| settings | `GET /api/cards/settings` | `Card[]` |

Notification control (not Card arrays):

| Method and path | Body in | Body out |
| --- | --- | --- |
| `POST /api/notification` | Notification create payload (client must not send system-managed fields) | created Notification |
| `POST /api/notification/dismiss/{notification_id}` | none | updated Notification (`dismissed` breadcrumb) |
| `POST /api/notification/cancel/{notification_id}` | none | updated Notification (`cancelled` breadcrumb) |

`dismissed` and `cancelled` are breadcrumbs, not booleans. There is no `saved` field on Notification.

## Goals

- `docs/openapi.yaml` `info` describes Discovery as the Card landing API plus Notification control (no Customer/Profile list API).
- Component schemas:
  - `Card` — aligned to the latest Card JSON schema from the configurator (types, required fields, descriptions).
  - `Notification` — aligned to the latest Notification JSON schema from the configurator, including `profile_id` / `customer_id` / `mentor_id`, `created`, `dismissed`, `cancelled` breadcrumbs, and the absence of `saved`.
- Every `GET /api/cards` and `GET /api/cards/{type}` operation:
  - Requires bearer auth.
  - Documents `offset` and `size` **request headers** (defaults `0` / `20`, max `100`).
  - Documents the default list query parameters used by `parse_list_request` (`contains` / `in_list` filters plus `sort_by` / `order`) for that type. Home (`GET /api/cards`) may omit type-specific filters if it only paginates the composite list.
  - `200` response is a JSON **array** of `Card` (not `{items, has_more, next_cursor}`).
  - Shares `401` / `400` / `500` with existing error responses; typed lists may omit `404`.
- `GET /api/cards` description states the composite home list:
  - Active Notifications for the token `profile_id` (not dismissed, not cancelled).
  - Members when the token roles include Customer or Coordinator (`Config.ROLE_CUSTOMER`, `Config.ROLE_COORDINATOR`), scoped by token `customer_id`.
  - Mentees when the token roles include Mentor (`Config.ROLE_MENTOR`), scoped by token `mentor_id`.
- `GET /api/cards/members` description: Profile Cards for the token `customer_id` when roles include Customer or Coordinator; default list pagination and query parameters.
- `GET /api/cards/mentees` description: Profile Cards for the token `mentor_id` when roles include Mentor; default list pagination and query parameters.
- Notification control operations:
  - `POST /api/notification` — `201` with `Notification`; `400` / `401` / `403` / `500` as appropriate.
  - `POST /api/notification/dismiss/{notification_id}` and `POST /api/notification/cancel/{notification_id}` — path parameter is a 24-char hex ObjectId; `200` with `Notification`; `404` when missing or hidden by outbound RBAC.
- Tags: `Cards`, `Notification`, plus existing Config / Metrics.
- The document remains valid OpenAPI 3.0.x.

## Testing Expectations

Run all commands from this API repository root.

- **Schema fetch** — both configurator curls succeed; record the schema versions in **Execution Notes**.
- **Spec validation**
  - `pipenv run python -c "import yaml; yaml.safe_load(open('docs/openapi.yaml'))"`
  - Confirm `Card`, `Notification`, every path in the tables above, array `Card` list responses, and `offset`/`size` headers are present.
  - Confirm no `/api/profile`, `/api/customer`, `after_id`, `has_more`, or `next_cursor`.
- **Unit / lint / build** (must still pass after a docs-only change)
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — served file includes the new Card and Notification paths

## Outputs

- `docs/openapi.yaml` — Card and Notification component schemas; all Card list paths; Notification POST / dismiss / cancel paths; remove any leftover Profile/Customer contract

The agent must not update files outside this list.

## Execution Notes

_Reserved for the task execution agent._
