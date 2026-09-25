"""Pre-refactor v1 bytes, with deterministic explicitly MODELED observations.

The old module fingerprint is e4fb88ca77c7e6defb40411b85d241bc46571731336d22e9fe91cacce9cd8d13.
No production/incapable child, CIM lookup, device or original-store action
runs. Runtime paths are fixed labels only, not files opened by these tests.
"""

from itertools import count
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import UUID

import pytest

from rocell.application import physical_camera_usb_qualification as codec
from rocell.application import wizard_device_selection as generic_owner
from rocell.application import wizard_native_camera_enrollment as native_owner
from rocell.providers.windows import host_boot_observation as boot_codec
from rocell.providers.windows import owned_usb_identity_evidence as owned
from rocell.providers.windows import usb_identity_registration as registration
from test_physical_camera_usb_qualification import (
    prerequisites,
    workspace,
    failed_series_fixture,
    plan_fixture,
    reference,
    subjects,
    usb_native_enrollment,
)
from test_owned_usb_identity_runner import usb_fixture, ENDPOINT, INSTANCE
from test_host_boot_observation import (
    request as boot_request,
    modeled_observation,
    WALL,
)
from test_arrival_usb_phase_ntfs_nominal import modeled_observed_evidence


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Golden originals use one fixed canonical Windows runtime path",
)
FIXED_WORKSPACE = Path("C:/MODELED/usb-v1-compatibility")
MONOTONIC = 1_000_000_000_000
GOLDEN = {
    "held_series": {
        "plan": {
            "bytes": 3365,
            "sha256": "41a3c6f3415971892450f263d6598ae0e811789892f4ebcc8bee6edb403d5d10",
        },
        "series": {
            "bytes": 2691,
            "sha256": "0d9fe3cf10f772e51b248ab9d9ffc73498a275aef6d654e8fe60795383db05f5",
        },
        "assessment": {
            "bytes": 19679,
            "sha256": "619d27f8df13f3a0257cf80d3255dcd571e4bb13c679ab55e4d313d5e239105b",
        },
        "review": {
            "bytes": 985,
            "sha256": "74e05b999312b21c334635493251bc773649f269310893400091332a8930ea98",
        },
        "BASELINE": {
            "bytes": 5574,
            "sha256": "2d89622fd24cd4e023c6720d7ec9103383cfe7999be6abffd0654bc5509841e6",
        },
        "RECONNECT_ABSENCE": {
            "bytes": 4129,
            "sha256": "098aa8f3531ac62ab64d3057d55435a9d1c7993428ea4f17bb6e04a4e20da09e",
        },
        "AFTER_RECONNECT": {
            "bytes": 5643,
            "sha256": "ca0f63875212cdec61d711c68c599b6835ca65343e1bc7b1e94d56079c1474ea",
        },
        "AFTER_REBOOT": {
            "bytes": 5640,
            "sha256": "699adb771f874a787e2ec517063b9cea5f3f3bb0e2b0bfbf5d382568a07132e9",
        },
    },
    "physical_shaped_baseline_ex2": {
        "plan": {
            "bytes": 3365,
            "sha256": "41a3c6f3415971892450f263d6598ae0e811789892f4ebcc8bee6edb403d5d10",
        },
        "BASELINE": {
            "bytes": 6360,
            "sha256": "e40b7e62316aeec9f3d4fdcd7e47c504e3cac0f9a28ce3b9de6e7d2a8adeef52",
        },
    },
    "physical_shaped_baseline_ex3": {
        "plan": {
            "bytes": 3365,
            "sha256": "41a3c6f3415971892450f263d6598ae0e811789892f4ebcc8bee6edb403d5d10",
        },
        "BASELINE": {
            "bytes": 6360,
            "sha256": "32ba9700b60bf56d58d2f3bae75212fd11b77aa35a60d744bc0fafde97c26a68",
        },
    },
}


