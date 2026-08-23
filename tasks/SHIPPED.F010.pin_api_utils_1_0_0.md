# F010 – Pin api-utils 1.0.0 and strip infinite-scroll surface

**Status**: Shipped  
**Type**: Feature  
**Depends On**: none  
**Description**: Pin `api-utils==1.0.0` and remove the Discovery API’s Customer/Profile infinite-scroll routes, services, and tests so the package can import. 1.0.0 does not export `execute_infinite_scroll_query`. This task leaves only standard config, metrics, and docs endpoints; Card and Notification work lands in later tasks.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — pin `api-utils==1.0.0`; standardized Get List (JSON array, `offset`/`size` headers); no infinite-scroll helper
- `Pipfile` — currently `api-utils==0.5.2`
- `src/server.py` — registers `/api/profile` and `/api/customer`
- `src/services/customer_service.py`
- `src/services/profile_service.py`
- `src/routes/customer_routes.py`
- `src/routes/profile_routes.py`
- `docs/openapi.yaml`
- `test/test_server.py`

**External prerequisite**: `api-utils==1.0.0` must be available on the CodeArtifact index. If `pipenv run install` cannot resolve 1.0.0, set **Status** to `Blocked` and stop.

**Why the strip is required in this task**: 1.0.0 will not import while local services still call `execute_infinite_scroll_query`. This issue is a full front-to-back refactor; later tasks replace Customer/Profile list/get with Card and Notification endpoints. Do not keep a local copy of the infinite-scroll helper. Do not migrate Customer/Profile to `execute_list_query` as a standing public API.

**MongoDB I/O**: Any remaining service code must use `MongoIO` (`get_document`, `get_documents`, `create_document`, `update_document`, `upsert_document`). Do not call PyMongo through `mongo.get_collection(...)`.

## Goals

- `Pipfile` and `Pipfile.lock` pin `api-utils==1.0.0` (CodeArtifact index unchanged).
- Dependencies are installed with `pipenv run install` (run `mh` first in the shell if CodeArtifact credentials are missing). Do **not** use bare `pipenv install`.
- These modules and their tests are **deleted** (not rewritten):
  - `src/services/customer_service.py`
  - `src/services/profile_service.py`
  - `src/routes/customer_routes.py`
  - `src/routes/profile_routes.py`
  - `test/services/test_customer_service.py`
  - `test/services/test_profile_service.py`
  - `test/routes/test_customer_routes.py`
  - `test/routes/test_profile_routes.py`
  - `test/e2e/test_customer.py`
  - `test/e2e/test_profile.py`
- `src/server.py` no longer imports or registers Customer or Profile blueprints. Keep explorer (`/docs`), config (`/api/config`), and metrics (`/metrics`).
- `docs/openapi.yaml` no longer documents `/api/profile`, `/api/customer`, or Profile/Customer component schemas. Keep Config, Metrics, Error, and bearer auth.
- `test/test_server.py` no longer asserts Profile/Customer blueprints or URL rules. It still asserts config, docs, metrics, and that credential-minting routes are absent.
- Zero remaining references to `execute_infinite_scroll_query`, `after_id`, `has_more`, or `next_cursor` in `src/`, `test/`, or `docs/openapi.yaml`.
- `README.md` no longer describes Customer/Profile infinite-scroll endpoints or the 0.5.2 bootstrap table as current behavior. A short note that Card/Notification endpoints land in follow-up tasks is enough.

## Testing Expectations

Run all commands from this API repository root.

- **Install**
  - `mh` once per shell if CodeArtifact credentials are not already available
  - `pipenv run install`
- **Confirmation**
  - `rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' --glob '*.py' --glob 'docs/openapi.yaml'` — zero hits
  - `rg 'customer_service|profile_service|create_customer_routes|create_profile_routes' src test` — zero hits
- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — served and no longer contains `/api/profile` or `/api/customer`
  - `pipenv run e2e` if any e2e tests remain; if the e2e folder only has auth helpers, the OpenAPI curl above is the packaging check

## Outputs

