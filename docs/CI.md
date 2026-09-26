# Tactevra offline verification

The [Offline verification workflow](../.github/workflows/offline-checks.yml) runs
on pull requests, pushes to main, and manual dispatch. It uses GitHub-hosted Linux
and Windows runners with Python 3.10 and 3.12. Each job creates a new virtual
environment and installs the package non-editably before running the introductory
demo. This checks packaging as well as source-tree behavior.

## What is checked

- Base installation and `pip check`, before adding test-only dependencies.
- Installed `rocell` import in isolated Python mode.
- Grounded `hi` request produces ordered H/I actions.
- Coordinate preview reports nominal geometry, no controller commands, and no
  execution authorization.
- Local file links in an explicit list of maintained docs; SVG XML validity.
- An explicit selection of AI/arm contract, ordering, evidence, and metric tests.
  The list is in [offline_checks.py](../scripts/ci/offline_checks.py).

The test extra declares `jsonschema`; no separate manual install is needed.
Dependency ranges are not a lockfile: these jobs check fresh resolution within
supported ranges, not bit-for-bit environment reproduction.

## Run locally from the repository root

Use a new `.venv-ci` environment (not your existing development environment):

```text
python -m venv .venv-ci
python scripts/ci/offline_checks.py install-base
python scripts/ci/offline_checks.py smoke
python scripts/ci/check_docs.py
python scripts/ci/offline_checks.py install-tests
python scripts/ci/offline_checks.py test
```

The helper chooses the virtual environment interpreter for Windows or Linux.
Installation needs package-index access; the selected demo and tests need no
model service, camera, arm, or private calibration records.

## Boundaries

No repository secrets, self-hosted runners, hardware connections, or deployment
steps are configured. The workflow uses a read-only GitHub token and does not
persist checkout credentials. Do not add live scripts or broad test discovery
without inspecting their side effects. These are scoped software checks, not a
security sandbox or proof of physical safety.

Green checks do not establish model accuracy, authenticated real-camera evidence,
measured calibration, physical typing, or full-suite qualification. Link checking
does not validate anchors or remote URLs. SVG parsing does not replace visual QA.
The repository snapshot audit remains a separate review. Its previously reported
synthetic fixtures have [exact documented exceptions](AUDIT_FIXTURE_REVIEW.md);
CI tests that mechanism but does not replace a full snapshot scan.

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

Configured on GitHub on 2026-09-26: pull requests, resolved review conversations,
an up-to-date branch, and all four checks below are required, including for admins:

- `Offline / ubuntu-latest / Python 3.10`
- `Offline / ubuntu-latest / Python 3.12`
- `Offline / windows-latest / Python 3.10`
- `Offline / windows-latest / Python 3.12`

Force pushes and branch deletion are disabled. No independent approving review
is mandatory (the approval count is zero), so a solo maintainer can merge after
the checks pass. These are repository settings, not settings installed by cloning
this source; recheck GitHub if policy changes.

Both AI and arm contributors should push a topic branch and open a PR rather
than pushing directly to `main`. Update the branch when `main` advances and let
the checks rerun. A green result remains scoped to the portable tier above.
