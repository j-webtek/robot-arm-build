"""Pure CIM fixtures and real incapable Job children; never query host metadata."""

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import pytest

import rocell.providers.windows.host_boot_observation as m


BOOT = "2026-01-01T01:00:00.000000Z"
WALL = m._utc_ns("2026-01-01T02:00:00.000000Z")
UUID = "12345678-1234-5678-9abc-0123456789ab"


def request(**changes):
    fields = dict(
        source_sha256="a" * 64,
        session_id="camera-session",
        launch_session_id="wizard-first",
        operation_id="boot-operation",
        trial_id="usbtrial-one",
        phase="BASELINE",
        expires_at_ns=time.monotonic_ns() + 30_000_000_000,
    )
    fields.update(changes)
    return m.HostBootRequest(**fields)


def response(req, **changes):
    value = dict(
        schema=m.RESPONSE_SCHEMA,
        request_sha256=req.sha256,
        provider="WINDOWS_LOCAL_CIM",
        machine_uuid=UUID,
        last_boot_up_time_utc=BOOT,
        confirmation_boot_up_time_utc=BOOT,
        os_version="10.0.19045",
        os_build="19045",
    )
    value.update(changes)
    return m._canonical(value)


def command():
    return dict(
        executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        executable_sha256="b" * 64,
        argv=list(m.CIM_ARGV),
        working_directory=r"C:\Windows\System32\WindowsPowerShell\v1.0",
        package_files=[],
        script_sha256=m.SCRIPT_SHA256,
        budget=asdict(
            m.WorkerProcessBudget(
                run_timeout_ms=10000,
                cleanup_timeout_ms=2000,
                stdin_bytes=4096,
                stdout_bytes=4096,
                stderr_bytes=4096,
                process_count=1,
                observed_handles_per_process=1024,
            )
        ),
    )


def execution(req, *, raw=None, wall=WALL, **changes):
    now = time.monotonic_ns()
    fields = dict(
        command=command(),
        status="SUCCEEDED",
        primary_error=None,
        cleanup_errors=(),
        process_created=True,
        initial_thread_resumed=True,
        tree_exit_confirmed=True,
        returncode=0,
        stdin_bytes_written=len(req.payload),
        stdout=response(req) if raw is None else raw,
        stderr=b"",
        started_monotonic_ns=now,
        finished_monotonic_ns=now + 1,
        started_utc_ns=wall,
        finished_utc_ns=wall + 1000,
        stdout_eof=True,
        stderr_eof=True,
    )
    fields.update(changes)
    return m.HostBootExecution(**fields)


class FakeExecutor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute(self, req, **kwargs):
        self.calls += 1
        kwargs["admission_check"]()
        return self.result


def modeled_observation(*, req=None, raw=None, wall=WALL, **changes):
    """Actual immutable producer; executor/CIM fields explicitly modeled."""
    req = request() if req is None else req
    owner = m.WindowsHostBootObserver(
        FakeExecutor(execution(req, raw=raw, wall=wall, **changes))
    )
    return owner.observe(
        req,
        cancellation=threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=lambda: None,
    )


def test_constructor_and_pure_restore_never_acquire(monkeypatch):
    original = modeled_observation()

    def forbidden(*args, **kwargs):
        pytest.fail("No process, system path or metadata lookup allowed")

    monkeypatch.setattr(m, "_system_powershell", forbidden)
    monkeypatch.setattr(m, "_native_owner", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    m.WindowsHostBootObserver()
    m.LocalCimHostBootExecutor()
    restored = m.HostBootObservation(original.payload)
    assert restored.sha256 == original.sha256
    assert restored.safe_summary()["origin"] == "INJECTED_CIM_EXECUTOR"


def test_roundtrip_detachment_complete_response_and_false_authority():
    original = modeled_observation()
    value = original.to_dict()
    assert value["status"] == "OBSERVED_HOST_BOOT"
    assert value["response"]["machine_uuid"] == UUID
    assert value["response"]["last_boot_up_time_utc"] == BOOT
    assert value["request"]["launch_session_id"] == "wizard-first"
    assert all(
        value[x] is False
        for x in ("physical_authority", "hardware_qualified", "device_io_performed")
    )
    assert original.sha256 == hashlib.sha256(original.payload).hexdigest()
    assert value["command"]["argv"] == list(m.CIM_ARGV)
    value["response"]["machine_uuid"] = "changed"
    assert original.to_dict()["response"]["machine_uuid"] == UUID
    assert m.HostBootObservation(original.payload).payload == original.payload


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "A" * 64),
        ("session_id", "a\nb"),
        ("trial_id", ""),
        ("launch_session_id", "a" * 129),
        ("phase", "REBOOT_NOW"),
        ("expires_at_ns", True),
        ("expires_at_ns", 0),
    ],
)
def test_request_is_closed_and_bounded(field, value):
    with pytest.raises(ValueError):
        request(**{field: value})


