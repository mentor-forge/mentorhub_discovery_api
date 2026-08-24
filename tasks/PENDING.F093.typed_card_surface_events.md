# F093 – Retire doomed typed Card lists and add GET /api/cards/events

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F092_home_cards_composite`  
**Description**: After home carries Customer / Member / Mentee / Admin / Journey cards, delete the doomed typed Card routes and register `GET /api/cards/events` in the same pass so `server.py` and URL-map tests are edited once.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — MongoIO only; bind shared GET factories to **local** subclasses
- `README.md`
- `docs/openapi.yaml` — F090 remaining typed paths
- `src/server.py` — current typed registrations
- `src/routes/card_routes.py` — local customer/products/settings factories; `register_list_only_blueprint`
- `src/services/card_service.py` — `get_customer_cards` / `get_product_cards` / `get_settings_cards` (home no longer needs the Product/Setting **lists**)
- `src/services/profile_service.py` — `MemberCardService` / `MenteeCardService` exist only for typed lists; keep `ProfileService.get_member_profiles` / `get_mentee_profiles` for home
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — `create_event_get_routes` is **list-only** (optional `profile_id` query). `create_resource_get_routes` / `create_path_get_routes` / `create_plan_get_routes` still need `register_list_only_blueprint`
- `../mentorhub_api_utils/api_utils/services/event_service.py` — `EventService.get_events`, `EVENT_LIST_FILTERS`, `EVENT_LIST_ORDER`
- `test/test_server.py` — `TYPED_CARD_PATHS`
- `test/routes/test_card_routes.py`
- `test/services/test_card_service.py`
- `test/e2e/test_cards.py`

**Doomed prefixes (delete routes, OpenAPI already dropped them in F090):**

| Prefix | Remove |
| --- | --- |
| `/api/cards/customer` | local factory `create_customer_cards_get_routes` |
| `/api/cards/products` | local factory `create_product_cards_get_routes` |
| `/api/cards/settings` | local factory `create_settings_cards_get_routes` |
| `/api/cards/members` | `create_profile_get_routes(MemberCardService, …)` |
| `/api/cards/mentees` | `create_profile_get_routes(MenteeCardService, …)` |

**Keep:** home `/api/cards`, `resources`, `paths`, `plans`, `notifications`, Notification control.

**Add:** `/api/cards/events`

- New local `src/services/event_service.py`: thin `EventService(SharedEventService)` plus `EventCardService` whose `get_events` calls `super().get_events(...)` then `CardService.project_all` with Card type Event.
- Event documents have `type` (enum), `context`, `created` — no `name` / `description`. Projection: Card `name` from Event `type`, omit `description` unless a real source field exists, Card `type` `"Event"`, `link` `mentee/event/{id}` (F090), `_id` passed through.
- Register with `create_event_get_routes(EventCardService, name="event_card_routes")` at `/api/cards/events`. Do **not** wrap in `register_list_only_blueprint` (factory is already list-only).
- Pass `token` into `project_all` so Event links are set.

After this task, `create_profile_get_routes` should have **no** Card registrations. Drop `MemberCardService` / `MenteeCardService` if nothing else imports them. Drop `get_customer_cards` / `get_product_cards` / `get_settings_cards` and `CARD_TYPE_CUSTOMER` / `PRODUCTS` / `SETTINGS` specs if unused. Keep `NAME_LIST_*` only if still referenced.

Do **not** change `api_utils`. Do **not** add Event POST (Discovery still creates Event elsewhere; this issue is the Card list only).

## Goals

- Flask URL map contains `/api/cards`, `/api/cards/resources`, `/api/cards/paths`, `/api/cards/plans`, `/api/cards/notifications`, `/api/cards/events` and **not** customer/members/mentees/products/settings.
- Unauthenticated GET of a doomed prefix is **404** (not 401).
- `GET /api/cards/events` returns `200` + JSON array of Cards with `type` Event (empty list OK); `401` without bearer.
- Resource/Path/Plan still register through `register_list_only_blueprint` (by-id stays 404).
- Home `get_home_cards` still works (Member/Mentee data still comes from `ProfileService` helpers).
- `rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' src test docs/openapi.yaml` remains zero hits.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/test_server.py` — `TYPED_CARD_PATHS` is the five kept typed lists; doomed prefixes absent; events present; doomed by-id-style URLs 404; Event list has no by-id rule
  - `test/routes/test_card_routes.py` — drop customer/products/settings/members/mentees cases; add events (mock `EventCardService.get_events`); keep home + resources/paths/plans/notifications
  - `test/services/test_card_service.py` — drop Product/Setting/Customer **list** tests; add Event `project` (name from Event `type`, link `mentee/event/{id}`)
  - New `test/services/test_event_service.py` if the subclass is non-trivial (list projects to Card; there is no local create override required)
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — `test/e2e/test_cards.py` typed paths are resources/paths/plans/notifications/events only; doomed prefixes 404; events 200 + array + `type` Event when seed Events exist (skip type assertion if empty)
  - `curl -s http://localhost:8397/docs/openapi.yaml` — `/api/cards/events` present; `/api/cards/members` absent

## Outputs

- `src/server.py` — unregister doomed typed blueprints; register `/api/cards/events`
- `src/routes/card_routes.py` — delete customer/products/settings factories if unused
- `src/services/event_service.py` — create (`EventService` + `EventCardService`)
- `src/services/__init__.py` — export Event service if the package exports others
- `src/services/card_service.py` — Event `CARD_TYPE_*` spec; remove unused Customer/Product/Setting list helpers
- `src/services/profile_service.py` — remove `MemberCardService` / `MenteeCardService` if unused; keep scoped Profile list helpers
- `test/test_server.py`
- `test/routes/test_card_routes.py`
- `test/services/test_card_service.py`
- `test/services/test_event_service.py` — create if needed
- `test/e2e/test_cards.py` — typed path set + doomed 404 + events list

The agent must not update files outside this list. Do not edit OpenAPI (already done in F090). README is F094.

## Execution Notes
