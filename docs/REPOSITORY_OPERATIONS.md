# Repository operations and contributor handoffs

This guide covers GitHub administration, documentation and maintenance. AI and
arm implementation remain owned by their respective workstreams. Repository
maintenance does not authorize model promotion, firmware deployment or movement.

## One change, one clear handoff

Use a topic branch and the [PR template](../.github/pull_request_template.md).
Name the lane and change owner, dependencies, affected contracts and intended
next owner. Use “none” with a reason where a field does not apply. Small cosmetic
changes do not need a lengthy integration report.

For shared schemas, coordinate frames, command formats, or evidence semantics,
link the producer and consumer checks and record the other lane's review before
merging. Keep unfinished dependencies explicit; passing CI does not resolve an
unmerged prerequisite. Do not invent GitHub handles or approvals. No CODEOWNERS
file is configured until actual reviewer identities and coverage are agreed.

The [shared workplan](../software/ai/docs/SHARED_AI_ARM_WORKPLAN.md) remains the
engineering evidence ledger. The public [status page](../PROJECT_STATUS.md)
summarizes capabilities, not every experiment. Update both only when relevant;
keep historical results intact and date new claims.

Required checks and branch-protection behavior are in [CI](CI.md). Cross-lane
review is a contributor process, not an enforced independent-review rule:
GitHub currently requires zero approving reviews so the solo maintainer can
merge. The maintainer is responsible for checking the handoff fields.

## Dependency-update operation

[Dependabot configuration](../.github/dependabot.yml) proposes weekly updates for
GitHub Actions and `software/pyproject.toml`, Monday at 09:00 America/New_York.
It takes effect when merged to the default branch; its first successful run must
be checked in GitHub before claiming the service is operating.

- At most two open Actions version-update PRs and three Python version-update PRs.
- Minor/patch version updates are grouped per ecosystem; majors remain separate.
- These limits apply to version updates, not a total cap on security-update PRs.
- No automatic merging or dependency installation on contributors' machines.
- Historical RC02/RC03 requirements, local model weights, vendor firmware and
  ignored toolchains are outside this configuration.
- Ranged Python requirements may already admit newer versions without a manifest
  change. A missing Dependabot PR is not evidence that every dependency was checked
  or that the resolved environment is secure. CI still resolves supported ranges.

For each dependency PR: read upstream changes, inspect permission/runtime changes,
check Python/OS support, run required checks, and ask the affected lane to review
behavioral risk. Optional serial/vision features are not fully exercised by the
portable matrix. Do not widen a version bound merely to make a bot PR mergeable.
Close or defer with an explanation if compatibility is not established.

Routine maintenance: check failed/cancelled workflows and Dependabot errors,
triage security reports privately, review stalled dependency PRs, and ensure
public links/status still match the supported entry path. No scheduled maintenance
agent or reminder is created by this guide.

## Actions and security baseline

The offline workflow uses full commit SHAs for checkout v7.0.1 and setup-python
v7.0.0, verified against upstream release tags on September 26, 2026. The upgrade
review covered the intervening Node 24 runner requirement, checkout credential
handling, event restrictions, and setup-python input changes. The hosted matrix
tests the combined revisions; no self-hosted runner compatibility is claimed.
Dependabot can propose later pin updates; pinning does not itself prove the action is safe.
The workflow retains read-only permissions, non-persisted checkout credentials,
hosted runners and bounded jobs. It does not use `pull_request_target` or deploy.

Read-only GitHub API inspection on September 26, 2026 found repository default
workflow permissions `read` and Actions PR-approval permission disabled. Private
vulnerability reporting is enabled as documented in [SECURITY.md](../SECURITY.md).
Dependabot security updates and secret scanning/push protection were reported
disabled at inspection; this PR does not enable them or claim coverage. Review
those separately, including access/availability and alert handling. The snapshot
audit is not their replacement.

References: [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
and [GitHub workflow hardening](https://docs.github.com/en/code-security/tutorials/secure-your-organization/protect-against-threats).
