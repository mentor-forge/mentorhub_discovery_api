# F100 – OpenAPI for F-DA07 Card updates

**Status**: Pending  
**Type**: Feature  
**Depends On**: `none`  
**Description**: Rewrite the Discovery Card OpenAPI so it matches F-DA07: Card `type` catalog, home/typed `link` values, markdown `description` semantics, Mentee/Member card content, and admin-only Notification list filters. Docs only — no Python.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `../mentorhub/DeveloperEdition/standards/ArchitecturePrinciples.md`
- `tasks/_PLANNING.md` — configurator is the schema source; MongoIO only; do not edit sibling repos
- `README.md`
- `docs/openapi.yaml` — current F090/F094 contract (`info.version` `0.3.0`)
- `../mentorhub_api_utils/README.md` — list GET is a JSON **array**; pagination is request headers `offset` / `size`
- `../mentorhub_api_utils/api_utils/flask_utils/list_request.py` — `parse_list_request` / `parse_filter_params` (`contains` / `in_list`)
- `../mentorhub_api_utils/api_utils/services/notification_service.py` — `NOTIFICATION_LIST_ORDER` (no `NOTIFICATION_LIST_FILTERS` today); shared `create_notification_get_routes` currently passes an empty filter spec
- `../mentorhub_api_utils/api_utils/services/rbac.py` — `is_admin` / `build_outbound_match`

**Definitive schemas** must be fetched from the running MongoDB configurator. Start the backing database if needed (`pipenv run db`), then:

```bash
curl -X GET "http://localhost:8383/api/configurations/json_schema/Card.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Notification.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Note.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Event.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Journey.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Profile.yaml/latest/" -H "accept: application/json"
```

If the configurator is unavailable, set **Status** to `Blocked` and stop — do not fall back to dictionary YAML in another repository.

Card remains a **configurator-only projection schema**. Every `GET /api/cards*` response is still a JSON array of Card. Property set stays aligned to live `Card.yaml` (`_id`, `name`, `description`, `link`, `type`; `additionalProperties: false`).

**External prerequisite (do not Block this task if the configurator is reachable):** live `Card.yaml` `type` enum is still collection-aligned (`Event | Member | Mentee | Notification | Path | Plan | Resource`). F-DA07 requires Discovery to emit additional `type` values so the Discovery SPA can icon/hover by type. **Union** the live enum with the values this API will emit (below). Record any delta versus live `Card.yaml` in **Execution Notes** as a MongoDB dictionary follow-up. Do **not** read files in other domain repos.

**Card `type` values this API will emit** (F-DA07 / F-DS05 catalog that Discovery actually returns):

| Card | `type` | Where |
| --- | --- | --- |
| Notification | `Notification` | home and `GET /api/cards/notifications` |
| Products (synthetic) | `Products` | home, Admin only |
| Discounts (synthetic) | `Discounts` | home, Admin only |
| Logs (synthetic) | `Logs` | home, Admin only |
| Customer (singleton) | `Customer` | home, Customer role only |
| Member | `Member` | home |
| Mentee | `Mentee` | home |
| Learning Journey (synthetic) | `Journey` | home, Mentee role only |
| Resource / Path / Plan / Event | existing | typed lists |

Do **not** add a Coordinator home section or a Coordinator card in this issue. If live `Card.yaml` includes `Coordinator`, keep it in the OpenAPI enum; otherwise omit it. Discovery does not emit `Coordinator`.

**Home composite** (`GET /api/cards`) — keep the eight-section order and role gates. Update descriptions for types, links, and markdown content:

1. Active Notifications for token `profile_id`, newest `created.at_time` first. **Every** Notification card now includes `link` `discovery/notification/{id}` (home no longer omits `link`).
2. Admin: synthetic Products — `type: Products`, `link: "admin/settings"`.
3. Admin: synthetic Discounts — `type: Discounts`, `link: "admin/settings?tab=discounts"`.
4. Admin: synthetic Logs — `type: Logs`, `link: "admin/logs"` (unchanged path).
5. Customer role: one Customer card — `type: Customer`, `link: "customer/customer/{id}"`.
6. Customer or Coordinator: Member cards, `saved.at_time` desc. `link` remains `customer/profile/{id}`. `description` is **Markdown** summarizing Journey progress (Library / Now / Next resource counts) and Activity (Event count in the last 30 days).
7. Mentor: Mentee cards, `saved.at_time` desc. `link` is `mentor/mentee/{id}` (was `mentee/mentee/{id}`). `description` is **Markdown** summarizing Activity (Event count in the last 30 days) and the mentor’s Notes on that mentee.
8. Mentee role: synthetic Learning Journey — `type: Journey`, `link: "mentee/journey"`.