- `Pipfile` — pin `api-utils==1.0.0`
- `Pipfile.lock` — refresh via `pipenv run install`
- `src/server.py` — drop Customer/Profile registration
- `docs/openapi.yaml` — remove Profile and Customer paths and schemas
- `test/test_server.py` — drop Profile/Customer assertions
- `README.md` — remove current Customer/Profile infinite-scroll documentation
- **Delete** `src/services/customer_service.py`
- **Delete** `src/services/profile_service.py`
- **Delete** `src/routes/customer_routes.py`
- **Delete** `src/routes/profile_routes.py`
- **Delete** `test/services/test_customer_service.py`
- **Delete** `test/services/test_profile_service.py`
- **Delete** `test/routes/test_customer_routes.py`
- **Delete** `test/routes/test_profile_routes.py`
- **Delete** `test/e2e/test_customer.py`
- **Delete** `test/e2e/test_profile.py`

The agent must not update files outside this list.

## Execution Notes

### Planned approach

1. **Pin the dependency.** Change `api-utils = {version = "==0.5.2", index = "codeartifact"}` to
   `==1.0.0` in `Pipfile`, keeping the single CodeArtifact `[[source]]` and the inline comment
   explaining why the index matters. Regenerate `Pipfile.lock` against CodeArtifact
   (`scripts/pipenv-lock.sh`, which is what refreshes the lock hashes `pipenv run install` then
   consumes via `pipenv requirements --dev`), then install with `pipenv run install`. Run `mh`
   first if CodeArtifact credentials are stale. If 1.0.0 will not resolve, set Status to Blocked
   and stop.
2. **Delete the Customer/Profile surface** rather than migrating it: the four `src/` modules
   (`customer_service.py`, `profile_service.py`, `customer_routes.py`, `profile_routes.py`) plus
   their six test modules (`test/services/`, `test/routes/`, `test/e2e/test_customer.py`,
   `test/e2e/test_profile.py`). Both services call `mongo.get_collection(...)` +
   `execute_infinite_scroll_query`, neither of which survives in 1.0.0, and the task explicitly
   forbids a local copy of the helper or a stopgap `execute_list_query` migration. Card and
   Notification endpoints replace this surface in F020–F070. Keep `test/e2e/e2e_auth.py` and the
   package `__init__.py` files so the empty test packages and the README token recipe still work.
3. **`src/server.py`** — drop the two `src.routes.*` imports, the two `register_blueprint` calls,
   and the two route-summary log lines. Keep explorer (`/docs`), config (`/api/config`), and
   metrics (`/metrics`), the Config/MongoIO singleton bootstrap, the signal handlers, and
   `DISCOVERY_API_PORT`. Retitle the module docstring since the server is now config/metrics/docs
   only.
4. **`docs/openapi.yaml`** — remove the four Profile/Customer paths, the `Profile`/`Customer`
   component schemas, and the `Profile`/`Customer` tags. That also removes every `after_id`,
   `has_more`, and `next_cursor` mention. Keep Config, Metrics, `Error`, `bearerAuth`, and the
   `BadRequest`/`Unauthorized`/`NotFound`/`InternalError` shared responses so later tasks can
   reference them. Update the `info.description` away from "customer and profile list/get".
5. **`test/test_server.py`** — delete `test_profile_routes_registered`,
   `test_customer_routes_registered`, and the blueprint-name assertions; convert the URL-map
   assertions to assert Profile/Customer are *absent* alongside the existing docs/config/metrics
   assertions and the credential-minting negative check.
6. **`README.md`** — drop the F-W18 0.5.2 bootstrap table and the Customer/Profile
   infinite-scroll wording, describe the now-minimal `src/` layout, note that Card and
   Notification endpoints land in follow-up tasks, and point the api-utils note at pinned 1.0.0
   (JSON-array list GETs with `offset`/`size` headers, no cursor envelope).
7. **Verify** with the task's Testing Expectations: the two `rg` zero-hit confirmations, then
   `pipenv run test`, `lint`, `build`, `container`, `api`, and a `curl` of
   `/docs/openapi.yaml`. No e2e tests remain after the deletions, so the curl is the packaging
   check per the task.

### Summary of changes

`api-utils==1.0.0` resolved and installed from CodeArtifact, so this task is **not** blocked.
Confirmed in the running container that 1.0.0 does not export the helper the old services
depended on: `hasattr(api_utils.mongo_utils, "execute_infinite_scroll_query") == False`, which is
exactly why the strip had to land in the same task as the pin.

