# F091 – Token-aware Card `link` projection

**Status**: Shipped  
**Type**: Defect  
**Depends On**: `F090_openapi_home_events_and_links`  
**Description**: Teach `CardService.project` to emit the SPA `link` values from F090. Remaining typed lists start returning the new links immediately. Home Notification cards keep omitting `link`. Do not change home section membership or delete typed routes.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — MongoIO only; do not edit sibling repos
- `README.md`
- `docs/openapi.yaml` — F090 `link` table
- `src/services/card_service.py` — `project` / `project_all`; Resource currently copies source `url` onto `link`
- `src/services/resource_service.py` — `ResourceCardService.get_resources` → `project_all`
- `src/services/path_service.py` — `PathCardService.get_paths`
- `src/services/plan_service.py` — `PlanCardService.get_plans`
- `src/services/notification_service.py` — `NotificationCardService.get_notifications` (typed list) vs `CardService.get_home_cards` (home)
- `src/services/profile_service.py` — `_member_cards` / `_mentee_cards` used by home and by the typed Member/Mentee lists that F093 will remove
- `test/services/test_card_service.py` — `test_project_resource_links_to_url` and other `project` cases
- `../mentorhub_api_utils/api_utils/mongo_utils/mongo_io.py` — I/O surface (this task should not add new queries)

**MongoDB I/O**: still MongoIO / `execute_list_query` only. `project` is a pure mapping.

**Why this is before the home rewrite:** F092’s new home sections (Customer, synthetic Admin/Journey, resorted Members/Mentees) must call the same `project` helper. Doing links first avoids rewriting home tests twice.

**`project` / `project_all` contract** (keep emitting only Card properties; omit absent fields; `_id` unchanged):

- Add `token` (roles from `token.get("roles") or []`; missing token ⇒ empty roles).
- Add an explicit flag for Notification links, e.g. `notification_link=False`.
  - Home (`get_home_cards`) passes `notification_link=False` (or relies on the default) so home Notification cards **omit** `link`.
  - `NotificationCardService` passes `notification_link=True` so typed Notification cards set `link` to `discovery/notification/{id}`.
- Member → `customer/profile/{id}`
- Mentee → `mentee/mentee/{id}`
- Resource → `mentor/resource/{id}` if `Config.ROLE_MENTOR` is in roles, else `mentee/resource/{id}`. **Stop** copying Resource `url` onto `link`.
- Path → `mentor/path/{id}` if Mentor, else `mentee/path/{id}`
- Plan → `mentor/plan/{id}` (role-independent)
- `{id}` is the 24-hex form of source `_id` (stringify ObjectId). Relative path, no leading slash.
- Customer / Products / Settings projections may omit `link` here if F092/F093 replace those typed lists; do not spend effort preserving Product/Setting list links.

Callers that already have a `token` (typed Card subclasses and `get_home_cards`) must pass it through `project` / `project_all`. Member/Mentee helpers in `profile_service.py` should accept `token` and forward it so home Member/Mentee cards get `customer/profile/{id}` and `mentee/mentee/{id}` in this task (those links are independent of the later home-section rewrite).

Do **not** add Event projection here (F093). Do **not** add synthetic Admin/Journey cards here (F092). Do **not** unregister routes.

## Goals

- `CardService.project` / `project_all` implement the F090 `link` table for Notification, Member, Mentee, Resource, Path, and Plan.
- Home Notification cards still have no `link`.
- `GET /api/cards/notifications` Card objects include `link` `discovery/notification/{id}`.
- Resource/Path links depend on whether token roles contain Mentor; Plan always uses the mentor plan path.
- Resource `url` is no longer copied to `link`.
- Existing home section membership (Notifications → Members → Mentees) is unchanged.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_card_service.py` — replace `test_project_resource_links_to_url` with mentor vs non-mentor Resource/Path cases; Plan link; Member/Mentee links; Notification omit vs include via the flag; `_id` hex in the path
  - Typed-subclass tests still pass; `NotificationCardService` list projection includes `link`
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — existing card e2e stay green (shape/type assertions). Do not add seed-persona link assertions yet (F094).
  - `curl -s http://localhost:8397/docs/openapi.yaml` — still the F090 spec

## Outputs

- `src/services/card_service.py` — token-aware `link` on `project` / `project_all`; home notifications omit `link`
- `src/services/resource_service.py` — pass `token` into `project_all`
- `src/services/path_service.py` — same
- `src/services/plan_service.py` — same
- `src/services/notification_service.py` — typed list sets `notification_link=True`
- `src/services/profile_service.py` — Member/Mentee `project_all` receives `token`
- `test/services/test_card_service.py` — link unit tests; drop Resource-`url`-as-link assertion

The agent must not update files outside this list. Do not change OpenAPI. Do not add or remove HTTP routes.

## Execution Notes

### Implementation Summary
- Updated `CardService.project` and `CardService.project_all` to accept `token` and `notification_link=False`:
  - Member -> `customer/profile/{id}`
  - Mentee -> `mentee/mentee/{id}`
  - Resource -> `mentor/resource/{id}` (if `ROLE_MENTOR` in roles) else `mentee/resource/{id}`. Stopped copying `url` to `link`.
  - Path -> `mentor/path/{id}` (if `ROLE_MENTOR` in roles) else `mentee/path/{id}`.
  - Plan -> `mentor/plan/{id}`.
  - Notification -> `discovery/notification/{id}` only when `notification_link=True`; omits `link` when `notification_link=False`.
- Updated callers to pass `token` into `project_all`:
  - `src/services/resource_service.py` (`ResourceCardService.get_resources`)
  - `src/services/path_service.py` (`PathCardService.get_paths`)
  - `src/services/plan_service.py` (`PlanCardService.get_plans`)
  - `src/services/notification_service.py` (`NotificationCardService.get_notifications` passes `notification_link=True`)
  - `src/services/profile_service.py` (`_member_cards`, `_mentee_cards`, and subclasses)
  - `src/services/card_service.py` (`get_home_cards`)
- Updated and expanded unit tests in `test/services/test_card_service.py` to cover all link projection scenarios.

### Verification Results
- `pipenv run format && pipenv run lint && pipenv run test`: 144 passed in 0.26s, lint clean.
- `pipenv run build`: passed cleanly.
- `pipenv run container && pipenv run api`: image built and service running.
- `pipenv run e2e`: 58 passed in 0.33s.
- `curl -s http://localhost:8397/docs/openapi.yaml`: served spec valid.
