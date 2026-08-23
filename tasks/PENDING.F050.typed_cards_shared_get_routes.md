# F050 – Typed GET /api/cards/{type} via shared GET factories

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F040_home_cards_get_factory`  
**Description**: Add one Card-array list endpoint per remaining landing-nav item. Prefer `api_utils` shared GET factories with local subclasses that project to Card. Use a local list factory only when no shared factory exists.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — `create_*_get_routes(service_cls)` include pattern; list body is a JSON array; `offset`/`size` headers; query filters/order
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — factory table and URL shapes
- `src/services/resource_service.py`
- `src/services/path_service.py`
- `src/services/plan_service.py`
- `src/services/profile_service.py`
- `src/services/notification_service.py`
- `src/services/card_service.py` — `project` and any customer/product/settings list helpers from F030
- `src/routes/card_routes.py` — home GET only after F040
- `src/server.py`
- `docs/openapi.yaml` — typed Card list paths from F020
- `test/routes/test_card_routes.py`
- `test/e2e/test_cards.py`

**Shared factories to use** (pass the **local** subclass, never `api_utils.services` directly). Override the shared list method to `super()` then `CardService.project(...)` so the factory returns `Card[]`:

| Path prefix | Factory | Local service | Card type |
| --- | --- | --- | --- |
| `/api/cards/resources` | `create_resource_get_routes` | `ResourceService` | resources |
| `/api/cards/paths` | `create_path_get_routes` | `PathService` | paths |
| `/api/cards/plans` | `create_plan_get_routes` | `PlanService` | plans |
| `/api/cards/members` | `create_profile_get_routes` | `ProfileService` (members subclass / `name=`) | members |
| `/api/cards/mentees` | `create_profile_get_routes` | `ProfileService` (mentees subclass / distinct `name=`) | mentees |
| `/api/cards/notifications` | `create_notification_get_routes` | `NotificationService` | notifications |

If a factory also registers GET by-id, override that getter to project a Card as well. OpenAPI for this issue only requires the **list** GET (`Card[]`). Do not add `/me` on Profile.

**No shared factory** (local blueprint that mirrors the shared HTTP layer: token, breadcrumb, `parse_list_request`, service/helper, jsonify array):

| Path prefix | Source | Card type |
| --- | --- | --- |
| `/api/cards/customer` | Customer collection via `execute_list_query` / F030 helper | customer |
| `/api/cards/products` | Persisted source from Card type catalog + Config (see F030 Execution Notes) | products |
| `/api/cards/settings` | `Config.SETTING_COLLECTION_NAME` via `execute_list_query` / F030 helper | settings |

Members list is Profiles visible as org members (token `customer_id` when the caller has Customer or Coordinator). Mentees list is Profiles visible as that mentor’s mentees (token `mentor_id` when the caller has Mentor). If the shared Profile list is already scoped by outbound RBAC, projection-only is enough; if it is wider than the typed list, AND `customer_id` (members) or `mentor_id` (mentees) in the local subclass list override.

Register members and mentees as **two** `create_profile_get_routes` blueprints with unique `name=` values (and distinct local subclasses or list overrides). Do **not** use `create_mentee_get_routes` for this list — that factory is get-by-id only and does not return `Card[]`.

**MongoDB I/O**: still MongoIO / `execute_list_query` only. No `get_collection`.

Blueprint `name=` must be unique when several factories are registered.

## Goals

- Each typed path in the tables above is registered and returns `200` with a JSON array of Card.
- Shared-factory routes call local subclasses whose list methods return projected Cards.
- Local-only types use `parse_list_request` with an explicit filter_spec / order_spec (name contains and the collection’s sensible default sort, typically `name` asc, unless the Card/source schema says otherwise).
- `src/server.py` registers all typed prefixes. Home `GET /api/cards` from F040 still works.
- Route unit tests per type (or parameterized): mocked service returns a one-element Card list; body is a `list`; 401 without token.
- E2E: each typed GET returns 200 and a list (empty list is OK when seed data has no documents).
- `rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' src test docs/openapi.yaml` still zero hits.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/routes/test_card_routes.py` (and additional route test modules if you split by type) cover every typed list path
  - `test/test_server.py` — URL map contains `/api/cards/resources`, `/api/cards/paths`, `/api/cards/plans`, `/api/cards/members`, `/api/cards/mentees`, `/api/cards/notifications`, `/api/cards/customer`, `/api/cards/products`, `/api/cards/settings`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — `test/e2e/test_cards.py` covers typed paths (array body, auth required)

## Outputs

- `src/services/resource_service.py` — list (and by-id if present) project to Card
- `src/services/path_service.py` — same
- `src/services/plan_service.py` — same
- `src/services/profile_service.py` — members and mentees lists project to Card; optional `customer_id` / `mentor_id` AND (split subclasses if needed)
- `src/services/notification_service.py` — `get_notifications` used by the cards factory projects to Card **without** breaking dismiss/cancel/create return shapes used in F060 (if projection on GET would leak into mutations, keep a dedicated list wrapper or `project` only in a cards-specific subclass)
- `src/services/card_service.py` — customer / products / settings list helpers if not already present
- `src/routes/card_routes.py` and/or new `src/routes/*_routes.py` — typed blueprint factories
- `src/server.py` — register typed prefixes
- `test/routes/test_card_routes.py` — typed list tests (and new test modules if split)
- `test/test_server.py` — typed URL rules
- `test/e2e/test_cards.py` — typed GET coverage
- `test/services/test_card_service.py` — tests for any new typed helpers

The agent must not update files outside this list. Do not add Notification POST/dismiss/cancel here.

## Execution Notes

_Reserved for the task execution agent._
