# F030 – Card projection and Notification control services

**Status**: Pending  
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

_Reserved for the task execution agent._
