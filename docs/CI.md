# Tactevra offline verification

The [Offline verification workflow](../.github/workflows/offline-checks.yml) runs
on pull requests, pushes to main, and manual dispatch. It uses GitHub-hosted
Ubuntu 24.04 and `windows-latest` runners with Python 3.10 and 3.12. Each job
creates a new virtual environment and installs the package non-editably before
running the introductory demo. This checks packaging as well as source-tree
behavior.

The protected Linux check names retain `ubuntu-latest` for status-context
continuity, but the workflow's actual `runs-on` value is pinned to
`ubuntu-24.04`. The environment summary is the source for the resolved runner OS.
Changing that image requires a reviewed workflow and documentation update; it
must not happen implicitly when GitHub moves the `ubuntu-latest` alias.

Repository policy requires full commit-SHA action pins and permits only
`actions/checkout`, `actions/setup-python`, `actions/upload-artifact`,
`actions/configure-pages`, and `actions/deploy-pages`. Fork workflows from
outside contributors require approval before running. A pending approval is not a failed
test; maintainers review the proposed code before allowing CI to execute. See
[Actions policy](REPOSITORY_OPERATIONS.md#september-26-2026-actions-policy-hardening)
for the dated settings and how to propose another action without bypassing them.

## What is checked

- Base installation and `pip check`, before adding test-only dependencies.
- Installed `rocell` import in isolated Python mode.
- Grounded `hi` request produces ordered H/I actions.
- Coordinate preview reports nominal geometry, no controller commands, and no
  execution authorization.
- Local file links in an explicit list of maintained docs; SVG XML validity.
  Links to this repository's new-issue templates are checked against local
  template filenames, catching stale `.md`/`.yml` routes without network access.
- The public project-status reviewed-through marker must match the newest ARM
  evidence-ledger record, and known issue dispositions must not regress.
- Published overview media and its authority manifest must match the exact
  sizes and SHA-256 identities in the public verification receipt.
- An explicit selection of AI/arm contract, ordering, evidence, and metric tests.
- A generated-evidence change budget that protects reviewability and clone cost;
  see [evidence retention](EVIDENCE_RETENTION.md).
  The list is in [offline_checks.py](../scripts/ci/offline_checks.py).
- A delta-based [repository artifact policy](ARTIFACT_GOVERNANCE.md) that rejects
  newly added or modified files over 10 MiB and byte-for-byte duplicate governed
  binaries unless their exact path and digest have a reviewed exception. Existing
  unchanged hardware-package duplication remains a historical baseline.
- A whole-tree [source-distribution footprint](SOURCE_DISTRIBUTION.md) check that
  contains tracked file count, logical bytes, single-blob size, and existing
  large-blob duplication. Reduction targets are reported separately from CI
  ceilings; a pass does not mean the current archive is small.
- Unit coverage for the read-only [external artifact contract](EXTERNAL_ARTIFACTS.md),
  including unavailable, verified, size-mismatch, digest-mismatch, and unsafe
  manifest states. No external artifact is downloaded or required by CI.
- A release-integrity path policy that rejects newly tracked private-backup,
  credential, key, executable, firmware, model-weight, and archive paths unless
  their exact bytes have a reviewed allowance. Ordinary CI does not clear the
  stricter release-candidate blockers; see [release preparation](RELEASING.md).
- Zero-write controller-byte previews, lifecycle fault rehearsal, published
  controller-boundary schemas, and the controller-evidence gate. These use
  synthetic/modeled records; a pass does not qualify an installed controller
  or authenticate physical evidence. No transport is opened by these tests.
- A Linux/Python 3.12 RC03 assembly-manual render using only the three
  documentation dependencies selected from `requirements-cad.txt`. The job checks
  PDF structure, page dimensions, minimum size/page count, source and output
  digests, and resolved package versions. It retains the PDF and JSON summary for
  14 days so representative pages can be reviewed. Structural success is not
  visual approval and does not qualify CAD or hardware.

The test extra declares `jsonschema`; no separate manual install is needed.
Dependency ranges are not a lockfile: these jobs check fresh resolution within
supported ranges, not bit-for-bit environment reproduction.

## Manual source-preview candidate audit

Before selecting a candidate, maintainers can produce a compact identity-bound
receipt from a fresh checkout:

```powershell
$candidate = git rev-parse HEAD
python scripts/ci/verify_clean_checkout.py `
  --expected-sha $candidate `
  --mode policy `
  --receipt clean-checkout-receipt.json
```

This verifies repository policy and archive shape without downloading external
model artifacts or touching hardware. Candidate mode additionally enforces the
tracked-path candidate policy and the reviewed offline blocker registry at
[`release-readiness.json`](../.github/release-readiness.json). It does not query
GitHub issue or approval state: closing an issue does not clear the gate until a
reviewed repository change records the resolution and durable evidence. See
[source-distribution footprint](SOURCE_DISTRIBUTION.md#clean-checkout-evidence).

The [Preview candidate audit](../.github/workflows/preview-candidate-audit.yml)
is a separate, manually dispatched, read-only workflow. It accepts one full
40-character commit SHA as an identity assertion. Select the intended protected
`main` revision in GitHub's **Run workflow from** control. The workflow checks out
that GitHub-selected revision, requires its immutable SHA to equal the assertion,
runs the strict release candidate inventory policy, performs the snapshot audit,
rechecks maintained documentation, and measures the source-archive footprint.
The input never selects code to check out.
This prevents an input-controlled revision from executing in the default-branch
workflow cache scope. The workflow uses a hosted Ubuntu runner, read-only repository
permission, non-persisted checkout credentials, and no repository secrets.

This workflow does not install the project, exercise hardware, upload artifacts,
create tags, or publish releases. It is not a required branch-protection check.
Use it only after identifying a proposed preview commit on protected `main`; a
moving branch name is not a candidate identity. Confirm the completed run names
the expected SHA. To assess some other revision without executing it in this
workflow context, use the documented fresh-checkout local procedure. A tracked-
path candidate blocker or an `open` offline readiness-registry entry correctly
fails the inventory step. The workflow does not query live issue state; the
reviewed registry and readiness dashboard must be reconciled together.

### Find the versions behind a result

Open **Actions → Offline verification → the relevant run**. Each job's summary
lists its Python/OS and installed distribution versions after test-extra
installation. Match the run's commit and job to your evidence; PR runs may test
a merge revision. The summary is an inventory, not a pass/fail report or lockfile.
The job steps remain the source for outcomes. An early installation failure can
prevent the summary from being produced; consult that step's log instead.

The reporter reads package metadata without importing camera or serial backends.
It does not include environment-variable dumps, pip configuration, installation
URLs, or local paths. Optional packages appearing in a local report do not mean
the portable tests exercised them. GitHub run retention applies; save the exact
run link and relevant result in the
[AI/arm evidence ledger](../software/ai/docs/EVIDENCE_LEDGER.md) for a promotion
decision, and update the shared workplan only when stage status or ownership changes.

## Run locally from the repository root

Use a new `.venv-ci` environment (not your existing development environment):

```text
python -m venv .venv-ci
python scripts/ci/offline_checks.py install-base
python scripts/ci/offline_checks.py smoke
python scripts/ci/check_docs.py
python scripts/ci/check_public_records.py
python scripts/ci/check_repository_health.py --policy-only
python scripts/ci/check_source_archive_footprint.py
python scripts/ci/check_release_integrity.py --mode policy
python scripts/ci/offline_checks.py install-tests
python scripts/ci/offline_checks.py environment
python scripts/ci/offline_checks.py test
```

The helper chooses the virtual environment interpreter for Windows or Linux.
Installation needs package-index access; the selected demo and tests need no
model service, camera, arm, or private calibration records.

## Boundaries

No repository secrets, self-hosted runners, or hardware connections are
configured in offline verification. That workflow uses a read-only GitHub token and does not
persist checkout credentials. Do not add live scripts or broad test discovery
without inspecting their side effects. These are scoped software checks, not a
security sandbox or proof of physical safety.

Green checks do not establish model accuracy, authenticated real-camera evidence,
measured calibration, physical typing, or full-suite qualification. Link checking
does not validate remote URLs or arbitrary Markdown anchors. SVG parsing does
not replace visual QA.
The documentation check also enforces explicitly listed public-page titles
and required navigation routes in `scripts/ci/check_docs.py`. Three selected
plain-heading anchors (installation, expected results, and export sharing) must
still exist exactly once at their destination. Backtick and tilde fenced examples
do not satisfy these checks. This is a narrow navigation contract, not a complete
Markdown parser or a check of every GitHub heading slug. Historical RoCell names,
package identifiers, technical documents, and body prose are not rebranding targets.
For an intentional title or route change, update the explicit contract and its
tests in the same PR; do not remove a check just to silence a regression.
The issue-template check verifies file existence, not GitHub form-schema validity
or submission behavior. Contact links are not template files; blank issues are
disabled by repository policy.
The repository snapshot audit remains a separate review. Its previously reported
synthetic fixtures have [exact documented exceptions](AUDIT_FIXTURE_REVIEW.md);
CI tests that mechanism but does not replace a full snapshot scan.

The separate Pages workflow deploys only the checked-in project player and
content-addressed overview media. Its build job has read-only repository access;
only the deploy job receives `pages: write` and an OIDC token. The build runs the
media-only receipt check before packaging, and the `github-pages` environment is
restricted to `main`. Both jobs run on the explicit `ubuntu-24.04` image.
`actions/configure-pages` and `actions/deploy-pages` are pinned to verified
v6.0.0 and v5.0.1 commits whose action runtimes are Node 24; this avoids both
the Node 20 removal and the announced `ubuntu-latest` image migration.

## Repository-health drift audit

`.github/workflows/repository-health.yml` runs a read-only public-state audit
every Monday and on manual dispatch. It compares repository metadata, default-
branch protection visibility, community-health percentage, required workflow
state, and the live Pages title with
`.github/repository-health-policy.json`. Drift fails the job and is summarized
in the Actions run; the workflow cannot change settings.

The policy also records owner-visible merge policy, branch protection, Actions,
security, and Pages expectations. Those endpoints require an owner token with
repository administration read access and are deliberately not granted to the
scheduled workflow. An authenticated maintainer can run the complete read-only
audit:

```powershell
$env:GH_TOKEN = gh auth token
python scripts/ci/check_repository_health.py --scope owner
Remove-Item Env:\GH_TOKEN
```

Do not store the token in Git, an issue, an Actions log, or a policy file. A
failed audit is evidence of drift to investigate; it is not permission for the
script or reviewer to restore settings automatically.

## Test tiers: choose the evidence you need

| Tier | Prerequisites | What a pass establishes |
| --- | --- | --- |
| Portable offline CI | Fresh Python environment and package-index access for installation | The explicitly selected packaging, contract, ordering and evidence checks pass; no devices or model services needed. |
| Native-helper offline tests | Windows, matching MSVC/Windows SDK and separately built incapable test helpers | Modeled native process/protocol behavior; not physical device qualification. |
| Model evaluation | The experiment's model artifacts, datasets and declared environment | Results for that evaluation population, not arm execution or general model accuracy. |
| Physical qualification | Measured setup, reviewed procedure, authorized operator and live-device prerequisites | Only the specific observations recorded by that procedure. Never inferred from CI. |

Directory names such as `unit` do not guarantee portability. Do not replace the
explicit CI list with unrestricted test discovery without inspecting dependencies
and side effects.

### Known clean-checkout native prerequisite

During the audit-fixture review, the broader affected-file run reported **465
passed and one failed**. The Windows case
`test_exact_owned_run_original_bytes_survive_export[False]` in
`software/tests/unit/test_physical_usb_identity_export.py` required
`software/native/windows_usb_identity/build/Release/rocell_usb_identity_entry_tests.exe`.
That generated helper was absent; the modeled run reported `FileNotFoundError`
and `no_attempt`. This is not a full-suite pass or evidence of a hardware fault.
The test was not weakened or silently skipped.

The [native component guide](../software/native/windows_usb_identity/README.md)
describes its build prerequisites and separately linked incapable test binaries.
Do not substitute the production USB executable. CMake registers additional
Python wire/admission tests only when its expected `software/.venv` interpreter
exists; `.venv-ci` alone does not enable those tests. Check the registered CTest
list before interpreting a result. No native helper or physical test is run by
the portable workflow.

## Main-branch merge policy

Configured on GitHub and last expanded on 2026-09-27: pull requests, resolved
review conversations, an up-to-date branch, linear history, and all six checks
below are required, including for admins:

- `Offline / ubuntu-latest / Python 3.10`
- `Offline / ubuntu-latest / Python 3.12`
- `Offline / windows-latest / Python 3.10`
- `Offline / windows-latest / Python 3.12`
- `RC03 manual / Ubuntu 24.04 / Python 3.12`
- `CodeQL`

Force pushes and branch deletion are disabled. No independent approving review
is mandatory (the approval count is zero), so a solo maintainer can merge after
the checks pass. These are repository settings, not settings installed by cloning
this source; recheck GitHub if policy changes.

The two `ubuntu-latest` strings above are stable required-check identifiers. They
currently run on the explicitly pinned Ubuntu 24.04 hosted image, as documented
at the top of this page.

The required `CodeQL` summary comes from GitHub Advanced Security and is app-bound.
It reports success after the applicable GitHub Actions, JavaScript/TypeScript, and
Python analyzers complete, or neutral when GitHub determines that a change cannot
affect a configured language. This avoids blocking dependency-only and prose-only
PRs on analyzer jobs that GitHub intentionally does not create. Inspect a failure,
missing summary, or unexpected neutral result rather than bypassing it. C/C++ and
C# are not covered by this setup. CodeQL success is not physical-safety,
release-readiness, or complete security evidence.

Both AI and arm contributors should push a topic branch and open a PR rather
than pushing directly to `main`. Update the branch when `main` advances and let
the checks rerun. A green result remains scoped to the portable tier above.
