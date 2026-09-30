from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import rocell.application.typing_profiled_shadow_service_campaign_v1 as campaign

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = Draft202012Validator(json.loads((ROOT / "software/ai/schemas/typing_profiled_shadow_service_campaign_v1.schema.json").read_text()))


def _environment():
    core = {"schema": "rocell.operational_benchmark_environment.v1", "captured_at_utc": "2026-09-30T03:00:00Z", "repository_commit": "a" * 40, "repository_dirty": False, "python_version": "3.10.10", "python_implementation": "CPython", "platform_system": "Windows", "platform_release": "10", "platform_machine": "AMD64", "logical_cpu_count": 24, "perf_counter_resolution_ns": 100, "benchmark_entrypoint": "software/scripts/run_typing_profiled_shadow_service_campaign_v1.py"}
    core["environment_sha256"] = campaign._sha(core); return core


def _cases():
    result = []
    for index, name in enumerate(campaign.CASES):
        enabled = index == 0
        counters = {"lookups": 24 if enabled else 0, "hits": 1 if enabled else 0, "misses": 23 if enabled else 0, "stores": 23 if enabled else 0, "capacity_skips": 0}
        result.append({"case": name, "status": "SHADOW_COMPLETED", "profile_decision": campaign.EXPECTED_DECISIONS[index], "exact_reuse_enabled": enabled, "cache_counters": counters})
    return result


def test_campaign_round_trip_and_schema():
    value = campaign.build_typing_profiled_shadow_service_campaign_v1(
        _cases(), campaign_id="campaign", environment=_environment(),
        reference_receipts_equivalent=True)
    VALIDATOR.validate(value)
    assert campaign.parse_typing_profiled_shadow_service_campaign_v1(value) == value
    assert value["physical_authority"] is False


def test_campaign_rejects_cache_use_on_fallback_and_tampering():
    cases = _cases(); cases[1]["cache_counters"]["lookups"] = 1
    with pytest.raises(campaign.TypingProfiledShadowServiceCampaignV1Error, match="touched cache"):
        campaign.build_typing_profiled_shadow_service_campaign_v1(
            cases, campaign_id="campaign", environment=_environment(),
            reference_receipts_equivalent=True)
    value = campaign.build_typing_profiled_shadow_service_campaign_v1(
        _cases(), campaign_id="campaign", environment=_environment(),
        reference_receipts_equivalent=True)
    changed = copy.deepcopy(value); changed["campaign_sha256"] = "f" * 64
    with pytest.raises(campaign.TypingProfiledShadowServiceCampaignV1Error, match="hash"):
        campaign.parse_typing_profiled_shadow_service_campaign_v1(changed)
