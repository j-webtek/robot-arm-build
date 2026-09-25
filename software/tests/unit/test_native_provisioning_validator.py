import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.native_provisioning_validator import NativeProvisioningValidator


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Host compiler required')
    root = Path(__file__).resolve().parents[2]
    executable = tmp_path_factory.mktemp('native-policy') / 'validate.exe'
    subprocess.run([compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/validate_provisioning_policy.cpp'),
        '-o', str(executable)], check=True, capture_output=True, timeout=60)
    return executable, hashlib.sha256(executable.read_bytes()).hexdigest()


def policy():
    # Synthetic policy only: not approved for an actual arm pose.
    return dict(schema='rocell.controller_diagnostics.v1', policy_id='offline-test',
        conversion_version='roarm-m3-example20260115-elbow-v1', start_port=8081,
        challenge_lifetime_us=30000000,
        elbow_bounds=dict(minimum_rad=1.6, maximum_rad=1.9, maximum_speed=40,
                          maximum_acceleration=1),
        whole_arm_policy=dict(joints=[[1900, 2200]] * 7, tracking_tolerance=2,
            maximum_pair_us=100, maximum_scan_us=1000, maximum_age_us=1000))


def test_actual_parser_acceptance(native):
    assert NativeProvisioningValidator(*native)(canonical(policy()))


@pytest.mark.parametrize('data', [b'{}', b'', b'x' * 4097,
    b'{"schema":"a","schema":"a"}'])
def test_invalid(native, data):
    assert not NativeProvisioningValidator(*native)(data)


def test_wrong_conversion_and_limits(native):
    validator = NativeProvisioningValidator(*native)
    data = policy()
    data['conversion_version'] = 'test-reference'
    assert not validator(canonical(data))


def test_no_windows_text_eof_truncation(native):
    assert not NativeProvisioningValidator(*native)(canonical(policy()) + b'\x1aignored')


def test_reversed_joint_window(native):
    data = policy()
    data['whole_arm_policy']['joints'][0] = [2200, 1900]
    assert not NativeProvisioningValidator(*native)(canonical(data))


def test_executable_identity(native):
    with pytest.raises(ValueError, match='identity changed'):
        NativeProvisioningValidator(native[0], '0' * 64)(canonical(policy()))
