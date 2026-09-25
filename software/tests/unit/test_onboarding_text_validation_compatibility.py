"""Preserve the exact historical text predicates while optimizing hot scans.

The policies differ intentionally: prerequisite JSON permits CR/LF/TAB and
DEL; intake template fields reject C0; hazard text rejects C0 and DEL. This is
not a broader Unicode sanitation policy and must not silently become one.
"""

import csv
import io
from pathlib import Path

import pytest

from rocell.application import physical_camera_prerequisites as prerequisites
from rocell.safety import onboarding_hazards as hazards


def test_every_unicode_code_point_preserves_node_and_hazard_rules():
    # Complete finite character domain, including unpaired surrogates. Avoid
    # normalization and surround whitespace so hazard trimming is not the test.
    for number in range(0x110000):
        char = chr(number)
        value = "A" + char + "Z"
        if 0xD800 <= number <= 0xDFFF:
            with pytest.raises(UnicodeEncodeError):
                prerequisites._node(value)
        elif number < 32 and char not in "\r\n\t":
            with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
                prerequisites._node(value)
        else:
            prerequisites._node(value)
        if number < 32 or number == 127:
            with pytest.raises(hazards.PhysicalOnboardingHazardError):
                hazards._text(value, "modeled")
        else:
            assert hazards._text(value, "modeled") == value


@pytest.mark.parametrize("position", [0, 127, 255])
@pytest.mark.parametrize("char", ["\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x1f"])
def test_invalid_character_anywhere_in_long_value_is_rejected(position, char):
    value = "X" * position + char + "Y" * (256 - position)
    with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
        prerequisites._node({"list": [value]})
    with pytest.raises(hazards.PhysicalOnboardingHazardError):
        hazards._text(value, "modeled")


def test_utf8_byte_depth_and_hazard_trim_bounds_are_unchanged():
    prerequisites._node("\u00e9" * (prerequisites.MAX_EVIDENCE_BYTES // 2))
    with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
        prerequisites._node("\u00e9" * (prerequisites.MAX_EVIDENCE_BYTES // 2 + 1))
    value = "X"
    for _ in range(16):
        value = [value]
    prerequisites._node(value)
    with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
        prerequisites._node([value])
    for text in ("", " X", "X ", "\tX", "X\n", "X" * 513):
        with pytest.raises(hazards.PhysicalOnboardingHazardError):
            hazards._text(text, "modeled")


def test_exact_json_string_type_and_legacy_hazard_subclass_behavior():
    class DisplayText(str):
        def __iter__(self):
            return iter("A\x00Z")

    value = DisplayText("otherwise ordinary display text")
    with pytest.raises(prerequisites.PhysicalCameraPrerequisitesError):
        prerequisites._node(value)
    # The public hazard helper historically accepts isinstance(str), then
    # iterates it. Keep that behavior instead of silently switching contracts.
    with pytest.raises(hazards.PhysicalOnboardingHazardError):
        hazards._text(value, "modeled")
    for value in (False, 4, [], {}, None):
        with pytest.raises(hazards.PhysicalOnboardingHazardError):
            hazards._text(value, "modeled")


@pytest.mark.parametrize("number", [*range(32), 32, 126, 127, 128, 0x00E9, 0x1F600])
def test_template_field_control_policy_is_not_json_or_hazard_policy(number):
    root = Path(__file__).resolve().parents[3]
    source = (root / prerequisites.SOURCES[-1][1]).read_bytes()
    rows = list(csv.DictReader(io.StringIO(source.decode("utf-8"), newline="")))
    # This field is descriptive, with no separate enum/identifier grammar.
    field = "notes"
    assert field in rows[0]
    placeholder = "MODELED-CONTROL-PLACEHOLDER"
    rows[0][field] = placeholder
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=prerequisites.INTAKE_HEADER, quoting=csv.QUOTE_ALL
    )
    writer.writeheader()
    writer.writerows(rows)
    wire = output.getvalue().encode("utf-8")
    assert wire.count(placeholder.encode("ascii")) == 1
    # Python 3.10's CSV writer refuses NUL before the actual parser under test.
    # Insert the candidate in the quoted field after serialization instead.
    payload = wire.replace(
        placeholder.encode("ascii"), ("A" + chr(number) + "Z").encode("utf-8")
    )
    if number < 32:
        with pytest.raises((prerequisites.PhysicalCameraPrerequisitesError, csv.Error)):
            prerequisites._template(payload)
    else:
        prerequisites._template(payload)
