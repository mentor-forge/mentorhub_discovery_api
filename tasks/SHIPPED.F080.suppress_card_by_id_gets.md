# F080 – Suppress typed Card GET-by-id routes

**Status**: Shipped  
**Type**: Defect  
**Depends On**: `F070_readme_e2e_and_packaging`  
**Description**: Remove the undocumented GET-by-id routes that shared `api-utils` GET factories mount under typed `/api/cards/{type}` prefixes. Discovery’s public Card contract is list-only (`Card[]`). Do not change `api-utils`.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `README.md` — currently notes shared-factory by-id GETs (e.g. `/api/cards/resources/{id}`) as an undocumented side effect
- `docs/openapi.yaml` — documents list GETs only; no Card by-id paths
- `src/server.py` — registers shared factories at `/api/cards/resources`, `/api/cards/paths`, `/api/cards/plans`, `/api/cards/members`, `/api/cards/mentees`
- `src/routes/card_routes.py` — home + local list-only factories for customer/products/settings
- `../mentorhub_api_utils/api_utils/routes/shared_get_routes.py` — `create_resource_get_routes`, `create_path_get_routes`, `create_plan_get_routes`, and `create_profile_get_routes` each register GET list **and** GET `/<id>`; `create_notification_get_routes` is already list-only
- `src/services/resource_service.py` — `ResourceCardService.get_resource` exists only to project the by-id GET
- `src/services/path_service.py` — `PathCardService.get_path`
- `src/services/plan_service.py` — `PlanCardService.get_plan`
- `src/services/profile_service.py` — `MemberCardService.get_profile` / `MenteeCardService.get_profile`
- `test/test_server.py`
- `test/routes/test_card_routes.py`
- `test/services/test_card_service.py` — `CARD_SUBCLASS_GETTERS` / by-id projection tests
- `test/e2e/test_cards.py`

**Do not** change files in `../mentorhub_api_utils`. Keep using the shared list factories for the five typed lists that have them; only suppress the by-id URL rules they add.

Customer, products, settings, notifications, and home are already list-only. Leave those prefixes unchanged except for any tests that should assert they still have no by-id GET.

**MongoDB I/O**: still MongoIO / `execute_list_query` only. Routes must not open collections.

## Goals

- After registration, the Flask URL map has **no** GET-by-id rule under:
  - `/api/cards/resources/<id>`
  - `/api/cards/paths/<id>`
  - `/api/cards/plans/<id>`
  - `/api/cards/members/<id>`
  - `/api/cards/mentees/<id>`
- `GET /api/cards/{type}` list routes still return `200` with a JSON array of Card (401 without bearer).
- `GET /api/cards/resources/<24-hex>` (and the other four prefixes) returns **404**, not a Card.
- Home `GET /api/cards`, local typed lists, `GET /api/cards/notifications`, and Notification control POSTs are unchanged.
- `README.md` no longer describes by-id Card GETs as part of the Discovery surface (remove the shared-factory side-effect paragraph).
- Drop Card-subclass `get_*` by-id overrides and their unit tests if they exist only to serve those routes (`get_resource`, `get_path`, `get_plan`, `get_profile` on the Card-projecting subclasses). Keep list projection (`get_resources` / `get_paths` / `get_plans` / `get_profiles`).
- Implementation stays in this API: wrap or post-process the shared-factory blueprints (for example strip rules whose path has arguments after `register_blueprint`). Do not fork the shared factories in `api-utils`.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/test_server.py` — URL map contains each typed **list** path and does **not** contain by-id rules for resources/paths/plans/members/mentees; an unauthenticated GET of a by-id URL is 404 (not 401)
  - `test/routes/test_card_routes.py` — list coverage unchanged; no remaining tests that expect a typed by-id 200
  - `test/services/test_card_service.py` — list projection tests remain; by-id getter projection tests removed if the methods are removed
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — existing card list tests still pass; add (or extend) `test/e2e/test_cards.py` so one typed prefix by-id GET is 404 with and without bearer
  - `curl -s http://localhost:8397/docs/openapi.yaml` — still has `/api/cards/resources` list and no by-id Card path

## Outputs

