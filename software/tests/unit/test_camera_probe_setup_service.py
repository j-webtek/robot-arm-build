"""Actual file-only writer with explicitly MODELED original/store/software facts.

Pure subject construction and independent context checks run. These callbacks
are not M1 authentication, a current OS observation, or hardware qualification.
Separate composition tests must cover the real original reader and UI owner.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import camera_probe_setup_service as m
from rocell.application import physical_camera_session as session_impl
from rocell.application.camera_probe_preparation import (
    CameraProbePreparation,
    CameraProbePreparationReview,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from test_camera_probe_preparation_readback import (
    current_enrollment,
    prepared_subject,
    PROBE_LAUNCH,
)
from test_camera_mode_entry_layout import reference
from test_native_camera_activation_expectation import enrollment as old_enrollment
from test_camera_activation_service_handoff import SOURCE


@pytest.fixture
def modeled(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("file-only writer started a process"),
    )
    previous = old_enrollment().export_snapshot()
    current = current_enrollment(previous, source=SOURCE)
    original = dict(
        schema=m.SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
        session_header_sha256="b" * 64,
        camera_mode_entry=dict(
            state="ENTERED",
            entry=dict(evidence_sha256="e" * 64),
            events=[dict(event_sha256="f" * 64, occurred_at_ns=10)],
        ),
        usb_qualification_reboot=dict(enrollment=dict(document=previous)),
    )
    bound = dict(
        workspace=str(tmp_path),
        directory=str(
            tmp_path / "software/runs/physical-camera-acquisition" / PROBE_LAUNCH
        ),
        source_sha256=SOURCE,
        cell_id="wizard-physical-camera-" + "b" * 16,
        session_id="physical-camera-" + "c" * 32,
    )
    software = prepared_subject(original, bound).to_dict()["software"]
    c = SimpleNamespace(
        original=original,
        bound=bound,
        events=[],
        stored={},
        clock=100,
        source=SOURCE,
        cancellation=Event(),
        current=current,
        software=software,
    )
    setup = SimpleNamespace(
        workspace=tmp_path,
        source_sha256=SOURCE,
        launch_id=PROBE_LAUNCH,
        _probe_queues={
            action: dict(
                claimed=True, context_sha256="a" * 64, operation_id="MODELED-" + action
            )
            for action in m.ACTIONS
        },
        _probe_attempts={},
        original_source_workflow=lambda: deepcopy(c.original),
    )
    c.setup = setup
    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))
    )
    c.tx = tx

    def store(stage, payload, **kwargs):
        c.events.append("store")
        assert stage is STAGE_ORDER[4]
        cls = (
            CameraProbePreparationReview
            if "camera-probe-review-" in kwargs["label"]
            else CameraProbePreparation
        )
        subject = cls(payload)
        ref = reference(
            payload,
            "review" if cls is CameraProbePreparationReview else "preparation",
            stage,
        )
        c.stored[ref.evidence_id] = (subject, ref)
        c.latest = ref
        return ref

    def read(ref):
        c.events.append("read")
        return c.stored[ref.evidence_id][0].payload

    def commit(*args, **kwargs):
        c.events.append("commit")
        c.commit_kwargs = kwargs
        return SimpleNamespace(
            committed_events=[
                SimpleNamespace(to_dict=lambda: dict(MODELED_COMMIT=True))
            ]
        )

    tx.store_evidence, tx.read_stage_evidence, tx.commit_stage_state = (
        store,
        read,
        commit,
    )

    def store_review(payload, **kwargs):
        document = CameraProbePreparationReview(payload).to_dict()
        return store(
            STAGE_ORDER[4],
            payload,
            label=m.camera_probe_label("review", document["preparation_id"]),
            **kwargs
        )

    tx.store_camera_probe_review = store_review

    @contextmanager
    def scope(**kwargs):
        c.events.append("lease")
        yield tx
        c.events.append("lease_exit")

    def after(**kwargs):
        c.events.append("original_after")
        result = deepcopy(c.original)
        subject, ref = c.stored[c.latest.evidence_id]
        row = result.get(
            "camera_probe_preparation", dict(preparation=None, review=None, events=[])
        )
        kind = (
            "review" if type(subject) is CameraProbePreparationReview else "preparation"
        )
        row[kind] = dict(
            document=subject.to_dict(),
            evidence_sha256=subject.sha256,
            reference=ref.to_dict(),
            retention="M1_FULL_BYTES_READ_BACK",
        )
        row["state"] = (
            "REVIEWED_FOR_ADMISSION" if kind == "review" else "PREPARED_REVIEW_REQUIRED"
        )
        result.update(
            schema=m.SOURCE_WORKFLOW_PROBE_SCHEMA, camera_probe_preparation=row
        )
        return result

    c.session = SimpleNamespace(
        descriptor=lambda: deepcopy(bound),
        view=lambda: dict(
            verification=dict(
                effects_allowed_by_m1_storage=True, challenge_sha256="c" * 64
            )
        ),
        stage_transaction=scope,
        refresh=lambda **k: c.events.append("refresh"),
        read_original_source_workflow=after,
    )
    setup.session = c.session

    def adopt(value):
        c.events.append("adopt")
        c.original = deepcopy(value)

    setup._adopt_source_workflow = adopt

    def before(*a, **k):
        c.events.append("original_before")
        return None, deepcopy(c.original)

    def software_check(candidate, **kwargs):
        purpose = candidate.to_dict()["purpose"]
        c.events.append("software_" + purpose)
        return deepcopy(software[purpose])

    monkeypatch.setattr(session_impl, "_read_original_evidence_under_lease", before)
    monkeypatch.setattr(m, "verify_reviewed_activation_runtime", software_check)
    monkeypatch.setattr(m, "source_fingerprint", lambda _: c.source)
    monkeypatch.setattr(m, "monotonic_ns", lambda: c.clock)
    monkeypatch.setattr(m, "time_ns", lambda: 1000)
    return c


def execute(c, action=m.PREPARE, **overrides):
    values = dict(
        operator_id="MODELED operator",
        enrollment=c.current,
        cancellation=c.cancellation,
        progress=lambda _: None,
        deadline_ns=100 + m.TIMEOUT_NS,
        validate_current_enrollment=lambda: None,
    )
    values.update(overrides)
    return m.write_probe_record(c.setup, action, **values)


def test_preparation_then_exact_review_preserves_file_boundaries_without_publishing(
    modeled,
):
    c = modeled
    row = execute(c)
    assert row["state"] == "PREPARED_REVIEW_REQUIRED"
    assert c.events == [
        "lease",
        "original_before",
        "software_probe",
        "software_capture",
        "store",
        "read",
        "commit",
        "lease_exit",
        "refresh",
        "original_after",
        "adopt",
    ]
    c.events.clear()
    row = execute(c, m.REVIEW)
    assert row["state"] == "REVIEWED_FOR_ADMISSION"
    assert len(c.commit_kwargs["evidence"]) == 2
    for attempt in c.setup._probe_attempts.values():
        assert attempt["record"]["retention"] == "M1_FULL_BYTES_READ_BACK"
        assert attempt["status"] == "ORIGINAL_READ_BACK"
    assert not hasattr(c.setup, "_publication")  # Arrival/Setup own final publication.


@pytest.mark.parametrize(
    "fault",
    [
        "stop",
        "deadline",
        "bool-deadline",
        "source",
        "queue",
        "boundary",
        "guard-missing",
        "guard-false",
    ],
)
def test_early_rejection_has_no_original_mutation(modeled, fault):
    c, options = modeled, {}
    if fault == "stop":
        c.cancellation.set()
    elif fault == "deadline":
        options["deadline_ns"] = c.clock
    elif fault == "bool-deadline":
        options["deadline_ns"] = True
    elif fault == "source":
        c.source = "f" * 64
    elif fault == "queue":
        c.setup._probe_queues[m.PREPARE]["claimed"] = False
    elif fault == "boundary":
        c.original["camera_mode_entry"]["state"] = "INCOMPLETE"
    elif fault == "guard-missing":
        options["validate_current_enrollment"] = None
    else:
        options["validate_current_enrollment"] = lambda: False
    with pytest.raises(WizardError):
        execute(c, **options)
    assert "store" not in c.events and not c.setup._probe_attempts


@pytest.mark.parametrize(
    "boundary", ["store", "read", "commit", "refresh", "original_after"]
)
def test_stop_preserves_known_records_without_adoption(modeled, boundary, monkeypatch):
    c = modeled
    owner, name = {
        "store": (c.tx, "store_evidence"),
        "read": (c.tx, "read_stage_evidence"),
        "commit": (c.tx, "commit_stage_state"),
        "refresh": (c.session, "refresh"),
        "original_after": (c.session, "read_original_source_workflow"),
    }[boundary]
    original = getattr(owner, name)

    def stop(*a, **k):
        value = original(*a, **k)
        c.cancellation.set()
        return value

    monkeypatch.setattr(owner, name, stop)
    with pytest.raises(WizardError, match="stopped or expired"):
        execute(c)
    attempt = c.setup._probe_attempts[m.PREPARE]
    assert attempt["record"] is not None and "adopt" not in c.events
    assert attempt["record"]["retention"] == (
        "M1_PUBLISHED_READBACK_PENDING"
        if boundary == "store"
        else "M1_FULL_BYTES_READ_BACK"
    )


@pytest.mark.parametrize(
    "boundary", ["store", "read", "commit", "refresh", "original_after"]
)
def test_failure_retains_uncertain_boundaries(modeled, boundary, monkeypatch):
    c = modeled
    owner, name = {
        "store": (c.tx, "store_evidence"),
        "read": (c.tx, "read_stage_evidence"),
        "commit": (c.tx, "commit_stage_state"),
        "refresh": (c.session, "refresh"),
        "original_after": (c.session, "read_original_source_workflow"),
    }[boundary]

    def fail(*a, **k):
        raise RuntimeError("MODELED storage failure")

    monkeypatch.setattr(owner, name, fail)
    with pytest.raises(RuntimeError):
        execute(c)
    attempt = c.setup._probe_attempts[m.PREPARE]
    expected = {
        "store": "M1_PUBLICATION_UNCONFIRMED",
        "read": "M1_PUBLISHED_READBACK_PENDING",
    }.get(boundary, "M1_FULL_BYTES_READ_BACK")
    assert attempt["record"]["retention"] == expected and "adopt" not in c.events


def test_review_cannot_restore_a_prior_launch_enrollment(modeled):
    c = modeled
    execute(c)
    c.events.clear()
    c.setup.launch_id = "wizard-" + "9" * 32
    with pytest.raises(WizardError, match="same preparation and current launch"):
        execute(c, m.REVIEW)
    assert "store" not in c.events
