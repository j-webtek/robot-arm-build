"""Host-specific ownership correction: fixed incapable child, never CIM/USB.

Pure tests label all constructed process/boot observations as injected. Actual
tests inspect only the exact Job/handles owned by the fixed incapable child.
"""

from dataclasses import replace
import ctypes
import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest

from rocell.providers.windows import host_boot_observation as m
from rocell.providers.windows import _owned_worker_win32 as backend
from test_host_boot_observation import (
    request,
    execution,
    response,
    modeled_observation,
    FakeExecutor,
    command,
    child,
    native,
)


@pytest.fixture(autouse=True)
def no_cim(monkeypatch):
    monkeypatch.setattr(
        m, "_system_powershell", lambda: pytest.fail("CIM is forbidden")
    )


def modeled_owned(**changes):
    req = request()
    result = execution(req)
    owned = dict(
        schema=m.OWNERSHIP_SCHEMA,
        accounting_complete=True,
        pid=31415,
        peak_processes=1,
        peak_handles=12,
        handles_remaining=0,
        pins_remaining=0,
        unclosed_handles_remaining=0,
        stdin_pending=False,
        cleanup_deadline_ns=result.finished_monotonic_ns + 1_000_000_000,
    )
    result = replace(
        result,
        command={**result.command, "process_model": m.PROCESS_MODEL},
        ownership=owned,
        **changes,
    )
    return m.WindowsHostBootObserver(FakeExecutor(result)).observe(
        req,
        cancellation=threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=lambda: None,
    )


def test_legacy_bytes_and_summary_never_gain_new_ownership():
    original = modeled_observation()
    before = original.payload
    restored = m.HostBootObservation(before)
    assert restored.payload == before and restored.to_dict()["schema"] == m.SCHEMA
    assert restored.safe_summary()["schema"] == "rocell.host_boot_summary.v1"
    assert "ownership" not in restored.safe_summary()
    assert "ownership" not in restored.to_dict()["execution"]
    current = modeled_owned()
    assert current.to_dict()["schema"] == m.OWNED_SCHEMA
    assert current.safe_summary()["schema"] == "rocell.host_boot_summary.v2"
    assert current.safe_summary()["origin"] == "INJECTED_CIM_EXECUTOR"


def test_modeled_historical_incapable_v1_keeps_original_two_process_budget():
    # A closed historical-format fixture, not a claim of a new owned run.
    doc = modeled_observation().to_dict()
    fixture = str(Path(m.__file__).with_name("_host_boot_fixture.py"))
    doc["origin"] = "INCAPABLE_OWNED_CHILD"
    doc["command"]["argv"] = ["-I", "-S", fixture, "nominal"]
    doc["command"]["package_files"] = [{"path": fixture, "sha256": "c" * 64}]
    doc["command"]["budget"]["process_count"] = 2
    doc["command"]["budget"]["run_timeout_ms"] = 700
    doc["command"]["budget"]["observed_handles_per_process"] = 512
    doc["command_sha256"] = m._sha(m._canonical(doc["command"]))
    original = m._canonical(doc)
    restored = m.HostBootObservation(original)
    assert restored.payload == original
    assert restored.to_dict()["command"]["budget"]["process_count"] == 2
    assert restored.safe_summary()["schema"] == "rocell.host_boot_summary.v1"
    assert "ownership" not in restored.safe_summary()


@native
@pytest.mark.parametrize("kind", ["legacy", "derived-host", "derived-usb"])
def test_detached_flag_is_exact_type_only_without_creating_process(
    tmp_path, monkeypatch, kind
):
    class DerivedHost(backend.WindowsOwnedHostBootPipeProcess):
        pass

    class DerivedUsb(backend.WindowsOwnedUsbPipeProcess):
        pass

    owner_type = {
        "legacy": backend.WindowsOwnedProcess,
        "derived-host": DerivedHost,
        "derived-usb": DerivedUsb,
    }[kind]
    owner = owner_type()
    flags = []

    def refuse_create(*args):
        flags.append(args[5])
        return False

    owner.k.CreateProcessW = refuse_create
    monkeypatch.setattr(m, "_native_owner", lambda: owner)
    doc = child(tmp_path).to_dict()
    assert len(flags) == 1 and flags[0] & 0x8000000 and not flags[0] & 0x8
    assert doc["status"] == "HELD"
    assert not doc["execution"]["process_created"]
    assert doc["execution"]["ownership"]["peak_processes"] == 0
    assert not owner.handles and not owner.pins and m._UNRESOLVED_OWNER is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("accounting_complete", False),
        ("pid", 0),
        ("pid", True),
        ("peak_processes", 2),
        ("peak_processes", None),
        ("peak_handles", 1025),
        ("handles_remaining", 1),
        ("pins_remaining", 1),
        ("unclosed_handles_remaining", 1),
        ("stdin_pending", True),
        ("cleanup_deadline_ns", 1),
    ],
)
def test_rehashed_owned_success_rejects_missing_or_exceeded_accounting(field, value):
    doc = modeled_owned().to_dict()
    doc["execution"]["ownership"][field] = value
    with pytest.raises(ValueError):
        m.HostBootObservation(m._canonical(doc))


