# Mentor Hub — Discovery API

## Prerequisites
- Mentor Hub [Developers Edition](https://github.com/mentor-forge/mentorhub/blob/main/CONTRIBUTING.md)
- Developer [API Standard Prerequisites](https://github.com/mentor-forge/mentorhub/blob/main/DeveloperEdition/standards/api_standards.md)

## Developer Commands

```bash
## Install dependencies (run `mh` first for CodeArtifact auth)
pipenv run install

# start backing db container
pipenv run db

## run unit tests
pipenv run test

## run api server in dev mode - serves API at localhost:8397
pipenv run dev

## run E2E tests (assumes running API at localhost:8397)
pipenv run e2e

## run tests with coverage report
pipenv run coverage

## build application (pre-compiles Python code)
pipenv run build

## build container
pipenv run container

## Run the backing database and api containers
pipenv run api

## Run the full microservice (db+api+spa)
pipenv run service

## format code
pipenv run format

## lint code
pipenv run lint
```

## Project Structure

- `src/` - Main package containing:
  - `server.py` - API entrypoint
  - `routes/` - HTTP request/response handlers
  - `services/` - Business logic and RBAC for collections this API controls

- `test/` - Test suite with matching directory structure:
  - `routes/` - Route unit tests
  - `services/` - Service unit tests
  - `e2e/` - End-to-end tests flagged with `@pytest.mark.e2e`

## api-utils notes

This API pins **`api-utils==1.0.0`** from CodeArtifact. In 1.0.0, list GETs return a plain JSON
**array** and paginate with the `offset` and `size` **request headers** (defaults `0` / `20`, max
`100`) — there is no cursor envelope and no infinite-scroll helper. MongoDB I/O goes through
`MongoIO` (`get_document`, `get_documents`, `create_document`, `update_document`,
`upsert_document`) rather than PyMongo collections.

The earlier Customer and Profile infinite-scroll list/get endpoints have been retired. The
Discovery **Card** and **Notification** endpoints that replace them land in follow-up tasks; today
this API serves the standard config, docs, and metrics endpoints only.

## API Endpoints

See the [Open API Specifications](./docs/openapi.yaml) for details on the API.

For E2E, mint a Bearer token via `test/e2e/e2e_auth.py` (`get_auth_token()`) with `pipenv run dev` (matching `JWT_SECRET`).

### Simple Curl Commands:
```bash
# Bearer token for local dev (same JWT settings as pipenv run dev / e2e):
export TOKEN="$(PYTHONPATH=. pipenv run python -c 'from test.e2e.e2e_auth import get_auth_token; print(get_auth_token())')"

# Get the API Configuration
curl http://localhost:8397/api/config \
  -H "Authorization: Bearer $TOKEN"

```
