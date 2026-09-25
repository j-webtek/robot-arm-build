"""Real predecessor owners over explicitly modeled audited-successor labels.

The existing fixtures build original subjects through their real codecs and
readers over modeled storage/physical facts. Only the workflow version at the
already-authenticated Setup-to-owner boundary is substituted here. In
particular, a v13 label is NOT a v13 reader, acquisition or activation claim.
No production helper, process, CIM, camera or arm operation is allowed.
"""

from copy import deepcopy

import pytest

from rocell.application import physical_camera_identity_service as identity_module
from rocell.application import physical_received_camera_service as received_module
from rocell.application import physical_source_qualification_service as source
from rocell.application import physical_static_camera_onboarding_service as static
from rocell.providers.windows.native_camera_protocol import canonical

from test_physical_camera_identity_service import identity, run as identity_run
from test_physical_received_camera_service import received
from test_physical_static_camera_onboarding_service import static_service
from test_physical_source_qualification_service import modeled
from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace


OWNERS = (
    (source, source.PhysicalSourceQualificationService),
    (static, static.PhysicalStaticCameraOnboardingService),
    (received_module, received_module.PhysicalReceivedCameraService),
    (identity_module, identity_module.PhysicalCameraIdentityService),
)
HISTORICAL = dict(status="HISTORICAL_HELD", operation_id=None)
IDENTITY_DENIAL = (
    "The original metadata prefix is historical after USB inspection starts; "
    "export it without replay."
)


def _activity(state):
    return (
        state["reads"],
        state["enters"],
        len(state["events"]),
        len(state["references"]),
    )


def _assert_exported_originals(module, exported, original):
    """Compare complete export subjects, including flattened nested documents."""

    def restore(document):
        return {
            (
                key.removesuffix("_document_key")
                if key.endswith("_document_key")
                else key
            ): (
                restore(exported[value])
                if key.endswith("_document_key")
                else deepcopy(value)
            )
            for key, value in document.items()
        }

    if module is source:
        expected = original["qualification_cycles"][-1]
        actual = exported["qualification_cycles"][-1]
    elif module is static:
        expected = original["static_contract"]
        actual = exported["static_contract"]
    elif module is received_module:
        expected = original["received_camera_cycles"][-1]
        actual = exported["cycles"][-1]
    else:
        expected = original["camera_identity_cycles"][-1]
        actual = exported["cycles"][-1]
    for role in module._CODECS:
        record, retained = actual[role], expected[role]
        assert record is not None and retained is not None, role
        document = (
            restore(exported[record["document_key"]])
            if "document_key" in record
            else record["document"]
        )
        assert canonical(document) == canonical(retained["document"]), role
        assert record["evidence_sha256"] == retained["evidence_sha256"], role
        assert record["reference"] == retained["reference"], role


def test_v11_v12_and_future_v13_preserve_full_history_without_replay(
    identity, monkeypatch
):
    current, state, inputs, _ = identity
    identity_run(current, inputs)
    identity_run(current, inputs, identity_module.REVIEW)
    setup = current.setup
    original = setup.original_source_workflow()
    original_wire = canonical(original)
    assert original["schema"] == "rocell.physical_camera_source_workflow_readback.v7"
    assert current.blocked_reason(identity_module.SUBMIT, **inputs) is None
    activity = _activity(state)

    for module, owner_type in OWNERS:
        # GET/adoption/export-payload retrieval must not perform a new source
        # scan, original transaction or native observation.
        monkeypatch.setattr(
            module, "source_fingerprint", lambda _: pytest.fail("unexpected source I/O")
        )
        previous_export = previous_view = None
        for version in (11, 12, 13):
            successor = deepcopy(original)
            successor["schema"] = (
                f"rocell.physical_camera_source_workflow_readback.v{version}"
            )
            successor_wire = canonical(successor)
            monkeypatch.setattr(
                setup, "original_source_workflow", lambda: deepcopy(successor)
            )
            owner = owner_type(setup)
            owner.observe_setup()
            view = owner.view()
            assert view["publication"] == HISTORICAL
            assert view["next_action"] is None
            assert view["physical_authority"] is False
            for action in module.ACTIONS:
                kwargs = inputs if module is identity_module else {}
                reason = owner.blocked_reason(action, **kwargs)
                if action == getattr(module, "EXPORT", None):
                    assert reason is None
                else:
                    assert reason is not None, (module.__name__, version, action)
                    if module is identity_module:
                        assert reason == IDENTITY_DENIAL
            exported = owner.retained_diagnostics()
            assert exported is not None
            assert exported["publication"] == HISTORICAL
            assert exported["physical_authority"] is False
            _assert_exported_originals(module, exported, original)
            wire = canonical(exported)
            if previous_export is not None:
                # Same complete subjects and references, not just safe hashes.
                assert wire == previous_export
                assert view == previous_view
            previous_export, previous_view = wire, deepcopy(view)
            exported.clear()
            view["publication"]["status"] = "CALLER_MUTATION"
            assert canonical(owner.retained_diagnostics()) == wire
            assert owner.view() == previous_view
            assert canonical(successor) == successor_wire
            assert _activity(state) == activity
    assert canonical(setup.session.retained_source_workflow()) == original_wire


@pytest.mark.parametrize(
    "fixture_name,module,action",
    [
        ("modeled", source, "physical_source_qualify"),
        ("static_service", static, "physical_static_contract_collect"),
        ("received", received_module, received_module.START),
        ("identity", identity_module, identity_module.SUBMIT),
    ],
)
def test_current_owner_and_unknown_version_behavior_are_unchanged(
    request, monkeypatch, fixture_name, module, action
):
    fixture = request.getfixturevalue(fixture_name)
    owner, state = fixture[:2]
    inputs = fixture[2] if module is identity_module else {}
    owner.observe_setup()
    original = owner.setup.original_source_workflow()
    assert original["schema"] not in {
        f"rocell.physical_camera_source_workflow_readback.v{version}"
        for version in (11, 12, 13)
    }
    current_view = owner.view()
    current_export = owner.retained_diagnostics()
    assert current_view["publication"]["status"] == "CURRENT"
    assert owner.blocked_reason(action, **inputs) is None
    current_reasons = {
        item: owner.blocked_reason(item, **inputs) for item in module.ACTIONS
    }
    activity = _activity(state)
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("unexpected source I/O")
    )
    for version in (14, 130):
        # This tests that the owner roster stays closed and literal, not that
        # unknown versions can pass the separate original reader/Setup gate.
        unknown = deepcopy(original)
        unknown["schema"] = (
            f"rocell.physical_camera_source_workflow_readback.v{version}"
        )
        monkeypatch.setattr(
            owner.setup, "original_source_workflow", lambda: deepcopy(unknown)
        )
        owner.observe_setup()
        assert owner.view() == current_view
        assert owner.retained_diagnostics() == current_export
        assert {
            item: owner.blocked_reason(item, **inputs) for item in module.ACTIONS
        } == current_reasons
        assert _activity(state) == activity
