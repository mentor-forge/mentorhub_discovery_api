# F161 – Use token.display_name (api-utils 1.0.1)

**Status**: Pending  
**Type**: Feature  
**Depends On**: `F160_bump_api_utils_1_0_1`  
**Description**: After the 1.0.1 pin, replace Flask-token `name` with `display_name` everywhere this API reads the token (attribute or dict). Leave Card, Notification, Profile, and Event **document** `name` fields unchanged. Align JWT minting and README with the 1.0.1 Token contract.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md`
- `tasks/PENDING.F160.bump_api_utils_1_0_1.md` (or `SHIPPED.F160.bump_api_utils_1_0_1.md`) — pin complete; Execution Notes may list 1.0.1 Token `to_dict` keys
- `README.md` — still says `api-utils==1.0.0`
- `src/routes/card_routes.py` — `create_flask_token()`
- `src/routes/notification_routes.py` — `create_flask_token()`
- `src/services/` — token is a **dict** (`token.get("user_id")`, `token.get("profile_id")`, …). Confirm none still read Flask-token `"name"`.
- `test/routes/test_card_routes.py` — `TOKEN` fixture
- `test/routes/test_notification_routes.py`
- `test/routes/test_notification_card_routes.py`
- `test/services/` — any token helper dicts
- `test/e2e/e2e_auth.py` — JWT claims (`sub`, `roles`, `profile_id`, …); today there is no `name` / `display_name` claim
- `test/e2e/test_cards.py` / `test/e2e/test_notification.py` — Card/Notification **document** `name` only

**Issue**: [F-DA08](https://github.com/mentor-forge/mentorhub_discovery_api/issues/13) — replace any use of `token.name` with `token.display_name`.

**1.0.1 Token contract** (installed package, not sibling `1.0.0` tree):

```bash
pipenv run python -c "import inspect; from api_utils.flask_utils import token as t; print(inspect.getsource(t.Token.to_dict)); print(inspect.getsource(t.Token._map_claims))"
```

Routes already call `create_flask_token()`, which returns a **dict**. Replacements are therefore:

| Do replace (Flask token) | Do **not** replace (domain documents / OpenAPI) |
| --- | --- |
| `token.name` (attribute) | Card `name` (`CARD_PROPERTIES`, projections, e2e) |
| `token["name"]` / `token.get("name")` when `token` is the Flask token dict | Notification `name` (create body, admin `?name=` filter) |
| JWT payload / e2e claims that populate the Token display field | Profile `name` / `full_name` |
| Mock `TOKEN` dicts that include a `"name"` key for the caller | Event card `name` (Event `type`) |
| README pin `==1.0.0` | Filter spec `"name": {"type": "contains", "field": "name"}` |

If 1.0.1 maps JWT claim `display_name` (and no longer `name`), add `display_name` to `get_auth_token` / persona payloads in `e2e_auth.py` the same way F010 required `profile_id`. If 1.0.1 still accepts claim `name` but exposes `display_name` on the dict, mint `display_name` (or both) so e2e tokens match login personas. Do not 401-fail e2e by omitting a claim the new Token mapper requires.

Shared `api_utils` GET factories are not copied locally; they pick up 1.0.1 automatically. Local factories in `card_routes.py` / `notification_routes.py` only change if they read the token display field.

**MongoDB I/O**: any service edit still uses `MongoIO` only. This task should not need new queries.

## Goals

- Zero Flask-token uses of `.name` / `["name"]` / `.get("name")` in `src/` and `test/` where the object is the caller token from `create_flask_token` / `Token`.
- Those call sites use `display_name` (attribute or dict key matching 1.0.1 `to_dict`).
- Unit-test `TOKEN` fixtures include `display_name` when tests or services read it; they do not keep a misleading `"name"` key on the **token** dict.
- `test/e2e/e2e_auth.py` JWTs satisfy 1.0.1 (`profile_id` remains required; add `display_name` if the mapper requires or prefers it).
- `README.md` api-utils notes pin **`api-utils==1.0.1`** (list GET / MongoIO wording otherwise unchanged).
- `docs/openapi.yaml` is unchanged unless it documents a token `name` claim (it should not; Card `name` stays).
- Confirmation greps (must stay **zero** for Flask-token `name`, while document `name` hits remain):
  ```bash
  rg 'token\.name' src test
  rg 'token\[.name.\]|token\.get\(.name.\)' src test
  ```

### Craftsmanship Expectations

- Do not rename Card / Notification / Profile / Event **resource** `name` to `display_name`.
- Do not implement a local alias (`token["name"] = token["display_name"]`) to avoid updating call sites.
- Do not patch `api_utils` in this repo; if 1.0.1 is missing `display_name`, F160 should have been Blocked.
- Prefer the installed Token dict keys as the single contract; do not re-derive claims in routes.

## Testing Expectations

Run all commands from this API repository root.

- **Install** (already 1.0.1 from F160; re-run if the venv is stale)
  - `mh` once per shell if CodeArtifact credentials are not already available
  - `pipenv run install`
- **Confirmation**
  - The two `rg` commands above — **zero** hits
  - `rg 'api-utils==1\.0\.0' README.md Pipfile` — **zero** hits
- **Unit tests**
  - `pipenv run test`
  - `pipenv run lint`
  - `pipenv run build`
  - Existing route tests still 401 without bearer; home / notification factories still pass the token dict through unchanged aside from the display field rename
  - Negative check: least-privileged persona JWTs still work; missing `profile_id` still 401 (do not weaken Token validation)
- **Packaging verification**
  - `pipenv run container`
  - `pipenv run api`
  - `docker exec` (or equivalent) `pip show api-utils` on the running Discovery API container → **1.0.1**
  - `pipenv run e2e` — full suite green against the containerized API (personas in `e2e_auth.py`)

## Outputs

- `src/routes/card_routes.py` — Flask token display field if referenced
- `src/routes/notification_routes.py` — same
- `src/services/*.py` — only if a service reads Flask-token `name`
- `test/routes/test_card_routes.py` — `TOKEN` fixture / assertions
- `test/routes/test_notification_routes.py`
- `test/routes/test_notification_card_routes.py`
- `test/services/*.py` — token helper dicts only if they include Flask-token `name`
- `test/e2e/e2e_auth.py` — JWT `display_name` (or equivalent 1.0.1 claim)
- `README.md` — pin text `1.0.1`

The agent must not update files outside this list. Do not edit `docs/openapi.yaml` unless a token-claim description is actually present.

## Execution Notes