`offset` / `size` still apply to the **combined** list. Relative SPA paths, no leading slash. `{origin}` in the GitHub issue is the SPA origin the client prepends — Discovery still emits the relative path only.

**Typed lists** — same five paths. Changes:

- `GET /api/cards/notifications`:
  - `link` `discovery/notification/{id}` (unchanged for this list; now matches home).
  - Query filters `name` (`contains`) and `status` (`in_list`, `active` / `archived`) are **admin-only**. Non-admin callers that send `name` or `status` receive `403`. Non-admin lists remain outbound-scoped and unfiltered by those params.
  - Default order remains `created.at_time` desc.
- Resource / Path / Plan / Event `link` conventions are unchanged.

Do **not** add by-id Card paths. Notification control POSTs are unchanged. Do not add `/api/cards/members` or `/api/cards/mentees`.

**Activity window:** document a constant **30 days** for Event counts on Member and Mentee cards.

Bump `info.version` to `0.4.0`.

## Goals

- `docs/openapi.yaml` `Card.type` enum includes every value Discovery will emit after F120 (`Customer`, `Products`, `Discounts`, `Logs`, `Journey`, plus the existing seven).
- `GET /api/cards` description lists the eight sections with the new `type` and `link` values, markdown `description` semantics for Member and Mentee, and Notification `link` always present.
- Products `link` is `admin/settings`; Discounts `link` is `admin/settings?tab=discounts`.
- Mentee `link` is `mentor/mentee/{id}`.
- `GET /api/cards/notifications` documents admin-only `name` / `status` filters and `403` for non-admin filter attempts.
- Card `description` is documented as Markdown (maxLength still from live `Card.yaml`).
- Notification control paths, typed Resource/Path/Plan/Event lists, pagination headers, and array `Card` responses are unchanged except as above.
- No `/api/profile`, `/api/customer`, by-id Card paths, `after_id`, `has_more`, or `next_cursor`.
- The document remains valid OpenAPI 3.0.x.

### Craftsmanship Expectations

- Ground property names, required lists, and `additionalProperties` in the live configurator schemas. Do not invent Card fields.
- `link` stays a relative journey path (F090 already noted live `Card.yaml` may still mark `format: uri`). Keep the configurator property set; state relative-path behavior on the operations.
- Do not copy SPA layout/icon details into this spec. Icon names are SPA-owned. This API only emits `type` and `link`.
- Derive role names from `Config` constants in prose (`ROLE_ADMIN`, `ROLE_CUSTOMER`, …), not from hardcoded display strings in other repos.

## Testing Expectations

Run all commands from this API repository root.

- **Schema fetch** — all configurator curls succeed; record schema versions in **Execution Notes**.
- **Spec validation**
  - `python3 -c "import yaml; yaml.safe_load(open('docs/openapi.yaml'))"`
  - Confirm `info.version` is `0.4.0`.
  - Confirm home description has all eight sections with the new types/links and markdown Member/Mentee content.
  - Confirm `Card.type` enum includes `Customer`, `Products`, `Discounts`, `Logs`, `Journey`.
  - Confirm `/api/cards/notifications` documents `name`, `status`, and admin `403`.
  - Confirm doomed typed paths (`/api/cards/members`, `/api/cards/mentees`, …) stay absent.
- **Unit / lint / build** (docs-only; suite must still pass)
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `curl -s http://localhost:8397/docs/openapi.yaml` — served file includes `0.4.0` and the new enum / notification filter params

This task does **not** require Python tests or runtime Card payloads to match the new contract yet (implementation is F110–F140).

## Outputs

- `docs/openapi.yaml` — Card type enum; home composite types/links/markdown; Mentee link; Products/Discounts links; Notification admin filters; `info.version` `0.4.0`

The agent must not update files outside this list.

## Execution Notes