**Modified (6)**

- `Pipfile` — `api-utils` pinned `==0.5.2` → `==1.0.0`, still `index = "codeartifact"`; the
  single `[[source]]` and the "must use codeartifact index" comment are unchanged.
- `Pipfile.lock` — regenerated against CodeArtifact; `api-utils` now `"version": "==1.0.0"` with
  refreshed hashes. Transitive bumps came along: `charset-normalizer` 3.4.9→3.5.1,
  `coverage` 7.15.2→7.15.4, `idna` 3.18→3.19, `nh3` 0.3.6→0.3.7, `packaging` 26.2→26.3,
  `setuptools`, `platformdirs`, `pygments`.
- `src/server.py` — removed both `src.routes.*` imports, both `register_blueprint` calls for
  `/api/profile` and `/api/customer`, and their two route-summary log lines. Module docstring now
  says config/docs/metrics and points at the follow-up tasks. Config/MongoIO bootstrap,
  `MongoJSONEncoder`, explorer/config/metrics registration, signal handlers, and
  `DISCOVERY_API_PORT = 8397` all unchanged.
- `docs/openapi.yaml` — dropped the `Profile` and `Customer` tags, all four paths
  (`/api/profile`, `/api/profile/{profile_id}`, `/api/customer`, `/api/customer/{customer_id}`),
  and the `Profile`/`Customer` component schemas. That removed every `after_id` / `has_more` /
  `next_cursor` occurrence. Kept `/api/config`, `/metrics`, `bearerAuth`, the `Error` schema, and
  the shared `BadRequest`/`Unauthorized`/`NotFound`/`InternalError` responses so F020 can
  reference them. `info.description` now notes Card/Notification arrive in follow-up tasks.
  429 → 124 lines.
- `test/test_server.py` — removed `test_profile_routes_registered`,
  `test_customer_routes_registered`, and `test_all_blueprints_registered` (it only asserted the
  two deleted blueprints). `test_url_map_contains_expected_routes` keeps docs/config/metrics plus
  the credential-minting negative check. Added `test_docs_route_registered` (the explorer had no
  direct coverage) and `test_retired_domain_routes_not_registered`, which asserts `/api/profile`
  and `/api/customer` are **absent** from the URL map so the strip cannot silently regress.
- `README.md` — deleted the "api-utils migration notes (F-W18 bootstrap)" section, including the
  0.5.2 bootstrap table and the F-DA01/F-AA01 follow-up line. Replaced it with an "api-utils
  notes" section stating the pinned 1.0.0 contract (list GET = JSON array, `offset`/`size`
  request headers, defaults 0/20 max 100, no cursor envelope, no infinite-scroll helper, MongoIO
  for all Mongo I/O) and noting the retired Customer/Profile endpoints are replaced by Card and
  Notification endpoints in follow-up tasks. Project-structure bullets no longer name
  `customer_routes` / `profile_routes`.

**Deleted (10)** — all as listed in Outputs: `src/services/customer_service.py`,
`src/services/profile_service.py`, `src/routes/customer_routes.py`,
`src/routes/profile_routes.py`, `test/services/test_customer_service.py`,
`test/services/test_profile_service.py`, `test/routes/test_customer_routes.py`,
`test/routes/test_profile_routes.py`, `test/e2e/test_customer.py`, `test/e2e/test_profile.py`.

Kept `test/e2e/e2e_auth.py` and every package `__init__.py`, so `src/routes/`, `src/services/`,
`test/routes/`, and `test/services/` are now empty packages awaiting F020–F070. No file outside
the Outputs list was touched (`git status` matches the Outputs list exactly). No local copy of the
infinite-scroll helper was kept, and Customer/Profile were **not** migrated to
`execute_list_query`. No remaining service code calls `mongo.get_collection(...)` — the only two
callers were the deleted services, and `src/` now has no service code at all.

### Commands run