@pytest.mark.parametrize(
    "raw",
    [b"{}", b"[]", b'{"x":1,"x":2}', b'{"x":NaN}', b"\xff", b"[" * 3000, b"x" * 4096],
)
def test_malformed_provider_preserves_exact_bytes_but_never_boot_key(raw):
    value = modeled_observation(raw=raw).to_dict()
    assert value["status"] == "HELD"
    assert value["response"] is None and value["host_key_sha256"] is None
    assert bytes.fromhex(value["execution"]["stdout_hex"]) == raw


@pytest.mark.parametrize(
    "changes",
    [
        {"extra": 1},
        {"request_sha256": "0" * 64},
        {"provider": "REMOTE_CIM"},
        {"machine_uuid": "not-a-uuid"},
        {"machine_uuid": UUID.upper()},
        {"last_boot_up_time_utc": "2026-01-01T01:00:00Z"},
        {"last_boot_up_time_utc": "2026-01-01T01:00:00.000000+00:00"},
        {"last_boot_up_time_utc": "2026-02-30T01:00:00.000000Z"},
        {"last_boot_up_time_utc": "1601-01-01T01:00:00.000000Z"},
        {"os_build": 19045},
        {"os_version": "Windows 10"},
    ],
)
def test_provider_wrong_binding_unavailable_or_ambiguous_field_is_held(changes):
    req = request()
    value = modeled_observation(req=req, raw=response(req, **changes)).to_dict()
    assert value["status"] == "HELD" and value["boot_key_sha256"] is None


@pytest.mark.parametrize(
    "uuid",
    ["00000000-0000-0000-0000-000000000000", "ffffffff-ffff-ffff-ffff-ffffffffffff"],
)
def test_unavailable_uuid_retained_but_no_stable_machine_key(uuid):
    req = request()
    value = modeled_observation(req=req, raw=response(req, machine_uuid=uuid)).to_dict()
    assert value["response"]["machine_uuid"] == uuid
    assert value["blockers"] == ["HOST_IDENTITY_UNAVAILABLE"]
    assert value["host_key_sha256"] is None


def test_boot_change_within_query_and_clock_rollback_held():
    req = request()
    value = modeled_observation(
        req=req,
        raw=response(req, confirmation_boot_up_time_utc="2026-01-01T01:30:00.000000Z"),
    ).to_dict()
    assert "HOST_BOOT_CHANGED_DURING_OBSERVATION" in value["blockers"]
    value = modeled_observation(finished_utc_ns=WALL - 1).to_dict()
    assert "HOST_CLOCK_CHRONOLOGY_INCONSISTENT" in value["blockers"]


def test_future_reported_boot_is_held_not_silently_rebased():
    req = request()
    later = "2026-01-01T03:00:00.000000Z"
    value = modeled_observation(
        req=req,
        raw=response(
            req, last_boot_up_time_utc=later, confirmation_boot_up_time_utc=later
        ),
    ).to_dict()
    assert "HOST_BOOT_CHRONOLOGY_INCONSISTENT" in value["blockers"]


def test_new_launch_same_boot_and_stable_keys_not_full_snapshot_hash():
    first = modeled_observation()
    second = modeled_observation(
        req=request(
            launch_session_id="wizard-new", operation_id="next", phase="AFTER_REBOOT"
        ),
        wall=WALL + 60_000_000_000,
    )
    assert first.sha256 != second.sha256
    assert first.to_dict()["boot_key_sha256"] == second.to_dict()["boot_key_sha256"]
    assert m.compare_boot_observations(first, second)["status"] == "SAME_HOST_SAME_BOOT"


@pytest.mark.parametrize("launch", ["wizard-first", "wizard-new"])
def test_actual_reported_boot_change_is_independent_of_app_launch_label(launch):
    first = modeled_observation()
    req = request(launch_session_id=launch, operation_id="next", phase="AFTER_REBOOT")
    later = "2026-01-01T03:00:00.000000Z"
    second = modeled_observation(
        req=req,
        raw=response(
            req, last_boot_up_time_utc=later, confirmation_boot_up_time_utc=later
        ),
        wall=WALL + 7200_000_000_000,
    )
    result = m.compare_boot_observations(first, second)
    assert result["status"] == "SAME_HOST_DIFFERENT_BOOT"
    assert result["cryptographic_attestation"] is False


