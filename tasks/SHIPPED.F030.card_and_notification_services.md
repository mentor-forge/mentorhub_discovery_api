# F030 – Card projection and Notification control services

**Status**: Shipped  
**Type**: Feature  
**Depends On**: `F020_openapi_cards_and_notifications`  
**Description**: Add local service subclasses and a Card projection/orchestration service. No HTTP routes in this task. Notification dismiss and cancel live only on the Discovery subclass. Card is not a Mongo collection.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `../mentorhub/DeveloperEdition/standards/ArchitecturePrinciples.md` — Discovery **controls** Notification, **creates** Event, **consumes** Profile, Customer, Journey, Resource, Path, Plan
- `tasks/README.md`
- `README.md`
- `../mentorhub_api_utils/README.md` — subclass shared services; routes (later) import the **local** subclass; outbound GET RBAC is on the shared class; inbound write checks are on the subclass
- `../mentorhub_api_utils/api_utils/services/notification_service.py` — `create_notification`, `get_notifications`; no dismiss/cancel on the shared class
- `../mentorhub_api_utils/api_utils/services/profile_service.py` — `get_profiles`, `PROFILE_LIST_FILTERS`, `PROFILE_LIST_ORDER`
- `../mentorhub_api_utils/api_utils/services/resource_service.py`
- `../mentorhub_api_utils/api_utils/services/path_service.py`
- `../mentorhub_api_utils/api_utils/services/plan_service.py`
- `../mentorhub_api_utils/api_utils/mongo_utils/mongo_io.py` — required I/O surface
- `../mentorhub_api_utils/api_utils/services/rbac.py` — `build_outbound_match`, `require_outbound`
- `docs/openapi.yaml` — Card and Notification shapes from F020

Re-fetch schemas if F020 notes are incomplete:

```bash
curl -X GET "http://localhost:8383/api/configurations/json_schema/Card.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Notification.yaml/latest/" -H "accept: application/json"
```

If the configurator is unavailable, set **Status** to `Blocked` and stop.

**MongoDB I/O**: All collection access goes through `MongoIO` (`get_document`, `get_documents`, `create_document`, `update_document`, `upsert_document`) or shared helpers that already wrap MongoIO (`execute_list_query`). Do **not** call PyMongo via `mongo.get_collection(...)`. Encode string ids with `encode_document` immediately before MongoIO. Do not stringify ObjectIds for output.

**Card is not persisted.** Do not add `CARD_COLLECTION_NAME`. Do not insert Card documents. `CardService` projects source documents into the Card schema and orchestrates the home list.

**Roles** (from `Config`): `ROLE_CUSTOMER`, `ROLE_COORDINATOR`, `ROLE_MENTOR`. Compare token `roles` to these values (lowercase).

## Goals

- Thin local subclasses (classmethod, inherit shared consume/create):
  - `src/services/notification_service.py` — `NotificationService(SharedNotificationService)`
  - `src/services/profile_service.py` — `ProfileService(SharedProfileService)` (consume only)
  - `src/services/resource_service.py` — `ResourceService(SharedResourceService)`
  - `src/services/path_service.py` — `PathService(SharedPathService)`
  - `src/services/plan_service.py` — `PlanService(SharedPlanService)`
- Optional thin subclasses only if F050 will mount their shared GET factories: Event is **create**, not a cards type. Do not add control mutations for collections Discovery does not control.
- `NotificationService` on the Discovery subclass:
  - `dismiss_notification(notification_id, token, breadcrumb)` — load the document (MongoIO `get_document` then `require_outbound` / equivalent so hidden ids are `404`), inbound check (authenticated caller whose token matches the notification target `profile_id` / `customer_id` / `mentor_id`, or admin), then `update_document` setting **only** `dismissed` to the request breadcrumb. No `saved` field.
  - `cancel_notification(notification_id, token, breadcrumb)` — same pattern, setting **only** `cancelled`.
  - Inherit `create_notification` and `get_notifications`. Do not copy dismiss from `api_utils.services`.
  - Active notifications for home: not dismissed and not cancelled (`dismissed` / `cancelled` absent).
