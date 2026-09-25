"""Real pure notebook -> strict cached UI, not physical measurement proof."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from threading import Event
from time import monotonic_ns

import pytest

from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.ui.terminal import _PhysicalIntakeDisplay
import test_arrival_wizard_device_selection_ui as dom
from test_arrival_wizard_terminal import action, run
from test_physical_camera_session import session_fixture
from test_physical_intake_notebook import record
from test_wizard_physical_camera_restart_ui import version_two
from test_wizard_physical_camera_setup_ui import modeled_storage


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def bound_notebook():
    from rocell.application import physical_camera_prerequisites as module

    setup = version_two(modeled_storage(session_fixture(WORKSPACE)), reopened=True)
    bound = setup["session"]["binding"]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, "source_fingerprint", lambda _: bound["source_sha256"])
        artifact = module.collect_physical_camera_prerequisites(
            WORKSPACE,
            source_sha256=bound["source_sha256"],
            session_id=bound["session_id"],
            launch_session_id=bound["launch_id"],
            cancellation=Event(),
            deadline_ns=monotonic_ns() + 30_000_000_000,
        )
    setup["prerequisites"] = artifact.safe_summary()
    setup["requirements_provenance"] = "REOPENED_ORIGINAL_CONTEXT"
    setup["session"].update(status="REFRESHED_STORAGE_ONLY", operation="REFRESH")
    setup["session"]["stages"][0].update(
        state="WAITING_OPERATOR", last_event_sequence=1
    )
    notebook = PhysicalIntakeNotebook.start(
        artifact, launch_session_id=setup["launch_session_id"]
    )
    return setup, notebook


def top(notebook=None, *, status=None):
    return {
        "schema": "rocell.wizard_physical_intake.v1",
        "status": status or ("NOT_STARTED" if notebook is None else "CURRENT_DRAFT"),
        "notebook": None if notebook is None else notebook.view(),
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Operator draft only; not accepted measurement or hardware qualification.",
    }


def record_action(notebook):
    fields = [
        {
            "name": "record_id",
            "type": "select",
            "label": "Question",
            "required": True,
            "options": notebook.choices(),
        },
        {
            "name": "observation_status",
            "type": "select",
            "label": "Observation status",
            "required": True,
            "default": "UNKNOWN",
            "options": [
                {"value": value, "label": value} for value in ("OBSERVED", "UNKNOWN")
            ],
        },
    ]
    for name, maximum in (
        ("observed_value", 256),
        ("method", 512),
        ("evidence_note", 1024),
        ("operator_id", 64),
    ):
        fields.append(
            {
                "name": name,
                "type": "textarea" if name == "evidence_note" else "text",
                "label": name,
                "required": True,
                "default": "",
                "max_length": maximum,
            }
        )
    item = action("physical_intake_record", fields=fields)
    item["section"] = "camera"
    return item


def view_for(setup, value, notebook):
    view = dom.MetadataService(dom.selection()).view()
    view.update(
        mode="physical",
        physical_camera_setup=deepcopy(setup),
        physical_intake=deepcopy(value),
        actions=[record_action(notebook)],
    )
    return view


def display(view, *, selected=None):
    if selected is None:
        page = dom.browser(dom.selection(), "camera", snapshot=view)
    else:
        # Exercise the real local change listener; this is a tests-only DOM.
        harness = dom._HARNESS.replace(
            "if(input.prepare){",
            "if(input.intakeSelection){const field=nodes.find(n=>n.id==='field-physical_intake_record-record_id');field.value=input.intakeSelection;field.listeners.change();}if(input.prepare){",
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(dom, "_HARNESS", harness)
            page = dom.browser(
                dom.selection(), "camera", snapshot=view, intakeSelection=selected
            )
    assert page["status"] == "Local service connected", page["error"]
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    service = dom.MetadataService(dom.selection())

    def cached():
        service.calls.append(("view",))
        return deepcopy(view)

    service.view = cached
    code, lines, _ = run(service, ["quit"])
    assert code == 0 and service.calls == [("view",)]
    return page, "\n".join(lines)


def test_actual_started_notebook_has_only_original_blank_observations(bound_notebook):
    setup, notebook = bound_notebook
    value = top(notebook)
    assert _PhysicalIntakeDisplay.validate(value, setup) == value
    page, console = display(view_for(setup, value, notebook))
    for text in (page["text"], console):
        assert "PHYSICAL_INTAKE_NOT_VERIFIED" not in text
        assert "DRAFT ONLY / NOT ACCEPTED" in text
        assert "No operator observation recorded" in text
        assert "draft restoration on another launch is not supported" in text
        assert "no attachment bytes are uploaded, read or verified" in text
    assert all(row["observation"] is None for row in value["notebook"]["rows"])
    assert len(value["notebook"]["rows"]) == 16
    assert "INT-018" not in {row["record_id"] for row in value["notebook"]["rows"]}
    for field in page["controls"]:
        if field["id"].startswith("field-physical_intake_record-"):
            assert field["value"] == (
                "UNKNOWN" if field["id"].endswith("observation_status") else ""
            )


def test_actual_revisions_distinguish_unknown_from_observed_and_never_accept(
    bound_notebook,
):
    setup, notebook = bound_notebook
    first = record(notebook)
    second = record(
        first,
        record_id="INT-005",
        observation_status="OBSERVED",
        observed_value="0",
        method="Modeled gauge reading",
        recorded_at_ns=1_800_000_000_000_000_003,
    )
    value = top(second)
    assert value["notebook"]["coverage"] == dict(
        total=16, observed=1, unknown=1, unrecorded=14
    )
    page, console = display(view_for(setup, value, second), selected="INT-005")
    for text in (page["text"], console):
        assert "PHYSICAL_INTAKE_NOT_VERIFIED" not in text
        assert "Hardware not received" in text and "Modeled gauge reading" in text
        assert "UNKNOWN is a reason, not measured coverage" in text
        assert "INT-005 flatness: a draft value does not accept" in text
        assert "1800000000000000003" not in text
        assert "1800000000000000000" not in text
    assert page["text"].count("INT-005 flatness:") == 2  # Table + selected question.
    assert notebook.to_dict()["revision"] == 0 and first.to_dict()["revision"] == 1


@pytest.mark.parametrize("status", ["NOT_STARTED", "HISTORICAL_HELD"])
def test_noncurrent_notebook_exposes_no_old_answers(bound_notebook, status):
    setup, notebook = bound_notebook
    page, console = display(view_for(setup, top(status=status), notebook))
    for text in (page["text"], console):
        assert "PHYSICAL_INTAKE_NOT_VERIFIED" not in text
        assert (
            "Current source-bound intake questions are unavailable" in text
            or text == console
        )
        assert "Hardware not received" not in text


@pytest.mark.parametrize(
    "path,value",
    [
        (("physical_authority",), True),
        (("hardware_qualified",), 0),
        (("notebook", "binding", "source_sha256"), "f" * 64),
        (("notebook", "binding", "session_id"), "physical-camera-" + "f" * 32),
        (("notebook", "binding", "origin_launch_id"), "wizard-" + "f" * 32),
        (("notebook", "binding", "launch_session_id"), "wizard-" + "f" * 32),
        (("notebook", "binding", "prerequisites_sha256"), "f" * 64),
        (("notebook", "revision"), True),
        (("notebook", "previous_sha256"), None),
        (("notebook", "coverage", "observed"), True),
        (("notebook", "coverage", "unknown"), 0),
        (("notebook", "canonical_stage_pass"), True),
        (("notebook", "attachment_bytes_verified"), True),
        (("notebook", "rows", 0, "record_id"), "INT-018"),
        (("notebook", "rows", 0, "candidate_or_requirement"), "RAW_SENTINEL"),
        (("notebook", "rows", 4, "acceptance", "status"), "ACCEPTED"),
        (("notebook", "rows", 0, "observation", "extra"), "RAW_SENTINEL"),
        (("notebook", "rows", 0, "observation", "method"), ""),
        (("notebook", "rows", 0, "observation", "evidence_note"), "line\nbreak"),
        (("notebook", "rows", 0, "observation", "operator_id"), "hidden\u200btext"),
        (("notebook", "rows", 0, "observation", "recorded_at_ns"), 0),
    ],
)
def test_malformed_changed_question_or_claim_is_withheld(bound_notebook, path, value):
    setup, notebook = bound_notebook
    draft = record(notebook)
    projection = top(draft)
    node = projection
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert _PhysicalIntakeDisplay.validate(projection, setup) is None
    page, console = display(view_for(setup, projection, draft))
    for text in (page["text"], console):
        assert "PHYSICAL_INTAKE_NOT_VERIFIED" in text
        assert "RAW_SENTINEL" not in text
        assert "Hardware not received" not in text


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD", "NOT_PUBLISHED"])
def test_notebook_requires_current_setup_publication(bound_notebook, publication):
    setup, notebook = bound_notebook
    held = deepcopy(setup)
    held["publication"]["status"] = publication
    held.update(prerequisites=None, requirements_provenance="NONE")
    value = top(record(notebook))
    assert _PhysicalIntakeDisplay.validate(value, held) is None
    page, console = display(view_for(held, value, notebook))
    assert (
        "PHYSICAL_INTAKE_NOT_VERIFIED" in page["text"]
        and "PHYSICAL_INTAKE_NOT_VERIFIED" in console
    )


def test_selected_question_and_explicit_preview_do_not_save_or_read_evidence(
    bound_notebook,
):
    setup, notebook = bound_notebook
    view = view_for(setup, top(notebook), notebook)
    fields = dict(
        record_id="INT-005",
        observation_status="UNKNOWN",
        observed_value="Not measured yet",
        method="Not measured",
        evidence_note="Not supplied",
        operator_id="operator",
    )
    prepared = dom.browser(
        dom.selection(),
        "camera",
        snapshot=view,
        prepare=True,
        action="physical_intake_record",
        values=fields,
    )
    assert [row["path"] for row in prepared["requests"]] == [
        "/api/view",
        "/api/prepare",
    ]
    assert prepared["requests"][-1]["body"]["input"] == fields
    service = dom.MetadataService(dom.selection())
    service.view = lambda: deepcopy(view)
    code, output, prompts = run(
        service,
        [
            "physical_intake_record",
            "INT-005",
            "UNKNOWN",
            "Not measured yet",
            "Not measured",
            "Not supplied",
            "operator",
            "",
            "quit",
        ],
    )
    assert code == 0
    assert [call for call in service.calls if call[0] == "prepare"] == [
        ("prepare", "physical_intake_record", fields, view["revision"])
    ]
    assert not any(call[0] == "execute" for call in service.calls)
    assert "Selected intake question INT-005" in "\n".join(output)
    assert notebook.to_dict()["revision"] == 0


@pytest.mark.parametrize("raw", ["0", "-1", "+1", "1e3", "NaN", "1,000"])
def test_numeric_draft_text_is_not_coerced_or_inferred(bound_notebook, raw):
    setup, notebook = bound_notebook
    draft = record(notebook, observation_status="OBSERVED", observed_value="1.25")
    value = top(draft)
    value["notebook"]["rows"][0]["observation"]["observed_value"] = raw
    assert _PhysicalIntakeDisplay.validate(value, setup) is None
    page, console = display(view_for(setup, value, draft))
    assert "PHYSICAL_INTAKE_NOT_VERIFIED" in page["text"]
    assert "PHYSICAL_INTAKE_NOT_VERIFIED" in console


def test_whole_canonical_byte_budget_is_not_only_per_field_bounds(bound_notebook):
    setup, notebook = bound_notebook
    value = top(notebook)
    data = value["notebook"]
    data.update(
        revision=16,
        previous_sha256="a" * 64,
        coverage=dict(total=16, observed=0, unknown=16, unrecorded=0),
    )
    for row in data["rows"]:
        row["observation"] = {
            "status": "UNKNOWN",
            "observed_value": "\u00e9" * 128,
            "method": "\u00e9" * 256,
            "evidence_note": "\u00e9" * 512,
            "operator_id": "\u00e9" * 32,
            "recorded_at_ns": 1,
        }
    # Every narrative is within its UTF-8 field limit, while canonical ASCII
    # expansion exceeds the model's whole 64 KiB payload budget.
    assert _PhysicalIntakeDisplay.validate(value, setup) is None
    page, console = display(view_for(setup, value, notebook))
    assert "PHYSICAL_INTAKE_NOT_VERIFIED" in page["text"]
    assert "PHYSICAL_INTAKE_NOT_VERIFIED" in console


@pytest.mark.parametrize("status", ["CURRENT_DRAFT", "HISTORICAL_HELD"])
def test_actual_public_intake_export_renders_without_dispatch(status):
    path = (
        WORKSPACE
        / "software/runs/wizard-exports"
        / "wizard-20260908T121815319658Z-459748eec82047bbb3a22a67c534c683"
        / "report.json"
    )
    if not path.is_file():
        pytest.skip("Optional actual public intake export is not present")
    # CURRENT_DRAFT is the exact public snapshot; HISTORICAL_HELD is a
    # display-only variant. Neither case reopens the retained M1 store.
    view = json.loads(path.read_text(encoding="utf-8"))["snapshot"]
    value = view["physical_intake"]
    assert value["status"] == "CURRENT_DRAFT"
    notebook = value["notebook"]
    assert notebook["revision"] == 1
    assert notebook["coverage"] == dict(total=16, observed=0, unknown=1, unrecorded=15)
    assert notebook["rows"][0]["record_id"] == "INT-001"
    assert notebook["rows"][0]["observation"]["status"] == "UNKNOWN"
    snapshot_hash = notebook["snapshot_sha256"]
    observation = notebook["rows"][0]["observation"]["observed_value"]
    assert all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"])
    if status == "HISTORICAL_HELD":
        value.update(status=status, notebook=None)
    assert (
        _PhysicalIntakeDisplay.validate(value, view["physical_camera_setup"]) == value
    )
    original = deepcopy(view)
    page, console = display(view)
    for text in (page["text"], console):
        assert "PHYSICAL_INTAKE_NOT_VERIFIED" not in text
        assert "DRAFT ONLY / NOT ACCEPTED" in text
        assert "no attachment bytes are uploaded, read or verified" in text
        if status == "CURRENT_DRAFT":
            assert snapshot_hash in text and observation in text
            assert "UNKNOWN is a reason, not measured coverage" in text
        else:
            assert "Current draft is held" in text
            assert snapshot_hash not in text and observation not in text
    assert view == original


def test_narratives_preserve_underscores_unicode_and_markup_as_literal_text(
    bound_notebook, monkeypatch
):
    setup, notebook = bound_notebook
    fields = {
        "observed_value": "bench_A_<unknown>_\u6e2c\u5b9a",
        "method": "caliper_A_\u00e9",
        "evidence_note": "<img src=x onerror=alert(1)>_description_only",
        "operator_id": "operator_A",
    }
    draft = record(notebook, **fields)
    view = view_for(setup, top(draft), draft)
    original_run = dom.subprocess.run

    def utf8_node(*args, **kwargs):
        # Node's stdout is UTF-8; do not misdecode it using Windows CP1252.
        return original_run(*args, **{**kwargs, "encoding": "utf-8"})

    monkeypatch.setattr(dom.subprocess, "run", utf8_node)
    page, console = display(view)
    for narrative in fields.values():
        assert narrative in page["text"]
        # Terminal records use lossless JSON ASCII escapes, not humanized text.
        assert json.dumps(narrative, ensure_ascii=True)[1:-1] in console
    assert "caliper A" not in page["text"]
    assert draft.to_dict()["rows"][0]["observation"]["method"] == "caliper_A_\u00e9"


def test_actual_export_narrative_variant_is_presented_exactly(monkeypatch):
    path = (
        WORKSPACE
        / "software/runs/wizard-exports"
        / "wizard-20260908T121815319658Z-459748eec82047bbb3a22a67c534c683"
        / "report.json"
    )
    if not path.is_file():
        pytest.skip("Optional actual public intake export is not present")
    view = json.loads(path.read_text(encoding="utf-8"))["snapshot"]
    # A rehashed display-only variant, not a new retained notebook or accepted
    # measurement. The on-disk export is never changed or replayed.
    observation = view["physical_intake"]["notebook"]["rows"][0]["observation"]
    observation.update(method="caliper_A", operator_id="operator_A")
    notebook = view["physical_intake"]["notebook"]
    notebook["snapshot_sha256"] = hashlib.sha256(
        json.dumps(
            {key: item for key, item in notebook.items() if key != "snapshot_sha256"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    page, console = display(view)
    assert "caliper_A" in page["text"] and "operator_A" in page["text"]
    assert "caliper_A" in console and "operator_A" in console
    assert "caliper A" not in page["text"]