@pytest.mark.parametrize(
    "kind", ["host", "source", "trial", "session", "chronology", "old-boot"]
)
def test_comparison_holds_changed_context_and_unsupported_reboot_proof(kind):
    first = modeled_observation()
    changes = (
        {"source_sha256": "b" * 64}
        if kind == "source"
        else (
            {"trial_id": "other"}
            if kind == "trial"
            else {"session_id": "other"} if kind == "session" else {}
        )
    )
    req = request(**changes)
    fields = (
        {"machine_uuid": "23456789-1234-5678-9abc-0123456789ab"}
        if kind == "host"
        else {}
    )
    if kind == "old-boot":
        fields.update(
            last_boot_up_time_utc="2026-01-01T01:30:00.000000Z",
            confirmation_boot_up_time_utc="2026-01-01T01:30:00.000000Z",
        )
    second = modeled_observation(
        req=req,
        raw=response(req, **fields),
        wall=WALL - 1000 if kind == "chronology" else WALL + 60_000_000_000,
    )
    assert m.compare_boot_observations(first, second)["status"] == "HELD"


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "authority",
        "status",
        "host-key",
        "stdout-hash",
        "request",
        "command",
        "budget",
        "script",
        "response",
        "cleanup",
        "stdin",
        "origin",
    ],
)
def test_retained_document_revalidates_all_structural_and_derived_fields(mutation):
    value = modeled_observation().to_dict()
    if mutation == "extra":
        value["extra"] = 1
    elif mutation == "authority":
        value["physical_authority"] = True
    elif mutation == "status":
        value["status"] = "PASS"
    elif mutation == "host-key":
        value["host_key_sha256"] = "f" * 64
    elif mutation == "stdout-hash":
        value["execution"]["stdout_sha256"] = "f" * 64
    elif mutation == "request":
        value["request"]["launch_session_id"] = "changed"
    elif mutation == "response":
        value["response"]["os_build"] = "1234"
    elif mutation == "cleanup":
        value["execution"]["tree_exit_confirmed"] = False
    elif mutation == "stdin":
        value["execution"]["stdin_bytes_written"] = 0
    elif mutation == "origin":
        value["origin"] = "USB_DEVICE"
    else:
        if mutation == "command":
            value["command"]["argv"] += ["-ComputerName", "other"]
        elif mutation == "budget":
            value["command"]["budget"]["stdout_bytes"] += 1
        else:
            value["command"]["script_sha256"] = "0" * 64
        value["command_sha256"] = m._sha(m._canonical(value["command"]))
    with pytest.raises(ValueError):
        m.HostBootObservation(m._canonical(value))


def test_cleanup_and_stderr_keep_original_response_as_held():
    value = modeled_observation(
        status="FAILED", cleanup_errors=("OWNED_RESOURCE_CLEANUP_UNCONFIRMED",)
    ).to_dict()
    assert value["response"]["machine_uuid"] == UUID and value["status"] == "HELD"
    value = modeled_observation(stderr=b"LOCAL_CIM_OBSERVATION_FAILED").to_dict()
    assert (
        value["status"] == "HELD" and "HOST_BOOT_STDERR_RETAINED" in value["blockers"]
    )


def test_precancel_is_retained_without_backend_or_file_calls(monkeypatch):
    monkeypatch.setattr(m, "_system_powershell", lambda: pytest.fail("No path lookup"))
    monkeypatch.setattr(m, "_native_owner", lambda: pytest.fail("No DLL"))
    stop = threading.Event()
    stop.set()
    req = request()
    owner = m.WindowsHostBootObserver()
    evidence = owner.observe(
        req,
        cancellation=stop,
        deadline_ns=req.expires_at_ns,
        admission_check=lambda: pytest.fail("No admission"),
    )
    assert evidence.to_dict()["execution"]["status"] == "CANCELLED"
    assert not evidence.to_dict()["execution"]["process_created"]
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        owner.observe(
            req,
            cancellation=stop,
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: None,
        )


def test_admission_denial_precedes_system_lookup(monkeypatch):
    monkeypatch.setattr(m, "_system_powershell", lambda: pytest.fail("No lookup"))
    req = request()

    def deny():
        raise PermissionError("Do not disclose a local path or operator text")

    value = (
        m.WindowsHostBootObserver()
        .observe(
            req,
            cancellation=threading.Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=deny,
        )
        .to_dict()
    )
    assert value["execution"]["primary_error"] == "ADMISSION_DENIED"
    assert b"disclose" not in m._canonical(value)