- `CardService` (`src/services/card_service.py`) is the orchestration/projection layer:
  - `project(card_type, document) -> dict` maps a source document onto the Card schema (fields from the configurator). `card_type` values correspond to the typed lists: `customer`, `members`, `mentees`, `resources`, `paths`, `plans`, `products`, `notifications`, `settings`, plus home-source types for notification / member / mentee.
  - `get_home_cards(token, breadcrumb, offset, size) -> list` builds, in order:
    1. Active Notifications for token `profile_id` (empty if no `profile_id`).
    2. Members — Profile documents for token `customer_id` **only if** roles include Customer or Coordinator (empty otherwise, or if no `customer_id`).
    3. Mentees — Profile documents for token `mentor_id` **only if** roles include Mentor (empty otherwise, or if no `mentor_id`).
    Then project each source to Card, concatenate, and apply `offset`/`size` to the combined list.
  - Home lists call **local** `NotificationService` / `ProfileService` (or `execute_list_query` via those services). Do not query collections from `CardService` except through those services or MongoIO helpers they already use.
- There is no shared Customer, Product, or Setting service. Typed list helpers for those collections (used in F050) may live on `CardService` as `get_customer_cards` / `get_product_cards` / `get_settings_cards` using `execute_list_query(collection_name, ...)` and `parse_list_request` specs. Confirm collection names from `Config` (`CUSTOMER_COLLECTION_NAME`, `SETTING_COLLECTION_NAME`) and the Card type catalog. If Product is not a persisted collection, document the chosen source in **Execution Notes** and still return `Card[]` (do not invent a Card collection).
- Unit tests mock MongoIO / shared service methods; they do not require a live database.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_notification_service.py` — dismiss sets only `dismissed`; cancel sets only `cancelled`; missing/hidden id → `HTTPNotFound`; no `saved`; inbound forbidden when applicable.
  - `test/services/test_card_service.py` — `project` output matches Card required fields; `get_home_cards` includes notifications for `profile_id`; omits members without Customer/Coordinator; omits mentees without Mentor; concatenates in the specified order; honors offset/size.
- **Packaging verification** (no new HTTP yet)
  - `pipenv run container`
  - `pipenv run api`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — still served

## Outputs

- `src/services/notification_service.py` — create (new)
- `src/services/profile_service.py` — create (new subclass; the F010 file was deleted)
- `src/services/resource_service.py` — create
- `src/services/path_service.py` — create
- `src/services/plan_service.py` — create
- `src/services/card_service.py` — create
- `src/services/__init__.py` — export local subclasses if the package currently exports services
- `test/services/test_notification_service.py` — create
- `test/services/test_card_service.py` — create

The agent must not update files outside this list. Do not add Flask routes in this task.

## Execution Notes

### Planned approach

Schemas re-fetched live from the configurator at `http://localhost:8383` (Card `0.0.0.0`,
Notification `0.1.0.0`, Setting `0.1.0.0`, Customer `0.1.0.0`) — no fallback to dictionary YAML.

1. **Thin consume subclasses** — `resource_service.py`, `path_service.py`, `plan_service.py`
   subclass the shared classes with no added surface (Discovery consumes only; no control
   mutations).
2. **`profile_service.py`** — subclasses `SharedProfileService` and adds two identity-scoped
   list helpers used by the home list and by the F050 Member/Mentee typed lists:
   `get_member_profiles` (scoped by token `customer_id`) and `get_mentee_profiles` (scoped by
   token `mentor_id`). Both AND the scope onto the shared `_outbound_match` and run through
   `execute_list_query`; the scope id is encoded with `encode_document` immediately before the
   MongoIO call.
3. **`notification_service.py`** — subclasses `SharedNotificationService`, inherits
   `create_notification` / `get_notifications`, and adds:
   - `dismiss_notification` / `cancel_notification`: `MongoIO.get_document` →
     `require_outbound` (missing *and* hidden ids both raise `HTTPNotFound`) → inbound target
     check → `update_document` with `set_data` containing **only** `dismissed` / `cancelled`.
   - `get_active_notifications`: delegates to the inherited `get_notifications` with a
     `dismissed`/`cancelled` `$exists: false` match.
