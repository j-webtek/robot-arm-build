# Repository operations and contributor handoffs

This guide covers GitHub administration, documentation and maintenance. AI and
arm implementation remain owned by their respective workstreams. Repository
maintenance does not authorize model promotion, firmware deployment or movement.

For a short working procedure, use the
[maintainer checklist](MAINTAINER_CHECKLIST.md). This guide supplies the detailed
policies and dated administrative evidence behind it.

## One change, one clear handoff

Use a topic branch and the [PR template](../.github/pull_request_template.md).
Name the lane and change owner, dependencies, affected contracts and intended
next owner. Use “none” with a reason where a field does not apply. Small cosmetic
changes do not need a lengthy integration report.

For shared schemas, coordinate frames, command formats, or evidence semantics,
link the producer and consumer checks and record the other lane's review before
merging. Keep unfinished dependencies explicit; passing CI does not resolve an
unmerged prerequisite. Do not invent GitHub handles or approvals. The repository
includes a conservative [CODEOWNERS map](../.github/CODEOWNERS) with `@j-webtek`
as the initial accountable maintainer. It documents routing but does not
manufacture independent approval; specialist owners can replace or join these
entries after accepting responsibility.

The [shared workplan](../software/ai/docs/SHARED_AI_ARM_WORKPLAN.md) coordinates
current engineering stages and ownership. The separate
[AI/arm evidence ledger](../software/ai/docs/EVIDENCE_LEDGER.md) preserves the
append-only test history. The public [status page](../PROJECT_STATUS.md)
summarizes capabilities, not every experiment. Update each only when relevant;
keep historical results intact and date new claims.

## Keep public documentation current

For each PR, classify its public impact: capability, limitation, setup, or none.
Capability or limitation changes update `PROJECT_STATUS.md`; setup changes update
the getting-started or contribution guide. Update the README only when the short
overview or supported entry path changes. A tooling-only change can state why no
capability update is needed instead of rewriting the status page.

Record a reviewed source commit and the relevant evidence-ledger IDs.
Keep the date and checkpoint explicit: a proposed branch is not merged capability,
and a documentation edit is not a new physical verification. For a feature PR,
identify the reviewed implementation commit and label the claim as pending merge
until that PR is merged. If public updates must be deferred, link a follow-up
issue, responsible lane and reason in the PR; do not quietly leave stale claims.

The repository maintainer checks this during review. This is a documented process,
not an automated semantic-accuracy gate. AI/arm owners supply technical evidence;
the repository lane translates it for readers without changing the evidence.

Apply the [evidence-retention policy](EVIDENCE_RETENTION.md) before accepting
generated reports. A green test suite does not make a multi-million-line data
diff reviewable; require compact scorecards or an exact-digest exception.

Apply [repository artifact governance](ARTIFACT_GOVERNANCE.md) to CAD, print,
media, archive, and rendered-document changes. Prefer one canonical source plus
a generator or manifest over repeated bytes in instructional folders. The
delta-based check preserves the existing historical baseline; it does not
authorize new duplication or replace privacy, provenance, or license review.

