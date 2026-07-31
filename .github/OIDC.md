# GitHub Actions — AWS OIDC (CodeArtifact read)

The `docker-push.yml` workflow matches `mentorhub_mentee_api` (same permissions, `AWS_ROLE_ARN_READ`, CodeArtifact token step). A failure like:

```text
Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

means this **repository is not listed** in the IAM role trust policy — not a workflow bug.

## Fix (Shared-Services account, SRE)

1. IAM → Roles → **`GitHubActionsCodeArtifactRead`** → Trust relationships → Edit.
2. Add to `token.actions.githubusercontent.com:sub`:

   ```text
   repo:mentor-forge/mentorhub_discovery_api:ref:refs/heads/main
   ```

3. Re-run the failed workflow on `main`.

Also add **`mentorhub_admin_api`**, **`mentorhub_admin_spa`**, and **`mentorhub_discovery_spa`** when those repos merge to `main`.

Canonical list: [mentorhub_cloudformation `config/aws-platform.yaml`](https://github.com/mentor-forge/mentorhub_cloudformation/blob/main/config/aws-platform.yaml) (`github_ci.codeartifact_read_trust_repos`) and [docs/github-ci.md](https://github.com/mentor-forge/mentorhub_cloudformation/blob/main/docs/github-ci.md).

## Workflow notes

- Trigger is **`push` to `main` only** — PR builds do not assume the CodeArtifact role (by design).
- Org secret **`AWS_ROLE_ARN_READ`** and org variables are inherited; no repo-level AWS secrets required.
- Job needs `permissions.id-token: write` (already set).
