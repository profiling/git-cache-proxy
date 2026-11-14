# Internal maintenance

This policy applies to profiling/git-cache-proxy only.

## Branches

- `main`: an exact mirror of rolandjitsu/git-cache-proxy main. No internal commits.
- `internal/main`: the default branch and internal integration history.
- Contribution branches: one change per community PR, based on official main.
- `archive/main-before-internal-20261114`: the original fork main, retained for recovery.

The initial internal tree combines community PR #67 at `17c8719` and #72 at
`205fc39`. PR #51 is already in official main. The upload-pack owner retains
both the mirror read guard from #67 and the concurrent writer from #72.

## Automation

Internal maintenance runs daily at 01:23 UTC (09:23 Asia/Shanghai), or manually
from Actions. It must live on the default branch, `internal/main`.

The workflow fast-forwards fork main to official main. If fork main has unique
commits, it fails without overwriting them. It opens at most one pending PR
from main to internal/main. Each pending integration is tested by merging it
in a temporary runner checkout, then running formatting, clippy and all-feature
tests. Validation also runs on internal pushes, pull requests and manual runs,
including when there are no official updates. Scheduled runs skip validation
when no integration is pending. Conflicts fail validation and require a reviewed
resolution.

The workflow summary also reports community PR #67 and #72 status. A merged
community PR still needs a code comparison, especially after an official squash.
Keep merge history on internal/main; do not squash or rebase official sync PRs.
The commit-message check exempts same-repository main-to-internal/main PRs in
this fork because official commit messages must be preserved. Other PRs retain
the normal commit-message policy, including its existing Dependabot exemption.

GitHub Actions must be enabled, and the repository must allow Actions to create
pull requests. The workflow uses GITHUB_TOKEN, with no personal token. Ordinary
PR workflows created by this token can require approval; inspect the maintenance
run itself and approve the PR checks when GitHub requests it.

Disable the inherited Release workflow in the fork. It is official release
machinery and is not the internal release process. Do not put internal workflow
commits on main, since main must remain identical to the official branch.

Scheduled runs can be delayed. GitHub can disable schedules in public repos
following 60 days of inactivity. Check the latest run weekly and re-enable the
workflow if needed. Manual fallback:

```shell
gh workflow run internal-maintenance.yml -R profiling/git-cache-proxy --ref internal/main
```

## Review and deployment

Review the sync PR and the validation result for its current head and base SHAs.
Resolve conflicts on a separate internal branch and test again. Merge only after
checks pass. Neither the sync job nor the PR deploys anything.

Deploy an immutable internal tag and image digest from a validated internal
commit. Record the official base SHA, extra patches, CI run and rollback digest
with the deployment. No image publisher or production deployment is installed
by this change.

For new community contributions, branch from origin/main, not internal/main.
Keep internal-only settings out of community PRs. Integrate each contribution
into internal/main through a separate internal PR.

## Bootstrap review

Before changing existing refs, publish the archive branch and verify its SHA.
Then publish internal/main and make it the default branch. Moving the old fork
main to official main requires an explicit lease bound to the inspected old SHA;
this is a one-time migration, not part of scheduled automation. Preserve the
community branches and their PRs.

After bootstrap, verify the default branch, mirror SHA, archive SHA, workflow
state and a successful manual run. The workflow does not use or modify local
worktrees. Keep Actions failure notifications enabled for this repository.
