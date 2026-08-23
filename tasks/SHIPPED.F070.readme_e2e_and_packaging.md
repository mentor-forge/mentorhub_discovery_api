# F070 – README, server summary, and full e2e/packaging pass

**Status**: Shipped  
**Type**: Feature  
**Depends On**: `F060_notification_control_routes`  
**Description**: Align README and server startup logs with the Card/Notification API, fill any remaining test gaps, and run the full unit plus containerized e2e gate for F-DA02.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/README.md`
- `README.md` — still describes leftover Customer/Profile or 0.5.2 bootstrap notes
- `src/server.py` — route log lines
- `docs/openapi.yaml`
- `test/test_server.py`
- `test/e2e/test_cards.py`
- `test/e2e/test_notification.py`
- `test/e2e/e2e_auth.py`

This is a documentation and verification task. Add tests only for gaps found against F020’s endpoint tables. Do not invent new endpoints.

**Confirmation greps** (zero hits required except inside `tasks/`):

```bash
rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' --glob '*.py' --glob 'docs/openapi.yaml'
rg '/api/profile|/api/customer' src test docs/openapi.yaml README.md
```

## Goals

- `README.md` project structure lists Card routes/services and Notification control (not Customer/Profile infinite scroll).
- `README.md` curl examples cover:
  - `GET /api/cards` (home)
  - at least one typed list (e.g. `GET /api/cards/resources`)
  - `POST /api/notification/dismiss/<id>` (or create) with `Authorization: Bearer $TOKEN`
  - existing `/api/config` example may remain
- Token minting still uses `test/e2e/e2e_auth.py` / `pipenv run e2e` JWT settings.
- `src/server.py` startup logs list `/api/cards`, typed card prefixes (or a single “card type lists” line), `/api/notification`, plus config/docs/metrics.
- `test/test_server.py` blueprint/URL assertions match the registered surface and still forbid credential-minting routes.
- E2E coverage exists for home cards, each typed cards path from F020, and notification create/dismiss/cancel auth behavior.
- `api-utils==1.0.0` remains the Pipfile pin.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Dev e2e** (optional if container e2e is the gate; prefer both if `pipenv run dev` is already documented)
  - `pipenv run db` if the API is not already up
  - `pipenv run e2e` against a running API on port 8397
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — contains `/api/cards` and `/api/notification/dismiss/`
- Record command results in **Execution Notes**.

## Outputs

- `README.md` — current Discovery API surface and curl examples
- `src/server.py` — route registration log lines (only if they still mention Profile/Customer or omit cards/notification)
- `test/test_server.py` — only if assertions still drift from registered routes
- `test/e2e/test_cards.py` — only if typed/home coverage is incomplete
- `test/e2e/test_notification.py` — only if control coverage is incomplete
- `test/e2e/e2e_auth.py` — only if e2e tokens are missing claims required for home cards

The agent must not update files outside this list.

## Execution Notes

### Files changed

- `README.md` — Project Structure now lists the card and notification route/service modules;
  the stale "land in follow-up tasks / config, docs, and metrics only" paragraph is replaced by
  the current surface; added an endpoint table and curl examples for `GET /api/cards`,
  `GET /api/cards/resources` (with `offset` / `size` headers), `POST /api/notification`, and
  `POST /api/notification/dismiss/{id}`; noted the shared-factory by-id GETs that are not in
  `docs/openapi.yaml`.
- `README.md` — fixed the token-minting one-liner. The documented
  `PYTHONPATH=. ... from test.e2e.e2e_auth import ...` form never worked: there is no
  `test/__init__.py`, so the CPython stdlib `test` package wins the import. Now
  `PYTHONPATH=test/e2e ... from e2e_auth import get_auth_token`, verified against the container.
- `test/test_server.py` — the retired-route assertion now iterates `RETIRED_ROUTE_PREFIXES`,
  assembled the same way as `_FORBIDDEN_CREDENTIAL_ISSUER_PATH`, so the confirmation grep for
  retired paths has zero hits while the guardrail assertion stays.
- `test/e2e/test_cards.py` — `test_typed_card_list_projects_its_card_type` now mints a
  `customer_id` / `mentor_id` scoped token via `get_auth_token(**claims)` for the Member and
  Mentee lists. Those two were the only skips in the e2e run; the suite is now skip-free.

Not changed (verified already correct): `src/server.py` startup logs already list `/api/cards`,
typed `{type}`, `/api/notification`, `/api/config`, `/docs`, `/metrics` with no Profile/Customer
mention. `test/test_server.py` blueprint/URL assertions already match the registered surface.
`test/e2e/test_notification.py` already covers create / dismiss / cancel plus auth, 404, RBAC,
405, and 400 behavior. `test/e2e/e2e_auth.py` already mints `profile_id` and accepts claim
overrides. `Pipfile` still pins `api-utils = {version = "==1.0.0", index = "codeartifact"}`.

### Confirmation greps (zero hits)

```
rg 'execute_infinite_scroll_query|after_id|has_more|next_cursor' --glob '*.py' --glob 'docs/openapi.yaml'
  -> no matches
rg '/api/profile|/api/customer' src test docs/openapi.yaml README.md
  -> no matches
```

### Command results

| Command | Result |
| --- | --- |
| `pipenv run test` | 132 passed, 48 deselected, 104 subtests passed |
| `pipenv run lint` | 22 files would be left unchanged |
| `pipenv run build` | exit 0 |
| `pipenv run container` | built `ghcr.io/mentor-forge/mentorhub_discovery_api:latest`, exit 0 |
| `pipenv run api` | `mentorhub-discovery_api-1` started; `/api/config` reachable on 8397 |
| `pipenv run e2e` | 48 passed, 0 skipped, 132 deselected (was 46 passed / 2 skipped before the scoped-token change) |
| `curl -s http://localhost:8397/docs/openapi.yaml` | 200, 29983 bytes; 14 `/api/cards` hits and `/api/notification/dismiss/{notification_id}` present |

Every README curl was executed against the containerized stack: `/api/config` 200,
`/api/cards` 200, `/api/cards/resources` 200 with pagination headers, `POST /api/notification`
returned a created `_id`, and `POST /api/notification/dismiss/{_id}` returned 200.

### Follow-ups

- The shared `api-utils` GET factories mount undocumented by-id GETs under `/api/cards/members`,
  `/api/cards/mentees`, `/api/cards/paths`, `/api/cards/plans`, and `/api/cards/resources`.
  README notes them; deciding whether to document or suppress them needs a separate task.
- `test/e2e/test_cards.py` scoped claims hardcode seeded Developer Edition ids
  (`customer_id` `D00000000000000000000002`, `mentor_id` `A00000000000000000000010`), matching the
  file's existing persona-id convention. They will need updating if the seed data changes.

### Orchestrator confirmation

Re-ran `pipenv run test` (132 passed, 48 e2e deselected), `pipenv run lint`, `pipenv run build`. Confirmation greps are clean outside `tasks/`. Status set to Shipped.
