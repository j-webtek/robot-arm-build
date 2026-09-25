"""Fault boundaries of the actual entry function over explicitly MODELED owners.

Original authentication and storage callbacks are modeled here, not qualified.
The real entry codec, source/context guards and retention ordering execute.
The separate public composition test exercises the complete original readers.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import physical_camera_mode_entry_service as m
from rocell.application import physical_camera_session as session_impl
from rocell.application.physical_camera_mode_entry import CameraModeEntry
from rocell.application.wizard_actions import WizardError
from test_camera_mode_entry_contract import binding


@pytest.fixture
def modeled(binding, monkeypatch):
    events, data = [], {}
    clock, source = [100_000_000_000], [binding["source_sha256"]]
    cancellation = Event()
    original = dict(
        schema=m.SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
        session_header_sha256=binding["header_sha256"],
        configuration_epochs={},
        usb_qualification_complete=dict(
            state="REVIEWED_PASS",
            series={},
            assessment={},
            review={},
            events=[{}, {}, {}],
        ),
    )
    bound = dict(
        session_id=binding["session_id"],
        cell_id=binding["cell_id"],
        launch_id=binding["origin_launch_id"],
    )
    setup = SimpleNamespace(
        source_sha256=source[0],
        workspace=Path("MODELED_NO_FILES"),
        launch_id=binding["entry_launch_id"],
        _mode_entry_queue=dict(claimed=True),
        _mode_entry_attempt=None,
        original_source_workflow=lambda: deepcopy(original),
        _adopt_source_workflow=lambda value: events.append("adopt"),
    )
    reference = SimpleNamespace(to_dict=lambda: dict(evidence_id="MODELED_REFERENCE"))
    tx = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="a" * 64))
    )

    def store(payload, **kwargs):
        events.append("store")
        data["entry"] = CameraModeEntry(payload)
        return reference

    def read(ref):
        events.append("read")
        assert ref is reference
        return data["entry"].payload

    def commit(*args, **kwargs):
        events.append("commit")
        event = dict(meaning="MODELED COMMIT ACKNOWLEDGMENT")
        return SimpleNamespace(
            committed_events=[SimpleNamespace(to_dict=lambda: event)]
        )

    tx.store_camera_mode_entry, tx.read_stage_evidence, tx.commit_stage_state = (
        store,
        read,
        commit,
    )

    @contextmanager
    def scope(**kwargs):
        events.append("lease")
        yield tx
        events.append("lease_exit")

    def original_after(**kwargs):
        events.append("original_after")
        assert kwargs["deadline_ns"] == clock[0] + m.TIMEOUT_NS
        return dict(
            camera_mode_entry=dict(
                state="ENTERED", entry=dict(document=data["entry"].to_dict())
            )
        )

    session = SimpleNamespace(
        descriptor=lambda: deepcopy(bound),
        view=lambda: dict(
            verification=dict(
                effects_allowed_by_m1_storage=True, challenge_sha256="c" * 64
            )
        ),
        stage_transaction=scope,
        refresh=lambda **kwargs: events.append("refresh"),
        read_original_source_workflow=original_after,
    )
    setup.session = session

    def before(*args, **kwargs):
        events.append("original_before")
        return None, deepcopy(original)

    monkeypatch.setattr(session_impl, "_read_original_evidence_under_lease", before)
    monkeypatch.setattr(m, "camera_mode_entry_binding", lambda *a, **k: dict(binding))
    monkeypatch.setattr(m, "source_fingerprint", lambda _: source[0])
    monkeypatch.setattr(m, "monotonic_ns", lambda: clock[0])
    monkeypatch.setattr(m, "time_ns", lambda: 200_000_000_000)
    return SimpleNamespace(
        setup=setup,
        session=session,
        tx=tx,
        events=events,
        data=data,
        clock=clock,
        source=source,
        cancellation=cancellation,
        original=original,
        bound=bound,
    )


def execute(case, *, deadline=None):
    return m.enter_camera_mode(
        case.setup,
        operator_id="MODELED-operator",
        cancellation=case.cancellation,
        progress=lambda _: None,
        deadline_ns=case.clock[0] + m.TIMEOUT_NS if deadline is None else deadline,
    )


def test_exact_order_and_known_retention_without_publication(modeled):
    c = modeled
    result = execute(c)
    assert result["state"] == "ENTERED"
    assert c.events == [
        "lease",
        "original_before",
        "store",
        "read",
        "commit",
        "lease_exit",
        "refresh",
        "original_after",
        "adopt",
    ]
    assert (
        c.setup._mode_entry_attempt["record"]["retention"] == "M1_FULL_BYTES_READ_BACK"
    )
    assert len(c.setup._mode_entry_attempt["events"]) == 1
    assert not hasattr(c.setup, "_publication")  # Arrival/Setup own publication.


@pytest.mark.parametrize(
    "fault",
    ["cancel", "deadline", "boolean_deadline", "source", "queue", "predecessor"],
)
def test_early_failures_make_no_original_mutation(modeled, monkeypatch, fault):
    c = modeled
    deadline = None
    if fault == "cancel":
        c.cancellation.set()
    elif fault == "deadline":
        deadline = c.clock[0]
    elif fault == "boolean_deadline":
        deadline = True
    elif fault == "source":
        c.source[0] = "f" * 64
    elif fault == "queue":
        c.setup._mode_entry_queue = dict(claimed=False)
    else:
        monkeypatch.setattr(
            session_impl,
            "_read_original_evidence_under_lease",
            lambda *a, **k: (None, {**c.original, "changed": True}),
        )
    with pytest.raises(WizardError):
        execute(c, deadline=deadline)
    assert "store" not in c.events and c.setup._mode_entry_attempt is None


@pytest.mark.parametrize(
    "boundary", ["store", "read", "commit", "refresh", "original_after"]
)
def test_stop_keeps_each_acknowledged_boundary_without_adopting(modeled, boundary):
    c = modeled
    owner, name = {
        "store": (c.tx, "store_camera_mode_entry"),
        "read": (c.tx, "read_stage_evidence"),
        "commit": (c.tx, "commit_stage_state"),
        "refresh": (c.session, "refresh"),
        "original_after": (c.session, "read_original_source_workflow"),
    }[boundary]
    original = getattr(owner, name)

    def stop(*args, **kwargs):
        value = original(*args, **kwargs)
        c.cancellation.set()
        return value

    setattr(owner, name, stop)
    with pytest.raises(WizardError) as caught:
        execute(c)
    assert caught.value.code == "CAMERA_MODE_INTERRUPTED"
    assert "adopt" not in c.events
    record = c.setup._mode_entry_attempt["record"]
    assert record["reference"] is not None
    assert record["retention"] == (
        "M1_PUBLISHED_READBACK_PENDING"
        if boundary == "store"
        else "M1_FULL_BYTES_READ_BACK"
    )
    assert len(c.setup._mode_entry_attempt["events"]) == int(
        boundary in {"commit", "refresh", "original_after"}
    )


def test_exact_readback_mismatch_cannot_commit(modeled):
    c = modeled
    c.tx.read_stage_evidence = lambda ref: b"changed"
    with pytest.raises(WizardError) as caught:
        execute(c)
    assert caught.value.code == "CAMERA_MODE_READBACK_CHANGED"
    assert "commit" not in c.events and "adopt" not in c.events
    assert (
        c.setup._mode_entry_attempt["record"]["retention"]
        == "M1_PUBLISHED_READBACK_PENDING"
    )


@pytest.mark.parametrize("published", [False, True])
def test_failed_store_acknowledgment_keeps_publication_uncertain(modeled, published):
    c = modeled
    original = c.tx.store_camera_mode_entry

    def failed(*args, **kwargs):
        if published:
            original(*args, **kwargs)
        raise RuntimeError("MODELED storage acknowledgment lost")

    c.tx.store_camera_mode_entry = failed
    with pytest.raises(RuntimeError, match="acknowledgment lost"):
        execute(c)
    record = c.setup._mode_entry_attempt["record"]
    assert record["retention"] == "M1_PUBLICATION_UNCONFIRMED"
    assert record["reference"] is None and record["document"]
    assert "commit" not in c.events and "adopt" not in c.events


@pytest.mark.parametrize("fault", ["session", "binding", "source"])
def test_changed_context_after_retention_cannot_advance(modeled, fault):
    c = modeled
    original = c.tx.store_camera_mode_entry

    def change(*args, **kwargs):
        result = original(*args, **kwargs)
        if fault == "session":
            c.setup.session = object()
        elif fault == "binding":
            c.bound["session_id"] = "changed"
        else:
            c.source[0] = "f" * 64
        return result

    c.tx.store_camera_mode_entry = change
    with pytest.raises(WizardError):
        execute(c)
    assert "read" not in c.events and "commit" not in c.events
