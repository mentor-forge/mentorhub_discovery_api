# F150 – README and seed-backed F-DA07 Card e2e

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F140_notification_admin_filters`  
**Description**: Point README at the F-DA07 Card contract and lock home/typed Card behaviour to Developer Edition seed personas so e2e asserts types, links, Mentee presence, markdown Member/Mentee descriptions, and admin-only Notification filters.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md`
- `README.md` — endpoint table and curl examples
- `docs/openapi.yaml` — F100 contract
- `src/server.py` — registered-route log lines
- `test/e2e/e2e_auth.py` — `PERSONA_MIKE` / `DANIEL` / `STACEY` / `EMMA` / `PAULA` and `get_persona_token`
- `test/e2e/test_cards.py` — update in place
- `test/e2e/test_notification.py` — only if Notification control tests assert Card `link` omission

**Seed personas** (same table as F094; mint JWTs with `get_persona_token`). If a seed document is missing, skip that assertion with a clear reason — do not fake data.

| `sub` | Home expectations after F110–F140 |
| --- | --- |
| `mike` (admin) | Products / Discounts / Logs cards with `type` `Products` / `Discounts` / `Logs` and links `admin/settings`, `admin/settings?tab=discounts`, `admin/logs`. No Customer/Member/Mentee/Journey sections. |
| `daniel` (mentee) | Notification cards include `link` `discovery/notification/{id}` (no longer omitted). Trailing Learning Journey card `type: Journey`, `link` `mentee/journey`. |
| `stacey` (customer) | Customer card `type: Customer`. Member cards `type: Member`, `link` `customer/profile/{id}`, `description` Markdown containing Progress (Library/Now/Next) and Activity (30 days). |
| `emma` (coordinator) | Member cards only (no Customer singleton). Same Member markdown as Stacey when Members exist. |
| `paula` (mentor) | **At least one** Mentee card when seed mentees exist for `mentor_id`/`profile_id` `A00000000000000000000010`. Each has `type: Mentee`, `link` `mentor/mentee/{id}`, `description` Markdown containing Activity (30 days) and Notes. |

**Typed lists:**

- `GET /api/cards/notifications` as daniel: `200` + Cards with `link` `discovery/notification/{id}`; `?name=` or `?status=` → `403`.
- `GET /api/cards/notifications?status=active` (and a `name` contains that matches a seeded notification) as mike (admin): `200` + array; results honor the filter when seed data exists.
- Resource/Path/Plan/Event link checks from F094 remain (mentor vs mentee prefixes).

**Card shape:** `CARD_TYPE_ENUM` must include `Customer`, `Products`, `Discounts`, `Logs`, `Journey`. `type` is no longer omitted on synthetics/Customer.

Do **not** mention paths in other repositories. Do not change Python production code unless README/server log lines are wrong.

## Goals

- `README.md` endpoint table and curl examples describe home composite types/links, typed lists, Notification control, and admin-only notification `name`/`status` query params (non-admin `403`).
- `test/e2e/test_cards.py` asserts the persona table above, including **non-empty Mentee cards for Paula when seed exists** (this is the e2e proof for D110).
- Home Notification cards assert `link` present.
- `CARD_TYPE_ENUM` / `_assert_card_shape` accept the F100 types.
- Existing 401 / pagination / doomed-prefix 404 / by-id 404 coverage remains.

### Craftsmanship Expectations

- Keep persona helpers in `e2e_auth.py`; do not duplicate JWT minting in the test module.
- Skip, don’t fail, when a specific seed document is absent; fail when the persona is present and the contract is wrong (e.g. Paula has a token but zero Mentee cards **and** the DB has matching mentee Profiles — if you cannot cheaply detect seed Profiles, skip with a reason rather than asserting `len >= 1` blindly).
- Do not weaken `_assert_card_shape` to allow extra properties.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — new/updated persona and filter tests pass (or skip with a missing-seed message)
  - `curl -s http://localhost:8397/docs/openapi.yaml` — `info.version` `0.4.0`; Card type enum includes `Journey` / `Products`
  - Spot-check README curl against the running API with a minted bearer

## Outputs

- `README.md` — endpoint table, project structure notes if needed, curl examples (notification filters)
- `src/server.py` — registered-route log lines only if they are misleading
- `test/e2e/e2e_auth.py` — only if a persona claim is wrong for D110 (Paula should keep `mentor_id`; add a comment that home also works from `profile_id`)
- `test/e2e/test_cards.py` — seed-backed types, links, Mentee presence, markdown, notification filter RBAC
- `test/e2e/test_notification.py` — only if it still assumes home Notification cards omit `link`
- `test/test_server.py` — only if startup-log tests exist and drift

The agent must not update files outside this list.

## Execution Notes
