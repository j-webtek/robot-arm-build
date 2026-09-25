"""Real isolated import checks only. No valid physical handoff is dispatched."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from rocell.providers.windows import passive_native_package as package


def run_child(tmp_path, mode="check-imports", digest=None, payload=b""):
    path = package.prepare(tmp_path)
    pinned = hashlib.sha256(path.read_bytes()).hexdigest()
    return subprocess.run(
        [
            str(Path(getattr(sys, "_base_executable", sys.executable))),
            "-I",
            "-S",
            str(package.CHILD),
            str(path),
            digest or pinned,
            mode,
        ],
        cwd=tmp_path,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )


def test_deterministic_closed_package_does_not_include_application_bootstrap():
    first = package.expected_archive()
    assert first == package.expected_archive()
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        names = set(archive.namelist())
        assert "rocell/application/passive_arm_child_claim.py" in names
        assert "serial/tools/list_ports_windows.py" in names
        assert "rocell/application/arrival_wizard_service.py" not in names
        assert b"application bootstrap" in archive.read("rocell/__init__.py")


def test_real_isolated_child_imports_without_device_access(tmp_path):
    result = run_child(tmp_path)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["status"] == "IMPORTS_OK_NOT_HARDWARE_TESTED"
    assert report["native"]["native_api_loaded"] is False
    assert report["physical_authority"] is report["connected"] is False


def test_wrong_archive_hash_exits_before_imports(tmp_path):
    result = run_child(tmp_path, digest="a" * 64)
    assert result.returncode == 4 and result.stdout == b""


def test_invalid_handoff_never_claims_or_enumerates(tmp_path):
    result = run_child(tmp_path, mode="observe", payload=b"{}")
    assert result.returncode != 0
    assert result.stdout == b""
    assert b"PASSIVE_NATIVE_WIRE_FIELDS" in result.stderr
    assert not list(tmp_path.glob("*-physical-passive-*.json"))


def test_real_child_claims_once_then_rejects_invalid_setup_original(tmp_path):
    import time
    from test_passive_arm_entry_policy import prepared
    from rocell.application.arm_bench_qualification_contract import (
        PassiveBenchRequest,
        _canonical,
    )
    from rocell.application.passive_arm_entry_policy import PassiveEntryEvidence
    from rocell.application.passive_arm_attempt_store import (
        PassiveAttemptJournal,
        inspect_attempt,
    )

    raw, evidence, originals = prepared()
    raw["attempt_id"] = evidence["attempt_id"] = "operation-" + "f" * 32
    now = time.monotonic_ns()
    evidence["setup_confirmed_monotonic_ns"] = now
    raw["parent_deadline_monotonic_ns"] = now + 30_000_000_000
    registration = {"fixture": "UNREGISTERED TEST CHILD; NO NATIVE RELEASE"}
    raw["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(registration)
    ).hexdigest()
    request = PassiveBenchRequest(_canonical(raw))
    journal = PassiveAttemptJournal(
        tmp_path,
        request,
        PassiveEntryEvidence(_canonical(evidence)),
        originals,
        registration,
        now_monotonic_ns=now,
    )
    receipt = journal.consume(now_monotonic_ns=time.monotonic_ns())
    handoff = dict(
        schema="rocell.passive_native_child_handoff.v1",
        root=str(tmp_path),
        request=request.to_dict(),
        setup_operation_id="operation-" + "a" * 32,
        consumption_sha256=receipt["consumption_sha256"],
        registration=registration,
    )
    from test_passive_native_wire import envelope

    result = run_child(tmp_path, mode="observe", payload=_canonical(envelope(handoff)))
    assert result.returncode != 0 and result.stdout == b""
    # The fixture's association-only attestation isn't a valid setup original.
    # The real child must stop at decoding it, BEFORE constructing the collector.
    assert b"JSONDecodeError" in result.stderr
    history = inspect_attempt(tmp_path, raw["attempt_id"])
    assert history["records"]["claimed"] is not None
    assert history["status"] == "OUTCOME_UNKNOWN_NO_REPLAY"
