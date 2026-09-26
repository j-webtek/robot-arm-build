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

## Keep public documentation current

For each PR, classify its public impact: capability, limitation, setup, or none.
Capability or limitation changes update `PROJECT_STATUS.md`; setup changes update
the getting-started or contribution guide. Update the README only when the short
overview or supported entry path changes. A tooling-only change can state why no
capability update is needed instead of rewriting the status page.

Record a reviewed source commit and the relevant shared-ledger evidence IDs.
Keep the date and checkpoint explicit: a proposed branch is not merged capability,
and a documentation edit is not a new physical verification. For a feature PR,
identify the reviewed implementation commit and label the claim as pending merge
until that PR is merged. If public updates must be deferred, link a follow-up
issue, responsible lane and reason in the PR; do not quietly leave stale claims.

The repository maintainer checks this during review. This is a documented process,
not an automated semantic-accuracy gate. AI/arm owners supply technical evidence;
the repository lane translates it for readers without changing the evidence.

Track remaining operations work in
[repository maintenance issues](https://github.com/j-webtek/robot-arm-build/issues?q=is%3Aissue%20is%3Aopen%20label%3Aarea%3Arepository).
Each issue should name its scope, completion criteria, evidence and exclusions.
Do not assign a person or promise a date without agreement. The shared engineering
ledger remains the source for AI/arm stage evidence, not this maintenance backlog.

Required checks and branch-protection behavior are in [CI](CI.md). Cross-lane
review is a contributor process, not an enforced independent-review rule:
GitHub currently requires zero approving reviews so the solo maintainer can
merge. The maintainer is responsible for checking the handoff fields.

## Issue and PR triage

Reuse `bug`, `documentation`, `enhancement`, and `question` for issue type.
Additional labels created on September 26, 2026:

| Label | Use |
| --- | --- |
| `area:repository` | GitHub configuration, CI, maintenance and contributor experience |
| `area:ai` | AI producer, model or vision changes |
| `area:arm` | Arm consumer, planner or controller changes |
| `cross-workstream` | Coordinated interface review is needed |
| `needs-owner-review` | An affected owner has not recorded a disposition |
| `release-readiness` | Release prerequisites and preparation |

Multiple area labels are appropriate for shared changes. Labels route work; they
do not assign a person, establish priority, grant approval, or enforce a merge
block. Do not invent assignees. Leave `needs-owner-review` until the relevant
disposition is recorded at an exact commit. Preserve unrelated labels.

Use the documentation template for unclear public guidance and the handoff
template for shared contracts. The shared workplan remains the engineering
ledger; link to it rather than copying long histories into issues. Keep security
details in the private reporting channel. No automatic stale-issue closer is
configured: inactivity is not evidence that a problem is resolved.

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

### September 26, 2026 dependency review

The maintainer approved proceeding with review of PRs
[#17](https://github.com/j-webtek/robot-arm-build/pull/17) and
[#18](https://github.com/j-webtek/robot-arm-build/pull/18). Approval is not a
substitute for compatibility checks.

- **pytest (#18):** permits pytest 9 while retaining pytest 8 support. Review
  uses the existing four-job offline matrix and a local Python 3.10 run with
  pytest 9.1.1. See the PR for exact tested commits and final check results.
  This is test tooling, not physical-device qualification. Upstream
  [release notes](https://docs.pytest.org/en/latest/changelog.html) describe
  removals and changed fixture/import behavior; broader optional/native suites
  remain the responsibility of their owning lanes.
- **OpenCV (#17): deferred.** The proposed `<6` installation bound conflicts
  with `<5` policies in `physical_host_readiness.py` and
  `physical_connection_rehearsal.py`. OpenCV 5.0.0.93 resolves on local Python
  3.10, but successful installation and portable CI do not qualify the camera
  backend. Keep the current `<5` bound until the arm/vision owners review
  backend compatibility, align manifest and readiness policies in one change,
  and supply optional-feature evidence. Do not bypass the readiness check.

For future optional dependency updates, compare package bounds with runtime
readiness policies before merging. Record deferred work on the dependency PR;
do not infer live camera or hardware coverage from the offline matrix.

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
