# F040 – Custom GET /api/cards factory (home composite)

**Status**: Pending  
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

_Reserved for the task execution agent._
