from pathlib import Path
import pytest
from rocell.application.p4_extension_review import review_p4_extension
from rocell.application.wizard_diagnostic_export import verify_export

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'runs/wizard-exports/wizard-20260924T100122313690Z-ba8afa38d92b436c8f137dae16978a84'
MODEL = ROOT/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf'
BOOT = '4ea6cf4781ec4a1ff14ebbe6a45bf2bc'


def record():
    assert verify_export(SOURCE)['valid']
    return bytes.fromhex((SOURCE/'attachment-large-pose-relief.hex.txt').read_text())


def test_measured_source_and_path_order():
    report = review_p4_extension(record(), expected_boot=BOOT, model_path=MODEL)
    assert report['source_positions'] == [2047,2225,1890,2780,1912,2041,2047]
    command = report['next_command']
    assert (command['servo_id'],command['target']) == (14,2711)
    assert command['command_delta_counts'] == -66
    assert command['target_minus_measured_position_counts'] == -69
    assert report['intermediate_name'] == 'P4E'
    start = report['start_tcp_mm']
    assert report['elbow_first_tcp_mm'][0] > start[0]+30
    assert report['elbow_first_tcp_mm'][2] > start[2]+9
    assert report['wrist_first_tcp_mm'][2] < start[2]-4
    assert report['first_step_full_travel']['samples'] == 161
    assert report['independent_progress']['samples'] == 1681
    assert report['first_step_full_travel']['minimum_tcp_z_mm'] == pytest.approx(start[2])
    assert report['elbow_first']['minimum_tcp_z_mm'] == pytest.approx(start[2])
    assert report['first_step_full_travel']['minimum_capsule_clearance_mm'] > 25
    for flag in ('movement_authorized','physical_clearance_verified','hardware_access',
                 'retry_allowed','automatic_wrist_follow_on'):
        assert report[flag] is False


def test_wrong_boot_rejected():
    with pytest.raises(ValueError, match='identity mismatch'):
        review_p4_extension(record(), expected_boot='ab'*16, model_path=MODEL)


def test_truncated_record_rejected():
    with pytest.raises(ValueError, match='framing'):
        review_p4_extension(record()[:-1], expected_boot=BOOT, model_path=MODEL)
