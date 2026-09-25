"""Bounded profiling of newly constructed originals, never saved-store replay.

Real NTFS reads, leases and validators run; stage subjects and the semantic
original owner are explicitly modeled. No device or child process is capable.
Profiling measures software work only and never constitutes admission approval.
"""

import cProfile
import json
import pstats
import sys
from time import perf_counter_ns

import pytest

from rocell.application import physical_onboarding_durability as durability
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from test_camera_probe_admission_audit_reuse import modeled_owner
from test_commissioning_camera_persistence import (
    LEASES,
    STAGE,
    WINDOWS,
    core_and_request,
    forbid_device_and_process_calls,
    runtime_and_adapter,
)
from test_physical_camera_prerequisites import workspace


pytestmark = WINDOWS


def _assert_zero_effect_result(core, worker, request):
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_KNOWN, (result, worker.error)
    assert worker.calls == 1 and worker.error is None
    assert result.receipt is not None
    assert (
        result.receipt.opens,
        result.receipt.reads,
        result.receipt.writes,
        result.receipt.frames,
        result.receipt.closes,
    ) == (0, 0, 0, 0, 0)


def _mixed_history(workspace, monkeypatch):
    """Real family records, modeled subjects; no saved original or USB query."""
    from rocell.application.physical_onboarding_v2 import V2StageState
    import test_commissioning_usb_presence_persistence as presence
    import test_commissioning_usb_identity as identity

    runtime, camera, store, case = presence.actual_case(workspace, monkeypatch)
    core, worker = presence.core(store, case)
    _assert_zero_effect_result(core, worker, presence.request(store))
    usb = identity.M1PhysicalUsbIdentityPersistence(
        runtime,
        workspace_source_sha256=identity.SOURCE,
        stage_policy=identity.POLICY,
        expected_usb_query_policy_sha256=identity.POLICY.sha256,
        admission_facts=identity.usb_facts,
    )
    for number in range(3):
        core, worker = identity.usb_core(usb)
        _assert_zero_effect_result(
            core, worker, identity.actual_request(usb, f"modeled-profile-usb-{number}")
        )
    # Explicit storage-only stage transition, not USB or camera qualification.
    timestamp = case.event.occurred_at_ns + 10
    with camera.stage_transaction(
        identity.SESSION,
        expected_challenge_sha256=camera.verification(
            identity.SESSION
        ).challenge_sha256,
    ) as tx:
        for offset, state in enumerate(
            (V2StageState.REVIEW_PENDING, V2StageState.PASS)
        ):
            tx.commit_stage_state(
                identity.STAGE,
                state,
                occurred_at_ns=timestamp + offset,
                detail_code="MODELED_STORAGE_ONLY_NOT_QUALIFICATION",
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=(case.reference,),
            )
        tx.commit_stage_state(
            STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=timestamp + 2,
            detail_code="MODELED_CAMERA_PROFILE_FOLLOWUP",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    core, worker, request = core_and_request(camera, key="modeled-profile-camera")
    _assert_zero_effect_result(core, worker, request)
    return runtime, camera


@pytest.mark.parametrize(
    "extra_references,prior_campaigns",
    [(0, 0), (66, 0), (66, 4), (66, 8), (66, "mixed")],
)
def test_profile_fresh_camera_storage_reader(
    tmp_path,
    monkeypatch,
    extra_references,
    prior_campaigns,
    record_testsuite_property,
    request,
):
    mixed = prior_campaigns == "mixed"
    history_id = prior_campaigns
    domains = []
    if mixed:
        runtime, adapter = _mixed_history(
            request.getfixturevalue("workspace"), monkeypatch
        )
        prior_campaigns = 5
        domains = [
            "INCAPABLE_CAMERA_CONTRACT",
            "INCAPABLE_USB_IDENTITY_CONTRACT",
            "INCAPABLE_USB_PRESENCE_CONTRACT",
        ]
    else:
        runtime, adapter = runtime_and_adapter(tmp_path)
        domains = ["INCAPABLE_CAMERA_CONTRACT"] if prior_campaigns else []
    # Build actual records through the production coordinator, using an
    # incapable zero-IO worker. No saved permit/store is used as a test seed.
    # These are camera-contract records, not USB identity receipt substitutes.
    for number in range(0 if mixed else prior_campaigns):
        core, worker, request = core_and_request(adapter, key=f"modeled-prior-{number}")
        _assert_zero_effect_result(core, worker, request)
    with adapter.transaction(LEASES) as tx:
        for number in range(extra_references):
            tx.store_evidence(
                STAGE,
                json.dumps(
                    {"MODELED_FILE_ONLY": number, "padding": "x" * 11_000}
                ).encode(),
                label="modeled reader profile history",
                media_type="application/json",
                captured_at_ns=5_000 + number,
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
        owner = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        tx._facts_provider = lambda request, snapshot: owner.owner(
            tx, request, snapshot
        )
        records = tx._audit_records(include_family=True)
        assert len(records) == prior_campaigns * 5
        attempts = tx._attempts.snapshot()
        assert len(attempts.latest_events) == prior_campaigns
        assert not attempts.unresolved_events and not attempts.uncertain_events
        expected = tx._fresh_admission(owner.request)
        durations = []
        # These samples do not include instrumentation. They are still ordinary
        # host wall times, not worst-case performance or hardware qualification.
        for _ in range(3):
            started = perf_counter_ns()
            assert tx._fresh_admission(owner.request) == expected
            durations.append(perf_counter_ns() - started)

        allocations = []
        create_buffer = durability.ctypes.create_string_buffer

        def counted_buffer(size, *args):
            if type(size) is int:
                allocations.append(size)
            return create_buffer(size, *args)

        profiler = cProfile.Profile()
        with monkeypatch.context() as patch:
            patch.setattr(durability.ctypes, "create_string_buffer", counted_buffer)
            profiler.enable()
            try:
                assert tx._fresh_admission(owner.request) == expected
            finally:
                profiler.disable()

        rows = []
        for (filename, line, function), stats in pstats.Stats(profiler).stats.items():
            primitive, calls, exclusive, inclusive, callers = stats
            rows.append(
                dict(
                    file=filename,
                    line=line,
                    function=function,
                    calls=calls,
                    primitive_calls=primitive,
                    exclusive_seconds=exclusive,
                    inclusive_seconds=inclusive,
                    # Caller edges attribute nested metadata work without
                    # adding another timed callback or caching any observation.
                    callers=[
                        dict(
                            file=caller_file,
                            line=caller_line,
                            function=caller_function,
                            primitive_calls=values[0],
                            calls=values[1],
                            exclusive_seconds=values[2],
                            inclusive_seconds=values[3],
                        )
                        for (
                            caller_file,
                            caller_line,
                            caller_function,
                        ), values in sorted(callers.items())
                    ],
                )
            )
        report = dict(
            schema="rocell.test_camera_storage_reader_profile.v1",
            python=sys.version.split()[0],
            windows_version=list(sys.getwindowsversion()[:3]),
            evidence_count=len(owner.snapshot.evidence),
            evidence_payload_bytes=sum(
                ref.payload_bytes for ref in owner.snapshot.evidence
            ),
            family_record_count=len(records),
            family_record_bytes=sum(
                len(canonical_json_bytes(record)) for record in records.values()
            ),
            record_domains=domains,
            attempt_count=len(attempts.latest_events),
            attempt_event_count=len(attempts.events),
            sibling_sessions=0,
            provenance=(
                "FRESH_MODELED_FILES_AND_INCAPABLE_MIXED_HISTORY_REAL_NTFS"
                if mixed
                else "FRESH_MODELED_FILES_AND_INCAPABLE_CAMERA_HISTORY_REAL_NTFS"
            ),
            uninstrumented_callback_ns=durations,
            instrumented_buffer_allocations=len(allocations),
            instrumented_buffer_allocated_bytes=sum(allocations),
            profile_rows=sorted(
                rows, key=lambda row: row["inclusive_seconds"], reverse=True
            ),
            timing_semantics="NESTED_INCLUSIVE_SPANS_OVERLAP_PROFILING_ADDS_OVERHEAD",
            hardware_qualified=False,
            physical_authority=False,
        )
        (tmp_path / "camera-storage-reader-profile.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        record_testsuite_property(
            f"camera_storage_profile_{extra_references}_{history_id}",
            json.dumps(
                {key: value for key, value in report.items() if key != "profile_rows"}
            ),
        )
        assert not (runtime.deployment_root / "native-camera-output").exists()
