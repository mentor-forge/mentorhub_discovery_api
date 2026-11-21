# Discovery API AWS exit audit

Before migration the Pipfile and lock pinned API Utils 1.0.4 from CodeArtifact.
The Pipfile and lock now pin the public API Utils 1.0.5 release wheel. The
README’s 1.0.3 reference and the older F160/F161 notes describe earlier pins.

| Surface | Current dependency | Planned change |
| --- | --- | --- |
| `Pipfile`, `Pipfile.lock`, `scripts/pipenv-install.sh`, `scripts/pipenv-lock.sh` | CodeArtifact source, AWS CLI authentication and temporary authenticated index | F163 uses public PyPI for third-party packages and locks API Utils to the exact GitHub release wheel and SHA-256. Use `pipenv run install` to sync the developer environment and `pipenv lock` to refresh the lock. |
| `Dockerfile`, `scripts/docker-build.sh` | Authenticated `PIP_INDEX_URL` build argument populated by AWS CLI | F164 will build from the hash-verified lock using public sources and preserve the existing image and port. |
| `.github/workflows/docker-push.yml`, `.github/OIDC.md` | AWS OIDC, CodeArtifact token and index passed to Docker | F165 will remove AWS authentication, preserve main-branch GHCR publishing and add separate read-only PR validation. |
| `README.md`, `tasks/_PLANNING.md` | Developer setup still references CodeArtifact | F166 will update dependency setup and record runtime and CI acceptance. |

The public [API Utils 1.0.5 wheel](https://github.com/mentor-forge/mentorhub_api_utils/releases/download/v1.0.5/api_utils-1.0.5-py3-none-any.whl)
downloaded without credentials and matched SHA-256
`79de3829e2baa294497e08925908645bcea53cdf497d02b6bed71322a503d952`.
Pipenv pins that URL and digest together. The PyPI project named
`api-utils` is unrelated. For a later rollback, restore a previously verified
wheel pin and its matching lock together, then repeat install and container
acceptance. This release is the first verified GitHub-hosted rollback floor.

## Runtime contracts

The current Developer Edition Discovery API service configures only MongoDB,
JWT validation, logging and ports. A search of tracked runtime and test source
found no direct Cognito, AWS SDK or AWS endpoint usage. Preserve existing
JWT issuer, audience, signature and role/scope checks. The verified wheel
requires `profile_id` and maps `display_name`, `user_id`, `roles`,
`profile_id`, `customer_id` and `mentor_id` for local persona tokens.
Discovery's E2E fixtures already mint `display_name` and `profile_id`.
The F161 blocked note reports a historical Profile-to-Card projection
failure. Current source projects Profile `display_name`; rerun packaged
E2E acceptance from this branch to verify it. F161 remains outside this wave.

Keep database calls through MongoIO. The published wheel supports
`get_documents(collection_name, match, project, sort_by, skip, limit)`,
`get_document(collection_name, document_id)` and
`create_document(collection_name, document)`. Its update method accepts
`document_id`, `match`, `set_data`, `push_data`, `add_to_set_data` and
`pull_data`. The shared list helper takes keyword-only `match`, `sort_by`,
`offset`, `size` and `project` after `collection_name`. These APIs retain
existing service ownership. No Discovery schema, OpenAPI or production
identity-provider changes are required for the migration.