@pytest.fixture
def deterministic(prerequisites, monkeypatch):
    # Entropy is fixture input, never production acceptance logic. Independent
    # generic/native token streams do not depend on machine or checkout paths.
    generic_ids, native_ids = count(1), count(1001)
    monkeypatch.setattr(generic_owner, "uuid4", lambda: UUID(int=next(generic_ids)))
    monkeypatch.setattr(native_owner, "uuid4", lambda: UUID(int=next(native_ids)))
    monkeypatch.setattr(time, "monotonic_ns", lambda: MONOTONIC)
    monkeypatch.setattr(time, "time_ns", lambda: WALL + 6000)
    candidate = registration.incapable_usb_identity_runtime_candidate
    monkeypatch.setattr(
        registration,
        "incapable_usb_identity_runtime_candidate",
        lambda _workspace, **kwargs: candidate(FIXED_WORKSPACE, **kwargs),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Compatibility fixture attempted process or host acquisition")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(boot_codec, "_native_owner", forbidden)
    monkeypatch.setattr(boot_codec, "_system_powershell", forbidden)
    from rocell.providers.windows.owned_usb_identity_runner import (
        OwnedUsbIdentityRunner,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

    monkeypatch.setattr(OwnedUsbIdentityRunner, "run", forbidden)
    for method in (
        "enumerate_metadata",
        "resolve_identity_metadata",
        "probe",
        "capture",
    ):
        monkeypatch.setattr(WindowsCameraWorkerClient, method, forbidden)
    return prerequisites


def fingerprints(values):
    return {
        name: {"bytes": len(value.payload), "sha256": value.sha256}
        for name, value in values.items()
    }


def assert_golden(name, values):
    actual = fingerprints(values)
    assert actual == GOLDEN.get(name), json.dumps({name: actual}, indent=2)


def test_v1_held_four_phase_series_exact_pre_refactor_bytes(deterministic):
    plan, series, assessment, phases, originals = failed_series_fixture(deterministic)
    review = codec.review_usb_qualification_series(
        plan,
        series,
        assessment,
        phases=phases,
        phase_sources=originals,
        received=subjects(deterministic),
        reviewer_id="golden-reviewer",
        review_launch_id="wizard-golden-review",
        reviewed_at_utc_ns=WALL + 1_000_000,
        decision="ACKNOWLEDGE_EXACT",
    )
    assert all(p.to_dict()["status"] == "HELD" for p in phases)
    assert assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "BLOCKED"
    assert_golden(
        "held_series",
        dict(
            plan=plan,
            series=series,
            assessment=assessment,
            review=review,
            **{p.to_dict()["phase"]: p for p in phases},
        ),
    )


@pytest.mark.parametrize("ex_speed", [2, 3])
def test_v1_physical_shaped_modeled_baseline_exact_pre_refactor_bytes(
    deterministic, ex_speed
):
    plan = plan_fixture(deterministic)[0]
    binding, launch = plan.to_dict()["binding"], "wizard-golden-physical-model"
    native = usb_native_enrollment(binding["source_sha256"], launch, suffix="golden")
    _, selection, _ = codec._native(
        plan, {"launch_session_id": launch}, codec.canonical(native)
    )
    case = usb_fixture(
        FIXED_WORKSPACE,
        incapable=False,
        source_sha256=binding["source_sha256"],
        selection_sha256=selection.sha256,
        native_identity_sha256=native["view"]["identity"]["identity_sha256"],
        endpoint=ENDPOINT,
        instance=INSTANCE,
        cell_id=binding["cell_id"],
        session_id=binding["session_id"],
        header_sha256=binding["header_sha256"],
        launch_session_id=launch,
        operation_sha256=codec.digest(b"golden-physical-model"),
        attempt_id="attempt-golden-physical-model",
    )
    run = modeled_observed_evidence(
        case.prepared,
        deadline=MONOTONIC + 25_000_000_000,
        started=MONOTONIC,
        utc=WALL + 2000,
        checks=[
            dict(
                boundary=name, started_ns=MONOTONIC, finished_ns=MONOTONIC, passed=True
            )
            for name in owned.BOUNDARIES
        ],
    )
    if ex_speed == 2:
        # Change the retained EX bytes and every matching raw trace call, then
        # re-parse. Do not relabel only the compact value or fabricate Mbps.
        raw = run.to_dict()
        stream = owned.stream_bytes(raw["stdout"], owned.MAX_EVIDENCE_BYTES)
        packet = json.loads(stream[raw["ready_length"] :])
        observed = packet["native_receipt"]

        def raw_ex2(value):
            result = bytearray.fromhex(value)
            result[23] = 2
            return result.hex()

        observed["link"].update(
            ex_speed=2, ex_raw_hex=raw_ex2(observed["link"]["ex_raw_hex"])
        )
        for call in observed["calls"]:
            if call["operation"] == "CONNECTION_EX":
                call["returned_raw_hex"] = raw_ex2(call["returned_raw_hex"])
        raw["stdout"] = owned.stream_record(
            stream[: raw["ready_length"]] + codec.canonical(packet), complete=True
        )
        run = owned.OwnedUsbIdentityRunEvidence(codec.canonical(raw))
    request = boot_request(
        source_sha256=binding["source_sha256"],
        session_id=binding["session_id"],
        trial_id=binding["trial_id"],
        phase="BASELINE",
        launch_session_id=launch,
        operation_id="golden-physical-model",
    )
    boot = modeled_observation(req=request, wall=WALL + 7000)
    # A physical-shaped pure fixture is not an actual host/CIM observation.
    document = boot.to_dict()
    document["origin"] = "WINDOWS_LOCAL_CIM"
    boot = boot_codec.HostBootObservation(codec.canonical(document))
    originals = dict(
        native_enrollment=codec.canonical(native),
        owned_usb_run=run.payload,
        host_boot=boot.payload,
    )
    phase = codec.build_usb_qualification_phase(
        plan,
        phase="BASELINE",
        predecessor=None,
        context=dict(
            launch_session_id=launch,
            operation_id="golden-physical-model",
            operator_id="golden-operator",
            started_at_utc_ns=WALL + 1000,
            finished_at_utc_ns=WALL + 10000,
        ),
        sources=originals,
        references={
            name: reference(raw, "golden-" + name) for name, raw in originals.items()
        },
    )
    data = phase.to_dict()
    assert data["status"] == "OBSERVATIONS_RETAINED"
    assert data["execution"]["usb3_operating"] is True
    assert data["execution"]["ex_speed"] == ex_speed
    assert data["values"]["vid"]["value"] == "1234"
    assert data["values"]["pid"]["value"] == "5678"
    assert data["values"]["descriptor_serial"]["value"] == "MODELED-ONLY"
    assert_golden(
        "physical_shaped_baseline_ex" + str(ex_speed), dict(plan=plan, BASELINE=phase)
    )