def test_missing_ownership_fields_remain_unknown_in_held_bytes():
    missing = m._ownership_snapshot(SimpleNamespace(), None)
    assert missing["accounting_complete"] is False
    assert missing["peak_processes"] is None and missing["stdin_pending"] is None
    req = request()
    result = execution(req, status="FAILED", primary_error="EXECUTION_FAILED")
    result = replace(
        result,
        command={**result.command, "process_model": m.PROCESS_MODEL},
        ownership=missing,
    )
    report = m.WindowsHostBootObserver(FakeExecutor(result)).observe(
        req,
        cancellation=threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=lambda: None,
    )
    assert report.to_dict()["status"] == "HELD"
    assert report.to_dict()["response"] is not None
    assert report.safe_summary()["ownership"]["pid"] is None


@pytest.mark.parametrize("mutation", ["model", "budget", "version", "cleanup-expiry"])
def test_owned_wire_version_command_and_deadline_are_closed(mutation):
    doc = modeled_owned().to_dict()
    if mutation == "model":
        doc["command"]["process_model"] = "CALLER_FLAGS"
    elif mutation == "budget":
        doc["command"]["budget"]["process_count"] = 2
    elif mutation == "version":
        doc["schema"] = m.SCHEMA
    else:
        doc["execution"]["ownership"]["cleanup_deadline_ns"] = doc["deadline_ns"] + 1
    doc["command_sha256"] = m._sha(m._canonical(doc["command"]))
    with pytest.raises(ValueError):
        m.HostBootObservation(m._canonical(doc))


@native
def test_actual_detached_host_job_is_owned_before_first_instruction(
    tmp_path, monkeypatch
):
    owner = m._native_owner()
    assert type(owner) is backend.WindowsOwnedHostBootPipeProcess
    events = []
    set_limits = owner.k.SetInformationJobObject
    create = owner.k.CreateProcessW
    member = owner.k.IsProcessInJob
    resume = owner.k.ResumeThread

    def limits(job, kind, pointer, size):
        if kind == 9:
            value = ctypes.cast(pointer, ctypes.POINTER(backend._Limits)).contents
            events.append(
                ("limits", int(job), value.basic.processes, value.basic.flags)
            )
        return set_limits(job, kind, pointer, size)

    def created(*args):
        events.append(("create", args[0], args[5]))
        return create(*args)

    def membership(process, job, result):
        ok = member(process, job, result)
        if process == owner.process and job == owner.job:
            events.append(("membership", int(job), bool(result._obj.value)))
        return ok

    def resumed(thread):
        assert any(row[0] == "membership" and row[2] for row in events)
        events.append(("resume", owner.peak_processes))
        return resume(thread)

    owner.k.SetInformationJobObject = limits
    owner.k.CreateProcessW = created
    owner.k.IsProcessInJob = membership
    owner.k.ResumeThread = resumed
    monkeypatch.setattr(m, "_native_owner", lambda: owner)
    value = child(tmp_path).to_dict()
    assert value["status"] == "OBSERVED_HOST_BOOT", value
    assert value["origin"] == "INCAPABLE_OWNED_CHILD"
    launched = next(row for row in events if row[0] == "create")
    assert launched[1] == value["command"]["executable"]
    assert Path(launched[1]).is_absolute()
    assert launched[2] & 0x8 and launched[2] & 0x4  # Detached and suspended.
    assert not launched[2] & (0x8000000 | 0x1000000)  # No console/breakaway flags.
    limit = next(row for row in events if row[0] == "limits")
    assert limit[2] == 1 and limit[3] & 0x2000
    assert not limit[3] & (0x800 | 0x1000)  # No breakaway/silent breakaway.
    assert next(row for row in events if row[0] == "resume")[1] == 1
    owned = value["execution"]["ownership"]
    assert owned["accounting_complete"] and owned["pid"] == owner.pid
    assert owned["peak_processes"] == 1 and owned["peak_handles"] > 0
    assert all(
        owned[name] == 0
        for name in (
            "handles_remaining",
            "pins_remaining",
            "unclosed_handles_remaining",
        )
    )
    assert owned["stdin_pending"] is False
    assert (
        value["execution"]["finished_monotonic_ns"]
        <= owned["cleanup_deadline_ns"]
        <= value["deadline_ns"]
    )
    assert value["execution"]["tree_exit_confirmed"]
    assert value["execution"]["stdout_eof"] and value["execution"]["stderr_eof"]
    assert value["response"]["request_sha256"] == value["request_sha256"]
    assert m._UNRESOLVED_OWNER is None


