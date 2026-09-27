# AI test ownership and execution

Every tracked `test_*.py` file in this directory has exactly one documented
workstream owner in
[`AI_WORK_REGISTRY.json`](../docs/AI_WORK_REGISTRY.json). The registry audit
fails when a test is missing, multiply owned, points at a missing path, or no
longer matches the registry hash.

## Test levels

1. **Focused tests** cover the changed workstream and run during development.
2. **AI suite** runs every test in this directory.
3. **Shared boundary tests** run when `ModelMotionBatch`, precision, capture,
   or arm-consumed contracts change.
4. **Portable repository suite** runs from a fresh `.venv-ci` environment.
5. **Repository audits** check documentation, evidence retention, public
   records, artifacts, and release integrity.

Create an isolated environment from the repository root. The repository test
installer supplies core and test dependencies; the AI requirements file adds
the exact NumPy and PyTorch versions used by localization research tests.

```powershell
python -m venv .venv-ai
.\.venv-ai\Scripts\python.exe scripts/ci/offline_checks.py install-base
.\.venv-ai\Scripts\python.exe scripts/ci/offline_checks.py install-tests
.\.venv-ai\Scripts\python.exe -m pip install -r software/ai/requirements-test.txt
```

Then run:

```powershell
.\.venv-ai\Scripts\python.exe -m pytest software/ai/tests -q
.\.venv-ai\Scripts\python.exe software/ai/eval/audit_ai_work_registry.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_docs.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_evidence_scope.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_public_records.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_repository_artifacts.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_release_integrity.py
```

The pinned packages reproduce test execution; they do not identify or qualify
an inference deployment. Model manifests separately bind every evaluated model
and runtime.

For the portable suite:

```powershell
python -m venv .venv-ci
.\.venv-ci\Scripts\python.exe scripts/ci/offline_checks.py install-base
.\.venv-ci\Scripts\python.exe scripts/ci/offline_checks.py smoke
.\.venv-ci\Scripts\python.exe scripts/ci/offline_checks.py install-tests
.\.venv-ci\Scripts\python.exe scripts/ci/offline_checks.py test
```

## Adding or changing a test

1. Assign the test to one registry workstream.
2. Link its source, governing documentation, and retained evidence.
3. Use synthetic fixtures only for behavior that can be established
   synthetically; label them as such.
4. Keep training, calibration, and held-out evaluation inputs disjoint.
5. Assert exact rejection reasons and zero writes for rejected cases.
6. Preserve the first failed result in the evidence ledger before recording a
   correction.
7. Record commands, counts, metrics, limitations, hardware writes, physical
   movements, and the next dependency.

Passing tests establish only their declared scope. They do not promote a model,
install calibration, authorize a camera, or grant physical execution.
