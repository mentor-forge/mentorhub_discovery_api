# F120 – Card `type` catalog and `link` projection

**Status**: Pending  
**Type**: Feature  
**Depends On**: `D110_fix_mentee_home_cards`  
**Description**: Emit F100 Card `type` values on every home card (including synthetics and Customer), always set Notification `link`, point Mentee cards at `mentor/mentee/{id}`, and retarget Products/Discounts links to Admin settings. Do not enrich Member/Mentee markdown yet (F130) and do not add Notification filters (F140).

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — MongoIO only; do not edit sibling repos
- `README.md`
- `docs/openapi.yaml` — F100 `type` / `link` table
- `src/services/card_service.py` — `project` / `project_all`, `get_home_cards` synthetics, `notification_link=False` on home
- `src/services/notification_service.py` — typed list already passes `notification_link=True`
- `src/services/profile_service.py` — Member/Mentee `project_all`
- `src/services/event_service.py` — Event links unchanged
- `test/services/test_card_service.py` — synthetic cards omit `type`; home notifications omit `link`; Mentee link is `mentee/mentee/{id}`; Products/Discounts links are `admin/products` / `admin/discounts`
- `test/e2e/test_cards.py` — same assumptions (full persona rewrite is F150; keep e2e green by updating assertions that would otherwise fail)

**`project` / `project_all` contract** (keep emitting only Card properties; omit absent fields; `_id` unchanged):

- Notification: **always** set `link` `discovery/notification/{id}` when `_id` is present. Remove the `notification_link` flag (or default it to `True` and stop passing `False` from home). Home and typed lists must match.
- Mentee → `mentor/mentee/{id}` (replace `mentee/mentee/{id}`).
- Member, Resource, Path, Plan, Event, Customer singleton links are unchanged except Customer now also emits `type: Customer`.
- `{id}` remains the 24-hex form of source `_id`. Relative path, no leading slash.

**Synthetic / singleton cards** (built in `get_home_cards`, not via `project` of a Mongo document except Customer):

| Card | `name` | `type` | `link` | `_id` |
| --- | --- | --- | --- | --- |
| Products | `Products` | `Products` | `admin/settings` | omit |
| Discounts | `Discounts` | `Discounts` | `admin/settings?tab=discounts` | omit |
| Logs | `Logs` | `Logs` | `admin/logs` | omit |
| Learning Journey | `Learning Journey` | `Journey` | `mentee/journey` | omit |
| Customer | from document | `Customer` | `customer/customer/{id}` | source `_id` |

Add `CARD_TYPE_*` specs for Products, Discounts, Logs, and Journey only if `project` needs them; synthetics may be small dict literals, but they must include `type`. Prefer one helper that builds a synthetic card so tests can target it.

**`CARD_TYPE_SPECS`**: Customer spec `type` becomes `"Customer"` (stop omitting). Do not add a Coordinator spec.

Callers: `get_home_cards` must stop passing `notification_link=False`. `NotificationCardService` can drop the flag once the default is always-on.

## Goals

- Home Products / Discounts / Logs / Journey / Customer cards include the F100 `type` values.
- Home Notification cards include `link` `discovery/notification/{id}`.
- Mentee cards use `mentor/mentee/{id}`.
- Products and Discounts use the Admin settings links above.
- Logs, Member, Resource, Path, Plan, Event links unchanged.
- Typed `/api/cards/{type}` routes are unchanged except Notification cards already had the link (now the same as home).
- D110 Mentor identity fallback remains in place.

### Craftsmanship Expectations

- Do not persist synthetic cards. Do not add a Card collection.
- Keep `project` a pure mapping from a source document plus token. Synthetics stay in `get_home_cards` (or a private helper), not in Mongo.
- Delete the `notification_link` parameter if nothing still needs two behaviors — do not leave a dead flag.
- Icon / hover text is SPA-owned; this task only sets `type` and `link`.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_card_service.py`:
    - Admin synthetics include `type` and the new Products/Discounts links
    - Customer projection emits `type: Customer`
    - Journey synthetic emits `type: Journey`
    - Home Notification cards include `link` (replace omit-link assertions)
    - Mentee link is `mentor/mentee/{id}`
    - Drop `notification_link=False` cases
  - Typed-subclass tests still pass (`NotificationCardService` still has `discovery/notification/{id}`)
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — update `test/e2e/test_cards.py` **only as needed to stay green** (Mike’s synthetic links, Daniel’s home Notification `link` / Journey `type`, Paula’s Mentee `link` prefix, Customer `type`). Do not add markdown or notification-filter coverage here (F130 / F140 / F150).
  - `curl -s http://localhost:8397/docs/openapi.yaml` — still the F100 spec

## Outputs

- `src/services/card_service.py` — types on synthetics/Customer; Notification link always; Mentee and Products/Discounts links
- `src/services/notification_service.py` — drop `notification_link` plumbing if unused
- `test/services/test_card_service.py` — type and link assertions
- `test/e2e/test_cards.py` — only assertions that would fail under the new contract
- `test/services/test_notification_service.py` — only if it asserts the home omit-link flag

The agent must not update files outside this list. Do not change OpenAPI. Do not add or remove HTTP routes. Do not change Member/Mentee `description` content.

## Execution Notes
