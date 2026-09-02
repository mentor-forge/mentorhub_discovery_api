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
    - `card_routes.py` - composite home list
    - `notification_routes.py` - Notification create, dismiss, and cancel
  - `services/` - Business logic and RBAC for collections this API controls
    - `card_service.py` - home composite aggregation and Card projections
    - `event_service.py` - Event consume surface and Card-projecting subclass
    - `notification_service.py` - Notification control rules and the Card-projecting subclass
    - `path_service.py`, `plan_service.py`, `profile_service.py`, `resource_service.py` -
      Domain services and Card-projecting subclasses bound to the shared `api-utils` GET factories

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
| `GET /api/cards` | Composite home Card list (Notifications, then role-gated Products / Discounts / Logs, Customer, Members, Mentees, Learning Journey). Every card has `type` and a relative SPA `link`. |
| `GET /api/cards/{type}` | Typed Card list — `events`, `notifications`, `paths`, `plans`, `resources`. Event cards omit `link`; `name` is the Event `type` and `description` is Markdown with type, Profile `full_name`, and `created.at_time`. |
| `GET /api/cards/notifications` | Notification Cards (`type: Notification`, `link: discovery/notification/{id}`). Query params `name` (contains) and `status` (`active` / `archived`) are **admin-only**; a non-admin caller that sends either receives `403`. |
| `POST /api/notification` | Create a Notification (returns a Notification document, not a Card) |
| `POST /api/notification/dismiss/{notification_id}` | Dismiss a Notification |
| `POST /api/notification/cancel/{notification_id}` | Cancel a Notification |
| `GET /api/config` | Configuration endpoint |

Home section `type` / `link` values (relative SPA paths, no leading slash):

- Notification — `discovery/notification/{id}`
- Products — `admin/settings` (Admin)
- Discounts — `admin/settings?tab=discounts` (Admin)
- Logs — `admin/logs` (Admin)
- Customer — `customer/customer/{id}` (Customer)
- Member — `customer/profile/{id}` (Customer or Coordinator); Markdown Progress (Library / Now / Next) and Activity (30 days)
- Mentee — `mentor/mentee/{id}` (Mentor); Markdown Activity (30 days) and Notes
- Journey — `mentee/journey` (Mentee)

Card lists return a bare JSON array and paginate with the `offset` and `size` request headers. The
typed lists carry per-type filter and order parameters; home paginates only. The Notification
control endpoints return Notification documents, not Cards. There is no Card by-id GET: the Card
surface is list-only, so a request such as `/api/cards/resources/{id}` returns 404.

For E2E, mint a Bearer token via `test/e2e/e2e_auth.py` (`get_auth_token()` or
`get_persona_token(...)`) with `pipenv run dev` (matching `JWT_SECRET`).

### Simple Curl Commands:
```bash
# Bearer token for local dev (same JWT settings as pipenv run dev / e2e):
export TOKEN="$(PYTHONPATH=test/e2e pipenv run python -c 'from e2e_auth import get_auth_token; print(get_auth_token())')"

# Mentee persona (non-admin) — used to show 403 on notification filters:
export DANIEL="$(PYTHONPATH=test/e2e pipenv run python -c 'from e2e_auth import PERSONA_DANIEL, get_persona_token; print(get_persona_token(PERSONA_DANIEL))')"

# Get the API Configuration
curl http://localhost:8397/api/config \
  -H "Authorization: Bearer $TOKEN"

# Get the composite home card list (types and links vary by token roles)
curl http://localhost:8397/api/cards \
  -H "Authorization: Bearer $TOKEN"

# Get a typed card list (first page of 5; supports resources, paths, plans, notifications, events)
curl http://localhost:8397/api/cards/resources \
  -H "Authorization: Bearer $TOKEN" \
  -H "offset: 0" -H "size: 5"

# Notification cards — admin may filter by name contains and status in_list
curl "http://localhost:8397/api/cards/notifications?status=active" \
  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8397/api/cards/notifications?name=Invite" \
  -H "Authorization: Bearer $TOKEN"

# Non-admin callers that send name or status receive 403
curl "http://localhost:8397/api/cards/notifications?name=x" \
  -H "Authorization: Bearer $DANIEL"

# Create a Notification (returns 201 and the created document)
curl -X POST http://localhost:8397/api/notification \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"readme-demo","message":"Hello from curl","status":"active"}'

# Dismiss that Notification by _id
curl -X POST http://localhost:8397/api/notification/dismiss/<notification_id> \
  -H "Authorization: Bearer $TOKEN"

```
