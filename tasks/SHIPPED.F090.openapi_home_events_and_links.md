# F090 – OpenAPI for home composite, remaining typed lists, Events, and Card links

**Status**: Shipped  
**Type**: Defect  
**Depends On**: `F080_suppress_card_by_id_gets`  
**Description**: Rewrite the Discovery Card OpenAPI so it matches the corrected home composite, the reduced typed-list surface, the new Events list, and the Card `link` conventions. Docs only — no Python.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md`
- `README.md`
- `docs/openapi.yaml` — current Card lists after F080 (home plus nine typed lists)
- `../mentorhub_api_utils/README.md` — list GET is a JSON **array**; pagination is request headers `offset` / `size`

**Definitive schemas** must be fetched from the running MongoDB configurator. Start the backing database if needed (`pipenv run db`), then:

```bash
curl -X GET "http://localhost:8383/api/configurations/json_schema/Card.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Event.yaml/latest/" -H "accept: application/json"
```

If the configurator is unavailable, set **Status** to `Blocked` and stop — do not fall back to dictionary YAML in another repository.

Card remains a **configurator-only projection schema**. Every `GET /api/cards*` response is still a JSON array of Card. Event is a persisted collection that Discovery **creates**; this task only documents an Event **Card list** (consume/projection), not Event POST.

**Typed Card lists to keep** (plus home):

| Path | Card `type` | Source |
| --- | --- | --- |
| `GET /api/cards/resources` | Resource | Resource |
| `GET /api/cards/paths` | Path | Path |
| `GET /api/cards/plans` | Plan | Plan |
| `GET /api/cards/notifications` | Notification | Notification |
| `GET /api/cards/events` | Event | Event (**new**) |

**Typed Card lists to remove from OpenAPI** (implementation is F093):

- `GET /api/cards/customer`
- `GET /api/cards/members`
- `GET /api/cards/mentees`
- `GET /api/cards/products`
- `GET /api/cards/settings`

Do **not** add by-id Card paths. Notification control POSTs are unchanged.

**Home composite** (`GET /api/cards`) — document this exact section order. `offset` / `size` still apply to the **combined** list. Role checks are list-contains against `Config` role constants (`ROLE_ADMIN` is `admin`, `ROLE_CUSTOMER` is `customer`, and so on):

1. Active Notifications for token `profile_id`, newest `created.at_time` first (neither `dismissed` nor `cancelled`).
2. If roles contain Admin: one synthetic **Products** card.
3. If roles contain Admin: one synthetic **Discounts** card.
4. If roles contain Admin: one synthetic **Logs** card.
5. If roles contain Customer: one **Customer** card for token `customer_id`.
6. If roles contain Customer or Coordinator: **Member** cards for Profiles with token `customer_id`, newest `saved.at_time` first.
7. If roles contain Mentor: **Mentee** cards for Profiles with token `mentor_id`, newest `saved.at_time` first.
8. If roles contain Mentee: one synthetic **Learning Journey** card.

Synthetic cards (Products, Discounts, Logs, Learning Journey) have no Card `type` enum value — document that they omit `type` (same rule F020 recorded for Customer/Product/Setting). The Customer home card also omits `type`.

**Card `link` conventions** (relative SPA paths, no leading slash, `{id}` is the source document `_id` hex). Document these on the relevant operations; do not invent new Card schema properties. If live `Card.yaml` still marks `link` as `format: uri`, keep the configurator property set and state in the operation text that Discovery emits relative journey paths:

| Card | Endpoint | `link` |
| --- | --- | --- |
| Notification | `GET /api/cards` (home) | **omit** `link` — the SPA opens a Dismiss confirmation, not a detail route |
| Notification | `GET /api/cards/notifications` | `discovery/notification/{id}` |
| Member | home (and any remaining Member projection) | `customer/profile/{id}` |
| Mentee | home (and any remaining Mentee projection) | `mentee/mentee/{id}` |
| Resource | `GET /api/cards/resources` | `mentor/resource/{id}` when roles contain Mentor, else `mentee/resource/{id}` |
| Path | `GET /api/cards/paths` | `mentor/path/{id}` when roles contain Mentor, else `mentee/path/{id}` |
| Plan | `GET /api/cards/plans` | `mentor/plan/{id}` |
| Event | `GET /api/cards/events` | `mentee/event/{id}` |
| Products (synthetic) | home | `admin/products` |
| Discounts (synthetic) | home | `admin/discounts` |
| Logs (synthetic) | home | `admin/logs` |
| Customer (home singleton) | home | `customer/customer/{id}` |
| Learning Journey (synthetic) | home | `mentee/journey` |

Event list query parameters must match `api_utils` `EVENT_LIST_FILTERS` / `EVENT_LIST_ORDER` (`type` `in_list`, default `created.at_time` desc). The shared Event GET factory is **list-only** (no by-id).

## Goals

- `docs/openapi.yaml` `GET /api/cards` description lists the eight-section home composite above, including Admin / Customer / Coordinator / Mentor / Mentee gates and the two sort rules (`created.at_time` desc for notifications, `saved.at_time` desc for Member and Mentee).
- Typed Card paths in the spec are exactly: `resources`, `paths`, `plans`, `notifications`, `events`. The five doomed paths are gone.
- `GET /api/cards/events` is documented as `Card[]` with `type` Event, bearer auth, `offset` / `size` headers, Event list filters/order, `400` / `401` / `500`.
- Each remaining Card operation documents the `link` convention for that list (home Notifications omit `link`; typed Notifications use `discovery/notification/{id}`).
- Card and Notification component schemas still match the live configurator. Add Event only as needed to describe Event **filters** (Event is not the list response schema — the list is still `Card[]`).
- Notification control paths are unchanged. No `/api/profile`, `/api/customer`, by-id Card paths, `after_id`, `has_more`, or `next_cursor`.
- The document remains valid OpenAPI 3.0.x. Bump `info.version` to `0.3.0`.

## Testing Expectations

Run all commands from this API repository root.

- **Schema fetch** — both configurator curls succeed; record schema versions in **Execution Notes**.
- **Spec validation**
  - `python3 -c "import yaml; yaml.safe_load(open('docs/openapi.yaml'))"`
  - Confirm home description has all eight sections; paths are home + five typed lists + Notification control + config/metrics; no customer/members/mentees/products/settings Card paths.
- **Unit / lint / build** (docs-only; suite must still pass)
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — served file includes `/api/cards/events` and no `/api/cards/members`

This task does **not** require Python tests to match the new path set yet (routes still register the old typed lists until F093).

## Outputs

- `docs/openapi.yaml` — home composite description; Card `link` conventions; add `/api/cards/events`; remove the five doomed typed Card paths; `info.version` `0.3.0`

The agent must not update files outside this list.

## Execution Notes

### Implementation Summary
- Fetched live schemas from MongoDB configurator:
  - `Card.yaml` (version `0.0.0.0`): properties `_id`, `description`, `link` (format `uri`), `name`, `type` (enum `["Event", "Member", "Mentee", "Notification", "Path", "Plan", "Resource"]`).
  - `Event.yaml` (`latest`): properties `_id`, `context` (`profile_id`), `created` breadcrumb, `type` (enum: `advanced`, `arrived`, `completed`, etc.).
- Bumped `info.version` to `0.3.0` in `docs/openapi.yaml`.
- Updated `GET /api/cards` description with the exact eight-section composite order, role gates, sorts, and link omission/behavior.
- Updated `GET /api/cards/resources`, `GET /api/cards/paths`, `GET /api/cards/plans`, and `GET /api/cards/notifications` descriptions to include link conventions.
- Removed doomed typed Card paths (`/api/cards/customer`, `/api/cards/members`, `/api/cards/mentees`, `/api/cards/products`, `/api/cards/settings`).
- Added `GET /api/cards/events` list endpoint with `type` in-list filter, `profile_id` query param, `sort_by` (`created.at_time`, `type`), and `order` (`desc`, `asc`).

### Verification Results
- Validated YAML with PyYAML: successfully parsed without errors.
- Unit tests: 140 passed in 0.26s (`pipenv run test`).
- Lint: clean (`pipenv run lint`).
- Build: successful (`pipenv run build`).
- Packaging & live server: `pipenv run container && pipenv run api` built and deployed container `discovery_api`.
- Verified live served spec `http://localhost:8397/docs/openapi.yaml`: version 0.3.0, `/api/cards/events` present, doomed `/api/cards/members` absent.