def test_fixed_script_no_remote_query_or_reboot_method():
    assert "-ComputerName" not in m.CIM_SCRIPT and "-CimSession" not in m.CIM_SCRIPT
    assert (
        "Invoke-CimMethod" not in m.CIM_SCRIPT
        and "Restart-Computer" not in m.CIM_SCRIPT
    )
    assert m.CIM_SCRIPT.count("Get-CimInstance") == 3
    assert "Win32_ComputerSystemProduct -Property UUID" in m.CIM_SCRIPT
    assert "confirmation_boot_up_time_utc" in m.CIM_SCRIPT
    assert m.CIM_ARGV[:3] == ("-NoLogo", "-NoProfile", "-NonInteractive")


def test_noncanonical_record_float_boolean_counts_and_deep_json_rejected():
    original = modeled_observation()
    with pytest.raises(ValueError):
        m.HostBootObservation(json.dumps(original.to_dict()).encode())
    for bad in (False, 0.0):
        value = original.to_dict()
        value["execution"]["stderr_bytes"] = bad
        with pytest.raises(ValueError):
            m.HostBootObservation(m._canonical(value))
    with pytest.raises(ValueError):
        m.HostBootObservation(b'{"x":' + b"[" * 20 + b"0" + b"]" * 20 + b"}")
    assert m.compare_boot_observations(original, original)["status"] == "HELD"


def test_clock_jump_and_incomplete_pipe_are_never_success():
    value = modeled_observation(finished_utc_ns=WALL + 5_000_000_000).to_dict()
    assert "HOST_CLOCK_DISCONTINUITY_OBSERVED" in value["blockers"]
    with pytest.raises(ValueError, match="PIPE_COMPLETION"):
        modeled_observation(stdout_eof=False)


def test_deadline_before_admission_never_resolves_system_path(monkeypatch):
    monkeypatch.setattr(m, "_system_powershell", lambda: pytest.fail("No lookup"))
    req = request(expires_at_ns=time.monotonic_ns() + 1_000_000)
    value = (
        m.WindowsHostBootObserver()
        .observe(
            req,
            cancellation=threading.Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: pytest.fail("No admission"),
        )
        .to_dict()
    )
    assert value["execution"]["primary_error"] == "TIMED_OUT"
    assert not value["execution"]["process_created"]


def test_late_stop_after_injected_executor_completion_is_retained_as_held():
    req = request()
    stop = threading.Event()

    class StopExecutor(FakeExecutor):
        def execute(self, req, **kwargs):
            stop.set()
            return self.result

    value = (
        m.WindowsHostBootObserver(StopExecutor(execution(req)))
        .observe(
            req,
            cancellation=stop,
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: None,
        )
        .to_dict()
    )
    assert value["execution"]["status"] == "CANCELLED" and value["response"] is not None
    assert value["status"] == "HELD"


def test_cleanup_uncertainty_preserves_owner_and_denies_next_executor(monkeypatch):
    class Backend:
        created = resumed = tree_exited = False
        pid = peak_processes = peak_handles = 0
        returncode = None
        written = 0
        stdout = stderr = b""
        stdout_eof = stderr_eof = False
        handles = {}
        pins = []
        unclosed_handles = {}
        pending = False

        def pin(self, reg):
            raise OSError("private exception text must never be projected")

        def cleanup(self, deadline):
            self.pending = True
            return ("PENDING_STDIN_STORAGE_RETAINED",)

    backend = Backend()

    class FixedFakeCommand(m.LocalCimHostBootExecutor):
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

    monkeypatch.setattr(m, "_UNRESOLVED_OWNER", None)
    monkeypatch.setattr(m, "_native_owner", lambda: backend)
    req = request()
    value = (
        m.WindowsHostBootObserver(FixedFakeCommand())
        .observe(
            req,
            cancellation=threading.Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: None,
        )
        .to_dict()
    )
    assert value["execution"]["primary_error"] == "EXECUTION_FAILED"
    assert value["execution"]["cleanup_errors"] == [
        "OWNED_RESOURCE_CLEANUP_UNCONFIRMED"
    ]
    assert m._UNRESOLVED_OWNER is backend
    monkeypatch.setattr(m, "_native_owner", lambda: pytest.fail("Quarantined"))
    req = request()
    value = (
        m.WindowsHostBootObserver()
        .observe(
            req,
            cancellation=threading.Event(),
            deadline_ns=req.expires_at_ns,
            admission_check=lambda: pytest.fail("No renewal"),
        )
        .to_dict()
    )
    assert value["execution"]["primary_error"] == "PROCESS_CLEANUP_HOLD"
    assert not value["execution"]["process_created"]


