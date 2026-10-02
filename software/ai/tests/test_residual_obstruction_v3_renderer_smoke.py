from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "software" / "ai"
sys.path.insert(0, str(ROOT / "software" / "integrations" / "isaac_sim"))

from residual_obstruction_v3_isaac_probe import (  # noqa: E402
    canonical,
    dynamic_root,
    load_fixture,
    sha256_bytes,
)


FIXTURE = AI_ROOT / "sim" / "evidence" / "residual_obstruction_successor_v3.json"
REPORT = AI_ROOT / "eval" / "residual_obstruction_v3_renderer_smoke_v1.json"
SCHEMA = AI_ROOT / "schemas" / "residual_obstruction_v3_renderer_smoke_v1.schema.json"


def test_fixture_loader_binds_frozen_v3_contract():
    fixture, payload = load_fixture(FIXTURE)
    assert fixture["bundle_sha256"] == "7e861cb17b5f4717d732989d1ddaaeb4ab3e3e4e0ae1d92dd19de35afa397fed"
    assert sha256_bytes(payload) == "56b04e0bcc35c26eea2848a0244827d7285e5056667f17deae628c0986921cbd"


def test_fixture_loader_rejects_tampering(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["hardware_writes"] = 1
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical hash mismatch"):
        load_fixture(path)


def test_dynamic_prims_are_namespaced_per_scene():
    assert dynamic_root(0) == "/World/SceneDynamic00"
    assert dynamic_root(11) == "/World/SceneDynamic11"
    with pytest.raises(ValueError, match="nonnegative"):
        dynamic_root(-1)


def test_retained_smoke_report_is_bound_and_incomplete():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)
    core = {key: value for key, value in report.items() if key != "report_sha256"}
    assert report["report_sha256"] == sha256_bytes(canonical(core))
    assert report["successful_smoke"]["unique_rgb_count"] == 192
    assert report["campaign_complete"] is False
    assert report["training_started"] is False
    assert report["evaluation_opened"] is False
    assert report["hardware_writes"] == 0
    assert report["physical_movements"] == 0
    assert report["physical_authority"] is False
