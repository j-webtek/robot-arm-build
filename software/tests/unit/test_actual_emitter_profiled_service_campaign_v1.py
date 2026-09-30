from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import rocell.application.actual_emitter_profiled_service_campaign_v1 as campaign

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = Draft202012Validator(json.loads((ROOT / "software/ai/schemas/actual_emitter_profiled_service_campaign_v1.schema.json").read_text()))


def _environment():
    core = {"schema": "rocell.operational_benchmark_environment.v1", "captured_at_utc": "2026-09-30T04:00:00Z", "repository_commit": "a" * 40, "repository_dirty": False, "python_version": "3.10.10", "python_implementation": "CPython", "platform_system": "Windows", "platform_release": "10", "platform_machine": "AMD64", "logical_cpu_count": 24, "perf_counter_resolution_ns": 100, "benchmark_entrypoint": "software/scripts/run_actual_emitter_profiled_service_campaign_v1.py"}
    core["environment_sha256"] = campaign._sha(core); return core


def _cases():
    result = []
    for index, name in enumerate(campaign.CASES):
        if index == 0: counters = {"lookups": 47, "hits": 7, "misses": 40, "stores": 40, "capacity_skips": 0}
        elif index == 1: counters = {"lookups": 47, "hits": 47, "misses": 0, "stores": 0, "capacity_skips": 0}
        else: counters = {"lookups": 0, "hits": 0, "misses": 0, "stores": 0, "capacity_skips": 0}
        result.append({"case": name, "status": campaign.EXPECTED_STATUS[index], "profile_decision": campaign.EXPECTED_DECISION[index], "duration_ns": 100 + index, "payload_sha256": f"{index + 1:x}" * 64, "cache_delta": counters})
    return result


def test_campaign_round_trip_schema_and_zero_authority():
    value = campaign.build_actual_emitter_profiled_service_campaign_v1(
        _cases(), campaign_id="campaign", environment=_environment(),
        ordered_targets=("R", "O", "B", "O", "T"))
    VALIDATOR.validate(value)
    assert campaign.parse_actual_emitter_profiled_service_campaign_v1(value) == value
    assert value["actual_shared_emitter_used"] is True
    assert value["timing_used_for_admission"] is value["physical_authority"] is False


def test_campaign_rejects_warm_miss_fallback_cache_and_hash_changes():
    cases = _cases(); cases[1]["cache_delta"]["misses"] = 1
    with pytest.raises(campaign.ActualEmitterProfiledServiceCampaignV1Error, match="warm"):
        campaign.build_actual_emitter_profiled_service_campaign_v1(
            cases, campaign_id="campaign", environment=_environment(),
            ordered_targets=("R", "O", "B", "O", "T"))
    cases = _cases(); cases[2]["cache_delta"]["lookups"] = 1
    with pytest.raises(campaign.ActualEmitterProfiledServiceCampaignV1Error, match="touched cache"):
        campaign.build_actual_emitter_profiled_service_campaign_v1(
            cases, campaign_id="campaign", environment=_environment(),
            ordered_targets=("R", "O", "B", "O", "T"))
    value = campaign.build_actual_emitter_profiled_service_campaign_v1(
        _cases(), campaign_id="campaign", environment=_environment(),
        ordered_targets=("R", "O", "B", "O", "T"))
    changed = copy.deepcopy(value); changed["campaign_sha256"] = "f" * 64
    with pytest.raises(campaign.ActualEmitterProfiledServiceCampaignV1Error, match="hash"):
        campaign.parse_actual_emitter_profiled_service_campaign_v1(changed)
