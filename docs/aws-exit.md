# Discovery API AWS exit audit

Before migration the Pipfile and lock pinned API Utils 1.0.4 from CodeArtifact.
The Pipfile and lock now pin the public API Utils 1.0.5 release wheel. The
older F160/F161 notes describe earlier pins.

| Surface | Previous dependency | Migration |
| --- | --- | --- |
| `Pipfile`, `Pipfile.lock`, `scripts/pipenv-install.sh`, `scripts/pipenv-lock.sh` | CodeArtifact source, AWS CLI authentication and temporary authenticated index | F163 uses public PyPI for third-party packages and locks API Utils to the exact GitHub release wheel and SHA-256. Use `pipenv run install` to sync the developer environment and `pipenv lock` to refresh the lock. |
| `Dockerfile`, `scripts/docker-build.sh` | Authenticated `PIP_INDEX_URL` build argument populated by AWS CLI | F164 builds from the hash-verified lock using public sources and preserves the existing image and port. |
| `.github/workflows/docker-push.yml`, `.github/OIDC.md` | AWS OIDC, CodeArtifact token and index passed to Docker | F165 removes AWS authentication, preserves main-branch GHCR publishing, and adds separate read-only PR validation. |
| `README.md`, `tasks/_PLANNING.md` | Developer setup referenced CodeArtifact | F166 documents the locked install and records runtime and CI acceptance. |

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
failure. The current branch projects Profile `display_name` onto Card `name`,
and the previously failing Marti home-card case passed in packaged acceptance.
F161 remains outside this wave.

Keep database calls through MongoIO. The published wheel supports
`get_documents(collection_name, match, project, sort_by, skip, limit)`,
`get_document(collection_name, document_id)` and
`create_document(collection_name, document)`. Its update method accepts
`document_id`, `match`, `set_data`, `push_data`, `add_to_set_data` and
`pull_data`. The shared list helper takes keyword-only `match`, `sort_by`,
`offset`, `size` and `project` after `collection_name`. These APIs retain
existing service ownership. No Discovery schema, OpenAPI or production
identity-provider changes are required for the migration.

## Container build

Run `pipenv run container` to build the Discovery API image with the committed
runtime lock. Pipenv exports requirements with hashes, and pip enforces those
hashes while downloading the public API Utils wheel and its dependencies. The
default image remains `ghcr.io/mentor-forge/mentorhub_discovery_api:latest`.
Set `DISCOVERY_API_IMAGE` to give an isolated local build its own tag.

A clean-environment ARM64 build passed. The final image reported API Utils
1.0.5 installed from the pinned GitHub release wheel with the expected SHA-256.
All 61 packaged E2E cases passed against fresh MongoDB and the seeded
Developer Edition configurator on a disposable network. The explorer, OpenAPI
file, metrics, and authenticated config endpoints returned HTTP 200.
An unauthenticated card request returned HTTP 401.

## GitHub Actions

Pull requests targeting main verify the dependency lock, sync development
dependencies, run lint and unit tests, compile Python sources, and build the
container from the runtime lock. The validation job uses read-only repository
access, with checkout credential persistence disabled.

The publishing workflow runs on pushes to main. It reads repository contents
and writes packages to GHCR using the GitHub Actions token, with separate
builds for Linux AMD64 and ARM64. The public wheel and PyPI supply the image
dependencies. The former AWS OIDC setup was removed.

Record hosted validation after the pull request opens. Publication is
verified separately after merge.

## Final local acceptance

On November 21, 2026, lock verification, a clean locked development install,
209 unit tests and 84 subtests, lint, compilation, and the AWS-free ARM64 image
build passed. The packaged API reported API Utils 1.0.5. All 61 packaged
end-to-end tests passed against disposable MongoDB and Developer Edition seed
data. The explorer, OpenAPI, metrics, and authenticated config returned HTTP
200. A valid mentee could list home cards but received HTTP 403 for a restricted
notification filter. Missing bearer credentials, a missing profile claim,
wrong issuer, wrong audience, wrong signature, and an expired token all
returned HTTP 401. No production identity-provider integration was needed.

The build reported the existing shell-form CMD warning, and JWT tests reported
the short Developer Edition test key warning. Hosted PR CI and post-merge GHCR
publication are separate from this local acceptance.
