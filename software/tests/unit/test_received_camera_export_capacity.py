"""A lower-bound capacity audit, not a new stage-3 persistence schema.

The source/static packet is produced by the actual public service/export path
with modeled ownership/M1. Four genuine notebook codec originals are a legal
large-input lower bound; pending stage-3 documents/references would add bytes.
No hardware observations, device calls or original-store changes occur.
"""

from copy import deepcopy
import json
from pathlib import Path

from rocell.application.arrival_wizard_service import _json_payload
from rocell.application.wizard_diagnostic_export import MAX_ATTACHMENT_BYTES
from test_arrival_static_onboarding_composed import (
    static_composed,
    composed,
    make_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    test_public_real_services_original_design_export_and_render as public_static_chain,
)
from test_physical_intake_export_budgets import _maximum_notebook
from test_physical_intake_submission import intake_fixture


def test_four_legal_notebook_originals_alone_exceed_combined_source_headroom(
    static_composed, monkeypatch
):
    public_static_chain(static_composed, monkeypatch, 8)
    arrival = static_composed[0]
    directory = Path(arrival._exports[-1]["path"])
    source = (directory / "attachment-source-qualification-data.json").read_bytes()
    packet = json.loads(source)
    fixture = intake_fixture(observed=True)
    notebook = _maximum_notebook(fixture, summary_heavy=True)
    notebooks = []
    for index in range(4):
        row = notebook.to_dict()["rows"][-1]
        observation = row["observation"]
        notebook = notebook.record(
            record_id=row["record_id"],
            observation_status="OBSERVED",
            observed_value=observation["observed_value"][:-1] + str(index),
            method=observation["method"],
            evidence_note=observation["evidence_note"],
            operator_id=observation["operator_id"],
            recorded_at_ns=100 + index,
        )
        assert len(notebook.payload) <= 65536
        notebooks.append(notebook)
    assert len({row.sha256 for row in notebooks}) == 4
    headroom = MAX_ATTACHMENT_BYTES - len(source)
    # Compact canonical notebook bytes alone exceed the full pretty-packet
    # allowance; this is not relying on future submission/report duplication.
    minimum = sum(len(row.payload) for row in notebooks)
    assert minimum > headroom
    hypothetical = deepcopy(packet)
    hypothetical["CAPACITY_AUDIT_NOT_A_STAGE3_SCHEMA"] = {
        f"notebook_original_{i + 1}": row.to_dict() for i, row in enumerate(notebooks)
    }
    combined_bytes = len(_json_payload(hypothetical))
    assert combined_bytes > MAX_ATTACHMENT_BYTES
    assert len(list(directory.glob("attachment-*.json"))) == 8
    assert (
        directory / "attachment-source-qualification-data.json"
    ).read_bytes() == source
    print(
        json.dumps(
            {
                "existing_source_static_bytes": len(source),
                "remaining_single_attachment_bytes": headroom,
                "four_distinct_canonical_notebook_bytes": minimum,
                "hypothetical_combined_pretty_bytes": combined_bytes,
                "existing_attachment_count": 8,
            }
        )
    )
