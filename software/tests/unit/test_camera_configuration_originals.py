"""Actual M1 probe/readback/facts; setup semantic authentication is MODELED.

The labeled fixture constructs the in-process setup handoff at the explicit
semantic-authentication seam. It does not claim a full v16 history. Native facts
come from an incapable owner; real M1, plan/evidence codecs, settings derivation,
capture capacity and subsequent original revalidation run normally.
"""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import time

import pytest

from rocell.application import camera_configuration_original_scope as m
from rocell.application import camera_configuration_admission as admission
from rocell.application import camera_configuration_capacity as capacity
from rocell.application import camera_probe_original_scope as probe_scope
from rocell.application.physical_camera_activation_campaign import (
    CONFIGURATION_PLAN_SCHEMA,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows.camera_worker_client import CameraCampaignBudget
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_original_probe_service import prepare_services, WINDOWS, LEASES
from test_camera_activation_dispatch_handoff import install_owner
from test_camera_activation_service_handoff import stage_settings, SOURCE
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner


BUDGET = CameraCampaignBudget(5000, 1, 16, 16)


def make_context(tmp_path, monkeypatch, *, sealed_configuration_capture=False):
    c = prepare_services(tmp_path, monkeypatch)
    install_owner(tmp_path, monkeypatch, purpose="probe")
    c.run()
    c.service.publish_retained_observation("operation-" + "1" * 32)
    stage_settings(c.service)
    return install_modeled_configuration_setup(
        c,
        tmp_path,
        monkeypatch,
        sealed_configuration_capture=sealed_configuration_capture,
    )


def install_modeled_configuration_setup(
    c, tmp_path, monkeypatch, *, sealed_configuration_capture=False
):
    """Reuse only the explicitly labeled semantic-auth seam in public tests."""
    c.capture_plan = c.service.preview_activation_plan(
        "capture",
        c.enrollment,
        capture_budget=BUDGET,
        configuration_verification=True,
        sealed_configuration_capture=sealed_configuration_capture,
    )
    c.caps = c.service._capture_workflow._capabilities
    c.settings = c.service._capture_workflow._configuration
    monkeypatch.setattr(probe_scope, "source_fingerprint", lambda _: SOURCE)
    catalog_path = (
        Path(__file__).resolve().parents[2]
        / "config/physical_onboarding_stage_catalog.json"
    )
    catalog = catalog_path.read_bytes()
    c.modeled_workflow = dict(
        prerequisites=dict(
            reference={"MODELED": "setup semantic authentication seam"},
            document=dict(
                source_files=[
                    dict(
                        role="stage_catalog",
                        payload_utf8=catalog.decode(),
                        sha256=digest(catalog),
                    )
                ]
            ),
        )
    )
    c.setup = None

    def read(tx, **kwargs):
        # Deliberately MODELED authentication, not an import/restore mechanism
        # in production. Actual original-store checks in assert_current remain.
        now = time.monotonic_ns()
        snapshot = tx.snapshot()
        c.setup = probe_scope.VerifiedCameraProbeOriginal(
            _snapshot=snapshot,
            _workflow=canonical(c.modeled_workflow),
            _binding=canonical(c.session.descriptor()),
            _preparation=SimpleNamespace(
                sha256="1" * 64,
                to_dict=lambda: {
                    "plan": c.plan,
                    "enrollment": c.enrollment.export_snapshot(),
                },
            ),
            _review=SimpleNamespace(sha256="2" * 64),
            _workspace=tmp_path,
            _source_sha256=SOURCE,
            _launch_id=c.service.launch_id,
            _cancellation=kwargs.get("cancellation", Event()),
            _read_completed_at_ns=now,
            _deadline_ns=kwargs.get("deadline_ns", now + probe_scope.MAX_CONTEXT_NS),
            _validate_current_context=kwargs.get(
                "validate_current_context", lambda: None
            ),
            _read_provenance=probe_scope._ORIGINAL_READ,
        )
        return c.setup

    # The public/private service composition may use this same narrow seam;
    # configuration original reading and fact derivation are NOT replaced.
    monkeypatch.setattr(probe_scope, "read_camera_probe_originals", read)
    c.read_setup = read
    c.arguments = dict(
        enrollment=c.enrollment,
        capabilities=c.caps,
        configuration=c.settings,
        plan=c.capture_plan,
        request_key="MODELED-settings-original",
        expected_plan_sha256=digest(canonical(c.capture_plan)),
    )
    return c


@WINDOWS
@pytest.mark.parametrize("sealed", [False, True])
def test_real_probe_originals_derive_stable_settings_facts_and_capacity(
    tmp_path, monkeypatch, sealed
):
    c = make_context(tmp_path, monkeypatch, sealed_configuration_capture=sealed)
    with c.session._store.transaction(LEASES) as tx:
        setup = c.read_setup(tx)
        original = m.read_camera_configuration_originals(setup, tx, **c.arguments)
        owner = admission.CameraConfigurationAdmission(
            original,
            tx,
            operator_id="MODELED settings operator",
            arm_actuator_supply_disconnected=True,
            bounded_configuration_capture_consent=True,
        )
        audit = tx._audit_records
        audit_calls = []

        def observed_audit(*args, **kwargs):
            assert not args and kwargs == {"include_family": True}
            audit_calls.append(True)
            return audit(*args, **kwargs)

        monkeypatch.setattr(tx, "_audit_records", observed_audit)
        facts = owner(tx, original._request, tx.snapshot())
        assert len(audit_calls) == 1
        assert owner(tx, original._request, tx.snapshot()) is facts
        # One fresh full audit per boundary, not a cross-call cached ledger or
        # five repeated reads of the same records to compute current headroom.
        assert len(audit_calls) == 2
        docs = owner.retained_documents()
        hazard = docs["hazard_assessment"]
        assert hazard["settings"] == c.settings.to_dict()
        assert hazard["current_condition_report"]["instrument_verified"] is False
        assert hazard["capacity_at_admission"]["output_budget"]["raw_frame_bytes"] == 16
        assert all(
            row["settings_epoch"] == c.settings.settings_epoch
            for row in docs["configuration_epochs"]
        )
        from rocell.application.physical_camera_activation_campaign import (
            SEALED_CONFIGURATION_PLAN_SCHEMA,
        )

        assert owner.campaign().plan()["schema"] == (
            SEALED_CONFIGURATION_PLAN_SCHEMA if sealed else CONFIGURATION_PLAN_SCHEMA
        )
        assert hazard["schema"] == (
            admission.SEALED_HAZARD_SCHEMA if sealed else admission.HAZARD_SCHEMA
        )
        assert hazard["action_id"] == owner.campaign().registration().action_id
        assert owner.persistence(c.runtime).requires_original_admission_evidence is True
        assert hazard["physical_authority"] is hazard["hardware_qualified"] is False
        assert (
            original.summary()["probe"]["attempt_id"]
            == c.caps.to_dict()["binding"]["attempt_id"]
        )
    with pytest.raises(Exception, match="scope has ended"):
        owner(tx, original._request, setup._snapshot)


@WINDOWS
def test_capacity_observation_rechecks_late_source_identity_stop_and_stage_changes(
    tmp_path, monkeypatch
):
    c = make_context(tmp_path, monkeypatch)
    with c.session._store.transaction(LEASES) as tx:
        original = m.read_camera_configuration_originals(
            c.read_setup(tx), tx, **c.arguments
        )
        snapshot = tx.snapshot()
        disk_usage = capacity.shutil.disk_usage
        for change in ("source", "enrollment", "snapshot", "stop"):
            with monkeypatch.context() as patch:

                def changed_during_disk_read(path):
                    observed = disk_usage(path)
                    if change == "source":
                        patch.setattr(
                            probe_scope, "source_fingerprint", lambda _: "f" * 64
                        )
                    elif change == "enrollment":
                        patch.setattr(c.enrollment, "export_snapshot", lambda: {})
                    elif change == "snapshot":
                        patch.setattr(tx, "snapshot", lambda: None)
                    else:
                        original._setup._cancellation.set()
                    return observed

                patch.setattr(capacity.shutil, "disk_usage", changed_during_disk_read)
                with pytest.raises(ValueError):
                    original.observe_current_capacity(tx, original._request, snapshot)


@WINDOWS
@pytest.mark.parametrize(
    "change",
    [
        "result",
        "accounting",
        "missing-facts",
        "capabilities",
        "plan",
        "settings",
        "profile",
    ],
)
def test_original_configuration_reader_rejects_inconsistent_subjects(
    tmp_path, monkeypatch, change
):
    c = make_context(tmp_path, monkeypatch)
    with c.session._store.transaction(LEASES) as tx:
        setup = c.read_setup(tx)
        args = dict(c.arguments)
        if change in {"result", "accounting"}:
            read = tx.read_campaign_result

            def substituted(attempt):
                value = read(attempt)
                return (
                    replace(
                        value,
                        state=AttemptState.SEALED_UNCERTAIN,
                        quarantine_latched=True,
                    )
                    if change == "result"
                    else replace(value, receipt=replace(value.receipt, writes=1))
                )

            monkeypatch.setattr(tx, "read_campaign_result", substituted)
        elif change == "missing-facts":

            def absent(attempt):
                raise ValueError("MODELED missing original admission facts")

            monkeypatch.setattr(tx, "read_campaign_admission_evidence", absent)
        elif change == "capabilities":
            value = c.caps.to_dict()
            value["modes"][0]["fps_numerator"] = 8
            args["capabilities"] = m.PhysicalCameraCapabilities(canonical(value))
        elif change == "plan":
            args["expected_plan_sha256"] = "a" * 64
        elif change == "settings":
            value = c.settings.to_dict()
            value["capabilities_sha256"] = "a" * 64
            args["configuration"] = m.StagedPhysicalCameraConfiguration(
                canonical(value)
            )
        else:
            value = c.service.preview_activation_plan(
                "capture", c.enrollment, capture_budget=BUDGET
            )
            args.update(plan=value, expected_plan_sha256=digest(canonical(value)))
        with pytest.raises(ValueError):
            m.read_camera_configuration_originals(setup, tx, **args)


@WINDOWS
def test_handoff_rechecks_original_records_action_current_owner_and_lease(
    tmp_path, monkeypatch
):
    c = make_context(tmp_path, monkeypatch)
    with c.session._store.transaction(LEASES) as tx:
        original = m.read_camera_configuration_originals(
            c.read_setup(tx), tx, **c.arguments
        )
        snap, request = tx.snapshot(), original._request
        with pytest.raises(ValueError, match="REQUEST_CHANGED"):
            original.assert_current(
                tx, replace(request, action_id=m.ACTION_IDS["probe"]), snap
            )
        with pytest.raises(ValueError, match="REQUEST_CHANGED"):
            original.assert_current(tx, replace(request, request_key="other"), snap)
        with monkeypatch.context() as patch:
            read = tx._audit_records

            def changed_records(*args, **kwargs):
                records = deepcopy(read(*args, **kwargs))
                first = next(iter(records.values()))
                first["data"]["MODELED_changed"] = True
                return records

            patch.setattr(tx, "_audit_records", changed_records)
            with pytest.raises(ValueError, match="PROBE_CHANGED"):
                original.assert_current(tx, request, snap)
        with monkeypatch.context() as patch:
            patch.setattr(c.enrollment, "export_snapshot", lambda: {})
            with pytest.raises(ValueError, match="ENROLLMENT_CHANGED"):
                original.assert_current(tx, request, snap)
        original.assert_current(tx, request, snap)
