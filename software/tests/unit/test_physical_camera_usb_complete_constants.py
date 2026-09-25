"""Suffix-name/capacity contract tests; no original-store acceptance."""

import pytest


from rocell.application import physical_camera_usb_complete_constants as m

SERIES_ID = "usbseries-" + "0123456789abcdef" * 2


def test_closed_suffix_capacity_has_no_extra_device_phase():
    assert m.SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA.endswith(".v14")
    assert tuple(m.USB_COMPLETE_ROLE_BYTES) == ("series", "assessment", "review")
    assert sum(m.USB_COMPLETE_ROLE_BYTES.values()) == 56 * 1024
    assert m.MAX_USB_COMPLETE_EVENTS == len(m.USB_COMPLETE_EVENTS) == 3
    assert not any("QUERY" in kind or "BOOT" in kind for kind in m.USB_COMPLETE_EVENTS)


@pytest.mark.parametrize("kind", m.USB_COMPLETE_EVENTS)
def test_event_round_trip_uses_complete_series_prefix_length(kind):
    event = m.usb_complete_event(kind, SERIES_ID)
    matched = m.USB_COMPLETE_EVENT.fullmatch(event)
    assert matched is not None
    assert matched.groups() == (kind, "0123456789ABCDEF" * 2)
    assert m.USB_COMPLETE_EVENT.fullmatch(event + "\n") is None


@pytest.mark.parametrize("role", m.USB_COMPLETE_ROLE_BYTES)
def test_role_round_trip_is_bound_to_one_series(role):
    label = m.usb_complete_label(role, SERIES_ID)
    matched = m.USB_COMPLETE_LABEL.fullmatch(label)
    assert matched is not None and matched.groups() == (role, SERIES_ID)
    assert m.USB_COMPLETE_LABEL.fullmatch(label + "\n") is None


@pytest.mark.parametrize(
    "identifier",
    [
        True,
        None,
        b"usbseries-" + b"a" * 32,
        "usbseries-" + "a" * 31,
        "usbseries-" + "A" * 32,
        "usbphase-" + "a" * 32,
        SERIES_ID + "\n",
        " " + SERIES_ID,
        SERIES_ID + "x",
    ],
)
def test_wrong_or_aliased_id_is_never_normalized(identifier):
    with pytest.raises(ValueError, match="USB_COMPLETE_SUFFIX_INVALID"):
        m.usb_complete_event("ASSESSMENT_REQUESTED", identifier)
    with pytest.raises(ValueError, match="USB_COMPLETE_SUFFIX_INVALID"):
        m.usb_complete_label("series", identifier)


@pytest.mark.parametrize("kind", [True, None, "QUERY_REQUESTED", "PASS", "REVIEWED "])
def test_unknown_event_is_rejected(kind):
    with pytest.raises(ValueError, match="USB_COMPLETE_SUFFIX_INVALID"):
        m.usb_complete_event(kind, SERIES_ID)


@pytest.mark.parametrize("role", [True, None, "execution", "phase_record", "series "])
def test_unknown_role_is_rejected(role):
    with pytest.raises(ValueError, match="USB_COMPLETE_SUFFIX_INVALID"):
        m.usb_complete_label(role, SERIES_ID)
