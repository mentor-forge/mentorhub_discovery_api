# F094 – README and seed-backed Card e2e

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F093_typed_card_surface_events`  
**Description**: Point README at the reduced Card surface and lock home/typed Card behaviour to Developer Edition seed personas so e2e asserts real documents, order, and `link` values.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md`
- `README.md` — still lists customer/members/mentees/products/settings typed lists
- `src/server.py` — startup log lines for typed cards
- `docs/openapi.yaml` — F090 contract
- `test/e2e/e2e_auth.py` — `get_auth_token(**claims)` already supports persona overrides; default is admin `profile_id` `A00000000000000000000001`
- `test/e2e/test_cards.py` — contract-level array/shape tests after F093
- `test/test_server.py` — only if log-line assertions drift

**Seed personas** (Developer Edition Mongo seed; mint JWTs with `get_auth_token`):

| `sub` | `profile_id` | `roles` | Extra claims | Home expectations |
| --- | --- | --- | --- | --- |
| `mike` | `A00000000000000000000001` | `["admin"]` | none | Products, Discounts, Logs cards with links `admin/products`, `admin/discounts`, `admin/logs`. No Customer/Member/Mentee/Journey sections. |
| `daniel` | `A00000000000000000000002` | `["mentee"]` | `customer_id` `D00000000000000000000002`, `mentor_id` `A00000000000000000000010` | Leading Notification `_id` `C00000000000000000000001` (InviteMember), **no** `link`. Trailing Learning Journey card, `link` `mentee/journey`. No Admin/Customer/Member/Mentee sections. |
| `stacey` | `A00000000000000000000008` | `["customer"]` | `customer_id` `D00000000000000000000002` | Customer card `_id` `D00000000000000000000002`, `link` `customer/customer/D00000000000000000000002`. Then Member cards for that customer, `saved.at_time` desc, each `link` `customer/profile/{id}`. |
| `emma` | `A00000000000000000000007` | `["coordinator"]` | `customer_id` `D00000000000000000000002` | Member cards only (no Customer singleton). |
| `paula` | `A00000000000000000000010` | `["mentor"]` | `mentor_id` `A00000000000000000000010` | Mentee cards for profiles with that `mentor_id`, `saved.at_time` desc, `link` `mentee/mentee/{id}`. |

If a seed document is missing (partial local DB), skip that assertion with a clear reason — do not fake data.

**Typed-list link checks** (use a bearer that includes Mentor when testing the mentor-side Resource/Path links):

- `GET /api/cards/notifications` as daniel: Notification `C00000000000000000000001` has `link` `discovery/notification/C00000000000000000000001`.
- `GET /api/cards/resources` as paula (mentor): each Resource `link` is `mentor/resource/{id}`. Same path as a non-mentor (e.g. daniel) uses `mentee/resource/{id}`.
- `GET /api/cards/paths` — same mentor vs non-mentor split (`mentor/path/{id}` vs `mentee/path/{id}`).
- `GET /api/cards/plans` — `mentor/plan/{id}` even for a non-mentor caller if the list is visible.
- `GET /api/cards/events` — when non-empty, `type` is Event and `link` is `mentee/event/{id}`.

Do **not** mention paths in other repositories. Do not change Python production code unless README/server log lines still name deleted prefixes.

## Goals

- `README.md` endpoint table and curl examples cover `GET /api/cards`, `GET /api/cards/resources` (and mention paths/plans/notifications/events), and Notification control. Doomed typed lists are gone.
- `src/server.py` log summary matches the remaining prefixes.
- `test/e2e/e2e_auth.py` exposes named persona helpers or constants for the table above (still one signing helper).
- `test/e2e/test_cards.py` asserts home section membership/order/`link` for the personas, plus the typed-list link cases. Existing 401 / pagination / by-id 404 coverage remains.
- Card shape assertions still allow omitted `type` on synthetic/Customer cards and omitted `link` on home Notifications.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — new persona tests pass (or skip with a missing-seed message)
  - `curl -s http://localhost:8397/docs/openapi.yaml` — remaining Card paths only
  - Spot-check README curl against the running API with a minted bearer

## Outputs

- `README.md` — endpoint table, project structure, curl examples
- `src/server.py` — registered-route log lines only if they still name doomed prefixes
- `test/e2e/e2e_auth.py` — persona helpers/constants
- `test/e2e/test_cards.py` — seed-backed home + link e2e
- `test/test_server.py` — only if startup-log tests exist and drift

The agent must not update files outside this list.

## Execution Notes