native = pytest.mark.skipif(
    os.name != "nt", reason="Actual Windows owned incapable process only"
)


def child(tmp_path, scenario="nominal", *, stop=None, admit=None):
    req = request()
    owner = m.WindowsHostBootObserver(m.IncapableHostBootExecutor(tmp_path, scenario))
    return owner.observe(
        req,
        cancellation=stop or threading.Event(),
        deadline_ns=req.expires_at_ns,
        admission_check=admit or (lambda: None),
    )


@native
def test_actual_incapable_child_exact_bound_request_and_complete_owned_cleanup(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(m, "_system_powershell", lambda: pytest.fail("Never CIM"))
    value = child(tmp_path).to_dict()
    assert value["status"] == "OBSERVED_HOST_BOOT", value
    assert value["origin"] == "INCAPABLE_OWNED_CHILD"
    assert (
        value["execution"]["process_created"]
        and value["execution"]["initial_thread_resumed"]
    )
    assert (
        value["execution"]["tree_exit_confirmed"]
        and not value["execution"]["cleanup_errors"]
    )
    assert value["response"]["request_sha256"] == value["request_sha256"]


@native
@pytest.mark.parametrize(
    "scenario,error",
    [
        ("stall", "TIMED_OUT"),
        ("stdout-flood", "STDOUT_LIMIT"),
        ("stderr-flood", "STDERR_LIMIT"),
        ("spawn-child", "PROCESS_EXIT_FAILED"),
        ("exit-failure", "PROCESS_EXIT_FAILED"),
        ("malformed", None),
        ("wrong-binding", None),
    ],
)
def test_actual_incapable_child_faults_are_bounded_and_no_retry(
    tmp_path, scenario, error
):
    start = time.monotonic()
    value = child(tmp_path, scenario).to_dict()
    assert value["status"] == "HELD", value
    assert value["execution"]["primary_error"] == error, value
    assert (
        value["execution"]["tree_exit_confirmed"]
        and not value["execution"]["cleanup_errors"]
    )
    assert (
        value["execution"]["stdout_bytes"] <= 4096
        and value["execution"]["stderr_bytes"] <= 4096
    )
    assert time.monotonic() - start < 4
    assert value["schema"] == m.OWNED_SCHEMA
    assert value["execution"]["ownership"]["accounting_complete"]
    assert value["execution"]["ownership"]["peak_processes"] == 1
    if scenario == "spawn-child":
        assert value["execution"]["returncode"] == 72
        assert b"FIXTURE_DESCENDANT_CREATION_DENIED" in bytes.fromhex(
            value["execution"]["stderr_hex"]
        )


@native
def test_actual_stop_after_child_start_retains_tree_exit(tmp_path):
    stop = threading.Event()
    calls = 0

    def admit():
        nonlocal calls
        calls += 1
        # Initial admission, CreateProcess and ResumeThread have happened;
        # the final stdin write guard supplies a deterministic Stop boundary.
        if calls == 4:
            stop.set()

    value = child(tmp_path, "stall", stop=stop, admit=admit).to_dict()
    assert value["execution"]["primary_error"] == "CANCELLED", value
    assert (
        value["execution"]["process_created"]
        and value["execution"]["tree_exit_confirmed"]
    )


@native
@pytest.mark.parametrize("kind", ["stop", "deny", "source"])
def test_actual_final_admission_change_prevents_first_instruction(tmp_path, kind):
    req = request()
    stop = threading.Event()
    calls = 0

    def admit():
        nonlocal calls
        calls += 1
        if calls == 2:
            if kind == "stop":
                stop.set()
            elif kind == "source":
                object.__setattr__(req, "source_sha256", "f" * 64)
            else:
                raise PermissionError("held exact source admission")

    value = (
        m.WindowsHostBootObserver(m.IncapableHostBootExecutor(tmp_path))
        .observe(
            req, cancellation=stop, deadline_ns=req.expires_at_ns, admission_check=admit
        )
        .to_dict()
    )
    assert value["status"] == "HELD"
    assert (
        value["execution"]["primary_error"]
        == {
            "stop": "CANCELLED",
            "deny": "ADMISSION_DENIED",
            "source": "COMMAND_CHANGED",
        }[kind]
    )
    assert not value["execution"]["process_created"]
    assert value["request"]["source_sha256"] == "a" * 64
    assert not value["execution"]["cleanup_errors"]
