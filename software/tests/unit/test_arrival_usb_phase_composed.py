"""Actual application/readback joins, explicitly modeled original storage/facts.

No native helper, local CIM, USB endpoint or owned child is executed here.
The renderer is the existing finite Node fake-DOM plus the real terminal view.
"""

from copy import deepcopy
from threading import Event
import time

import pytest

from rocell.application import physical_usb_identity_service as module
from rocell.application import physical_usb_trial_service as phase_module
from rocell.application.physical_usb_identity_export import (
    prepare_usb_identity_diagnostics_export,
)
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.ui.terminal import _UsbQualificationDisplay
from test_arrival_usb_qualification_composed import (
    declared_prefix,
    identity_composed,
    identity_wait,
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    original_epochs,
    make_service,
    VALUES,
    _run,
    _complete,
    complete_modeled_storage_projection,
)
from test_physical_usb_identity_service import modeled_files
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_arrival_wizard_service import _ticket

REVIEW_VALUES = dict(
    reviewer_id="Phase Reviewer",
    confirm_policy_review=True,
    confirm_runtime_review=True,
    confirm_exact_target=True,
    confirm_boot_metadata=True,
)


@pytest.fixture
def phase_case(declared_prefix, monkeypatch):
    from rocell.application import physical_camera_usb_readback

    monkeypatch.setattr(
        physical_camera_usb_readback, "read_original_usb_campaigns", lambda *a, **kw: ()
    )
    monkeypatch.setattr(phase_module, "inspect_usb_identity_runtime", modeled_files)
    monkeypatch.setattr(
        phase_module,
        "inspect_usb_identity_stage_policy",
        module.inspect_usb_identity_stage_policy,
    )
    # The in-memory journal has no actual disk latency; Windows Python's UTC
    # clock can repeat within that interval. Model its strictly ordered event
    # ticks explicitly, without changing any production clock or old subjects.
    last = [time.time_ns()]

    def ordered_utc():
        last[0] = max(time.time_ns(), last[0] + 1)
        return last[0]

    monkeypatch.setattr(phase_module, "time_ns", ordered_utc)
    return declared_prefix


def run(case, action, values):
    op = _run(case[0], action, values)
    assert op["status"] == "SUCCEEDED", (
        op,
        [(e.detail_code, e.occurred_at_ns) for e in case[2]["events"][-5:]],
    )
    return op


def assert_rendered(arrival):
    snapshot = arrival.view()
    card = snapshot["usb_qualification"]
    _UsbQualificationDisplay._validate(card, snapshot)
    before = deepcopy(snapshot)
    for text in render_snapshot(snapshot):
        for marker in (
            "USB_QUALIFICATION_NOT_VERIFIED",
            "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED",
            "USB_IDENTITY_NOT_VERIFIED",
        ):
            assert marker not in text
        assert "new app launch is not a reboot" in text
    assert snapshot == before
    return card


def publish_modeled_acquisitions(arrival):
    """Explicit test-only successful publisher model; not actual OS metadata."""
    helper = arrival._usb_identity._trial
    snapshot = arrival._native_camera.export_snapshot()
    rows = (
        (
            "inventory_devices",
            snapshot["generic_review"]["operation_id"],
            snapshot["generic_review"]["inventory_report"],
        ),
        (
            "native_camera_inventory",
            snapshot["view"]["inventory_operation_id"],
            snapshot["inventory_packet"],
        ),
        (
            "native_camera_identity",
            snapshot["view"]["identity"]["operation_id"],
            snapshot["identity_packet"],
        ),
    )
    for action, op, document in rows:
        token = helper.acquisition_started(action, op, phase_module.time_ns())
        helper.acquisition_published(
            token,
            finished_at_ns=phase_module.time_ns(),
            document=document,
            result_sha256=digest(
                canonical({"explicitly_modeled_logged_result": document})
            ),
        )


