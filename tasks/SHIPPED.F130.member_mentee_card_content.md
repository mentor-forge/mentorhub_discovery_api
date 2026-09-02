# F130 – Member and Mentee card Markdown content

**Status**: Shipped  
**Type**: Feature  
**Depends On**: `F120_card_type_and_link_projection`  
**Description**: Replace Member and Mentee Card `description` with Markdown that a Customer (progress + activity) or Mentor (activity + notes) can scan. Keep F120 `type`/`link` behavior. Enrichment is consume-only via local Journey / Event / Note subclasses and MongoIO.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md` — services are collection-aligned; CardService orchestrates; no PyMongo `get_collection` in `src/`
- `tasks/_PLANNING.md` — MongoIO only (`get_document`, `get_documents`, `execute_list_query`); `encode_document` before MongoIO
- `README.md`
- `docs/openapi.yaml` — F100 Member/Mentee markdown semantics; 30-day activity window
- `src/services/card_service.py` — `get_home_cards` Member/Mentee sections; `project` currently copies Profile `description`
- `src/services/profile_service.py` — `get_member_profiles` / `get_mentee_profiles` (D110 identity fallback)
- `src/services/event_service.py` — thin consume subclass; shared `get_events` outbound is **own-profile only** and must **not** be used to count another person’s events
- `../mentorhub_api_utils/api_utils/services/journey_service.py` — `get_journey_progress` exists but is mentor/admin-gated and returns zeros when Journey outbound fails; **do not** call it for Customer Member cards
- `../mentorhub_api_utils/api_utils/services/event_service.py` — Event identity/outbound
- `../mentorhub_api_utils/api_utils/services/note_service.py` — Note list is resource-scoped and own-profile outbound; **do not** use `get_notes_for_resource` for mentee notes
- `../mentorhub_api_utils/api_utils/mongo_utils/mongo_io.py` — `get_documents`
- `../mentorhub_api_utils/api_utils/config.py` — `JOURNEY_COLLECTION_NAME`, `EVENT_COLLECTION_NAME`, `NOTE_COLLECTION_NAME`
- `test/services/test_card_service.py`

Re-fetch live schemas if F100 notes are incomplete:

```bash
curl -X GET "http://localhost:8383/api/configurations/json_schema/Journey.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Event.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Note.yaml/latest/" -H "accept: application/json"
curl -X GET "http://localhost:8383/api/configurations/json_schema/Card.yaml/latest/" -H "accept: application/json"
```

If the configurator is unavailable, set **Status** to `Blocked` and stop.

**Activity window:** `CARD_ACTIVITY_WINDOW_DAYS = 30`. Count Events whose `created.at_time` is on or after `now - 30 days` (UTC). Confirm the Event time field from live `Event.yaml` (`created.at_time`).

**Who can see what:** Enrichment runs **only** for Profile documents already returned by `get_member_profiles` / `get_mentee_profiles` (Profile outbound + D110 scope). Do not scan Journey / Event / Note globally. Do not use shared Event/Note outbound (own-profile) for these counts — that would always be zero for a Customer/Mentor looking at someone else. The authorization boundary is “this Profile is already on the caller’s Member or Mentee home section.”

**Collection-aligned helpers** (thin local subclasses; CardService orchestrates):

1. `src/services/journey_service.py` — `JourneyService(SharedJourneyService)` plus `resource_counts_for_profile(profile_id, token, breadcrumb) -> {"library": int, "now": int, "next": int}`.
   - Match active Journey for that `profile_id` via MongoIO (`status: active` if that is the live status enum; confirm from `Journey.yaml`).
   - Count: `library` and `now` = `len` of those arrays; `next` = sum of `resources` across Next topics (same arithmetic as shared `get_journey_progress`).
   - Missing journey → zeros. Do **not** call shared `get_journey_progress` (wrong RBAC for Customer).
2. `EventService` (existing local subclass) — `recent_event_count_for_profile(profile_id, token, breadcrumb, *, days=CARD_ACTIVITY_WINDOW_DAYS) -> int`.
   - MongoIO `get_documents` (or `execute_list_query`) on `EVENT_COLLECTION_NAME` with `profile_id` (and/or `context.profile_id` if that is how seed Events are stored — confirm from live schema and existing Event projection) plus the time window.
   - Return `len(docs)` (cap at `MAX_SIZE` if using `execute_list_query`). Do not use PyMongo `count_documents`.
3. `src/services/note_service.py` — `NoteService(SharedNoteService)` plus `notes_for_profile(profile_id, token, breadcrumb) -> list`.
   - Match notes whose subject is the mentee `profile_id` using live `Note.yaml` fields.
   - Prefer the **caller’s** notes (“their notes on the Mentee”): if `created.by_user` (or equivalent) exists, AND it with `token.user_id`.
   - Newest first. A small cap (e.g. 3) is enough for a card; do not dump the full history.
   - Empty list when none match.

**Markdown `description`** (must fit Card `description` maxLength from live `Card.yaml`, currently 4096). Build on a **copy** of the Profile document (set `description` then `project`) so `project` stays a pure field map. Do not keep the Profile’s original `description` when enrichment ran.

Member (Customer/Coordinator home):

```markdown
**Progress**
- Library: {n}
- Now: {n}
- Next: {n}

