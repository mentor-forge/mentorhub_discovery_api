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
  - `server.py` - API entrypoint and blueprint registration
  - `routes/` - HTTP request/response handlers
    - `card_routes.py` - composite home list plus the Customer, Product, and Setting typed lists
    - `notification_routes.py` - Notification create, dismiss, and cancel
  - `services/` - Business logic and RBAC for collections this API controls
    - `card_service.py` - home aggregation and the Card projections with no shared service class
    - `notification_service.py` - Notification control rules and the Card-projecting subclass
    - `path_service.py`, `plan_service.py`, `profile_service.py`, `resource_service.py` -
      Card-projecting subclasses bound to the shared `api-utils` GET factories

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

The earlier Customer and Profile list/get endpoints have been retired. Discovery now serves the
composite home **Card** list, the typed `/api/cards/{type}` lists, and the **Notification** control
endpoints, alongside the standard config, docs, and metrics endpoints.

## API Endpoints

See the [Open API Specifications](./docs/openapi.yaml) for details on the API.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/cards` | Composite home card list |
| `GET /api/cards/{type}` | Typed card list — `customer`, `members`, `mentees`, `notifications`, `paths`, `plans`, `products`, `resources`, `settings` |
| `POST /api/notification` | Create a Notification |
| `POST /api/notification/dismiss/{notification_id}` | Dismiss a Notification |
| `POST /api/notification/cancel/{notification_id}` | Cancel a Notification |
| `GET /api/config` | Configuration endpoint |

Card lists return a bare JSON array and paginate with the `offset` and `size` request headers. The
Notification control endpoints return Notification documents, not Cards.

The shared `api-utils` GET factories also mount by-id GETs under some typed prefixes (for example
`/api/cards/resources/{id}`). Those are a side effect of the shared factories, are not part of the
documented Discovery contract, and are not in `docs/openapi.yaml`.

For E2E, mint a Bearer token via `test/e2e/e2e_auth.py` (`get_auth_token()`) with `pipenv run dev` (matching `JWT_SECRET`).

### Simple Curl Commands:
```bash
# Bearer token for local dev (same JWT settings as pipenv run dev / e2e):
export TOKEN="$(PYTHONPATH=test/e2e pipenv run python -c 'from e2e_auth import get_auth_token; print(get_auth_token())')"

# Get the API Configuration
curl http://localhost:8397/api/config \
  -H "Authorization: Bearer $TOKEN"

# Get the composite home card list
curl http://localhost:8397/api/cards \
  -H "Authorization: Bearer $TOKEN"

# Get a typed card list (first page of 5)
curl http://localhost:8397/api/cards/resources \
  -H "Authorization: Bearer $TOKEN" \
  -H "offset: 0" -H "size: 5"

# Create a Notification (returns 201 and the created document)
curl -X POST http://localhost:8397/api/notification \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"readme-demo","message":"Hello from curl","status":"active"}'

# Dismiss that Notification by _id
curl -X POST http://localhost:8397/api/notification/dismiss/<notification_id> \
  -H "Authorization: Bearer $TOKEN"

```
