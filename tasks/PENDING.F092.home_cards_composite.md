# F092 – Rewrite GET /api/cards home composite

**Status**: Pending  
**Type**: Defect  
**Depends On**: `F091_card_link_projection`  
**Description**: Replace `CardService.get_home_cards` with the eight-section composite from F090. Keep every typed `/api/cards/{type}` route working so F093 can reshape that surface in one pass.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — MongoIO only; all collection I/O through `MongoIO` / `execute_list_query`
- `README.md`
- `docs/openapi.yaml` — F090 home description and synthetic-card `link` values
- `src/services/card_service.py` — `get_home_cards` currently concatenates active Notifications, then Members (Customer/Coordinator), then Mentees (Mentor)
- `src/services/notification_service.py` — `get_active_notifications` (already newest `created.at_time` first)
- `src/services/profile_service.py` — `get_member_profiles` / `get_mentee_profiles` (default Profile order is `name` asc; home must override)
- `../mentorhub_api_utils/api_utils/services/profile_service.py` — `PROFILE_LIST_ORDER` allows `saved.at_time`
- `../mentorhub_api_utils/api_utils/config.py` — `ROLE_ADMIN`, `ROLE_CUSTOMER`, `ROLE_COORDINATOR`, `ROLE_MENTOR`, `ROLE_MENTEE`
- `test/services/test_card_service.py` — home composition tests
- `test/e2e/test_cards.py` — home still only asserts array/shape

**MongoDB I/O**: MongoIO / `execute_list_query` only. Do not call `get_collection`. The Customer singleton may use `MongoIO.get_document` on `Config.CUSTOMER_COLLECTION_NAME` with outbound RBAC (`build_outbound_match` / `require_outbound` as used elsewhere), or a size-1 `execute_list_query` keyed by token `customer_id`. Skip the Customer card when `customer_id` is missing or the document is hidden.

**Home sections** (concatenate, then slice `offset`/`size` on the combined list). Fetch each sourced section from offset `0` with `size` capped at `min(offset + size, MAX_SIZE)` so the combined page is complete (same pagination approach as today):

1. Active Notifications for token `profile_id` via `NotificationService.get_active_notifications`, match `{profile_id: token.profile_id}`, newest created first. Skip if no `profile_id`. Project with F091 default (`notification_link` false).
2. If `Config.ROLE_ADMIN` in roles: one synthetic card `{name: "Products", description: "Manage subscription products", link: "admin/products"}` (omit `_id` and `type`).
3. If Admin: `{name: "Discounts", description: "Manage discount codes", link: "admin/discounts"}`.
4. If Admin: `{name: "Logs", description: "View system logs", link: "admin/logs"}`.
5. If `Config.ROLE_CUSTOMER` in roles and `customer_id` present: one Customer Card from that Customer document (`name` / `description` from the document, omit `type`, `link` `customer/customer/{id}`).
6. If `ROLE_CUSTOMER` or `ROLE_COORDINATOR` in roles and `customer_id` present: Member Cards from `ProfileService.get_member_profiles` with `sort_by` `saved.at_time` **desc**.
7. If `ROLE_MENTOR` in roles and `mentor_id` present: Mentee Cards from `ProfileService.get_mentee_profiles` with `sort_by` `saved.at_time` **desc**.
8. If `ROLE_MENTEE` in roles: one synthetic card `{name: "Learning Journey", description: "Continue your learning journey", link: "mentee/journey"}` (omit `_id` and `type`).

A caller with several roles receives **every** matching section, in the order above (e.g. Customer+Coordinator still emits one Customer card then Members, not Members twice).

Synthetic cards are not persisted. Do not insert into Mongo. Do not add a Card collection.

Keep `get_customer_cards` / `get_product_cards` / `get_settings_cards` for the still-registered typed lists; F093 deletes them. Do not use those list helpers for the Admin synthetics (those are not Setting rows).

## Goals

- `get_home_cards` emits sections in the F090 order with the role gates and sorts above.
- Admin-only callers get Products, Discounts, Logs (and Notifications if they have a `profile_id` with active notifications).
- Customer callers get the Customer singleton; Coordinator-only callers do not.
- Member/Mentee home cards are ordered by `saved.at_time` descending and already carry F091 links.
- Mentee callers get the Learning Journey card last among their sections.
- Combined-list pagination still honors `offset` / `size` and `MAX_SIZE`.
- Typed `/api/cards/{type}` routes are **unchanged**.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_card_service.py`:
    - Admin token includes Products → Discounts → Logs in that order (mock Config roles)
    - Customer role + `customer_id` includes one Customer card (mock `get_document` / list helper)
    - Coordinator without Customer role includes Members but not the Customer card
    - Member/Mentee fetches are called with `saved.at_time` desc
    - Mentee role appends Learning Journey
    - Multi-role token concatenates in full eight-section order
    - Notification home cards still omit `link`
    - Existing pagination tests updated for the new section lengths
  - `test/routes/test_card_routes.py` — home still calls `get_home_cards(token, breadcrumb, offset, size)`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — home still returns `200` + Card array (seed-persona order assertions are F094)
  - `curl -s http://localhost:8397/docs/openapi.yaml` — F090 spec unchanged

## Outputs

- `src/services/card_service.py` — rewrite `get_home_cards`; small helpers for synthetic cards and the Customer singleton
- `test/services/test_card_service.py` — home composition tests for all eight sections, role gates, sorts, pagination

The agent must not update files outside this list. Do not add or remove HTTP routes. Do not edit OpenAPI.

## Execution Notes
