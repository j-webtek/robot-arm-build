"""Wizard adapter for fixed memory-only powered feedback scenarios.

Synthetic originals are explicitly labeled and never qualify a physical arm.
The service retains the complete bytes independently of its rotating UI cards.
"""

import hashlib
import time

from .arm_bench_qualification_contract import _canonical
from .passive_arm_identity import PassiveControllerSelection
from .powered_arm_feedback_contract import (
    LIMITS,
    PURPOSE,
    REFERENCE_NAMES,
    SCHEMA,
    PoweredFeedbackIntent,
)
from .wizard_device_selection import WizardDeviceSelection
from .wizard_inventory_fixture import rehearsal_device_inventory
from .wizard_native_arm_metadata import (
    correlate_native_arm_metadata,
    rehearse_native_arm_metadata_snapshot,
)
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32Scenario,
    IncapableWin32SerialApi,
)
from rocell.providers.windows.powered_feedback_binding import PoweredFeedbackBinding
from rocell.providers.windows.powered_feedback_observation import observe_rehearsal

ACTION = "rehearse_powered_arm_feedback"
SCENARIOS = (
    "nominal",
    "stale-input",
    "incomplete-reply",
    "short-write",
    "cleanup-unknown",
)
REPLY = b'{"T":1051,"x":300,"y":0,"z":200,"tit":0,"b":0,"s":0,"e":1.5,"t":0,"r":0,"g":3,"v":1200}\n'


def run_rehearsal(*, session_id, operation_id, source_sha256, scenario, cancellation):
    """Run one closed scenario; no endpoint, command or native provider input."""
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("Unknown powered feedback rehearsal scenario")
    selection = WizardDeviceSelection("rehearsal", session_id, source_sha256)
    selection.ingest(rehearsal_device_inventory("nominal"), operation_id=operation_id)
    review = selection.review(
        selection.choices("SERIAL")[0]["value"], "SERIAL", "synthetic-reviewer"
    )
    native = _canonical(
        correlate_native_arm_metadata(
            rehearse_native_arm_metadata_snapshot("nominal"),
            review,
            mode="rehearsal",
            session_id=session_id,
            source_sha256=source_sha256,
            operation_id=operation_id,
        )
    )
    # These hash-bound labels are modeled inputs, not approved review evidence.
    originals = {
        name: _canonical({"origin": "SYNTHETIC_REHEARSAL", "name": name})
        for name in REFERENCE_NAMES
    }
    refs = {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()}
    refs.update(
        source_sha256=source_sha256,
        native_identity_original_sha256=hashlib.sha256(native).hexdigest(),
    )
    now = time.monotonic_ns()
    intent = PoweredFeedbackIntent(
        _canonical(
            {
                "schema": SCHEMA,
                "purpose": PURPOSE,
                "mode": "rehearsal",
                "session_id": session_id,
                "attempt_id": operation_id,
                "references": refs,
                "startup_recorded_monotonic_ns": now,
                "parent_deadline_monotonic_ns": now + 20_000_000_000,
                "limits": LIMITS,
            }
        )
    )
    changes = {
        "nominal": {},
        "stale-input": {"startup_bytes": REPLY},
        "incomplete-reply": {"response_bytes": b'{"T":1051}\n'},
        "short-write": {"short_write": 2},
        "cleanup-unknown": {"fail_operations": ("close_port",)},
    }[scenario]
    api = IncapableWin32SerialApi(
        IncapableWin32Scenario(**{"response_bytes": REPLY, **changes})
    )
    observation = observe_rehearsal(
        PoweredFeedbackBinding(PassiveControllerSelection(native), intent),
        api,
        cancellation,
    )
    raw = _canonical(
        {
            "schema": "rocell.wizard_powered_feedback_rehearsal_original.v1",
            "session_id": session_id,
            "operation_id": operation_id,
            "source_sha256": source_sha256,
            "scenario": scenario,
            "origin": "SYNTHETIC_REHEARSAL",
            "intent": intent.to_dict(),
            "observation": observation,
            "physical_authority": False,
        }
    )
    success = observation["status"] == "FEEDBACK_OBSERVED_CLOSED"
    status = (
        "CANCELLED" if cancellation.is_set() else ("SUCCEEDED" if success else "FAILED")
    )
    result = {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": ACTION,
        "status": status,
        "steps": [
            {
                "name": "powered_feedback_rehearsal",
                "exit_code": 0 if success else 1,
                "report": {
                    "origin": "SYNTHETIC_REHEARSAL",
                    "scenario": scenario,
                    "status": observation["status"],
                    "errors": observation["errors"],
                    "original_sha256": hashlib.sha256(raw).hexdigest(),
                    "simulated_write_bytes": observation["lifecycle"][
                        "confirmed_write_bytes"
                    ],
                    "cleanup_confirmed": observation["lifecycle"]["cleanup_confirmed"],
                    "connected": False,
                    "physical_authority": False,
                },
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }
    return result, raw
