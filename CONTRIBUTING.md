# Contributing to Tactevra

Use **Tactevra** in new public-facing prose. Preserve `rocell` executable names,
schemas, historic release paths, and third-party attribution. See the
[brand guide](docs/brand/BRAND_GUIDE.md) for shared naming and presentation rules.

## Get the source

You need Git, Python 3.10 or newer, and access to `j-webtek/robot-arm-build`.
For a first software demonstration, use [getting started](docs/GETTING_STARTED.md).
For development, install the runtime and test extra:

```powershell
git clone https://github.com/j-webtek/robot-arm-build.git
cd robot-arm-build
python -m venv .venv
.\.venv\Scripts\python -m pip install -e './software[test]'
```

The test extra includes `jsonschema` for the shared AI v2 schema integration
tests. Use [offline verification](docs/CI.md) to reproduce the bounded CI checks
in a fresh environment before submitting a change.

Use the same virtual environment interpreter for test commands. Model training
and optional vision runtimes have additional requirements documented under
[software/ai](software/ai/README.md).

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) before following older plans.
Optional camera/serial dependencies and live commissioning are documented in
`software/README.md`. Do not run installers, deployment scripts, or hardware
campaigns as part of ordinary source setup.

## Work in reviewable increments

Use the [repository operations guide](docs/REPOSITORY_OPERATIONS.md) for ownership,
cross-workstream handoffs and dependency-update review. Fill the PR template;
do not assume a passing check constitutes the other workstream's approval.

For vulnerabilities or exposed secrets, use [private security reporting](SECURITY.md)
instead of a public issue. For other questions, see [support](SUPPORT.md).

1. Open an issue describing the behavior, evidence, and acceptance criteria.
2. Start a branch: `git switch -c feature/short-description`.
3. Make a bounded change and run its hardware-free tests. Record the exact
   command and result; do not describe simulation as a successful live test.
4. Review `git diff` and `git status`. Stage explicit paths with `git add`.
5. Run `python scripts/audit_github_snapshot.py`; review any findings without
   posting secret values. This heuristic audit is not a security guarantee.
   [Reviewed fixture exceptions](docs/AUDIT_FIXTURE_REVIEW.md) are exact and
   fail on changed content; never blanket-ignore tests or refresh exceptions blindly.
6. Commit, push the branch, and open a pull request with results and limitations.
7. Update the relevant plan's checkpoint after evidence changes. Never rewrite
   an earlier failed result into a success; record the later correction.

## Keep user documentation current

Update [project status](PROJECT_STATUS.md) when a capability or its limitations
change, and update [getting started](docs/GETTING_STARTED.md) when a command or
dependency changes. Keep the root README brief enough for a new reader to choose
a next step. Explain unfamiliar terms on first use; put internal stage IDs,
hashes and detailed test counts in the linked engineering evidence.

Date capability claims and distinguish simulation, controller feedback, physical
measurement and verified device input. Check example commands against the code
and use repository-relative Markdown links so the guide works on GitHub and in
a clone. Historical records should retain their original outcomes and be labeled
as dated evidence rather than presented as current instructions.

Do not force-push shared history. Preserve concurrent work and frozen release
packages. A clean clone lacks ignored lab data/toolchains; some historical tests
require those inputs and cannot reproduce full qualification from source alone.
Select hardware-free unit tests explicitly rather than invoking live scripts.

## Export sharing

Normal wizard exports remain under `software/runs/wizard-exports/` locally.
For a shared investigation, copy only the needed sanitized result to a new
`evidence/<issue-or-run>/` folder and include a README describing:

- test intent, firmware/configuration identity, and software commit;
- requested/transmitted targets and fresh measured feedback with units;
- result classification, timing, discrepancies, and stop reason;
- original local export identifier, omitted fields, and sanitization performed.

Remove credentials, signing keys, authorization headers, private device settings,
and unrelated images. Inspect archives as well as loose files. Never use
`git add -f` to upload private backups or raw runs. Private repository visibility
does not make credentials safe to commit. Retain the untouched original locally.

## CAD, releases, and access

STEP/STP, STL, 3MF, and ZIP packages are ordinary Git objects in this baseline.
The initial LFS upload was blocked by the account's LFS budget; no billing change
was made. Clones are consequently larger. Keep individual files below GitHub's
100 MiB limit and review storage strategy before adding repeated large revisions.
A future LFS migration requires available quota and coordination before rewriting
shared history. Text files retain original bytes to preserve release hashes.

Invite collaborators through repository access settings. This repository is
public; review privacy and third-party licenses before publishing new material. Original
project contributions are licensed under the [Apache License, Version 2.0](LICENSE).
Third-party code and vendor assets retain their respective licenses and
attribution notices. Contributions intentionally submitted for inclusion are
under Apache 2.0 unless explicitly stated otherwise, as described in its
contribution terms. Preserve the source and license information for any
third-party material you add.
Hardware release/deployment remains a separate reviewed action, not an automatic
consequence of a commit, pull request, or passing software test.
