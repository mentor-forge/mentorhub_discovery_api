# F150 – README and seed-backed F-DA07 Card e2e

**Status**: Shipped  
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

### Plan (written before implementation)

README is still the F094 Card surface: endpoint table and curls do not describe home composite `type`/`link` values, Notification `link` always on, or admin-only `name`/`status` on `GET /api/cards/notifications`. `src/server.py` log lines are already accurate (home, typed `{type}`, notification control) — leave them. `test_notification.py` never asserts home Notification `link` omission — leave it. `test_server.py` has no startup-log string assertions — leave it.

`e2e_auth.py`: Paula already keeps `mentor_id` `A00000000000000000000010` (same as `profile_id`). Add a D110 comment that home Mentee cards also resolve from `profile_id` when `mentor_id` is absent. Do not drop `mentor_id`.

`test_cards.py` already has F100 `CARD_TYPE_ENUM`, persona home stubs, typed Resource/Path/Plan/Event links, Daniel notification links, admin `?name=Invite` 200, mentee `?name=x` 403. Fill the F150 gaps without weakening `_assert_card_shape`:

- Mike: assert Products/Discounts/Logs `type` + links; no Customer/Member/Mentee/Journey types (not just prefix checks).
- Daniel: keep Journey trailing card + Notification `link`; add mentee `?status=` → 403.
- Stacey: skip if Customer seed missing; Member cards get Progress (Library/Now/Next) + Activity (30 days) markdown, skip if no Members.
- Emma: no Customer singleton; same Member markdown when Members exist.
- Paula (D110 proof): if home returns Mentee cards, each `type: Mentee`, `link: mentor/mentee/{id}`, markdown Activity (30 days) + Notes. If zero cards, skip with a missing-seed reason — Discovery has no Profile list, so seed Profiles cannot be detected cheaply over HTTP.
- All home persona tests: any Notification card must include `link discovery/notification/{id}`; use `size: 100` so pagination does not hide trailing Journey.
- Admin `?status=active` (and existing `?name=Invite`): 200 + Card array; skip when the filter matches nothing; do not fake data.

### Implementation

- `README.md`: endpoint table now describes home composite `type`/`link` values, typed lists, Notification control, and admin-only `name`/`status` on `GET /api/cards/notifications` (non-admin `403`). Curl examples mint admin + Daniel tokens and exercise those filters.
- `test/e2e/e2e_auth.py`: Paula still has `mentor_id`; comment notes home also works from `profile_id` (D110).
- `test/e2e/test_cards.py`: persona home helpers (`size: 100`, Notification `link` always on); Mike Products/Discounts/Logs types + no Customer/Member/Mentee/Journey; Daniel Journey + links; Stacey Customer (hex-case-insensitive `_id`) + Member markdown; Emma Member markdown, no Customer; Paula Mentee presence + `mentor/mentee/{id}` + Activity/Notes markdown (skip if no seed mentees); admin `?status=active` 200; mentee `?status=` 403. `_assert_card_shape` still rejects extra properties.
- Left unchanged: `src/server.py`, `test/e2e/test_notification.py`, `test/test_server.py`.

### Tests

| Command | Result |
| --- | --- |
| `pipenv run format && pipenv run lint` | Pass |
| `pipenv run test` | 204 passed, 60 deselected |
| `pipenv run build` | Pass |
| `pipenv run container` | Image `ghcr.io/mentor-forge/mentorhub_discovery_api:latest` |
| `pipenv run api` | `mh start down` then `mh start up discovery-api` (db + API back) |
| `pipenv run e2e` | **60 passed**, 0 skipped. Paula mentee home **passed** (seed mentees present; D110 proven). Stacey/Emma Member markdown passed. Admin Invite + `status=active` passed. Daniel `?name=` and `?status=` 403 passed. |
| `curl -s http://localhost:8397/docs/openapi.yaml` | `info.version` `0.4.0`; Card type enum includes Journey, Products, Customer, Discounts, Logs |
| README curl spot-check | `/api/config` 200; home admin Products/Discounts/Logs + Notification `discovery/notification/{id}`; resources 200 array; `?status=active` 200; `?name=Invite` → MemberInvite/InviteMember; Daniel `?name=x` 403 |

Orchestrator confirmed unit/lint/build. Pre-PR QA gate runs after this commit.
