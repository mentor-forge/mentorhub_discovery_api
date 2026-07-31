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
  - `routes/` - HTTP request/response handlers (`customer_routes`, `profile_routes`)
  - `services/` - Local business logic for customer/profile list-get patterns

- `test/` - Test suite with matching directory structure:
  - `routes/` - Route unit tests
  - `services/` - Service unit tests
  - `e2e/` - End-to-end tests flagged with `@pytest.mark.e2e`

## api-utils migration notes (F-W18 bootstrap)

Bootstrapped from `mentorhub_customer_api` with **api-utils 0.2.1 → 0.5.2**.

| Service | Status | Notes |
|---------|--------|-------|
| `CustomerService` | **Local** (`src/services/customer_service.py`) | No `api_utils.services.CustomerService` yet; harvest tracked for F-UA08 / F-DA01. Uses `Config.CUSTOMER_COLLECTION_NAME` (no local `_collection_name()` fallback). |
| `ProfileService` | **Local** (`src/services/profile_service.py`) | Discovery uses infinite-scroll list/get, not the mentor-dashboard `api_utils.services.ProfileService`. Do not swap imports until a shared list/get implementation is harvested (F-UA08). |

Follow-up (F-DA01): dashboard aggregate and notification dismiss routes; ingress (Stripe/Cognito webhooks) moves to Admin API (F-AA01).

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
