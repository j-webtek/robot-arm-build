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

After the workflow has run successfully, maintainers can choose these checks in
branch protection. This change does not modify branch protection settings.
