# F160 – Pin api-utils 1.0.1

**Status**: Shipped  
**Type**: Feature  
**Depends On**: none  
**Description**: Pin `api-utils==1.0.1` from CodeArtifact so Discovery consumes the Token contract that exposes `display_name` instead of `name`. Application replacements land in F161.

## Context

Always read these files before implementation:

- `../mentorhub/DeveloperEdition/standards/api_standards.md`
- `tasks/_PLANNING.md` — CodeArtifact install is `pipenv run install` (not bare `pipenv install`); lock via `scripts/pipenv-lock.sh` when hashes must refresh
- `README.md` — currently documents `api-utils==1.0.0`
- `Pipfile` / `Pipfile.lock` — currently pin `api-utils==1.0.0` on the `codeartifact` index
- `../mentorhub_api_utils/README.md` — release/pin notes
- `../mentorhub_api_utils/api_utils/flask_utils/token.py` — sibling tree may still be `1.0.0`; **do not** treat it as the 1.0.1 contract

**Issue**: [F-DA08](https://github.com/mentor-forge/mentorhub_discovery_api/issues/13) — bump `api_utils` to **1.0.1**.

**External prerequisite**: `api-utils==1.0.1` must be on the CodeArtifact index. If `scripts/pipenv-lock.sh` / `pipenv run install` cannot resolve 1.0.1, set **Status** to `Blocked` and stop. Run `mh` once per shell if CodeArtifact credentials are missing.

**Installed package is source of truth** for 1.0.1. After install, inspect the CodeArtifact copy (not the sibling working tree):

```bash
pipenv run python -c "import inspect; from api_utils.flask_utils import token as t; print(inspect.getsource(t.Token.to_dict)); print(inspect.getsource(t.Token._map_claims)); print(inspect.getsource(t.create_flask_token))"
```

Confirm `create_flask_token()` / `Token.to_dict()` expose **`display_name`** and no longer treat Flask-token `"name"` as the display field.

This task is **dependency pin only**. Do not rewrite routes, services, tests, OpenAPI, or README here (README pin text is F161). Do **not** paper over a pin failure with a local Token shim.

**Orchestrator:** A `pipenv run test` failure whose traceback is only Flask-token `name` vs `display_name` is **expected** and is **not** a Task Failure Case. Record it in Execution Notes, mark this task Shipped after the pin/install/inspect goals succeed, and continue to F161. Halt only if 1.0.1 will not resolve, install fails, or tests fail for a different reason.

## Goals

- `Pipfile` pins `api-utils==1.0.1` with `index = "codeartifact"` (keep the existing comment that the PyPI package named `api-utils` is unrelated).
- `Pipfile.lock` is regenerated against CodeArtifact (`scripts/pipenv-lock.sh`) and consumed by `pipenv run install`.
- `pip show api-utils` (inside the Pipenv) reports **1.0.1**.
- Import check after install:
  ```python
  from api_utils.flask_utils.token import Token, create_flask_token

  assert callable(create_flask_token)
  assert hasattr(Token, "to_dict")
  ```
  Plus the inspect check above: `to_dict` keys include `display_name` (not Flask-token `name` as the display field).
- No `src/`, `test/`, `docs/`, or `README.md` edits in this task.

### Craftsmanship Expectations

- Do not vendor or copy `Token` / `create_flask_token` into this repo.
- Do not bump to `1.1.0` or an unreleased sibling version; the issue is **1.0.1**.
- MongoDB I/O stays on `MongoIO`; this task does not touch `src/services/`.

## Testing Expectations

Run all commands from this API repository root.

- **Install**
  - `mh` once per shell if CodeArtifact credentials are not already available
  - `sh scripts/pipenv-lock.sh`
  - `pipenv run install`
  - Inspect installed `Token.to_dict` / `_map_claims` as above
- **Unit tests**
  - `pipenv run test` — existing suite against 1.0.1 **before** F161. Token-field-only failures: document, do not revert the pin, proceed (see Orchestrator note).
  - `pipenv run lint`
  - `pipenv run build`
- **Packaging verification**
  - Defer `pipenv run container` / `pipenv run api` / `pipenv run e2e` to F161 so the image and e2e JWTs are verified after `display_name` replacements. Optionally `pipenv run container` here if unit tests are already green and you want an early image check; it is not required to mark this task Shipped.

## Outputs

- `Pipfile` — pin `api-utils==1.0.1`
- `Pipfile.lock` — refresh via `scripts/pipenv-lock.sh` and `pipenv run install`

The agent must not update files outside this list.

## Execution Notes

**Plan**
- Pin-only: update `Pipfile` `api-utils` from `==1.0.0` to `==1.0.1` (keep `index = "codeartifact"` and the unrelated-PyPI comment).
- Do not edit `src/`, `test/`, `docs/`, or `README.md` (F161 owns token rewrites and README pin text).
- Do not path-install the sibling `mentorhub_api_utils` checkout; CodeArtifact is source of truth.
- Sequence from repo root: `mh` if needed → `sh scripts/pipenv-lock.sh` → `pipenv run install`.
- Confirm `pipenv run pip show api-utils` is 1.0.1; inspect installed `Token.to_dict` / `_map_claims` / `create_flask_token` for `display_name` (not Flask-token `"name"` as the display field).
- Run `pipenv run test`, `pipenv run lint`, `pipenv run build`. Token-field-only test failures are expected and recorded; halt only if 1.0.1 will not resolve, install fails, or tests fail for a different reason.
- Container/e2e deferred to F161.

**Commands**
- `mh` — CodeArtifact auth refreshed.
- `sh scripts/pipenv-lock.sh` — lock succeeded; `Pipfile.lock` hash `2c13125c2a1a16b1878b52856aa62749db7411a4e64b1dd259bab5d924430f82`.
- `pipenv run install` — installed `api-utils-1.0.1` from CodeArtifact (replaced 1.0.0). No sibling path-install.

**Version confirmation**
- `pipenv run pip show api-utils` → **Version: 1.0.1** (location: Pipenv site-packages, not sibling tree).
- Import check: `create_flask_token` callable; `Token.to_dict` present.

**Installed Token contract (CodeArtifact 1.0.1)**
- `Token.to_dict()` keys: `user_id`, **`display_name`**, `roles`, `profile_id`, `customer_id`, `mentor_id`, `remote_ip`.
- Display field is `display_name`; value is `claims.get("name") or claims.get("display_name") or ""` (JWT wire claim may still be OIDC `name`; Flask-token dict key is not `name`).
- `_map_claims()` maps `sub` → `user_id`, normalizes `roles`, requires `profile_id`, defaults `customer_id` / `mentor_id`. Does not put a Flask-token `name` key on the application dict.
- `create_flask_token()` returns `Token().to_dict()`.

**Test results**
- `pipenv run test` — **209 passed**, 61 deselected (e2e), 84 subtests passed. No Flask-token `name` vs `display_name` failures.
- `pipenv run lint` — black check clean (30 files unchanged).
- `pipenv run build` — `compileall` succeeded (quiet).
- `pipenv run container` / `api` / `e2e` deferred to F161.

**Follow-ups**
- F161 owns `src/` / `test/` / README `display_name` replacements and packaging verification.
- No blockers. Did not commit or push.