Track remaining operations work in
[repository maintenance issues](https://github.com/j-webtek/tactevra/issues?q=is%3Aissue%20is%3Aopen%20label%3Aarea%3Arepository).
Each issue should name its scope, completion criteria, evidence and exclusions.
Do not assign a person or promise a date without agreement. The shared engineering
ledger remains the source for AI/arm stage evidence, not this maintenance backlog.

Required checks and branch-protection behavior are in [CI](CI.md). Cross-lane
review is a contributor process, not an enforced independent-review rule:
GitHub currently requires zero approving reviews so the solo maintainer can
merge. The maintainer is responsible for checking the handoff fields.
The repository accepts squash merges only, deletes a merged head branch
automatically, and enforces linear history on protected `main`. Linear-history
enforcement was enabled and read back on September 27, 2026; strict required
checks, admin enforcement, the zero-approval solo-maintainer rule, stale-review
dismissal, conversation resolution, and the force-push/deletion prohibitions were
confirmed unchanged in the same readback. Together these controls keep one
reviewed change per main-branch commit and reduce stale branch clutter. They do
not replace the required checks, handoff review, or exact-commit evidence. Do not
enable merge commits or rebase merging without updating this policy and checking
the protected-branch behavior first.

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

Bug and documentation intake use YAML issue forms, with only the core context
required. Unknown versions are acceptable; users are not asked to repeat a live
test or supply personal contact details. Feature and cross-workstream templates
remain Markdown, and blank issues/private security contact links remain available.
Forms help collect information; required fields are not evidence validation,
security screening, or an enforced review gate for all issue-creation methods.
For future edits, follow [GitHub's form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms),
check IDs and labels for uniqueness, and verify the chooser and unsubmitted forms
after merge. Do not create public test issues or submit private data for UI testing.

## Dependency-update operation

[Dependabot configuration](../.github/dependabot.yml) proposes weekly updates for
GitHub Actions, `software/pyproject.toml`, and the active RC03 CAD/vision
requirements, Monday at 09:00 America/New_York. Each scope takes effect when
merged to the default branch; its first successful run must be checked in GitHub
before claiming that scope is operating.

- At most two open Actions version-update PRs, three runtime Python update PRs,
  and two RC03 tool update PRs.
- Minor/patch version updates are grouped per ecosystem; majors remain separate.
- These limits apply to version updates, not a total cap on security-update PRs.
- No automatic merging or dependency installation on contributors' machines.
- Historical RC02 requirements, local model weights, vendor firmware, and
  ignored toolchains remain outside this configuration. RC03 coverage proposes
  dependency changes only; it does not release prints, qualify CAD output,
  validate cameras, or approve native installations.
- Direct attribution and external-artifact boundaries are indexed in
  [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). Dependabot coverage does
  not establish license compatibility or redistribution permission.
- Ranged Python requirements may already admit newer versions without a manifest
  change. A missing Dependabot PR is not evidence that every dependency was checked
  or that the resolved environment is secure. CI still resolves supported ranges.

For each dependency PR: read upstream changes, inspect permission/runtime changes,
check Python/OS support, run required checks, and ask the affected lane to review
behavioral risk. Optional serial/vision features are not fully exercised by the
portable matrix. Do not widen a version bound merely to make a bot PR mergeable.
Close or defer with an explanation if compatibility is not established.

Treat a lower-bound-only proposal according to why the floor would change:

- **Routine latest-version proposal:** if the existing range already admits the
  proposed release, close the PR unless a documented compatibility baseline or
  required capability justifies removing older environments.
- **Security-driven proposal:** verify the upstream advisory and whether the
  repository uses the affected feature. A security release can justify a higher
  minimum, but the affected component must still receive a focused compatibility
  check. Generic green checks are not evidence for a component they do not install
  or execute.
- **Unexercised optional tooling:** hold the PR with `needs-owner-review` and a
  precise evidence request. Do not represent dependency resolution, import
  success, or unrelated CI as behavior qualification.

For example, the protected offline matrix does not install
`active-project/RoCell_v0_3/requirements-cad.txt` or render the RC03 assembly
manual in its four portable package jobs. The separate `RC03 manual` job selects
the manual dependencies from that requirements file, performs an actual
Markdown-to-PDF render, checks PDF integrity, and retains the result for
representative-page review. That focused job plus human page review is the
acceptance path for a WeasyPrint floor change. Record failed qualification
attempts as inconclusive; an unavailable package index is not compatibility
evidence.

### September 27, 2026 RC03 first-run triage

The first active-RC03 Dependabot run completed successfully and opened two
minimum-version proposals. [PR #94](https://github.com/j-webtek/tactevra/pull/94)
was closed because the existing Beautiful Soup range already admitted the
proposed release and no new minimum was justified.
[PR #93](https://github.com/j-webtek/tactevra/pull/93) remains held for focused
review because WeasyPrint 70 is identified upstream as a security release, while
the current protected matrix does not exercise the RC03 PDF generator. This
triage confirms that the monitor is operating; it does not qualify either
dependency or the RC03 toolchain.

### September 26, 2026 dependency review

The maintainer approved proceeding with review of PRs
[#17](https://github.com/j-webtek/tactevra/pull/17) and
[#18](https://github.com/j-webtek/tactevra/pull/18). Approval is not a
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

### Read-only repository-health audit

The repository declares its expected public and owner-visible GitHub settings in
`.github/repository-health-policy.json`. The weekly `Repository health` workflow
checks only publicly observable state with a read-only token: repository metadata,
default-branch protection visibility, community profile health, required workflow
state, and the live Pages title. A failure signals drift for a maintainer to
review; the workflow cannot repair settings, merge changes, or publish a release.

Owner-visible expectations include branch protection, selected-action policy,
workflow-token permissions, security features, and Pages configuration. Run the
owner audit manually with a short-lived authenticated environment as documented
in [CI](CI.md#repository-health-drift-audit). Never add a personal token to the
workflow. After an intentional settings change, update the policy and its
operations documentation in a reviewed PR so the declared baseline and GitHub
state remain aligned.

## Actions and security baseline

The offline workflow uses full commit SHAs for checkout v7.0.1, setup-python
v7.0.0, and upload-artifact v7.0.1, verified against upstream release tags by
September 27, 2026. The upgrade
review covered the intervening Node 24 runner requirement, checkout credential
handling, event restrictions, and setup-python input changes. The hosted matrix
tests the combined revisions; no self-hosted runner compatibility is claimed.
The Linux jobs run on the explicit `ubuntu-24.04` image so GitHub's announced
October 2026 `ubuntu-latest` migration cannot silently change the build. Their
protected check identifiers retain `ubuntu-latest` for continuity and are not
the runner selector; the CI guide documents this distinction.

Dependabot can propose later pin updates; pinning does not itself prove the action is safe.
The workflow retains read-only permissions, non-persisted checkout credentials,
hosted runners and bounded jobs. It does not use `pull_request_target` or deploy.
The manually dispatched preview-candidate audit uses the same two pinned actions,
read-only permissions, and a hosted Ubuntu runner. GitHub selects the checkout
revision; the caller-supplied full commit SHA is only an identity assertion and
cannot select code to run. It audits only and has no release, artifact-upload,
deployment, or hardware step. It is intentionally outside branch protection
because it applies to a selected candidate rather than every development commit.

The initial September 26, 2026 inspection found Dependabot alerts/security updates
and secret scanning/push protection disabled. The later approved repository
security review enabled and read back the following settings:

| Setting | Verified state |
| --- | --- |
| Secret scanning | Enabled |
| Secret-scanning push protection | Enabled |
| Dependabot alerts | Enabled |
| Dependabot security updates | Enabled, not paused |
| Private vulnerability reporting | Enabled; retained |
| Automatic PR merging | Disabled; retained |
| Default workflow token | Read-only; retained |
| Actions approval of PR reviews | Disabled; retained |
| Non-provider-pattern scanning / validity checks | Disabled; unchanged |

On September 27, 2026, CodeQL default setup was enabled with the default query
suite and remote threat model for GitHub Actions, JavaScript/TypeScript, and
Python. C/C++ and C# are not covered by this initial setup. The first scan ran
against commit `92d404ba401af3cafba41e1e6d79a3b50f2b28f2`. CodeQL immediately
identified an input-controlled checkout in the manually dispatched candidate
audit; the remediation keeps the SHA input as an equality assertion but makes
GitHub's dispatch revision the only checkout source. CodeQL was initially
observational while its first recurring and pull-request runs were observed.
After successful scans on `main` and multiple pull-request revisions, the three
app-bound analyzer contexts—`Analyze (actions)`, `Analyze
(javascript-typescript)`, and `Analyze (python)`—were initially added to strict
branch protection on September 27, 2026. GitHub intentionally omits those
language-specific jobs for changes that cannot affect a configured language,
which left dependency-only PRs permanently blocked. Branch protection was then
corrected to require the app-bound `CodeQL` summary instead: it succeeds after
applicable analyzers complete and reports neutral when none apply. The focused
RC03 manual-render job was also made required. These checks supplement rather
than replace the four offline compatibility checks. A green or neutral summary
is not a security certification, and an unavailable or unexpected result must be
investigated rather than bypassed.

Attempts to enable GitHub's optional non-provider-pattern and secret-validity
scanning modes did not change their reported disabled state. Treat those modes as
unavailable for this repository unless a later settings review proves otherwise;
do not claim that the core secret scanner covers generic credentials or validates
whether a detected credential is active.

This used repository-level controls on the public repository. No paid product,
billing option, bypass, history rewrite, or runtime change was requested. Settings
apply on GitHub, not when someone clones the repository. No historical scan
completion, absence of vulnerabilities, or full secret-pattern coverage is claimed.
The snapshot audit remains a complementary, limited review.

### September 26, 2026 Actions-policy hardening

Following the owner's approval, repository settings were changed and read back:

| Control | Verified state |
| --- | --- |
| Allowed Actions | Selected only: `actions/checkout@*`, `actions/setup-python@*`, `actions/upload-artifact@*`, `actions/configure-pages@*`, and `actions/deploy-pages@*` |
| Broad GitHub-owned / verified-creator allowances | Both disabled |
| Full-length commit-SHA pinning | Required |
| Outside-contributor fork workflows | Approval required for all outside contributors |
| Default token / permission to approve PR reviews | Read-only / disabled, unchanged |

The action patterns allow reviewed pin updates within these five repositories;
they do not waive the separate full-SHA requirement. Adding a new action needs
an owner-approved allowlist change and review of its source, requested permissions,
and workflow use. Do not broaden the allowlist just to clear a failed run.

The upload action was added on September 27, 2026 for bounded workflow
artifacts. The offline workflow retains the generated RC03 PDF and JSON summary
for 14 days and has no release or deployment authority. The Pages workflow uses
the same action for a one-day site package; its build job remains read-only and
only its deploy job receives `pages: write` plus an OIDC token. Both Pages jobs
use the explicit Ubuntu 24.04 hosted image. `configure-pages` and `deploy-pages`
are pinned to verified v6.0.0 and v5.0.1 Node 24 release commits. Artifact
retention is review or deployment staging, not source-release publication.

Before approving an outside contributor's workflow, inspect the proposed code
and workflow changes at the revision being approved. Approval allows CI code to
run; it is not a code-review sign-off, permission to merge, or hardware authority.
Do not switch to `pull_request_target`, expose secrets, or use a self-hosted
workcell runner to work around pending approval. These settings do not sandbox
arbitrary shell commands or dependencies installed by an allowed workflow.

Existing required checks and branch protections remain unchanged, including
zero required approving reviews for the solo-maintainer workflow. Independent
review requirements need an agreed, available reviewer before enablement.
Installed GitHub Apps could not be enumerated with the available authentication;
account-wide tokens, OAuth grants, 2FA, and notification delivery were not verified.
This is a scoped repository-settings record, not a full access certification.

## Security alert handling

The owner confirmed **j-webtek** as the initial contact on September 26, 2026.
On the same date, repository **Watch → Custom → Security alerts** was saved and
verified for that account, without subscribing to all issues, PRs or releases.
The owner's selected default notification email was saved privately, and Watching
delivery was set to **On GitHub + Email**. Dependabot new-vulnerability delivery
was already enabled for GitHub, email and CLI, with a weekly email digest.
The default email and Watching preferences are account-wide, not repository-only;
other collaborators must configure their own subscriptions. Personal email
addresses are intentionally omitted from this public record.

These are verified settings, not an end-to-end delivery test: receipt of an alert
email and private-report notification has not been tested. Recheck preferences
when the responsible account or destination changes. Consult
[GitHub's security-notification guide](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-security-notifications).
Do not assume enabling a scanner subscribes every collaborator or delivers every
pre-existing finding. Inspect the repository Security view after enablement.

Maintainer procedure, without an automatic monitor or promised response time:

1. Review private vulnerability reports, secret-scanning alerts and Dependabot
   alerts in GitHub's restricted security views. Also inspect security-update PRs.
2. For a suspected exposed secret, validate privately and revoke/rotate through
   its owning service. Removing a file does not invalidate a credential. Never
   paste secret values or private findings into public issues, CI logs or PRs.
3. For dependencies, assess affected versions and actual usage with the owning
   AI/arm lane, record a disposition in the alert, and test the proposed fix.
   Security-update PRs still need compatibility review and required checks; no
   automatic merge or runtime-policy relaxation is allowed. The OpenCV #17 hold
   is not lifted by enabling security updates.
4. Dismiss only with an evidence-backed reason; do not bulk-dismiss findings or
   add blanket exclusions for synthetic tests. The snapshot audit's fixture
   registry does not configure GitHub's scanner exceptions.
5. Coordinate private disclosure and sanitized remediation guidance when needed.
   History rewriting, changes to credentials, billing, or device deployments
   require their own scoped authorization; this procedure does not grant it.

Keep the assigned contact and settings record current when ownership changes.
If personal notifications are unavailable, review the restricted views directly;
do not claim unattended alert coverage.

References: [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
and [GitHub workflow hardening](https://docs.github.com/en/code-security/tutorials/secure-your-organization/protect-against-threats).