- `src/routes/card_routes.py` and/or `src/server.py` — suppress by-id rules from the five shared-factory blueprints
- `src/services/resource_service.py` — remove `ResourceCardService.get_resource` if unused
- `src/services/path_service.py` — remove `PathCardService.get_path` if unused
- `src/services/plan_service.py` — remove `PlanCardService.get_plan` if unused
- `src/services/profile_service.py` — remove Card-subclass `get_profile` if unused
- `test/test_server.py` — assert by-id Card routes are absent / 404
- `test/routes/test_card_routes.py` — drop by-id happy-path tests if present
- `test/services/test_card_service.py` — drop by-id projection tests if methods are removed
- `test/e2e/test_cards.py` — by-id 404 coverage
- `README.md` — remove the undocumented by-id GET note

The agent must not update files outside this list. Do not add OpenAPI by-id paths. Do not change Notification control routes.

## Execution Notes

### Plan

1. Add `register_list_only_blueprint(app, blueprint, url_prefix)` to
   `src/routes/card_routes.py`. It shadows `app.add_url_rule` for the duration of
   one `register_blueprint` call and drops any rule whose URL carries a path
   argument, then restores the bound method. Flask's `BlueprintSetupState`
   resolves the full URL before calling `app.add_url_rule`, so a rule containing
   `<` is exactly the shared factory's by-id rule. Nothing in `api_utils`
   changes, the list rule registers normally, and the suppressed view function
   never lands in `app.view_functions`.
2. `src/server.py` registers the five shared-factory Card blueprints
   (`resources`, `paths`, `plans`, `members`, `mentees`) through the helper.
   Home, the local typed lists, notifications, and the Notification control
   blueprint keep plain `register_blueprint` — they are already list-only.
3. Drop the by-id Card projections that only fed the suppressed routes:
   `ResourceCardService.get_resource`, `PathCardService.get_path`,
   `PlanCardService.get_plan`, and `get_profile` on `MemberCardService` /
   `MenteeCardService`. The unprojected shared by-id reads stay inherited.
4. Tests: `test/test_server.py` asserts the URL map has no rule under the five
   typed prefixes with an argument and that an unauthenticated by-id GET is 404
   (auth never runs, so it must not be 401); `test/routes/test_card_routes.py`
   covers the helper directly (list rule kept, by-id rule and view function
   dropped, plain registration still mounts by-id); `test_card_service.py` loses
   `CARD_SUBCLASS_GETTERS` and the by-id projection test;
   `test/e2e/test_cards.py` adds by-id 404 coverage with and without a bearer.
5. `README.md` loses the shared-factory by-id side-effect paragraph.

### Decisions

- Suppression happens at registration rather than by mutating `app.url_map`
  afterwards. Werkzeug 3's `Map` has no rule removal API, so post-processing
  would mean rebuilding the map and hand-pruning `view_functions`; intercepting
  the one registration call keeps the by-id rule from ever existing.
- The filter keys on "the URL has a path argument" instead of naming each
  suppressed rule, so a future shared factory that adds another parameterized
  GET under a Card prefix stays suppressed by default.

### Results

- `pipenv run test` — 140 passed, 134 subtests passed, 58 e2e deselected.
- `pipenv run lint` — 22 files unchanged. `pipenv run build` — clean.
- `pipenv run container` — image built. `pipenv run api` — stack up on 8397.
- `pipenv run e2e` — 58 passed (10 new by-id 404 checks: five prefixes with and
  without a bearer).
- `curl http://localhost:8397/docs/openapi.yaml` — the ten Card list paths are
  there, `/api/cards/resources` included, and no Card by-id path.
- Manual container checks: `GET /api/cards/resources` is 200 with a bearer and
  401 without; all five `/{prefix}/665f1c2a9b1e4c0a1b2c3d21` URLs are 404 with
  and without a bearer; home and `/api/cards/notifications` are still 200.

### Follow-ups

- `api_utils`'s `create_resource_get_routes`, `create_path_get_routes`,
  `create_plan_get_routes`, and `create_profile_get_routes` still couple the list
  GET to a by-id GET. A shared change that lets a caller ask for the list rule
  only (as `create_notification_get_routes` already is) would let Discovery drop
  `register_list_only_blueprint`. That is an `api-utils` task, out of scope here.
- The shared by-id reads stay inherited on `ResourceCardService`,
  `PathCardService`, `PlanCardService`, `MemberCardService`, and
  `MenteeCardService` (unprojected, from the shared base). Nothing calls them;
  `test_card_service.py` now asserts none of the subclasses override them.

### Orchestrator confirmation

Re-ran `pipenv run test` (140 passed, 58 e2e deselected), `pipenv run lint`, `pipenv run build`. Typed Card by-id GETs are 404; list GETs remain. Status set to Shipped.
