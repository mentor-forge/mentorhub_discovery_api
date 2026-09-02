# D110 – Default search must return Mentee cards

**Status**: Pending  
**Type**: Defect  
**Depends On**: `F100_openapi_card_updates`  
**Description**: `GET /api/cards` (the default search / home composite) does not return Mentee cards for Mentor callers whose token has `profile_id` but no `mentor_id` claim. Align mentee scope with shared Profile outbound (fall back to `profile_id`) so Mentor home lists include Mentee cards. Do not change Card `type`, `link`, or markdown content in this task.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — MongoIO only; all collection I/O through `MongoIO` / `execute_list_query`
- `README.md`
- `docs/openapi.yaml` — F100 home section 7 (Mentor → Mentee cards)
- `src/services/card_service.py` — `get_home_cards` section 7 currently requires **both** `Config.ROLE_MENTOR` in roles **and** `token.get("mentor_id")`. Missing `mentor_id` skips the section entirely.
- `src/services/profile_service.py` — `get_mentee_profiles` scopes with `token.get("mentor_id")` and returns `[]` when that claim is absent
- `../mentorhub_api_utils/api_utils/services/profile_service.py` — `_profile_identity_or` already falls back: if `mentor_id` is missing, it uses `{"mentor_id": token.profile_id}` so mentors remain in Profile outbound scope
- `test/services/test_card_service.py` — `test_mentees_omitted_without_mentor_id` encodes the buggy gate
- `test/e2e/test_cards.py` — Paula persona asserts Mentee `link` prefix but does **not** fail when the list is empty

**Why this is a defect:** Developer Edition mentor JWTs may carry `profile_id` (the mentor’s Profile `_id`) without a separate `mentor_id` claim. Seed mentee Profiles store `mentor_id` as that Profile `_id`. Shared Profile outbound already understands that fallback; Discovery’s home composite and `get_mentee_profiles` do not, so default search returns no Mentee cards.

**MongoDB I/O**: still MongoIO / `execute_list_query` only. Do not call `get_collection`. Do not add new collections.

Do **not** change Notification links, synthetic card types, Member/Mentee markdown, or Products/Discounts links (F120 / F130). Do not add HTTP routes.

**Mentor identity helper** (use in both files; keep it small):

- `mentor_scope_id(token)` → `token.get("mentor_id") or token.get("profile_id")` (first present wins).
- Home section 7: include Mentee cards when `Config.ROLE_MENTOR` is in roles **and** `mentor_scope_id(token)` is present.
- `ProfileService.get_mentee_profiles` uses `mentor_scope_id(token)` as the `mentor_id` match value (still `encode_document` on that id immediately before MongoIO).
- Callers without Mentor role still skip the section in `get_home_cards` (role gate stays on `CardService`).
- Empty list when the resolved scope id is missing.

## Goals

- A Mentor token with `profile_id` and **no** `mentor_id` still loads Mentee Profiles whose `mentor_id` equals that `profile_id`.
- A Mentor token that **does** set `mentor_id` still scopes by `mentor_id` (claim wins over `profile_id`).
- Non-Mentor roles still get no Mentee section even if `mentor_id` / `profile_id` are present.
- Member section, Notification section, and synthetic cards are unchanged.
- `get_member_profiles` is unchanged (still `token.customer_id`).

### Craftsmanship Expectations

- Reuse the same identity fallback the shared Profile service already uses. Do not invent a second meaning for `mentor_id`.
- Keep role gating on `CardService.get_home_cards`. Do not push Mentor-role checks into `ProfileService.get_mentee_profiles` (that helper stays identity-scoped; home owns the role gate).
- Do not query Profile from `CardService` except through `ProfileService.get_mentee_profiles`.

## Testing Expectations

Run all commands from this API repository root.

- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - `test/services/test_card_service.py`:
    - Replace `test_mentees_omitted_without_mentor_id` with: Mentor role + `profile_id` only **does** call `get_mentee_profiles` and project Mentee cards.
    - Mentor role + explicit `mentor_id` still scopes by `mentor_id` (claim wins).
    - Non-Mentor with `mentor_id` still omits the section (`get_mentee_profiles` not called).
  - Add or update `test/services/test_profile_service.py` (create if missing) so `get_mentee_profiles` encodes `profile_id` into the `mentor_id` match when the claim is absent, and uses `mentor_id` when present.
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `pipenv run e2e` — existing suite stays green. Do **not** yet require Paula to return a non-empty Mentee list (that assertion is F150, after seed-backed content/link updates). A Mentor-with-`profile_id`-only unit test is the proof for this defect.

## Outputs

- `src/services/card_service.py` — Mentor section gate uses `mentor_id` or `profile_id`
- `src/services/profile_service.py` — `get_mentee_profiles` scopes with the same identity fallback
- `test/services/test_card_service.py` — updated Mentor/Mentee home tests
- `test/services/test_profile_service.py` — create or update mentee-scope tests

The agent must not update files outside this list. Do not edit OpenAPI. Do not add or remove HTTP routes.

## Execution Notes
