# F040 – Custom GET /api/cards factory (home composite)

**Status**: Shipped  
**Type**: Feature  
**Depends On**: `F030_card_and_notification_services`  
**Description**: Add a local GET factory for `GET /api/cards` that returns the home composite Card array. Typed `/api/cards/{type}` lists are F050.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — HTTP layer is token, breadcrumb, parse, call service, jsonify; `handle_route_exceptions`; no payload mutation in routes
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — factory pattern to copy for the **custom** home factory (`_auth_context`, `_json_ok`, `parse_list_request` / `parse_pagination_headers`)
- `../mentorhub_api_utils/api_utils/flask_utils/list_request.py` — `parse_list_request`, `parse_pagination_headers`
- `src/services/card_service.py` — `get_home_cards`
- `src/server.py` — register the new blueprint
- `docs/openapi.yaml` — `GET /api/cards`
- `test/test_server.py`
- `test/e2e/e2e_auth.py`

Routes import **local** `CardService`, not `api_utils.services`. The home endpoint is custom because it aggregates three sources; do not use a shared GET factory for `GET /api/cards`.

**HTTP contract**

- `GET /api/cards`
- Bearer JWT required
- Pagination headers `offset` / `size` (defaults `0` / `20`, max `100`)
- `200` body: JSON array of Card
- Composite contents (service already implements): active Notifications for token `profile_id`; Members when roles include Customer or Coordinator (token `customer_id`); Mentees when roles include Mentor (token `mentor_id`)

## Goals

- `src/routes/card_routes.py` exposes `create_cards_get_routes()` (name may be `create_home_cards_get_routes`) that returns a Flask Blueprint:
  - `GET ""` → `create_flask_token`, `create_flask_breadcrumb`, parse pagination, `CardService.get_home_cards(...)`, `jsonify` array, `200`.
  - Decorate with `handle_route_exceptions`.
  - Do not validate or reshape Card payloads in the route.
- `src/server.py` registers the blueprint at `/api/cards` and logs the route.
- `test/test_server.py` asserts the `/api/cards` rule exists and Profile/Customer rules remain absent.
- Route unit tests mock `CardService.get_home_cards` and the token/breadcrumb helpers; assert `200` + `isinstance(body, list)`; unauthenticated token failure maps through `handle_route_exceptions`.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/routes/test_card_routes.py` — happy path array body; service called with token, breadcrumb, offset, size; 401 without a valid token
  - `test/test_server.py` — `/api/cards` registered
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` after adding `test/e2e/test_cards.py` for `GET /api/cards` (array body, 401 without bearer). If seed data is missing, assert status and type only.
  - `curl` of `/docs/openapi.yaml` still succeeds

Extend `test/e2e/e2e_auth.py` claims with `profile_id` / `customer_id` / `mentor_id` / `roles` only if required for a green e2e; keep the helper in this task’s Outputs if changed.

## Outputs

- `src/routes/card_routes.py` — create
- `src/server.py` — register `/api/cards`
- `test/routes/test_card_routes.py` — create
- `test/test_server.py` — assert `/api/cards`
- `test/e2e/test_cards.py` — create
- `test/e2e/e2e_auth.py` — update only if home e2e needs extra JWT claims

The agent must not update files outside this list. Do not add typed `/api/cards/{type}` routes here.

## Execution Notes

### Planned approach

1. `src/routes/card_routes.py` — new module copying the `shared_get_routes.py` factory style
   (`_auth_context`, `_json_ok`, module `logger`, `logger.info` on registration). Expose
   `create_cards_get_routes(*, name="card_routes")` returning a Blueprint with a single
   `GET ""` handler decorated with `handle_route_exceptions`. The handler calls
   `parse_pagination_headers(request)` — home is pagination-only, so no `parse_list_request`,
   no filter/order spec — then `CardService.get_home_cards(token, breadcrumb, offset, size)`
   and `_json_ok(cards)`. `CardService` is imported from `src.services.card_service`; no
   MongoIO, no payload reshaping.
2. `src/server.py` — import the factory with the other route imports and
   `app.register_blueprint(create_cards_get_routes(), url_prefix="/api/cards")`, plus a
   `/api/cards` line in the registered-routes log summary and a refreshed module docstring
   (Cards are no longer "follow-up").
3. `test/routes/test_card_routes.py` — build a throwaway Flask app around the blueprint;
   patch `src.routes.card_routes.create_flask_token` / `create_flask_breadcrumb` and
   `CardService.get_home_cards`. Assert 200 + list body, positional service args
   `(token, breadcrumb, offset, size)`, header-driven and default pagination, 401 when the
   token helper raises `HTTPUnauthorized`, and 400 when pagination validation rejects the
   headers.
4. `test/test_server.py` — extend the URL-map tests with a `/api/cards` assertion (and no
   typed `/api/cards/<type>` rules yet), keeping the Profile/Customer absence assertions.
