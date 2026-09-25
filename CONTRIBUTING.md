# Developing and sharing RoCell

## Get the source

Access is restricted to invited collaborators of `j-webtek/robot-arm-build`.
Install Git, then:

```powershell
git clone https://github.com/j-webtek/robot-arm-build.git
cd robot-arm-build
python -m venv .venv
.\.venv\Scripts\python -m pip install -e './software[test]'
```

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) before following older plans.
Optional camera/serial dependencies and live commissioning are documented in
`software/README.md`. Do not run installers, deployment scripts, or hardware
campaigns as part of ordinary source setup.

## Work in reviewable increments

1. Open an issue describing the behavior, evidence, and acceptance criteria.
2. Start a branch: `git switch -c feature/short-description`.
3. Make a bounded change and run its hardware-free tests. Record the exact
   command and result; do not describe simulation as a successful live test.
4. Review `git diff` and `git status`. Stage explicit paths with `git add`.
5. Run `python scripts/audit_github_snapshot.py`; review any findings without
   posting secret values. This heuristic audit is not a security guarantee.
6. Commit, push the branch, and open a pull request with results and limitations.
7. Update the relevant plan's checkpoint after evidence changes. Never rewrite
   an earlier failed result into a success; record the later correction.

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

Invite collaborators through repository access settings. Do not make the repo
public without a separate privacy and third-party license review. Original
project contributions are licensed under the [Apache License, Version 2.0](LICENSE).
Third-party code and vendor assets retain their respective licenses and
attribution notices. Contributions intentionally submitted for inclusion are
under Apache 2.0 unless explicitly stated otherwise, as described in its
contribution terms. Preserve the source and license information for any
third-party material you add.
Hardware release/deployment remains a separate reviewed action, not an automatic
consequence of a commit, pull request, or passing software test.