4. **`card_service.py`** — projection + orchestration.
   - `project(card_type, document)` is table-driven from `CARD_TYPE_SPECS`; it emits only Card
     schema properties and omits any field whose source value is absent. `_id` passes through as
     the source `ObjectId` (no stringify — `MongoJSONEncoder` decodes at the Flask boundary).
   - `get_home_cards` assembles notifications → members → mentees, then slices the combined list
     by `offset`/`size`. Each source is fetched at `offset=0` with
     `size = min(offset + size, MAX_SIZE)` so the combined slice is correct without exceeding the
     shared pagination ceiling.
   - `get_customer_cards` / `get_product_cards` / `get_settings_cards` use `execute_list_query`
     against `Config.CUSTOMER_COLLECTION_NAME` / `Config.SETTING_COLLECTION_NAME` with
     `NAME_*` filter/order specs matching the F020 OpenAPI parameters.
5. **`src/services/__init__.py`** exports the local subclasses plus `CardService`.
6. **Tests** mock `MongoIO` / `Config` / the local service classmethods; no live DB.

### Summary of changes

| File | Change |
| --- | --- |
| `src/services/notification_service.py` | new — `NotificationService(SharedNotificationService)` with `dismiss_notification`, `cancel_notification`, `get_active_notifications`, `active_match()` |
| `src/services/profile_service.py` | new — `ProfileService(SharedProfileService)` with `get_member_profiles` / `get_mentee_profiles` |
| `src/services/resource_service.py` | new — consume-only subclass |
| `src/services/path_service.py` | new — consume-only subclass |
| `src/services/plan_service.py` | new — consume-only subclass |
| `src/services/card_service.py` | new — `CardService.project`, `get_home_cards`, `get_customer_cards`, `get_product_cards`, `get_settings_cards` |
| `src/services/__init__.py` | exports the six local classes |
| `test/services/test_notification_service.py` | new — 22 tests |
| `test/services/test_card_service.py` | new — 33 tests (9 subtests) |

No Flask routes were added and `src/server.py` is untouched.

### Card `type` mapping

The configurator Card `type` enum is exactly
`Event | Member | Mentee | Notification | Path | Plan | Resource`; `type` is **not** required and
`additionalProperties` is `false`.

| `card_type` argument | Card `type` | Source fields → Card fields |
| --- | --- | --- |
| `notifications` / `notification` | `Notification` | `name` → `name`, `message` → `description` |
| `members` / `member` | `Member` | `full_name` (else `name`) → `name`, `description` → `description` |
| `mentees` / `mentee` | `Mentee` | `full_name` (else `name`) → `name`, `description` → `description` |
| `resources` | `Resource` | `name`, `description`, `url` → `link` |
| `paths` | `Path` | `name`, `description` |
| `plans` | `Plan` | `name`, `description` |
| `customer` | *omitted* | `name`, `description` |
| `products` | *omitted* | `name`, `description` |
| `settings` | *omitted* | `name`, `description` |

`customer`, `products`, and `settings` **omit** `type` (the preferred option in the task brief)
because the enum has no Customer, Product, or Setting value; they still return `Card[]`. `_id` is
the source document id passed through unchanged as `ObjectId` — nothing is stringified for output,
and `encode_document` is applied to inbound scope ids immediately before the MongoIO call. A field
whose source value is absent is omitted rather than emitted as null, which is valid because Card
has no required properties. An unknown `card_type` raises `HTTPBadRequest`.

### Customer / Products / Settings source choice

Confirmed against the live configurator (`GET /api/collections/`) and `Config`:

- **Customer** → `Config.CUSTOMER_COLLECTION_NAME` (`"Customer"`), a real collection. Outbound
  scope is `status != archived` AND `_id == token.customer_id`; a caller with no `customer_id`
  falls to `EMPTY_SCOPE_MATCH` rather than falling open. Admin is unrestricted.
