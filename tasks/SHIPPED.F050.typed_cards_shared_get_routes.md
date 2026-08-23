# F050 – Typed GET /api/cards/{type} via shared GET factories

**Status**: Shipped  
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

**Plan**

1. `CardService._project_all` becomes public `project_all(card_type, documents)` so the consume
   services can project without reaching into a private helper. No behaviour change.
2. One Card-projecting subclass per consume service, registered with the shared factory:
   - `ResourceCardService` / `PathCardService` / `PlanCardService` — `super()` then project the
     list and the by-id document.
   - `MemberCardService` / `MenteeCardService` in `profile_service.py` — `get_profiles` delegates
     to `get_member_profiles` / `get_mentee_profiles` (identity scope already AND'd on there) and
     projects; `get_profile` projects the shared by-id read.
   - `NotificationCardService` in `notification_service.py` — projects `get_notifications` only.
3. **Notification projection isolation**: `NotificationService.get_notifications` is left
   untouched, so `create_notification`, `dismiss_notification`, and `cancel_notification` keep
   returning Notification documents for F060. Only the cards-only subclass bound to
   `create_notification_get_routes` projects.
4. `card_service.py` imports `notification_service` and `profile_service`, so those two modules
   import `CardService` at call time inside a small module-level projection helper rather than at
   module scope. `resource/path/plan_service.py` are not part of that cycle and import normally.
5. Customer / products / settings have no shared factory: `card_routes.py` gets a private local
   factory (token, breadcrumb, `parse_list_request` with the F030 specs, late-bound
   `CardService` getter so tests can patch it, jsonify array) wrapped by three named factories.
   `_auth_context` / `_json_ok` from F040 are reused.
6. `server.py` registers the nine typed prefixes with unique blueprint `name=` values; home
   `GET /api/cards` is unchanged.

**Decisions**

- The shared Resource/Path/Plan/Profile factories also mount a by-id GET. Those rules exist in the
  URL map but are not in `docs/openapi.yaml` (this issue documents the list GET only), so the
  by-id getters project a Card too rather than leaking a raw document.
- `/api/cards/notifications` lists every visible Notification (shared outbound RBAC), not just the
  active ones — that matches the F020 OpenAPI description. The active-only read stays on the
  composite home list.
- `test/test_server.py` swaps `test_typed_card_routes_not_registered_yet` for a positive URL-map
  assertion over every typed prefix, and adds a negative assertion that the Notification control
  routes are still absent until F060.

**Results**

- `pipenv run test` — 104 passed, 93 subtests passed, 35 deselected.
- `pipenv run lint` — clean; `pipenv run build` — clean.
- `rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' src test docs/openapi.yaml` —
  zero hits.
- `pipenv run container` / `pipenv run api` / `pipenv run e2e` — 33 passed, 2 skipped. The skips
  are `/api/cards/members` and `/api/cards/mentees`: the admin e2e persona carries no
  `customer_id` or `mentor_id`, so both lists are correctly empty.
- Spot checked against seed data: resources, paths, notifications, plans project their Card type;
  customer, products, and settings omit `type`; the factory by-id routes project a Card too.

**Follow-ups**

- `README.md` still says the typed Card lists "land in follow-up tasks" — F070 owns that file.
- The shared Resource/Path/Plan/Profile factories mount by-id GETs under the typed prefixes that
  `docs/openapi.yaml` does not document. Either document them or drop them once F060/F070 settle
  the surface.

### Orchestrator confirmation

Re-ran `pipenv run test` (104 passed, 35 e2e deselected), `pipenv run lint`, `pipenv run build`. Infinite-scroll grep still zero hits. Notification control routes still absent. Status set to Shipped.
