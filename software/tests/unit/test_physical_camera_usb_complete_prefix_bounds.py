"""Cheap private-extension rejection; no predecessor, storage or provider calls."""

from importlib import import_module
from inspect import signature, Parameter

import pytest

from rocell.application.physical_camera_session import PhysicalCameraSessionError
from test_physical_camera_usb_complete_layout import case


PREFIXES = (
    (
        "physical_camera_identity_readback",
        "_verify_camera_identity_prefix",
        "verify_camera_identity_workflow",
    ),
    (
        "physical_camera_usb_readback",
        "_verify_usb_baseline_prefix",
        "verify_usb_baseline_workflow",
    ),
    (
        "physical_camera_usb_trial_readback",
        "_verify_usb_qualification_trial_prefix",
        "verify_usb_qualification_trial_workflow",
    ),
    (
        "physical_camera_usb_phase_readback",
        "_verify_usb_phase_prefix",
        "verify_usb_phase_workflow",
    ),
    (
        "physical_camera_usb_absence_readback",
        "_verify_usb_absence_prefix",
        "verify_usb_absence_workflow",
    ),
    (
        "physical_camera_usb_reconnect_readback",
        "_verify_usb_reconnect_prefix",
        "verify_usb_reconnect_workflow",
    ),
)


def args_for(function):
    args = {}
    for name, parameter in signature(function).parameters.items():
        if name == "snapshot":
            args[name] = case()[0]
        elif name == "prefix_event_count":
            args[name] = 1
        elif name.endswith("_evidence_ids"):
            args[name] = frozenset()
        elif name.endswith("_extension"):
            args[name] = True
        elif name == "original_presence_campaigns":
            args[name] = ({},)
        elif parameter.default is Parameter.empty:
            args[name] = {}
    return args


@pytest.mark.parametrize("module_name,private,public", PREFIXES)
@pytest.mark.parametrize(
    "change",
    ["non-bool", "mutable-ids", "too-many", "no-extension", "no-prefix", "alias"],
)
def test_complete_extension_rejects_bad_scope_before_predecessor(
    module_name, private, public, change, monkeypatch
):
    module = import_module("rocell.application." + module_name)
    function = getattr(module, private)
    args = args_for(function)
    if change == "non-bool":
        args["usb_complete_extension"] = 1
    elif change == "mutable-ids":
        args["usb_complete_evidence_ids"] = set()
    elif change == "too-many":
        args["usb_complete_evidence_ids"] = frozenset("abcd")
    elif change == "no-extension":
        args["usb_complete_extension"] = False
        args["usb_complete_evidence_ids"] = frozenset({"extra"})
    elif change == "no-prefix":
        args["prefix_event_count"] = None
    elif change == "alias":
        args["usb_complete_evidence_ids"] = frozenset({"same"})
        args["usb_reboot_evidence_ids"] = frozenset({"same"})

    def denied(*args, **kwargs):
        pytest.fail("invalid extension reached a predecessor reader")

    # Patch the downstream imports, not the function under test.
    targets = (
        *PREFIXES,
        (
            "physical_received_camera_readback",
            "_verify_received_camera_prefix",
            "verify_received_camera_workflow",
        ),
    )
    for lower_name, lower_private, _ in targets:
        if lower_name != module_name:
            monkeypatch.setattr(
                import_module("rocell.application." + lower_name), lower_private, denied
            )
        if lower_private != private and hasattr(module, lower_private):
            monkeypatch.setattr(module, lower_private, denied)
    with pytest.raises(PhysicalCameraSessionError):
        function(**args)


@pytest.mark.parametrize("module_name,private,public", PREFIXES)
def test_public_legacy_reader_does_not_expose_extension(module_name, private, public):
    module = import_module("rocell.application." + module_name)
    names = signature(getattr(module, public)).parameters
    assert "usb_complete_extension" not in names
    assert "usb_complete_evidence_ids" not in names
    assert "prefix_event_count" not in names
