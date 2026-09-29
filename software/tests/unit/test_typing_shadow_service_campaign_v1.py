from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "software/scripts"))

import run_typing_shadow_service_campaign_v1 as runner  # noqa: E402
import rocell.application.typing_shadow_service_campaign_v1 as campaign  # noqa: E402


VALIDATOR = Draft202012Validator(json.loads((
    ROOT / "software/ai/schemas/typing_shadow_service_campaign_v1.schema.json"
).read_text(encoding="utf-8")))


def _environment() -> dict:
    core = {
        "schema": "rocell.operational_benchmark_environment.v1",
        "captured_at_utc": "2026-09-29T23:55:00Z",
        "repository_commit": "a" * 40,
        "repository_dirty": False,
        "python_version": "3.10.10",
        "python_implementation": "CPython",
        "platform_system": "Windows",
        "platform_release": "10",
        "platform_machine": "AMD64",
        "logical_cpu_count": 24,
        "perf_counter_resolution_ns": 100,
        "benchmark_entrypoint": (
            "software/scripts/run_typing_shadow_service_campaign_v1.py"
        ),
    }
    from rocell.application.operational_latency_reference_v1 import _sha
    return {**core, "environment_sha256": _sha(core)}


@pytest.fixture(scope="module")
def report() -> dict:
    return campaign.build_typing_shadow_service_campaign_v1(
        runner._campaign_cases(),
        campaign_id="typing-shadow-service-campaign-fixture",
        environment=_environment(),
    )


def _rehash(report: dict) -> None:
    unsigned = {
        key: value for key, value in report.items() if key != "campaign_sha256"
    }
    report["campaign_sha256"] = campaign._sha(unsigned)


def test_service_campaign_is_schema_valid_complete_and_zero_authority(report):
    assert list(VALIDATOR.iter_errors(report)) == []
    assert dict(campaign.parse_typing_shadow_service_campaign_v1(report)) == report
    assert [item["case"] for item in report["cases"]] == list(campaign.CASES)
    assert report["all_expected_outcomes"] is True
    assert report["decision_hashes_unchanged"] is True
    assert report["diagnostics_used_for_admission"] is False
    assert report["controller_opened"] is False
    assert report["transport_opened"] is False
    assert report["controller_commands"] == []
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert report["physical_authority"] is False


def test_service_campaign_covers_bounds_lifecycle_failure_and_race(report):
    indexed = {item["case"]: item for item in report["cases"]}
    assert indexed["FIFO_COMPLETION"]["owner_runs"] == 1
    assert indexed["CANCEL_BEFORE_ADMISSION"]["owner_runs"] == 0
    assert indexed["RELOAD_STALE_REJECTION"]["observed_outcome"] == (
        "STALE_GENERATION_REJECTED"
    )
    assert indexed["RESTART_STALE_REJECTION"]["observed_outcome"] == (
        "STALE_GENERATION_REJECTED"
    )
    assert indexed["QUEUE_BOUND_REJECTION"]["after_service_snapshot"][
        "maximum_queued"
    ] == 1
    assert indexed["EXPLICIT_INVALIDATION"]["after_service_snapshot"][
        "invalidated_queued"
    ] == 1
    assert indexed["UNEXPECTED_SHADOW_FAILURE"]["after_service_snapshot"][
        "shadow_rejected"
    ] == 1
    assert indexed["ADMISSION_RELOAD_SERIALIZATION"][
        "transition_waited"
    ] is True


@pytest.mark.parametrize("mutation,match", (
    ("order", "case order"),
    ("outcome", "outcome differs"),
    ("receipt", "service receipt is invalid"),
    ("snapshot", "snapshot outcome differs"),
    ("decision", "decision hashes differ"),
    ("authority", "authority"),
))
def test_rehashed_service_campaign_mutations_fail_closed(
    report: dict, mutation: str, match: str,
):
    changed = copy.deepcopy(report)
    if mutation == "order":
        changed["cases"][0], changed["cases"][1] = (
            changed["cases"][1], changed["cases"][0]
        )
    elif mutation == "outcome":
        changed["cases"][1]["owner_runs"] = 1
    elif mutation == "receipt":
        changed["cases"][1]["service_receipt"]["status"] = "SHADOW_REJECTED"
        from rocell.application.typing_shadow_service_v1 import _sha
        receipt = changed["cases"][1]["service_receipt"]
        core = {
            key: value for key, value in receipt.items()
            if key != "service_receipt_sha256"
        }
        receipt["service_receipt_sha256"] = _sha(core)
    elif mutation == "snapshot":
        snapshot = changed["cases"][1]["after_service_snapshot"]
        snapshot["canceled"] = 0
        snapshot["completed"] = 1
        from rocell.application.typing_shadow_service_v1 import _sha
        core = {
            key: value for key, value in snapshot.items()
            if key != "service_snapshot_sha256"
        }
        snapshot["service_snapshot_sha256"] = _sha(core)
    elif mutation == "decision":
        changed["cases"][-1]["shadow_receipt_sha256"] = "f" * 64
        receipt = changed["cases"][-1]["service_receipt"]
        receipt["shadow_receipt_sha256"] = "f" * 64
        from rocell.application.typing_shadow_service_v1 import _sha
        core = {
            key: value for key, value in receipt.items()
            if key != "service_receipt_sha256"
        }
        receipt["service_receipt_sha256"] = _sha(core)
    else:
        changed["physical_authority"] = True
    _rehash(changed)
    with pytest.raises(campaign.TypingShadowServiceCampaignV1Error, match=match):
        campaign.parse_typing_shadow_service_campaign_v1(changed)
