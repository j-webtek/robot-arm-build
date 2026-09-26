# Experimental source-preview candidate: dcd87db

Prepared September 26, 2026 for [issue #25](https://github.com/j-webtek/robot-arm-build/issues/25).
**Disposition: HOLD for publication.** This is preparation evidence, not a release
approval, firmware review, or physical qualification.

## Proposed identity

- Source: `dcd87db12c9593f1c17b7a222cb711c4fbe7845e`, merged on protected main.
- Proposed title: **Tactevra v0.1.0-alpha.1 — experimental source preview**.
- Proposed tag: `tactevra-v0.1.0-alpha.1`; not created or approved. Remote tag and
  release listings were empty at this review; recheck before publication.
- Publication decision owner: repository maintainer `j-webtek`.
- Assets: GitHub-generated source archives only, if approved. No uploaded
  installer, firmware binary, trained model bundle or new print package.
- These preparation documents are later than the candidate. They do not silently
  change its source identity. To include later changes in the archive, select a
  new SHA and repeat candidate-specific checks.

## Included progress and review boundary

The [earlier compatibility/content review](COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md)
at `3660fc4` is the declared comparison baseline, not a previous published release.
The merged change log from that baseline through this candidate was reviewed for
release scope. Principal additions are:

| Area | Included changes | What remains unproved |
| --- | --- | --- |
| Arm-facing contracts | Passive evidence and installed-surface gates; host runtime contract; r97 source staging and accepted-once acknowledgment correlation (ARM-024 through ARM-032) | Installed identity, configuration binding, physical response and arrival |
| AI interface | Existing v2 producer/consumer boundary retained; added arm-side schemas and evidence records | Newer unmerged AI experiments are excluded; no model promotion or real-camera qualification |
| Repository operations | Reviewed Actions pins, pytest 9 support, CI environment inventory, handoff templates, newcomer guidance, security operations and refreshed public status | Optional camera/native compatibility, full-history security coverage and notification receipt |
| Hardware assets | No tracked changes under `active-project` or `hardware` since the comparison baseline | Vendor redistribution and embedded third-party metadata review |

README, getting started, project status, support and security guidance were read
against this snapshot. The public capability checkpoint is `4a166c8`, its preceding
implementation merge; `dcd87db` adds the reviewed public summary. There is no claim
that all historical lab instructions are current or suitable for a new user.

## Exact-candidate verification

The [merged-main CI run](https://github.com/j-webtek/robot-arm-build/actions/runs/36260595859)
completed successfully at the full candidate SHA:

| Required job | Result |
| --- | --- |
| Offline / ubuntu-latest / Python 3.10 | PASS |
| Offline / ubuntu-latest / Python 3.12 | PASS |
| Offline / windows-latest / Python 3.10 | PASS |
| Offline / windows-latest / Python 3.12 | PASS |

Each job's environment summary records its resolved dependencies. This is the
merged-main run, not an assumption that an earlier PR result covers a newer SHA.

A fresh detached worktree and new `.venv-ci` also tested this exact revision on
Windows build 26200 with Python 3.10.10. It shares Git objects with the existing
clone; it is not a fresh network clone, clean OS image or graphical UI test.
Package installation used PyPI and a process-only `PIP_EXTRA_INDEX_URL` override
to the same index; no persistent pip configuration was changed. Downloads may
reuse pip's cache. No private lab files or existing environment were copied.

Commands, from the candidate checkout root:

```text
python -m venv .venv-ci
python scripts/ci/offline_checks.py install-base
python scripts/ci/offline_checks.py smoke
python scripts/ci/offline_checks.py install-tests
python scripts/ci/offline_checks.py test
python scripts/ci/offline_checks.py environment
python scripts/ci/check_docs.py
python -m unittest discover -s scripts/ci -p "test_*.py"
python scripts/audit_github_snapshot.py
```

- Non-editable base and test-extra installs passed; both `pip check` runs found
  no broken requirements. Installed package: `rocell` 0.1.0.
- Smoke passed: isolated installed import; literal `hi` preserved as H then I;
  nominal/unmeasured coordinates; no controller commands or execution authority.
- Portable selection: **171 passed in 15.37 seconds**.
- Additional offline selection using the environment's Python:
  `-m pytest -q software/tests/test_r97_production_runtime_firmware.py software/tests/unit/test_production_controller_runtime_contract_v1.py`:
  **38 passed in 0.80 seconds**. Source-generation/host-contract checks only;
  no compile, independent linked-image review, controller connection or movement.
- Candidate documentation: 23 maintained documents and two SVG assets passed;
  three CI-script unit tests passed. No remote-link or visual-rendering coverage.
- Tracked checkout remained clean after these checks.
- Snapshot audit passed: 5,712 paths, 903.8 MiB, zero unresolved review findings
  and 14 reviewed synthetic fixtures. This heuristic snapshot scan does not
  certify full Git history, embedded content, redistribution rights or security.

Resolved local distributions (observation, not a lockfile or security assessment):

```text
attrs 26.1.0; colorama 0.4.6; exceptiongroup 1.3.1; iniconfig 2.3.0
jsonschema 4.26.0; jsonschema-specifications 2025.9.1; packaging 26.3
pillow 12.3.0; pip 22.3.1; pluggy 1.6.0; Pygments 2.21.0
pytest 9.1.1; referencing 0.37.0; rocell 0.1.0; rpds-py 0.30.0
setuptools 65.5.0; tomli 2.4.1; typing_extensions 4.16.0
```

The [earlier newcomer check](NEWCOMER_CHECK_2026-09-26.md) covers terminal and
loopback HTTP startup at `28aef3d`, not this candidate. It remains supporting
historical evidence and is not relabeled as a current UI acceptance test.

## Contents, provenance and exclusions

Tracked extension inventory: 97 `.3mf`, 113 `.step`, 246 `.stl`, and one `.zip`.
No tracked `.bin`, `.pt`, `.pth`, `.onnx`, `.gguf` or `.safetensors` filenames were
found. This is not an exhaustive embedded-binary or secret detector. The existing
ZIP and other hardware assets are unchanged from the earlier content review;
its container-inspection limits still apply.

Generated source archives contain these tracked assets; they are not software-only
downloads. The root Apache-2.0 license covers original contributions, not all
third-party material. Preserve existing notices and historical identifiers.

**Specific unresolved item:**
`hardware/static_overhead_camera/vendor/B0477.STEP` is recorded as downloaded
Arducam geometry. Its adjacent README provides source/date/hash and fit cautions,
but no redistribution license or permission disposition. The project-design
[authorship declaration](../HARDWARE_PROVENANCE.md) does not cover that vendor
file. This review establishes a documentation gap, not a legal conclusion.
Record applicable terms or permission before approving an archive containing it;
do not invent a license, delete assets or rewrite history to clear the checklist.

Local weights, private calibration, raw device exports, credentials, generated
native helpers and local firmware images are not supplied by this plan. No local
cache or build directory should be attached as a release asset. A source archive
lacks Git metadata; `git ls-files`-based audit requires a checkout.

## Known limitations for readers

- No demonstrated reliable camera-to-arm typing or phone-operation system.
- Nominal geometry and synthetic tests are not measured tip accuracy.
- r97 remains an offline candidate with independent review and configuration
  binding outstanding. Do not run historical live scripts as setup instructions.
- Native-helper suites require separately generated Windows test helpers. The
  known missing-helper failure remains documented in [CI tiers](../CI.md).
- ARM-031 also records an unscoped collection failure from legacy `scripts`
  package-name collisions. Broad suite discovery was not rerun or repaired here.
- Dependency ranges are not a reproducible lockfile. OpenCV #17 remains deferred
  pending the arm/vision owners' compatibility review; no bound was widened.
- Firmware compilation, trained model evaluation, visual browser acceptance and
  actual security-email receipt are not established by this release preparation.

## Remaining decisions and owner handoff

| Owner/lane | Required disposition at this SHA | Status |
| --- | --- | --- |
| AI owner | Producer/schema compatibility; code/data/model attribution; identify any release-blocking limitations | Awaiting recorded owner review |
| Arm owner | Consumer/encoder/runtime compatibility; vendor-derived source/notice review; preserve unqualified hardware status | Awaiting recorded owner review |
| Hardware/repository maintainer | Vendor STEP redistribution terms and applicable embedded metadata disposition | Open |
| Repository maintainer | Approve exact title, tag, source SHA, notes and generated-source-only assets after remaining gates close | Not requested as an immediate publication action; no approval recorded |

For each owner response, record reviewer identity, exact SHA, scope, pass/hold,
evidence links and remaining exclusions on issue #25 or the preparation PR.
Do not treat this repository-lane review as either workstream's sign-off. If a
fix changes the source candidate, create a new pinned verification record.

No tag, GitHub release, model promotion, firmware deployment or hardware action
was performed. Follow [RELEASING](../RELEASING.md) only after explicit approval.
