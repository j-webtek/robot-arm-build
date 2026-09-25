"""Physical-shaped wire fixtures, never a live hardware dispatch."""

from copy import deepcopy
import hashlib
from threading import Event

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.providers.windows.powered_feedback_native_wire import validate_result
from rocell.providers.windows.powered_telemetry_observation import observe_rehearsal
from rocell.providers.windows.nonpurging_serial_api import IncapableWin32SerialApi, IncapableWin32Scenario
from test_powered_telemetry_observation import telemetry_binding
from test_powered_feedback_observation import REPLY
from test_powered_feedback_native_wire import envelope
from test_wizard_native_arm_integration import modeled_physical_snapshot


@pytest.fixture(scope="module")
def captured():
    return observe_rehearsal(telemetry_binding(),
        IncapableWin32SerialApi(IncapableWin32Scenario(startup_bytes=REPLY)), Event())


def result(captured):
    request = envelope(telemetry=True)
    obs = deepcopy(captured)
    # Translate memory-clock durations into this synthetic envelope's epoch.
    offset = obs["started_monotonic_ns"] - 2_000_000_000
    for name in ("started_monotonic_ns", "acquisition_started_monotonic_ns", "observation_finished_monotonic_ns", "finished_monotonic_ns"):
        obs[name] -= offset
    for row in obs["read_windows"]:
        row[2] -= offset
        row[3] -= offset
    obs["origin"] = "PHYSICAL_OBSERVATION"
    obs["request_sha256"] = request["operation_sha256"]
    obs["lifecycle"]["composition"] = "WINDOWS_POWERED_FEEDBACK_ENGINEERING"
    return request, {
        "schema": "rocell.owned_powered_feedback_native_result.v1",
        "attempt_id": request["attempt_id"], "request_sha256": request["request_sha256"],
        "physical_authority": False, "connected": False,
        "child_result": {"schema": "rocell.powered_feedback_native_child_result.v1",
            "claim_sha256": "e"*64, "fresh_snapshot": modeled_physical_snapshot("nominal"),
            "observation": obs, "physical_authority": False, "connected": False},
    }


def test_physical_shaped_telemetry_result_reconstructs(captured):
    request, value = result(captured)
    validated = validate_result(value, wire=request)
    assert validated["capture"]["pose_sample_count"] == 1
    assert validated["capture"]["query_response_verified"] is False


@pytest.mark.parametrize("change", ["pose", "count", "freshness", "raw", "write", "cleanup", "early", "query-schema", "window-gap", "window-time", "missing-window"])
def test_forged_interpretation_or_lifecycle_rejected(captured, change):
    request, value = result(captured)
    obs = value["child_result"]["observation"]
    if change == "pose": obs["capture"]["latest_pose_record"]["fields"]["x"] = 999
    elif change == "count": obs["capture"]["pose_sample_count"] = 20
    elif change == "freshness": obs["capture"]["sample_freshness_verified"] = True
    elif change == "raw": obs["capture"]["raw"]["sha256"] = "a"*64
    elif change == "write": obs["lifecycle"]["confirmed_write_bytes"] = 10
    elif change == "cleanup": obs["lifecycle"]["cleanup_confirmed"] = False
    elif change == "early": obs["observation_finished_monotonic_ns"] = obs["started_monotonic_ns"] + 1
    elif change == "window-gap": obs["read_windows"][0][0] = 1
    elif change == "window-time": obs["read_windows"][0][3] = obs["finished_monotonic_ns"] + 1
    elif change == "missing-window": obs["read_windows"] = []
    else: obs["schema"] = "rocell.powered_feedback_observation.v1"
    with pytest.raises(ValueError): validate_result(value, wire=request)


def test_query_request_cannot_accept_telemetry_result(captured):
    _, value = result(captured)
    request = envelope()
    value["request_sha256"] = request["request_sha256"]
    value["child_result"]["observation"]["request_sha256"] = request["operation_sha256"]
    with pytest.raises(ValueError): validate_result(value, wire=request)


@pytest.mark.parametrize('fault', ['missing', 'null', 'bool', 'before', 'after', 'read-before'])
def test_acquisition_boundary_is_required_and_ordered(captured, fault):
    request, value = result(captured)
    obs = value['child_result']['observation']
    if fault == 'missing': del obs['acquisition_started_monotonic_ns']
    elif fault == 'null': obs['acquisition_started_monotonic_ns'] = None
    elif fault == 'bool': obs['acquisition_started_monotonic_ns'] = True
    elif fault == 'before': obs['acquisition_started_monotonic_ns'] = obs['started_monotonic_ns'] - 1
    elif fault == 'after': obs['acquisition_started_monotonic_ns'] = obs['observation_finished_monotonic_ns'] + 1
    else: obs['acquisition_started_monotonic_ns'] = obs['read_windows'][0][2] + 1
    with pytest.raises(ValueError): validate_result(value, wire=request)


def test_original_v2_remains_reconstructable_without_invented_startup_time(captured):
    request, value = result(captured)
    obs = value['child_result']['observation']
    obs['schema'] = 'rocell.powered_telemetry_observation.v2'
    del obs['acquisition_started_monotonic_ns']
    assert validate_result(value, wire=request)['schema'].endswith('.v2')
