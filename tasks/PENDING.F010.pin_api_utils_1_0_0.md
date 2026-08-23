# F010 – Pin api-utils 1.0.0 and strip infinite-scroll surface

**Status**: Pending  
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

_Reserved for the task execution agent._