def test_public_begin_prepare_review_and_inert_original_rendering(
    phase_case, monkeypatch
):
    case = phase_case
    arrival, owner, state, _, runner = case
    monkeypatch.setattr(
        phase_module,
        "inspect_usb_identity_stage_policy",
        module.inspect_usb_identity_stage_policy,
    )
    monkeypatch.setattr(phase_module, "inspect_usb_identity_runtime", modeled_files)
    run(case, module.DECLARE, VALUES)
    before = deepcopy(state["payloads"])
    assert assert_rendered(arrival)["next_action"] == module.BEGIN
    run(case, module.BEGIN, dict(operator_id="Phase Operator", file_only=True))
    current = owner.setup.original_source_workflow()
    assert current["schema"].endswith(".v10")
    assert current["usb_qualification_baseline"]["state"] == "PREPARATION_REQUESTED"
    assert before.items() <= state["payloads"].items()
    card = assert_rendered(arrival)
    assert card["baseline"]["acquisition_ledger"] is None
    assert render(arrival.view())["links"][0]["id"] == "inventory_devices"
    with pytest.raises(WizardError):
        arrival.prepare_action(
            module.PREPARE,
            dict(operator_id="Phase Operator", file_only=True),
            arrival.view()["revision"],
        )
    publish_modeled_acquisitions(arrival)
    op = run(case, module.PREPARE, dict(operator_id="Phase Operator", file_only=True))
    assert op["completion_log_persisted"]
    assert op["result"]["steps"][0]["report"]["meaning"] == phase_module.MEANING
    card = assert_rendered(arrival)
    assert card["baseline"]["state"] == "PREPARED"
    assert card["baseline"]["preparation"]["operator_id"] == "Phase Operator"
    values = dict(
        reviewer_id="Phase Reviewer",
        confirm_policy_review=True,
        confirm_runtime_review=True,
        confirm_exact_target=True,
        confirm_boot_metadata=True,
    )
    run(case, module.PHASE_REVIEW, values)
    card = assert_rendered(arrival)
    assert card["baseline"]["state"] == "REVIEWED"
    assert card["next_action"] == module.PHASE_COLLECT
    assert (
        card["baseline"]["host_boot"] is None and card["baseline"]["execution"] is None
    )
    baseline = owner.setup.original_source_workflow()["usb_qualification_baseline"]
    assert len(baseline["events"][-1]["evidence"]) == 6
    assert baseline["boot_request"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    diagnostic = owner.retained_diagnostics()
    assert diagnostic["schema"] == "rocell.wizard_usb_identity_diagnostics.v3"
    assert diagnostic["qualification_baseline"] == baseline
    assert prepare_usb_identity_diagnostics_export(
        diagnostic, source_sha256=owner.source_sha256, launch_id=owner.launch_id
    )[0]["schema"].endswith(".v3")
    assert not runner.calls


def test_acquisition_publish_requires_exact_order_token_and_completion(phase_case):
    declared_prefix = phase_case
    run(declared_prefix, module.DECLARE, VALUES)
    run(
        declared_prefix,
        module.BEGIN,
        dict(operator_id="Phase Operator", file_only=True),
    )
    owner = declared_prefix[1]
    helper = owner._trial
    token = helper.acquisition_started(
        "native_camera_identity", "too-early", time.time_ns()
    )
    helper.acquisition_published(
        token, finished_at_ns=time.time_ns(), document={}, result_sha256="a" * 64
    )
    assert helper.ledger["entries"] == []

    token = helper.acquisition_started(
        "inventory_devices", "failed-no-publish", time.time_ns()
    )
    assert helper.ledger["entries"] == []
    # A different source/phase token cannot publish a row.
    token["phase_id"] = "usbphase-" + "0" * 32
    helper.acquisition_published(
        token, finished_at_ns=time.time_ns(), document={}, result_sha256="a" * 64
    )
    assert helper.ledger["entries"] == []
    publish_modeled_acquisitions(declared_prefix[0])
    assert len(helper.ledger["entries"]) == 3
    helper.acquisition_started(
        "inventory_devices", "new-upstream-attempt", time.time_ns()
    )
    assert helper.ledger["entries"] == []


def test_original_partial_identity_without_boot_intent_reopens_as_held(
    phase_case, monkeypatch
):
    arrival, owner, state, _, _ = phase_case
    run(phase_case, module.DECLARE, VALUES)
    run(phase_case, module.BEGIN, dict(operator_id="Phase Operator", file_only=True))
    publish_modeled_acquisitions(arrival)
    run(phase_case, module.PREPARE, dict(operator_id="Phase Operator", file_only=True))
    retain = owner._trial._retain

    def refuse_boot_intent(tx, payload, role, phase_id):
        if role == "boot_request":
            raise ValueError("MODELED_BOOT_INTENT_STORAGE_REFUSAL")
        return retain(tx, payload, role, phase_id)

    with monkeypatch.context() as fault:
        fault.setattr(owner._trial, "_retain", refuse_boot_intent)
        failed = _run(arrival, module.PHASE_REVIEW, REVIEW_VALUES)
    assert failed["status"] == "FAILED"
    # The original reader, not a patched display fixture, authenticates this
    # legal stored-before-commit prefix. A fresh service has no volatile attempt.
    run(phase_case, "physical_camera_refresh", {})
    original = owner.setup.original_source_workflow()
    baseline = original["usb_qualification_baseline"]
    assert baseline["state"] == "INCOMPLETE"
    assert baseline["identity"] is not None and baseline["boot_request"] is None
    fresh = module.PhysicalUsbIdentityService(owner.setup)
    fresh.observe_setup()
    arrival._usb_identity = fresh
    card = assert_rendered(arrival)
    assert card["baseline"]["review"] is None
    assert card["baseline"]["execution"] is None
    assert card["next_action"] == module.EXPORT
    assert fresh.retained_diagnostics()["qualification_baseline"] == baseline


@pytest.mark.parametrize("known_counts", [False, True])
def test_reopened_original_campaign_without_stage_transfer_preserves_evidence(
    known_counts,
):
    from test_owned_usb_identity_runner import usb_fixture
    from test_physical_usb_identity_dispatch_m1 import failure_evidence
    from test_physical_camera_usb_readback import modeled_clean_held_evidence

    # No runner is called. These actual immutable codecs contain explicitly
    # modeled native/process observations, including an unknown-count failure.
    case = usb_fixture(incapable=False)
    evidence = (
        modeled_clean_held_evidence(case.prepared)
        if known_counts
        else failure_evidence(
            case.prepared,
            deadline_ns=time.monotonic_ns() + 25_000_000_000,
            checks=[],
            started_ns=time.monotonic_ns(),
            started_utc_ns=time.time_ns(),
            process_created=True,
        )
    )
    baseline = dict(
        phase_id="usbphase-" + "e" * 32,
        state="ORIGINAL_CAMPAIGN_HELD",
        execution=None,
        original_campaign=dict(
            evidence=evidence.to_dict(), evidence_sha256=evidence.sha256
        ),
    )
    fresh = phase_module._UsbTrialBaseline(None)
    fresh.adopt({"usb_qualification_baseline": baseline})
    assert fresh.attempt is None
    assert fresh.execution().payload == evidence.payload
    summary = fresh.execution_summary()
    assert summary == evidence.safe_summary()
    assert summary["actual_counts"] == (
        evidence.actual_counts if known_counts else None
    )
    assert summary["counter_coverage"] == (
        "NATIVE_RECEIPT" if known_counts else "NOT_REPORTED"
    )
    assert (module._observation(fresh.execution()) is not None) is known_counts
    baseline["original_campaign"]["evidence_sha256"] = "0" * 64
    fresh.adopt({"usb_qualification_baseline": baseline})
    with pytest.raises(WizardError) as changed:
        fresh.execution()
    assert changed.value.code == "USB_PHASE_EXECUTION_HASH_CHANGED"


@pytest.mark.parametrize(
    "fault", [None, "worker_failure", "stop", "source", "completion_log"]
)
def test_public_metadata_worker_log_boundary_produces_only_successful_fresh_rows(
    phase_case, monkeypatch, fault
):
    arrival, owner, state, source, runner = phase_case
    run(phase_case, module.DECLARE, VALUES)
    run(phase_case, module.BEGIN, dict(operator_id="Phase Operator", file_only=True))
    document = deepcopy(
        arrival._native_camera.export_snapshot()["generic_review"]["inventory_report"]
    )
    entered, release = Event(), Event()
    real_runner = runner.run

    def worker(action, values, **kwargs):
        assert action == "inventory_devices"
        assert owner._trial.ledger["entries"] == []
        entered.set()
        if fault == "stop":
            assert release.wait(5)
        result = real_runner(action, values, **kwargs)
        result["steps"] = [
            dict(
                name="metadata_inventory",
                exit_code=1 if fault == "worker_failure" else 0,
                report=deepcopy(document),
            )
        ]
        if fault == "worker_failure":
            result["status"] = "FAILED"
        if fault == "source":
            source["hash"] = "f" * 64
        return result

    monkeypatch.setattr(runner, "run", worker)
    append = arrival._append_event

    def log(kind, details):
        if (
            kind == "ACTION_FINISHED"
            and details.get("action_id") == "inventory_devices"
        ):
            assert owner._trial.ledger["entries"] == []
            if fault == "completion_log":
                return False
        return append(kind, details)

    monkeypatch.setattr(arrival, "_append_event", log)
    ticket = _ticket(arrival, "inventory_devices", {"power_disconnected": True})
    queued = arrival.execute_action(ticket["ticket_id"])
    assert entered.wait(5)
    if fault == "stop":
        stop = _ticket(arrival, "stop_operation")
        arrival.execute_action(stop["ticket_id"])
        release.set()
    op = _complete(arrival, queued["operation_id"])
    ledger = owner._trial.ledger
    if fault is None:
        assert op["status"] == "SUCCEEDED" and op["completion_log_persisted"]
        assert len(ledger["entries"]) == 1
        row = ledger["entries"][0]
        assert row["operation_id"] == op["operation_id"]
        assert row["document_sha256"] == digest(canonical(document))
        assert row["result_sha256"] == op["result_sha256"]
        assert row["completion_logged"] is True
        assert (
            ledger["phase_started_at_utc_ns"]
            <= row["started_at_utc_ns"]
            <= row["finished_at_utc_ns"]
            <= row["published_at_utc_ns"]
        )
    else:
        assert op["status"] != "SUCCEEDED"
        assert ledger["entries"] == []
