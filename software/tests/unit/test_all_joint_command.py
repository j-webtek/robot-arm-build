import math
import pytest

from rocell.arm.all_joint_command import all_joint_command, identification_command
from rocell.arm.protocol import ProtocolError, decode_line, encode_line


def test_exact_reference_packet_and_roundtrip():
    command = all_joint_command([.1, .2, .3, .4, .5, .6], speed=20, acceleration=1)
    assert command == dict(T=102, base=.1, shoulder=.2, elbow=.3,
                           wrist=.4, roll=.5, hand=.6, spd=20, acc=1)
    assert decode_line(encode_line(command)) == command


def test_non_test_targets_and_input_preserved():
    baseline = [.1, .2, .3, .4, .5, .6]
    command = identification_command(baseline, {"elbow": .31, "wrist": .39},
                                     speed=20, acceleration=1)
    assert baseline == [.1, .2, .3, .4, .5, .6]
    assert [command[k] for k in ("base", "shoulder", "roll", "hand")] == [.1,.2,.5,.6]
    assert command["elbow"] == .31 and command["wrist"] == .39


@pytest.mark.parametrize("field,value", [("speed", 0), ("speed", -1),
    ("speed", 65536), ("speed", True), ("speed", 20.0),
    ("acceleration", 0), ("acceleration", 256), ("acceleration", False)])
def test_settings_rejected(field, value):
    settings = dict(speed=20, acceleration=1)
    settings[field] = value
    with pytest.raises(ProtocolError):
        all_joint_command([0]*6, **settings)


@pytest.mark.parametrize("targets", [[0]*5, [0]*7, [math.nan]*6,
                                    [math.inf]*6, [True]*6, ["0"]*6])
def test_invalid_targets(targets):
    with pytest.raises(ProtocolError):
        all_joint_command(targets, speed=20, acceleration=1)


@pytest.mark.parametrize("overrides", [{}, {"t": .1}, {"wrist": math.nan}])
def test_invalid_overrides(overrides):
    with pytest.raises(ProtocolError):
        identification_command([0]*6, overrides, speed=20, acceleration=1)