def test_host_serviced_hardlink_policy_does_not_change_legacy(tmp_path):
    original = tmp_path / "fixed.exe"
    alias = tmp_path / "serviced-alias.exe"
    original.write_bytes(b"incapable file pin fixture")
    os.link(original, alias)
    assert backend.WindowsOwnedHostBootPipeProcess._regular(original).st_nlink == 2
    with pytest.raises(ValueError, match="SINGLE_LINK"):
        backend.WindowsOwnedProcess._regular(original)
    with pytest.raises(ValueError):
        backend.WindowsOwnedHostBootPipeProcess._regular(tmp_path)


def test_host_pin_path_rejects_reparse_ancestor(monkeypatch):
    path = Path(r"C:\parent\fixed.exe")

    def fake_stat(value, *, follow_symlinks):
        return SimpleNamespace(
            st_mode=stat.S_IFREG if value == path else stat.S_IFDIR,
            st_file_attributes=0x400 if value == path.parent else 0,
        )

    monkeypatch.setattr(Path, "stat", fake_stat)
    with pytest.raises(ValueError, match="PIN_PATH_LINK"):
        backend.WindowsOwnedHostBootPipeProcess._regular(path)


def modeled_process(monkeypatch, req, *, processes=1, handles=12):
    """Exercise the real executor with an explicitly modeled, no-process seam."""

    class FixedCommand(m.LocalCimHostBootExecutor):
        def _command(self, check):
            check()
            fields = command()
            return m._Command(
                m.PinnedWorkerFile(
                    Path(fields["executable"]), fields["executable_sha256"]
                ),
                tuple(fields["argv"]),
                Path(fields["working_directory"]),
                m.WorkerProcessBudget(**fields["budget"]),
            )

    class ModeledOwner:
        pid = peak_processes = peak_handles = 0
        created = resumed = tree_exited = False
        stdout_eof = stderr_eof = pending = False
        returncode = None
        written = 0
        stdout = stderr = b""

        def __init__(self):
            self.handles, self.pins, self.unclosed_handles = {}, [], {}

        def pin(self, command):
            pass

        def _active(self, **kwargs):
            self.peak_processes, self.peak_handles = processes, handles
            return processes

        def start(self, command, payload, *, check):
            self.created, self.pid = True, 31415
            check()  # The production executor samples this suspended owner.
            self.resumed = True
            self.written = len(payload)
            self.stdout = response(req)

        def poll(self, budget):
            self.tree_exited = self.stdout_eof = self.stderr_eof = True
            self.returncode = 0
            return True

        def cleanup(self, deadline):
            self.tree_exited = True
            return ()

    owner = ModeledOwner()
    monkeypatch.setattr(m, "_UNRESOLVED_OWNER", None)
    monkeypatch.setattr(m, "_native_owner", lambda: owner)
    return m.WindowsHostBootObserver(FixedCommand()), owner


@pytest.mark.parametrize(
    "processes,handles,error",
    [(2, 12, "OBSERVED_PROCESS_LIMIT"), (1, 1025, "OBSERVED_HANDLE_LIMIT")],
)
def test_observed_limit_is_retained_held_before_resume(
    monkeypatch, processes, handles, error
):
    req = request()
    observer, owner = modeled_process(
        monkeypatch, req, processes=processes, handles=handles
    )
    value = observer.observe(
        req,
        cancellation=threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=lambda: None,
    ).to_dict()
    assert value["origin"] == "INJECTED_CIM_EXECUTOR"
    assert value["status"] == "HELD" and value["response"] is None
    assert value["execution"]["primary_error"] == error
    assert value["execution"]["ownership"]["peak_processes"] == processes
    assert value["execution"]["ownership"]["peak_handles"] == handles
    assert owner.created and not owner.resumed and owner.written == 0
    assert value["execution"]["tree_exit_confirmed"]
    assert not value["execution"]["cleanup_errors"]
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        observer.observe(
            req,
            cancellation=threading.Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: pytest.fail("No automatic retry"),
        )


def test_late_final_admission_keeps_response_and_original_cleanup_deadline(monkeypatch):
    req = request()
    clock = [m.time.monotonic_ns()]
    monkeypatch.setattr(m.time, "monotonic_ns", lambda: clock[0])
    observer, _ = modeled_process(monkeypatch, req)
    checks = []

    def admission():
        checks.append(clock[0])
        if len(checks) == 3:  # Final admission after completed owned cleanup.
            clock[0] += 2_100_000_000

    value = observer.observe(
        req,
        cancellation=threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=admission,
    ).to_dict()
    assert len(checks) == 3
    assert value["status"] == "HELD"
    assert value["execution"]["primary_error"] == "TIMED_OUT"
    assert bytes.fromhex(value["execution"]["stdout_hex"]) == response(req)
    assert value["response"]["request_sha256"] == req.sha256
    assert (
        value["execution"]["ownership"]["cleanup_deadline_ns"]
        == checks[0] + 2_000_000_000
    )
    assert (
        value["execution"]["ownership"]["cleanup_deadline_ns"]
        < value["execution"]["finished_monotonic_ns"]
    )
    assert value["execution"]["ownership"]["handles_remaining"] == 0
    assert m._UNRESOLVED_OWNER is None