**Activity**
- {n} events in the last 30 days
```

Mentee (Mentor home):

```markdown
**Activity**
- {n} events in the last 30 days

**Notes**
- {note text or *No notes*}
```

Use GitHub-flavored Markdown lists and bold headings. Note lines should be the note body field from `Note.yaml` (likely a text/message field — confirm live). Truncate individual note lines so the whole `description` stays within maxLength.

**Performance:** Member/Mentee home pages are small (`size` ≤ 100, typically a handful of Profiles). Per-profile MongoIO reads are acceptable. Do not add a Card collection or cache layer.

Export new services from `src/services/__init__.py` if that package currently exports services.

## Goals

- Member home cards `description` is Markdown with Library / Now / Next counts and a 30-day Event count.
- Mentee home cards `description` is Markdown with a 30-day Event count and the mentor’s notes (or an explicit empty-notes line).
- Counts are zero / notes empty when there is no matching Journey / Event / Note — never `null` description.
- F120 `type` and `link` values are unchanged.
- Typed Resource/Path/Plan/Event/Notification lists do not call these enrichment helpers.
- All new I/O uses MongoIO / `execute_list_query`. `rg 'get_collection' src` remains zero in Discovery code (api_utils internals do not count).

### Craftsmanship Expectations

- Journey / Event / Note I/O lives on those services, not as raw queries inside `CardService`.
- Do not duplicate `get_journey_progress` RBAC; implement a Discovery consume helper whose only callers are already-authorized Member/Mentee Profiles.
- Do not widen shared Event/Note outbound in `api_utils`. Do not bump `Pipfile` for this task.
- Prefer deleting Profile `description` passthrough for Member/Mentee cards rather than concatenating old prose with the new Markdown.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_card_service.py` — Member description contains `Library`, `Now`, `Next`, and `30 days`; Mentee description contains `30 days` and a Notes section; zeros when helpers return empty; `project` still maps other types unchanged
  - `test/services/test_journey_service.py` — create; resource counts; missing journey → zeros; `encode_document` used on `profile_id`
  - `test/services/test_event_service.py` — add recent-count tests (window match; unrelated `profile_id` not counted)
  - `test/services/test_note_service.py` — create; mentee notes filtered to caller `user_id` when that field exists; empty list otherwise
  - Least-privilege: Customer Member enrichment does **not** require Mentor role; Mentor Mentee enrichment does **not** require Customer role. A non-member/non-mentee path must not call the helpers (home role gates).
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — keep green; do not yet require seed markdown strings (F150). Shape tests must still accept `description` as a string.
  - `curl -s http://localhost:8397/docs/openapi.yaml` — F100 spec unchanged

## Outputs

- `src/services/card_service.py` — orchestrate enrichment before Member/Mentee `project`
- `src/services/journey_service.py` — create (thin subclass + `resource_counts_for_profile`)
- `src/services/event_service.py` — `recent_event_count_for_profile`
- `src/services/note_service.py` — create (thin subclass + `notes_for_profile`)
- `src/services/__init__.py` — export new classes
- `test/services/test_card_service.py`
- `test/services/test_journey_service.py` — create
- `test/services/test_event_service.py` — update
- `test/services/test_note_service.py` — create

The agent must not update files outside this list. Do not change OpenAPI. Do not add HTTP routes. Do not change Notification filters.

## Execution Notes

### Plan (before implementation)

Configurator reachable. Live latest JSON schemas (versioned URLs HTTP 200):