5. `test/e2e/e2e_auth.py` — add the `profile_id` claim (24-hex, Developer Edition seed
   persona) because `create_flask_token` in api-utils 1.0.0 401s without it; keep the admin
   role.
6. `test/e2e/test_cards.py` — `@pytest.mark.e2e` black-box tests: 200 + JSON array with a
   bearer, every card's keys a subset of the Card schema and `type` (when present) inside the
   Card enum, and 401 without a bearer. Seed-data independent.
7. Verify with `pipenv run test`, `pipenv run lint`, `pipenv run build`,
   `pipenv run container`, `pipenv run api`, `pipenv run e2e`, and a `curl` of
   `/docs/openapi.yaml`.

### Summary

Implemented as planned; no deviations from the approach above.

- `src/routes/card_routes.py` (new) — `create_cards_get_routes(*, name="card_routes")`
  returns a Blueprint with one `GET ""` handler wrapped in `handle_route_exceptions`. The
  handler is token → breadcrumb → `parse_pagination_headers(request)` →
  `CardService.get_home_cards(token, breadcrumb, offset, size)` → `_json_ok(cards)`, with
  `_auth_context` / `_json_ok` / registration logging copied from
  `api_utils/routes/shared_get_routes.py`. `CardService` is the local
  `src.services.card_service` class; the module never touches MongoIO and never reshapes a
  Card. No typed `/api/cards/{type}` rules and no notification POST routes.
- `src/server.py` — registers the blueprint at `/api/cards`, logs the route in the
  registered-routes summary, and the module docstring now says the home Card list ships
  (typed lists and Notification control remain follow-ups).
- `test/routes/test_card_routes.py` (new, 9 tests) — blueprint mounted on a throwaway Flask
  app with the token/breadcrumb helpers and `CardService.get_home_cards` patched: 200 +
  list body, empty-array pass-through, payload returned unchanged, positional service call
  `(token, breadcrumb, offset, size)`, header pagination (`offset: 5` / `size: 10`) and the
  `0` / `20` defaults, breadcrumb built from the token, 401 when `create_flask_token` raises
  `HTTPUnauthorized`, 400 for `size` above `MAX_SIZE`, and 500 for a service failure.
- `test/test_server.py` — added `test_cards_route_registered`, an `/api/cards` entry in the
  URL-map test, and `test_typed_card_routes_not_registered_yet` (the only `/api/cards*` rule
  is `/api/cards`). The Profile/Customer absence assertions are unchanged.
- `test/e2e/e2e_auth.py` — **claims were added.** `profile_id`
  (`A00000000000000000000001`, the seeded admin Profile) is now in the payload because
  api-utils 1.0.0 `create_flask_token` 401s without it; the admin role, subject, and signing
  settings are unchanged. `get_auth_token(**claims)` now accepts claim overrides so a test
  can borrow the signing settings for another persona scope. `customer_id` / `mentor_id`
  were not needed.
- `test/e2e/test_cards.py` (new, 5 tests) — 200 + JSON array, every card's keys a subset of
  the Card schema with `type` inside the Card enum, active notifications projected as
  `Notification` cards for a seeded mentee persona (skips if the persona has no seeded
  notification), `offset`/`size` honored, 400 for `size: 101`, and 401 without a bearer.

### Commands and results

| Command | Result |
| --- | --- |
| `pipenv run test` | **84 passed**, 5 deselected, 9 subtests passed (9 new route tests, 3 new server tests) |
| `pipenv run lint` | **clean** — 19 files unchanged |
| `pipenv run build` | **clean** — `compileall` of `src/` |
| `pipenv run container` | **success** — `ghcr.io/mentor-forge/mentorhub_discovery_api:latest` |
| `pipenv run api` | mongodb + discovery-api containers up on `:8397` |
| `pipenv run e2e` | **5 passed**, 84 deselected |
| `curl /docs/openapi.yaml` | `200` |

Live container checks with a minted bearer: `GET /api/cards` → `200 []` for the admin
persona, `200` with a projected `Notification` card for the seeded mentee persona
(`A00000000000000000000002`) and a `Member` card for a Customer/Coordinator persona,
`size: 101` → `400 {"error":"size must be <= 100"}`, no bearer → `401`.

### Notes for later tasks

- The admin e2e persona sees an empty home array: it has no profile-scoped seeded
  notification, and the Members / Mentees sections are gated on Customer/Coordinator and
  Mentor roles. Seeded cards do flow (verified above), so F050 / F070 may want persona
  helpers in `e2e_auth.py` if they need richer seed-backed assertions.
- `_auth_context` and `_json_ok` are duplicated from `shared_get_routes.py` because
  api-utils does not export them; F050 should reuse the local copies in `card_routes.py`
  rather than adding a third.

### Orchestrator confirmation

Re-ran `pipenv run test` (84 passed, 5 e2e deselected), `pipenv run lint`, `pipenv run build`. Home blueprint is registered at `/api/cards` only; no typed prefixes yet. Status set to Shipped.
