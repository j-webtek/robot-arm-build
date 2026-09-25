"""Scoped application bridge; actual NTFS/owned-process test is explicitly slow."""

from dataclasses import replace
from pathlib import Path
import os
import shutil
import threading

import pytest

from rocell.application import incapable_native_admission_campaign as module
from rocell.application.cell_commissioning_coordinator import (
    CellCommissioningCoordinator,
    RegisteredActionRequest,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    RehearsalAdmissionFacts,
    rehearsal_source_binding,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_native_camera_evidence import (
    verify_owned_native_camera_run_evidence,
)
from rocell.providers.windows.owned_native_camera_runner import INCAPABLE_CHILD_PATH

ROOT = Path(__file__).resolve().parents[3]
CELL = "wizard-rehearsal-" + "8" * 16
SESSION = "rehearsal-" + "9" * 32


def test_campaign_constructor_registration_and_plan_are_inert(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("Inert campaign attempted execution or file access")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(module, "source_fingerprint", forbidden)
        patch.setattr(module, "IncapableNativeAdmissionRunner", forbidden)
        worker = module.IncapableNativeAdmissionCampaign(
            ROOT,
            tmp_path,
            source_sha256="a" * 64,
            selected_camera=module.incapable_native_admission_identity(),
        )
        plan = worker.plan()
        plan["selected_camera"]["endpoint"] = "changed"
        assert (
            worker.plan()["selected_camera"]
            == module.incapable_native_admission_identity()
        )
        assert worker.registration().budget.maximum_opens == 0
        assert worker.registration().budget.maximum_frames == 0
        assert worker.registration().effect_class.value == "NO_DEVICE_IO"
        assert worker.evidence is None
    with pytest.raises(ValueError, match="SCOPED_RETAINED"):
        worker.run_campaign(None)
    with pytest.raises(ValueError, match="SCOPED_RETAINED"):
        worker.run_retained_campaign(None)


@pytest.mark.parametrize(
    "fault", ["real-endpoint", "wrong-domain", "extra-field", "relative-path"]
)
def test_campaign_cannot_be_repurposed_for_a_real_endpoint(tmp_path, fault):
    identity = module.incapable_native_admission_identity()
    workspace = ROOT
    if fault == "real-endpoint":
        identity["endpoint"] = "another-device"
    elif fault == "wrong-domain":
        identity["provenance"] = "WINDOWS_NATIVE_METADATA"
    elif fault == "extra-field":
        identity["physical_authority"] = True
    else:
        workspace = Path("relative")
    with pytest.raises(ValueError):
        module.IncapableNativeAdmissionCampaign(
            workspace, tmp_path, source_sha256="a" * 64, selected_camera=identity
        )


def _copy_fixed_source_closure(target: Path) -> str:
    """Isolate the complete fingerprint closure from concurrent UI development.

    Copy only registered source/config files; no runs, exports, devices or native
    binaries. Before/after fingerprints must agree; this is not fabricated source.
    """
    before = source_fingerprint(ROOT)
    relatives = [Path("software/pyproject.toml"), Path("rocell.ps1")]
    for root, suffixes in (
        (ROOT / "software/src/rocell", {".py", ".html", ".css", ".js"}),
        (ROOT / "software/config", {".json"}),
    ):
        for current, directories, names in os.walk(root, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name != "__pycache__"
            )
            relatives.extend(
                (Path(current) / name).relative_to(ROOT)
                for name in sorted(names)
                if Path(name).suffix in suffixes
            )
    for relative in relatives:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    assert (
        source_fingerprint(ROOT) == before
    ), "Source changed while copying; no nominal claim"
    assert source_fingerprint(target) == before
    return before


@pytest.mark.slow
@pytest.mark.skipif(
    os.name != "nt" or not INCAPABLE_CHILD_PATH.is_file(),
    reason="Requires real local NTFS qualification and the fixed incapable C++ child",
)
def test_actual_m1_scoped_authority_owned_child_and_full_evidence(tmp_path):
    # This is a real isolated copied source closure, not a constant injected
    # fingerprint. The fixed admission-only executable remains independently
    # pinned to its source/binary by the closed provider registration.
    workspace = tmp_path / "source-closure"
    source = _copy_fixed_source_closure(workspace)
    identity = module.incapable_native_admission_identity()
    deployed = tmp_path / "qualified-m1"
    deployed.mkdir()
    assigned = tmp_path / "assigned-campaigns"
    assigned.mkdir()
    runtime = PhysicalOnboardingM1Runtime.initialize(
        deployed,
        source_binding_sha256=rehearsal_source_binding(source),
        cell_id=CELL,
        created_at_ns=1000,
    )
    runtime.create_session(
        SESSION, created_at_ns=2000, mode="REHEARSAL", workspace_source_sha256=source
    )

    def facts(request, snapshot):
        assert source_fingerprint(workspace) == source
        return RehearsalAdmissionFacts(
            {
                "source": source,
                "hardware_incapable": True,
                "diagnostic": "ADMISSION_ONLY",
            },
            tuple({"epoch": index, "source": source} for index in range(8)),
            identity,
        )

    persistence = M1CommissioningPersistence(
        runtime, workspace_source_sha256=source, admission_facts=facts
    )
    with persistence.stage_transaction(
        SESSION,
        expected_challenge_sha256=persistence.verification(SESSION).challenge_sha256,
    ) as tx:
        tx.commit_stage_state(
            module.STAGE,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=2001,
            detail_code="REHEARSAL_EVIDENCE_PENDING",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    worker = module.IncapableNativeAdmissionCampaign(
        workspace, assigned, source_sha256=source, selected_camera=identity
    )
    registration = worker.registration()
    leases = (LeaseSpec(LeaseLevel.CELL, CELL), LeaseSpec(LeaseLevel.SESSION, SESSION))
    request = RegisteredActionRequest(
        CELL, SESSION, registration.action_id, "one-scoped-admission", "a" * 64
    )
    with persistence.transaction(leases) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    coordinator = CellCommissioningCoordinator(
        persistence=persistence,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        scoped_campaign_actions=(registration.action_id,),
    )
    permit = coordinator.prepare(request)
    assert worker.evidence is None
    result = coordinator.execute(permit, cancellation=threading.Event())
    detail = None if worker.evidence is None else worker.evidence.to_dict()
    assert result.state is AttemptState.SEALED_KNOWN, (result, detail)
    assert result.physical_authority == "NONE"
    assert worker.evidence is not None
    assert worker.evidence.safe_summary()["status"] == "SUCCEEDED_ADMISSION_ONLY"
    assert worker.evidence.safe_summary()["process_cleanup_confirmed"] is True
    assert worker.evidence.to_dict()["process"]["created"] is True
    assert worker.evidence.to_dict()["native_validated"] is False
    with persistence.transaction(leases) as tx:
        retained = tx.read_campaign_evidence(permit.attempt_id)
        assert len(retained) == 1 and retained[0].payload == worker.evidence.payload
        restored = verify_owned_native_camera_run_evidence(
            worker.evidence.to_dict(),
            expected_preparation_sha256=worker.evidence.to_dict()["preparation_sha256"],
            expected_evidence_sha256=retained[0].payload_sha256,
        )
        assert restored.safe_summary()["hardware_qualified"] is False
        assert tx.snapshot().state_for(module.STAGE) is V2StageState.WAITING_OPERATOR
    actual = runtime.verify(SESSION)
    assert not actual.unresolved_attempt_ids and not actual.uncertain_attempt_ids
    assert not actual.active_lease_owners
    # Same exact request returns the retained result; the one-use worker cannot
    # replay, and no stage transition or second attempt is authorized.
    assert coordinator.execute(permit) is result
    assert source_fingerprint(workspace) == source