- **Products** → **not a collection.** The configurator describes `Setting` as a "Polymorphic
  Admin/reference bag (Product catalog and Discount codes)", and `Setting.0.1.0.0` is a root
  `oneOf` of a **Product** variant and a **Discount** variant, each with a constant `type`
  discriminator. `get_product_cards` therefore reads `Config.SETTING_COLLECTION_NAME`
  (`"Setting"`) with `{"type": "Product"}`. The discriminator is AND'd on **outside**
  `build_outbound_match` so an admin's unrestricted `{}` scope still excludes Discount rows.
- **Settings** → `Config.SETTING_COLLECTION_NAME` with no discriminator, i.e. every Setting
  variant (Product plus Discount) visible to the caller.

No `CARD_COLLECTION_NAME` was added and no Card document is ever written.

### Other implementation decisions

- **Home pagination.** Each section is fetched at `offset=0` with
  `size = min(offset + size, MAX_SIZE)` and the combined list is sliced `[offset:offset+size]`.
  This keeps every section request inside the shared `size <= 100` ceiling, so a home page beyond
  combined index 100 is not reachable — acceptable for a landing list, and callers get a `400`
  from `validate_pagination` for an out-of-range `size`.
- **Dismiss / cancel inbound check.** Admin always passes; otherwise the caller must hold the token
  claim (`profile_id` / `customer_id` / `mentor_id`) naming the notification's target. Because
  outbound RBAC uses the same claim set, a targeted notification the caller can see is a
  notification the caller may retire; the check therefore bites on **globally scoped**
  notifications, where a dismiss would hide the document for every reader. Non-admins get `403`
  there. If product decides individual users should be able to dismiss global notifications, that
  needs per-user dismissal state (a new field) rather than the shared `dismissed` breadcrumb —
  flagged as a follow-up, not implemented here.
- Missing ids and outbound-hidden ids both raise `HTTPNotFound` via `require_outbound`, so a
  hidden id is never leaked through a `403`.

### Testing results

All commands run from the API repository root.

| Command | Result |
| --- | --- |
| `pipenv run test` | **73 passed, 9 subtests passed** |
| `pipenv run lint` | **16 files would be left unchanged** |
| `pipenv run format` | reformatted `src/services/notification_service.py` (now clean) |
| `pipenv run build` | success |
| `pipenv run container` | image `ghcr.io/mentor-forge/mentorhub_discovery_api:latest` built |
| `pipenv run api` | `mentorhub-discovery_api-1` started |
| `curl -s http://localhost:8397/docs/openapi.yaml` | **200**, spec body served |

Schemas were re-fetched live rather than trusted from notes:
`curl http://localhost:8383/api/configurations/json_schema/{Card,Notification,Setting,Customer}.yaml/latest/`
plus `curl http://localhost:8383/api/collections/`.

### Follow-ups for later tasks

- **F040–F060** own the Flask routes. They should import the **local** subclasses
  (`src.services.*`) and use `parse_list_request` with `CardService.CUSTOMER_LIST_FILTERS` /
  `PRODUCT_LIST_*` / `SETTING_LIST_*` and `PROFILE_LIST_FILTERS` / `PROFILE_LIST_ORDER` for the
  member and mentee lists.
- Typed Card lists for resources / paths / plans / notifications / members / mentees are not
  wrapped on `CardService`; F050 should call the local service list method and pass the documents
  through `CardService.project(<card_type>, document)`.
- `test/e2e/e2e_auth.py` still lacks a `profile_id` claim, so an E2E home list would return no
  notification cards. F040+ owns that file (out of scope here).

### Orchestrator confirmation

Working tree had no staged `tasks/README.md` deletion. Re-ran `pipenv run test` (73 passed, 9 subtests), `pipenv run lint` (16 files unchanged), `pipenv run build`. Confirmed no `get_collection` in `src/` and no new Flask routes. Status set to Shipped.
