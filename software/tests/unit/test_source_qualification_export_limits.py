"""Full supported history through the actual flatten/sanitizer/export encoding.

M1 scopes and ownership observations are explicit models; all source, ownership,
qualification and reader codecs are real. No ownership child or hardware runs.
"""

from copy import deepcopy

import pytest

from rocell.application.physical_source_qualification_service import (
    PhysicalSourceQualificationService,
)
from rocell.application.arrival_wizard_service import MAX_RESULT_BYTES, _json_payload
from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
from rocell.providers.windows.native_camera_protocol import canonical

from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_source_qualification_readback import (
    source_model,
    retained_cycle,
    covered_ownership,
    refresh_read,
)


def shape(value):
    pending, nodes, maximum_depth = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        maximum_depth = max(maximum_depth, depth)
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    return nodes, maximum_depth


@pytest.fixture
def full_history(setup_flow, source_model):
    setup, _, _ = setup_flow
    previous = predecessor = None
    for index in range(8):
        qualification = f"sourcequal-{index + 20:032x}"
        predecessor, previous, _ = retained_cycle(
            source_model,
            qualification=qualification,
            previous=previous,
            predecessor=predecessor,
            ownership=covered_ownership(source_model, qualification),
        )
    workflow = refresh_read(source_model)
    assert len(workflow["qualification_cycles"]) == 8
    assert all(
        cycle["state"] == "REVIEWED_BLOCKED"
        for cycle in workflow["qualification_cycles"]
    )
    setup._adopt_source_workflow(workflow)
    service = PhysicalSourceQualificationService(setup)
    service.observe_setup()
    return service, workflow


@pytest.mark.parametrize(
    "duplicate_latest_attempt",
    [False, True],
    ids=["history-only", "history-and-latest-attempt"],
)
def test_supported_eight_cycle_history_exports_full_exact_bytes(
    full_history, duplicate_latest_attempt
):
    service, original = full_history
    if duplicate_latest_attempt:
        last = original["qualification_cycles"][-1]
        receipt = last["receipt"]["document"]
        # Exact shape retained by successful qualification collection. The
        # original reader still holds this same cycle, so the latest attempt
        # genuinely duplicates its source/ownership documents and record bytes.
        service._attempt = {
            "qualification_id": last["qualification_id"],
            "action_id": "physical_source_qualify",
            "ownership_directory": receipt["ownership_report"]["binding"]["directory"],
            "software_receipt": deepcopy(receipt["software_receipt"]),
            "ownership_report": deepcopy(receipt["ownership_report"]),
            "records": {
                role: deepcopy(last[role]) for role in ("receipt", "assessment")
            },
        }
    before = canonical(original)
    diagnostics = service.retained_diagnostics()
    assert diagnostics is not None
    nodes, depth = shape(diagnostics)
    print(
        f"QUALIFICATION_EXPORT duplicate={duplicate_latest_attempt} canonical={len(canonical(diagnostics))} pretty={len(_json_payload(diagnostics))} sanitizer_nodes={nodes} depth={depth}"
    )
    assert before == canonical(service.setup.session.retained_source_workflow())
    clean = sanitize_diagnostic_record(diagnostics, maximum_bytes=MAX_RESULT_BYTES)
    assert clean == diagnostics
    payload = _json_payload(
        {
            **clean,
            "schema": "rocell.wizard_source_qualification_export.v1",
            "publication": deepcopy(service._publication),
            "original_bytes_preserved": True,
            "physical_authority": False,
            "hardware_qualified": False,
            "meaning": "Original source qualification metadata and references only, not private isolation bytes or native release. Redacted documents are not the original subjects named by their hashes; no automatic restoration or replay.",
        }
    )
    assert len(payload) <= MAX_RESULT_BYTES
    # Rebuild each immutable receipt from the actual flattened documents. This
    # catches hash-only omission or mutation masquerading as a smaller export.
    for index, original_cycle in enumerate(original["qualification_cycles"], 1):
        row = diagnostics["qualification_cycles"][index - 1]
        receipt = deepcopy(diagnostics[row["receipt"]["document_key"]])
        for nested in ("software_receipt", "ownership_report"):
            receipt[nested] = diagnostics[receipt.pop(nested + "_document_key")]
        assert canonical(receipt) == canonical(original_cycle["receipt"]["document"])
