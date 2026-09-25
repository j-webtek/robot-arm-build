"""Synthetic filesystem, synthetic credential, installed-candidate parser only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from test_diagnostic_provisioning_image import library, image
from test_hold_prepared_start import fixture
from rocell.application.first_motion_contract import canonical
from rocell.application.diagnostic_provisioning_image import stage_hold_image, stage_startup_image
from rocell.application.native_provisioning_validator import NativeProvisioningValidator


@pytest.fixture
def hold_validator(tmp_path):
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Native compiler required')
    candidate = root / '.firmware-tools/configured-diagnostic-candidate-r7/RoArm-M3_example'
    exe = tmp_path / 'hold-validator.exe'
    result = subprocess.run([compiler, '-std=c++17', '-I'+str(candidate),
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/validate_hold_provisioning.cpp'), '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return NativeProvisioningValidator(exe, hashlib.sha256(exe.read_bytes()).hexdigest())


def test_hold_staging_preserves_existing_startup_and_rejects_bad_policy(tmp_path, library, hold_validator):
    root = Path(__file__).resolve().parents[2]
    validator = hold_validator
    draft = json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes())
    assert validator(canonical(draft))  # Human-readable draft must be canonicalized before provisioning.
    source = image(library)
    # This permissive validator is used only to seed old synthetic startup files.
    old_policy = canonical(dict(schema='rocell.controller_startup.v1', controller_policy={}, startup_policy={}))
    source, _ = stage_startup_image(source, hashlib.sha256(source).hexdigest(),
        old_policy, b'S'*32, littlefs=library, validate_policy=lambda _: True)
    policy, _, _ = fixture()
    config = dict(schema='rocell.controller_hold.v1', command_id='reviewed-hold',
                  hold_policy=policy, start_port=8081)
    raw = canonical(config)
    def stage(data=source, payload=raw):
        return stage_hold_image(data, hashlib.sha256(data).hexdigest(), payload, b'H'*32,
                                littlefs=library, validate_policy=validator)
    staged, review = stage()
    assert review['schema'] == 'rocell.offline_hold_provisioning_image.v1'
    assert review['existing_entries_preserved'] == 4 and review['remount_verified']
    assert not review['device_modified'] and review['physical_authority'] == 'NONE'
    assert review['policy_sha256'] == hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match='already exist'): stage(staged)
    for payload in (old_policy, b'{}', raw+b' ', raw.replace(b'"servo_id":14',b'"servo_id":12')):
        with pytest.raises(ValueError): stage(payload=payload)
    with pytest.raises(Exception): stage(bytes(len(source)))
    # No real key/image is loaded or stored; the caller's source is immutable.
    assert hashlib.sha256(source).hexdigest() == review['source_sha256']


def test_explicit_replacement_preserves_key_and_rejects_stale_source(library, hold_validator):
    from rocell.application.diagnostic_provisioning_image import replace_hold_policy_image
    root = Path(__file__).resolve().parents[2]
    old = canonical(json.loads((root/'docs/hold-r7-policy-draft.json').read_bytes()))
    new = canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    empty = image(library)
    source, _ = stage_hold_image(empty, hashlib.sha256(empty).hexdigest(), old, b'H'*32,
                                 littlefs=library, validate_policy=hold_validator)
    digest = hashlib.sha256(source).hexdigest()
    def replace(data=source, prior=old, policy=new, expected=digest):
        return replace_hold_policy_image(data, expected, prior, policy,
            littlefs=library, validate_policy=hold_validator)
    candidate, review = replace()
    assert candidate != source and review['remount_verified']
    assert review['schema'] == 'rocell.offline_hold_policy_replacement.v1'
    assert review['existing_entries_preserved'] == 3
    fs = library.LittleFS(context=library.UserContext(buffer=bytearray(candidate)),
        mount=False, block_size=4096, block_count=352, read_size=256, prog_size=256)
    fs.mount()
    try:
        with fs.open('/rocell-hold.key', 'rb') as stream:
            assert stream.read() == b'H'*32
        with fs.open('/rocell-hold.json', 'rb') as stream:
            assert stream.read() == new
    finally:
        fs.unmount()
    for kwargs in ({'expected':'00'*32}, {'prior':new, 'policy':old}, {'policy':old},
                   {'policy':b'{}'}, {'data':empty, 'expected':hashlib.sha256(empty).hexdigest()}):
        with pytest.raises(ValueError):
            replace(**kwargs)
    assert hashlib.sha256(source).hexdigest() == digest