| Dictionary | Latest version | Notes for F130 |
| --- | --- | --- |
| Journey.yaml | `0.1.0.0` | `status` enum `active`/`archived`. Match `{profile_id, status: active}`. `library`/`now` are arrays; `next` is modules with nested `topics.resources` in the live schema, but counts must use the same arithmetic as shared `get_journey_progress` (sum `len(item.resources)` over `next`). |
| Event.yaml | `0.1.0.0` | Identity is `context.profile_id` (no top-level `profile_id`). Time field is `created.at_time`. Also match legacy top-level `profile_id` like shared Event identity. Window: `created.at_time >= now - 30 days` UTC. |
| Note.yaml | `0.1.0.0` | Body field is `note`. Subject/author identity field is `profile_id`. Author breadcrumb is `created.by_user`. `status` enum `active`/`archived`. Newest `created.at_time` first, cap 3. |
| Card.yaml | `0.0.0.0` | `description` maxLength **4096**. |

Approach:

1. Add `JourneyService(SharedJourneyService)` with `resource_counts_for_profile` via MongoIO `get_documents` + `encode_document` on `profile_id`. Missing journey → zeros. Do **not** call shared `get_journey_progress`.
2. Add `EventService.recent_event_count_for_profile` via MongoIO `get_documents` with `$or` of encoded `context.profile_id` / `profile_id` plus `created.at_time $gte` cutoff. Return `len(docs)`. Constant `CARD_ACTIVITY_WINDOW_DAYS = 30`.
3. Add `NoteService(SharedNoteService)` with `notes_for_profile`: match encoded mentee `profile_id`, exclude archived, AND `created.by_user` with `token.user_id` when present, sort newest first, size 3. Empty list when none.
4. `CardService.get_home_cards` copies each Member/Mentee Profile, sets Markdown `description` from those helpers, then `project`. `project` stays a pure field map. Typed Resource/Path/Plan/Event/Notification lists do not call helpers. F120 `type`/`link` unchanged.
5. Export `JourneyService` and `NoteService` from `src/services/__init__.py`.
6. Tests: unit coverage for markdown/zeros/least-privilege/encode; then lint/build/container/api/e2e; curl OpenAPI still F100.

No OpenAPI, routes, Notification filters, Pipfile, or api_utils changes.

### Implementation summary

- `JourneyService.resource_counts_for_profile` — MongoIO `get_documents` on active Journey for encoded `profile_id`; Library/Now `len`; Next sums `resources` like shared `get_journey_progress` (no shared RBAC call). Missing → zeros.
- `EventService.recent_event_count_for_profile` — MongoIO `get_documents` `$or` of encoded `context.profile_id` / `profile_id` plus `created.at_time $gte now-30d` UTC. Returns `len(docs)`.
- `NoteService.notes_for_profile` — `execute_list_query` on encoded mentee `profile_id`, exclude archived, AND `created.by_user` = `token.user_id` when present, newest first, size 3. Body field `note`. Empty list when none.
- `CardService` copies each Member/Mentee Profile, sets Markdown `description`, then `project`. F120 `type`/`link` unchanged. Typed lists do not call helpers.
- Exported `JourneyService` and `NoteService` from `src/services/__init__.py`.

Live `Note.yaml` `profile_id` is described as the note-taker; it is the only Profile identity field, so it is used as the mentee subject match per the task. Live `Journey.yaml` `next` is modules→topics→resources; counts still use shared `get_journey_progress` arithmetic (sum `next[].resources`).

`rg 'get_collection' src` is zero. No Blocked condition.

### Test results

| Command | Result |
| --- | --- |
| Configurator schema curls (Journey, Event, Note, Card) | Pass (HTTP 200); versions `0.1.0.0` / `0.1.0.0` / `0.1.0.0` / `0.0.0.0` |
| `pipenv run test` | Pass (177 passed, 56 deselected, 89 subtests) |
| `pipenv run lint` | Pass (after `pipenv run format` on new tests) |
| `pipenv run build` | Pass |
| `pipenv run container` | Pass |
| `pipenv run api` | Pass (`mh up discovery-api`) |
| `pipenv run e2e` | Pass (56 passed, 177 deselected) |
| `curl -s http://localhost:8397/docs/openapi.yaml` | Pass — F100 spec unchanged (`info.version: 0.4.0`, Member Library/Now/Next, Mentee `mentor/mentee/{id}`, 30-day window) |
| `rg 'get_collection' src` | Zero matches |

Orchestrator confirmed unit/lint/build and `rg get_collection src` is zero.