| Command | Result |
|---|---|
| `aws sts get-caller-identity --profile mentorhub-shared` | OK — CodeArtifact creds already valid, so `mh` was not needed |
| `sh scripts/pipenv-lock.sh` | ✅ exit 0 — `api-utils==1.0.0` resolved; `Updated Pipfile.lock (e905a816…)` |
| `pipenv run install` | ✅ exit 0 — `Successfully installed api-utils-1.0.0 …` (uninstalled `api_utils-0.5.2`) |
| `rg 'execute_infinite_scroll_query\|after_id\|has_more\|next_cursor' --glob '*.py' --glob 'docs/openapi.yaml'` | ✅ **zero hits** (rg exit 1) |
| `rg 'customer_service\|profile_service\|create_customer_routes\|create_profile_routes' src test` | ✅ **zero hits** (rg exit 1) |
| `rg -i 'customer\|profile' src test docs/openapi.yaml` | 3 hits, all intentional — the new negative-assertion test and its docstring |
| `pipenv run test` | ✅ **16 passed** in 0.09s |
| `pipenv run lint` | ✅ `All done! 8 files would be left unchanged.` |
| `pipenv run build` | ✅ exit 0 (`compileall` clean) |
| `pipenv run container` | ✅ built `ghcr.io/mentor-forge/mentorhub_discovery_api:latest` → `sha256:fc5ff893bb7e…` (only pre-existing `JSONArgsRecommended` CMD warning) |
| `pipenv run api` | ✅ mongodb healthy, `mentorhub-discovery_api-1` started on the freshly built image (verified `docker inspect` image digest == build digest) |
| `curl -s http://localhost:8397/docs/openapi.yaml` | ✅ **200**, 3638 bytes; served paths are only `/api/config` and `/metrics`; grep for `api/profile\|api/customer\|after_id\|has_more\|next_cursor` → **zero hits** |
| `pipenv run e2e` | 16 deselected / **0 selected** — no e2e tests remain (only `e2e_auth.py`), so per the task the OpenAPI curl is the packaging check |

Live endpoint checks against the container: `/metrics` → 200, `/docs/openapi.yaml` → 200,
`/api/config` → 401 (auth required, route present), `/api/profile` → **404**, `/api/customer` →
**404**. `docker exec … pip show api-utils` → `Version: 1.0.0`. Stack torn down with `mh down`
afterwards; `__pycache__` / `.pyc` build artifacts cleaned (all gitignored).

### Findings for the orchestrator

1. **`test/e2e/e2e_auth.py` needs a `profile_id` claim for api-utils 1.0.0.** An authenticated
   `GET /api/config` with a token minted by `get_auth_token()` returns
   `401 {"error":"Missing profile_id claim"}`. The signature, `iss`, and `aud` all validate (a
   garbage token fails earlier with an `Invalid token` decode error), so this is purely the new
   1.0.0 token contract: 1.0.0 RBAC scopes callers by token `profile_id` / `customer_id` /
   `mentor_id`, and the helper's payload only carries `iss`, `aud`, `sub`, `iat`, `exp`, `roles`.
   `e2e_auth.py` is **not** in this task's Outputs, so it was left untouched. Whichever task first
   adds real e2e coverage (F040+) must add the claim, or every e2e request will 401.
2. **Pre-existing, unrelated:** the README token recipe
   `PYTHONPATH=. pipenv run python -c 'from test.e2e.e2e_auth import get_auth_token; …'` fails with
   `ModuleNotFoundError: No module named 'test.e2e'`. There is no `test/__init__.py` (confirmed
   never tracked via `git ls-files`), so the local `test/` is a namespace package and Python's
   **stdlib `test` package wins** (`import test` resolves to
   `…/python3.12/lib/python3.12/test/__init__.py`). `pipenv run e2e` is unaffected because pytest
   imports test modules by path. Not caused by this task and not fixed here; worth a small
   follow-up task.
3. `src/server.py` still has a pre-existing unused `from flask import … send_from_directory`.
   Left alone as unrelated to this task; `black` does not flag it.
4. `src/routes/`, `src/services/`, `test/routes/`, and `test/services/` are now empty packages
   (only `__init__.py`). Intentional — F020–F070 repopulate them. Unit coverage is currently
   `test/test_server.py` only.
5. Status left as **Running** per instructions; no commit was made.

### Orchestrator confirmation

Re-ran `pipenv run test` (16 passed), `pipenv run lint`, `pipenv run build`, `pipenv run container`, `pipenv run api`, and `curl -s http://localhost:8397/docs/openapi.yaml` (200; only `/api/config` and `/metrics`; zero retired-path hits). Status set to Shipped.
