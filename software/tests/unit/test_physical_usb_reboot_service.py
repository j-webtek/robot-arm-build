"""Reboot helper composition with real codecs and explicit modeled boundaries.

Storage, admission, publication logs and observations are models, not original
M1 authentication or received hardware. Policy/runtime reviews, independent
permit reconstruction and complete final-phase joins use the real codecs.
No production helper, process, CIM, camera or arm method may execute.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import json
from threading import Event, RLock
from types import SimpleNamespace

import pytest

from rocell.application import physical_usb_reboot_service as m
from rocell.application.physical_usb_identity_service import PhysicalUsbIdentityService
from rocell.application.physical_usb_reboot_boot import (
    build_usb_reboot_boot_intent,
    classify_usb_reboot_boot_observation,
)
from rocell.application.physical_usb_reboot_phase import (
    FLAGS as PHASE_FLAGS,
    verify_usb_reboot_qualification_phase,
)
from rocell.application.physical_onboarding_v2 import V2JournalEvent, V2StageState
from rocell.application.physical_onboarding import _parse_evidence_reference
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.usb_identity_protocol import canonical, digest

from test_physical_camera_usb_reboot_preparation import (
    prepared_case,
    no_native_or_process,
)
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_reboot_phase import predecessor
from test_physical_usb_presence_binding import reference
from test_physical_usb_identity_phase_operation import phase_permit
from test_physical_usb_reconnect_phase import modeled_reconnect_run


def record(payload, ref):
    return dict(
        document=json.loads(payload),
        evidence_sha256=digest(payload),
        reference=ref.to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )


class ModelTransaction:
    """In-memory original-shaped events and exact immutable role byte reads."""

    def __init__(self, c):
        self.c = c
        self.events = [c.args["phase_start_event"]]
        self.payloads = {}
        self.refs = {}
        self.stores = []
        self.failed_store = None

    def keep(self, payload, ref):
        self.payloads[ref.evidence_id] = payload
        self.refs[ref.evidence_id] = ref

    def snapshot(self):
        return SimpleNamespace(
            head=SimpleNamespace(head_sha256=self.events[-1].event_sha256),
            committed_events=tuple(self.events),
        )

    def read_stage_evidence(self, ref):
        assert self.refs[ref.evidence_id] == ref
        return self.payloads[ref.evidence_id]

    def store_evidence(self, stage, payload, **kwargs):
        assert stage is m.STAGE
        assert kwargs["expected_head_sha256"] == self.events[-1].event_sha256
        assert kwargs["media_type"] == "application/json"
        label = kwargs["label"]
        self.stores.append(label)
        if self.failed_store and self.failed_store in label:
            raise RuntimeError("MODELED_STORE_FAILURE")
        ref = reference(payload, label)
        self.keep(payload, ref)
        return ref

    def commit_stage_state(self, stage, state, **kwargs):
        assert stage is m.STAGE
        assert kwargs["expected_head_sha256"] == self.events[-1].event_sha256
        old = self.events[-1]
        event = V2JournalEvent.build(
            header=SimpleNamespace(
                session_id=old.session_id, header_sha256=old.session_header_sha256
            ),
            sequence=old.sequence + 1,
            stage=stage,
            previous_state=old.state,
            state=state,
            occurred_at_ns=kwargs["occurred_at_ns"],
            previous_event_sha256=old.event_sha256,
            evidence=kwargs["evidence"],
            detail_code=kwargs["detail_code"],
        )
        self.events.append(event)
        return self.snapshot()


def helper(c):
    plan = c.args["original_baseline"]["plan"]
    binding = plan.to_dict()["binding"]
    setup = SimpleNamespace(
        mode="physical",
        view=lambda: {
            "publication": {"status": "CURRENT", "operation_id": "MODELED-reopen-log"}
        },
    )
    owner = SimpleNamespace(
        _lock=RLock(),
        source_sha256=binding["source_sha256"],
        launch_id=c.subject.context["launch_session_id"],
        workspace=c.subject.operation.to_dict()["workspace"],
        setup=setup,
        _publication={"status": "CURRENT", "operation_id": "MODELED-original-log"},
        _workflow={"binding": binding},
        _attempted=set(),
        _qualification_trial={"plan": {"document": plan.to_dict()}},
        _attempt_key=lambda action, original: action
        + ":"
        + original["session_head_sha256"],
    )
    owner._read_records = (
        lambda tx, records, guard: PhysicalUsbIdentityService._read_records(
            owner, tx, records, guard
        )
    )
    phase = m._UsbTrialReboot(owner)
    phase.predecessor = {
        key: c.args[key]
        for key in (
            "original_baseline",
            "received",
            "absence",
            "absence_reference",
            "absence_sources",
            "reconnect",
            "reconnect_reference",
            "reconnect_sources",
            "reconnect_permit",
        )
    }
    phase_id = c.args["phase_id"]
    phase.reboot = dict(
        phase_id=phase_id,
        phase="AFTER_REBOOT",
        state="PREPARATION_REQUESTED",
        events=[c.args["phase_start_event"].to_dict()],
        **{role: None for role in m.USB_REBOOT_ROLE_BYTES},
        original_campaign=None,
        original_campaign_event=None,
    )
    phase.reboot["operator_event"] = record(
        c.subject.event.payload, c.args["operator_event_reference"]
    )
    phase.ledger = deepcopy(c.args["acquisition_ledger"])
    phase.attempt = dict(
        action_id=m.BEGIN, phase_id=phase_id, records={}, boot=None, dispatch=None
    )
    return phase


def test_real_reviews_independent_permit_and_complete_phase_transfer(
    prepared_case, monkeypatch
):
    c = prepared_case
    phase = helper(c)
    owner = phase.owner
    tx = ModelTransaction(c)
    row = phase.reboot
    for role, payload, ref in (
        ("operator_event", c.subject.event.payload, c.args["operator_event_reference"]),
        (
            "enrollment",
            c.subject.sources["native_enrollment"],
            c.args["enrollment_reference"],
        ),
        (
            "preparation",
            c.prepared.payload,
            reference(c.prepared.payload, "MODELED-service-preparation"),
        ),
        (
            "operation",
            c.subject.operation.payload,
            reference(c.subject.operation.payload, "MODELED-service-operation"),
        ),
    ):
        tx.keep(payload, ref)
        row[role] = record(payload, ref)
    now = [c.args["prepared_at_utc_ns"] + 1]

    def tick():
        now[0] += 1
        return now[0]

    monkeypatch.setattr(m, "time_ns", tick)
    monkeypatch.setattr(
        m, "inspect_usb_identity_stage_policy", lambda _: usb_identity_stage_policy()
    )
    phase._commit(
        tx,
        "PREPARED",
        V2StageState.REVIEW_PENDING,
        row["phase_id"],
        [m._reference(row[key]) for key in tuple(m.USB_REBOOT_ROLE_BYTES)[:4]],
    )
    row["state"] = "PREPARED"
    phase.attempt["action_id"] = m.REVIEW
    phase._review(
        tx,
        row,
        c.args["original_baseline"]["plan"],
        phase.predecessor,
        {"reviewer_id": "MODELED-new-reboot-reviewer"},
        lambda: None,
    )
    row.update(deepcopy(phase.attempt["records"]))
    row["events"] = [event.to_dict() for event in tx.events]
    row["state"] = "REVIEWED"
    assert len(tx.events[-1].evidence) == 8
    assert {ref.evidence_id for ref in tx.events[-1].evidence} == {
        m._reference(row[role]).evidence_id
        for role in tuple(m.USB_REBOOT_ROLE_BYTES)[:8]
    }
    intent = m.UsbRebootBootIntent(canonical(row["boot_request"]["document"]))
    assert (
        build_usb_reboot_boot_intent(
            preparation=c.prepared,
            preparation_reference=m._reference(row["preparation"]),
            reconnect=c.args["reconnect"],
            reconnect_reference=c.args["reconnect_reference"],
        ).payload
        == intent.payload
    )
    requested = phase._commit(
        tx,
        "BOOT_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        row["phase_id"],
        [m._reference(row["boot_request"])],
    )
    # Owned execution/boot provenance is explicitly physical-shaped MODELED data;
    # this tests retention/classification, never the actual collector admission.
    boot = c.subject.boot
    assert (
        classify_usb_reboot_boot_observation(
            boot,
            intent=intent,
            expected_sha256=boot.sha256,
            requested_event=requested,
            reconnect_boot=m.HostBootObservation(
                c.args["reconnect_sources"]["host_boot"]
            ),
        )
        == "BOOT_RETAINED"
    )
    now[0] = boot.to_dict()["execution"]["finished_utc_ns"] + 1
    br = phase._retain(tx, boot.payload, "host_boot", row["phase_id"])
    row["host_boot"] = deepcopy(phase.attempt["records"]["host_boot"])
    phase._commit(
        tx,
        "BOOT_RETAINED",
        V2StageState.BLOCKED,
        row["phase_id"],
        [m._reference(row["boot_request"]), br],
    )
    phase._commit(
        tx,
        "QUERY_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        row["phase_id"],
        [m._reference(row[key]) for key in ("identity", "boot_request", "host_boot")],
    )
    row.update(state="QUERY_REQUESTED", events=[event.to_dict() for event in tx.events])
    workflow = dict(
        binding=c.args["original_baseline"]["plan"].to_dict()["binding"],
        usb_qualification_reboot=row,
    )
    runtime = object.__new__(m.PhysicalOnboardingM1Runtime)
    runtime.source_binding_sha256 = m.physical_camera_source_binding(
        owner.source_sha256
    )
    owner.setup.session = SimpleNamespace(_store=SimpleNamespace(_runtime=runtime))
    # This first helper test explicitly MODELS the admission-facts boundary;
    # full v13 leased-snapshot/epoch facts require the separate original reader.
    sentinel = object()
    phase._facts_provider = lambda *args: sentinel
    calls = []

    class ModelPersistence:
        def __init__(self, supplied, **kwargs):
            assert supplied is runtime and kwargs["admission_facts"] is sentinel

        def verification(self, session_id):
            return SimpleNamespace(challenge_sha256="c" * 64)

        @contextmanager
        def stage_transaction(self, session_id, **kwargs):
            assert kwargs["expected_challenge_sha256"] == "c" * 64
            yield tx

    class ModelDispatch:
        def __init__(self, persistence, campaign, **kwargs):
            self.campaign, self.original = campaign, None

        def perform(self, *, request_key, cancellation):
            assert request_key == "usb-reboot-" + row["phase_id"]
            calls.append(request_key)
            permit = replace(
                phase_permit(self.campaign),
                attempt_id="attempt-"
                + digest(b"MODELED-new-reboot-service-attempt")[:32],
                nonce=digest(b"MODELED-new-reboot-service-nonce"),
            )
            observed = modeled_reconnect_run(
                self.campaign.preparation_for_permit(permit), utc=tick() + 100
            )
            now[0] = observed.to_dict()["finished_utc_ns"] + 1
            self.original = json.loads(
                canonical(
                    dict(
                        permit=asdict(permit),
                        result={"state": "SEALED_KNOWN"},
                        admission_evidence={"MODELED": True},
                        evidence=observed.to_dict(),
                        evidence_sha256=observed.sha256,
                        reference={"MODELED": True},
                        retention="M1_FULL_BYTES_READ_BACK",
                    )
                )
            )
            return {"MODELED_PENDING_DISPATCH": True}

        def retained_diagnostics(self):
            return {"original": deepcopy(self.original)}

    monkeypatch.setattr(m, "M1PhysicalUsbIdentityPersistence", ModelPersistence)
    monkeypatch.setattr(m, "PhysicalUsbIdentityDispatchOwner", ModelDispatch)
    phase._collect_usb(workflow, None, phase.predecessor, lambda: None, Event())
    assert len(calls) == 1 and phase.query_attempted
    assert len(tx.events[-1].evidence) == 11
    row.update(deepcopy(phase.attempt["records"]))
    final = row["phase_record"]
    from rocell.application.commissioning_usb_identity_persistence import (
        decode_physical_usb_identity_permit,
    )

    verified = verify_usb_reboot_qualification_phase(
        canonical(final["document"]),
        expected_sha256=final["evidence_sha256"],
        **phase.predecessor,
        permit=decode_physical_usb_identity_permit(
            phase.attempt["dispatch"]["original"]["permit"]
        ),
        sources={
            key: canonical(row[stored]["document"])
            for key, stored in (
                ("operation", "operation"),
                ("operator_event", "operator_event"),
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            )
        },
        references={
            key: m._reference(row[stored])
            for key, stored in (
                ("operation", "operation"),
                ("operator_event", "operator_event"),
                ("native_enrollment", "enrollment"),
                ("owned_usb_run", "execution"),
                ("host_boot", "host_boot"),
            )
        },
    )
    assert verified.to_dict()["status"] == "REBOOT_OBSERVATIONS_RETAINED"
    assert verified.to_dict()["missing_requirements"] == []
    assert all(verified.to_dict()[flag] is False for flag in PHASE_FLAGS)
    assert verified.to_dict()["metadata_acquisition_freshness_verified"] is False
    assert c.subject.reconnect.payload == phase.predecessor["reconnect"].payload
    assert len(phase.attempt["events"]) == 6


def test_new_launch_projection_and_exact_metadata_publication_ledger(
    prepared_case, monkeypatch
):
    c, phase = prepared_case, helper(prepared_case)
    owner = phase.owner
    old = dict(
        schema="rocell.wizard_usb_qualification.v4",
        publication={"status": "HISTORICAL_HELD", "operation_id": None},
        status="HISTORICAL_HELD",
        reconnect={"state": "RETAINED_BLOCKED"},
        next_action=m.EXPORT,
        plan={"MODELED": True},
    )
    saved = deepcopy(old)
    row = phase.reboot
    phase.reboot = phase.attempt = None
    value = phase.projection(old)
    assert value["schema"] == "rocell.wizard_usb_qualification.v5"
    assert (
        value["publication"]["status"] == "CURRENT" and value["next_action"] == m.BEGIN
    )
    assert value["reconnect"] == old["reconnect"] and old == saved
    assert phase.diagnostics({}) == {}
    entry = dict(
        schema="rocell.physical_camera_source_workflow_readback.v12",
        configuration_epochs={"MODELED": True},
        session_head_sha256="a" * 64,
    )
    assert phase.blocked_reason(m.BEGIN, entry, None, None) is None
    new_launch = owner.launch_id
    owner.launch_id = c.args["reconnect"].to_dict()["context"]["launch_session_id"]
    assert phase.projection(old) == old
    assert "new app launch" in phase.blocked_reason(m.BEGIN, entry, None, None)
    owner.launch_id = new_launch
    phase.reboot = row
    phase.ledger = None
    now = [c.subject.event.to_dict()["reported_at_utc_ns"] + 1]
    monkeypatch.setattr(m, "time_ns", lambda: now[0])
    raw = json.loads(c.subject.sources["native_enrollment"])
    docs = (
        raw["generic_review"]["inventory_report"],
        raw["inventory_packet"],
        raw["identity_packet"],
    )
    ids = (
        raw["generic_review"]["operation_id"],
        raw["view"]["inventory_operation_id"],
        raw["view"]["identity"]["operation_id"],
    )
    for (_, action), document, operation_id in zip(m.ACQUISITIONS, docs, ids):
        token = phase.acquisition_started(action, operation_id, now[0])
        assert token is not None
        for key, wrong in (
            ("source_sha256", "f" * 64),
            ("launch_session_id", "wizard-other"),
            ("phase_id", "usbphase-" + "a" * 32),
        ):
            before = deepcopy(phase.ledger)
            phase.acquisition_published(
                dict(token, **{key: wrong}),
                finished_at_ns=now[0],
                document=document,
                result_sha256="a" * 64,
            )
            assert phase.ledger == before
        now[0] += 2
        phase.acquisition_published(
            token,
            finished_at_ns=now[0] - 1,
            document=document,
            result_sha256=digest(
                canonical({"MODELED_COMPLETION_LOG_RESULT": operation_id})
            ),
        )
        now[0] += 2
    assert len(phase.ledger["entries"]) == 3
    assert [row["document_sha256"] for row in phase.ledger["entries"]] == [
        digest(canonical(doc)) for doc in docs
    ]
    assert all(row["completion_logged"] is True for row in phase.ledger["entries"])
    saved_ledger = deepcopy(phase.ledger)
    for token in (None, {}, {"action_id": "camera_capture"}):
        phase.acquisition_published(
            token, finished_at_ns=now[0], document={}, result_sha256="a" * 64
        )
    assert phase.ledger == saved_ledger
    phase.attempt = dict(action_id=m.PREPARE)
    assert (
        phase.acquisition_started("inventory_devices", "MODELED-after-attempt", now[0])
        is None
    )
    assert phase.ledger == saved_ledger
    phase.attempt = None
    owner._publication = dict(status="HISTORICAL_HELD", operation_id=None)
    assert phase.projection(old)["next_action"] == "physical_camera_refresh"
    owner.launch_id = "wizard-newer-launch"
    assert phase.acquisition_started("inventory_devices", "new", now[0]) is None
    assert phase.projection(old)["next_action"] == m.EXPORT
    assert phase.projection(old)["publication"]["status"] == "HISTORICAL_HELD"


@pytest.mark.parametrize(
    "state,campaign,event",
    [
        ("BOOT_RETAINED", None, None),
        ("INCOMPLETE", None, None),
        ("ORIGINAL_CAMPAIGN_HELD", None, None),
        ("QUERY_REQUESTED", {"MODELED": "terminal"}, None),
        ("QUERY_REQUESTED", None, {"MODELED": "pending"}),
    ],
)
def test_existing_or_wrong_original_query_never_constructs_dispatch(
    state, campaign, event, monkeypatch
):
    def forbidden(*a, **k):
        pytest.fail("A retained/partial reboot must not create another dispatcher")

    for name in (
        "UsbIdentityOperation",
        "PhysicalUsbIdentityCampaign",
        "M1PhysicalUsbIdentityPersistence",
        "PhysicalUsbIdentityDispatchOwner",
    ):
        monkeypatch.setattr(m, name, forbidden)
    phase = m._UsbTrialReboot(SimpleNamespace())
    workflow = {
        "usb_qualification_reboot": dict(
            state=state, original_campaign=campaign, original_campaign_event=event
        )
    }
    with pytest.raises(WizardError) as raised:
        phase._collect_usb(workflow, None, None, forbidden, None)
    assert raised.value.code == "USB_REBOOT_ORIGINAL_ATTEMPT_EXISTS"
    assert not phase.query_attempted


def test_closed_action_forms_and_constructor_are_inert():
    phase = m._UsbTrialReboot(SimpleNamespace())
    assert phase.diagnostics({}) == {}
    assert not phase.has_diagnostics() and not phase.query_attempted
    expected = {
        m.BEGIN: ("operator_id", "file_only", "confirm_host_restarted"),
        m.PREPARE: ("operator_id", "file_only"),
        m.REVIEW: (
            "reviewer_id",
            "confirm_policy_review",
            "confirm_runtime_review",
            "confirm_exact_target",
            "confirm_boot_metadata",
        ),
        m.BOOT_COLLECT: ("confirm_host_boot", "confirm_no_capture_or_arm"),
        m.COLLECT: ("confirm_usb_query", "confirm_no_capture_or_arm"),
    }
    assert set(expected) == m.ACTIONS
    for action, names in expected.items():
        fields = phase.fields(
            action,
            lambda name, label: dict(name=name, default=False),
            lambda name, label: dict(name=name, default=""),
        )
        assert tuple(row["name"] for row in fields) == names
        assert all(row["default"] in (False, "") for row in fields)
    with pytest.raises(KeyError):
        phase.fields("physical_usb_reconnect_collect", lambda *a: None, lambda *a: None)


def test_successful_commit_is_retained_before_later_guard_failure(monkeypatch):
    phase = m._UsbTrialReboot(SimpleNamespace())
    phase.attempt = dict(phase_id="usbphase-" + "1" * 32, records={})
    calls = []

    def before():
        calls.append("snapshot")
        assert calls == ["snapshot"]
        return SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))

    def commit(stage, state, **kwargs):
        calls.append("commit")
        event = V2JournalEvent.build(
            header=SimpleNamespace(
                session_id="MODELED-session", header_sha256="b" * 64
            ),
            sequence=1,
            stage=stage,
            previous_state=V2StageState.BLOCKED,
            state=state,
            occurred_at_ns=kwargs["occurred_at_ns"],
            previous_event_sha256="a" * 64,
            evidence=(),
            detail_code=kwargs["detail_code"],
        )
        return SimpleNamespace(committed_events=(event,))

    tx = SimpleNamespace(snapshot=before, commit_stage_state=commit)
    with pytest.raises(RuntimeError, match="MODELED_LATE_GUARD"):
        event = phase._commit(
            tx,
            "PREPARATION_REQUESTED",
            V2StageState.WAITING_OPERATOR,
            phase.attempt["phase_id"],
            [],
        )
        raise RuntimeError("MODELED_LATE_GUARD")
    assert calls == ["snapshot", "commit"]
    assert phase.diagnostics({})["qualification_reboot_attempt"]["events"] == [
        event.to_dict()
    ]
    assert phase.reboot is None and not phase.query_attempted
