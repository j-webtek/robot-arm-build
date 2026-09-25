"""Offline installer binding tests; no serial, reset or flash access."""
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def deployment():
    path = Path(__file__).resolve().parents[2] / 'scripts/deploy_reviewed_diagnostic_app.py'
    spec = importlib.util.spec_from_file_location('reviewed_deployment_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r69_retry_retained_failure_binding(deployment, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    assert deployment.second_r69_journal(root, 69) == 'app-r69-attempt2-deployment-events.jsonl'
    for revision in (68, True, '69'):
        with pytest.raises(ValueError):
            deployment.second_r69_journal(root, revision)
    from rocell.application import product_ghost_export_review as exports
    monkeypatch.setattr(exports, '_read', lambda *args: ({'app_write_attempted': True}, 'invalid'))
    with pytest.raises(ValueError, match='Pinned r69 prewrite failure differs'):
        deployment.second_r69_journal(root, 69)


def fake_artifacts(module, monkeypatch, *, wrong_length=False):
    seen = []
    def checked(path, expected):
        seen.append((path, expected))
        if path.name.startswith('flash-pair-'):
            assert expected == module.BACKUP_HASH
            return b'b' * 4194304
        if path.name == 'original-app0-slot.bin':
            assert expected == module.RECOVERY_HASH
            return b'r' * 1310720
        if 'candidate-r6--' in str(path):
            assert expected == module.R6_HASH
            return b'6' * (1081871 if wrong_length else 1081872)
        if 'candidate-r7--' in str(path):
            assert expected == module.R7_HASH
            return b'7' * 1070912
        if 'candidate-r10--' in str(path):
            assert expected == module.R10_HASH
            return b'x' * 1103808
        if 'candidate-r11--' in str(path):
            assert expected == module.R11_HASH
            return b'y' * 1103872
        if 'candidate-r12--' in str(path):
            assert expected == module.R12_HASH
            return b'z' * 1103920
        if 'candidate-r13--' in str(path):
            assert expected == module.R13_HASH
            return b'w' * 1104048
        if 'candidate-r14--' in str(path):
            assert expected == module.R14_HASH
            return b'v' * 1106528
        if 'candidate-r16--' in str(path):
            assert expected == module.R16_HASH
            return b'u' * 1120240
        assert 'candidate-r3--' in str(path) and expected == module.R3_HASH
        return b'3' * 1076384
    monkeypatch.setattr(module, 'checked', checked)
    return seen


def test_exact_revision_edge_and_separate_journal(deployment):
    assert deployment.revision_spec(50) == (deployment.R50_HASH, 1158736, 49, 'app-r50-deployment-events.jsonl')
    assert deployment.revision_spec(49) == (deployment.R49_HASH, 1158528, 48, 'app-r49-deployment-events.jsonl')
    assert deployment.revision_spec(48) == (deployment.R48_HASH, 1158256, 47, 'app-r48-deployment-events.jsonl')
    assert deployment.revision_spec(47) == (deployment.R47_HASH, 1157936, 46, 'app-r47-deployment-events.jsonl')
    assert deployment.revision_spec(46) == (deployment.R46_HASH, 1157936, 45, 'app-r46-deployment-events.jsonl')
    assert deployment.revision_spec(45) == (deployment.R45_HASH, 1157616, 44, 'app-r45-deployment-events.jsonl')
    assert deployment.revision_spec(44) == (deployment.R44_HASH, 1157616, 43, 'app-r44-deployment-events.jsonl')
    assert deployment.revision_spec(43) == (deployment.R43_HASH, 1156992, 42, 'app-r43-deployment-events.jsonl')
    assert deployment.revision_spec(42) == (deployment.R42_HASH, 1156992, 41, 'app-r42-deployment-events.jsonl')
    assert deployment.revision_spec(41) == (deployment.R41_HASH, 1156992, 40, 'app-r41-deployment-events.jsonl')
    assert deployment.revision_spec(40) == (deployment.R40_HASH, 1156384, 39, 'app-r40-deployment-events.jsonl')
    assert deployment.revision_spec(39) == (deployment.R39_HASH, 1156384, 38, 'app-r39-deployment-events.jsonl')
    from rocell.application.held_pair_installation_evidence import _profile
    assert _profile(50)[:3] == (deployment.R50_HASH, 1158736, 'app-r50-deployment-events.jsonl')
    assert _profile(49)[:3] == (deployment.R49_HASH, 1158528, 'app-r49-deployment-events.jsonl')
    assert _profile(48)[:3] == (deployment.R48_HASH, 1158256, 'app-r48-deployment-events.jsonl')
    assert _profile(47)[:3] == (deployment.R47_HASH, 1157936, 'app-r47-deployment-events.jsonl')
    assert _profile(46)[:3] == (deployment.R46_HASH, 1157936, 'app-r46-deployment-events.jsonl')
    assert _profile(45)[:3] == (deployment.R45_HASH, 1157616, 'app-r45-deployment-events.jsonl')
    assert _profile(44)[:3] == (deployment.R44_HASH, 1157616, 'app-r44-deployment-events.jsonl')
    assert _profile(43)[:3] == (deployment.R43_HASH, 1156992, 'app-r43-deployment-events.jsonl')
    assert _profile(42)[:3] == (deployment.R42_HASH, 1156992, 'app-r42-attempt2-deployment-events.jsonl')
    assert _profile(41)[:3] == (deployment.R41_HASH, 1156992, 'app-r41-deployment-events.jsonl')
    assert _profile(40)[:3] == (deployment.R40_HASH, 1156384, 'app-r40-deployment-events.jsonl')
    assert _profile(39)[:3] == (deployment.R39_HASH, 1156384, 'app-r39-deployment-events.jsonl')
    assert deployment.revision_spec(38) == (deployment.R38_HASH, 1156048, 37, 'app-r38-deployment-events.jsonl')
    assert deployment.revision_spec(37) == (deployment.R37_HASH, 1156080, 36, 'app-r37-deployment-events.jsonl')
    assert deployment.revision_spec(36) == (deployment.R36_HASH, 1155600, 35, 'app-r36-deployment-events.jsonl')
    assert deployment.revision_spec(35) == (deployment.R35_HASH, 1155456, 34, 'app-r35-deployment-events.jsonl')
    assert deployment.revision_spec(34) == (deployment.R34_HASH, 1155184, 33, 'app-r34-deployment-events.jsonl')
    assert deployment.revision_spec(33) == (deployment.R33_HASH, 1154048, 31, 'app-r33-deployment-events.jsonl')
    assert deployment.revision_spec(31) == (deployment.R31_HASH, 1150592, 29, 'app-r31-deployment-events.jsonl')
    from rocell.application.held_pair_installation_evidence import _profile
    assert _profile(34)[:3] == (deployment.R34_HASH, 1155184, 'app-r34-deployment-events.jsonl')
    assert _profile(33)[:3] == (deployment.R33_HASH, 1154048, 'app-r33-deployment-events.jsonl')
    with pytest.raises(ValueError): deployment.revision_spec(32)
    assert _profile(31)[:3] == (deployment.R31_HASH, 1150592, 'app-r31-deployment-events.jsonl')
    with pytest.raises(ValueError): deployment.revision_spec(30)
    assert deployment.revision_spec(29) == (deployment.R29_HASH, 1146336, 28, 'app-r29-deployment-events.jsonl')
    assert deployment.revision_spec(28) == (deployment.R28_HASH, 1145728, 27, 'app-r28-deployment-events.jsonl')
    assert deployment.revision_spec(27) == (deployment.R27_HASH, 1145280, 26, 'app-r27-deployment-events.jsonl')
    assert deployment.revision_spec(26) == (deployment.R26_HASH, 1143376, 25, 'app-r26-deployment-events.jsonl')
    assert deployment.revision_spec(23) == (deployment.R23_HASH, 1141360, 22, 'app-r23-deployment-events.jsonl')
    assert deployment.revision_spec(6) == (deployment.R6_HASH, 1081872, 3, 'app-r6-deployment-events.jsonl')
    assert deployment.revision_spec(7) == (deployment.R7_HASH, 1070912, 6, 'app-r7-deployment-events.jsonl')
    assert deployment.revision_spec(10) == (deployment.R10_HASH, 1103808, 7, 'app-r10-deployment-events.jsonl')
    assert len({deployment.revision_spec(rev)[3] for rev in (2, 3, 6, 7)}) == 4
    assert deployment.revision_spec(11) == (deployment.R11_HASH, 1103872, 10, 'app-r11-deployment-events.jsonl')
    assert deployment.revision_spec(12) == (deployment.R12_HASH, 1103920, 11, 'app-r12-deployment-events.jsonl')
    assert deployment.revision_spec(13) == (deployment.R13_HASH, 1104048, 12, 'app-r13-deployment-events.jsonl')
    assert deployment.revision_spec(14) == (deployment.R14_HASH, 1106528, 13, 'app-r14-deployment-events.jsonl')
    assert deployment.revision_spec(16) == (deployment.R16_HASH, 1120240, 14, 'app-r16-deployment-events.jsonl')
    assert deployment.revision_spec(17) == (deployment.R17_HASH, 1122416, 16, 'app-r17-deployment-events.jsonl')
    assert deployment.revision_spec(19) == (deployment.R19_HASH, 1122896, 17, 'app-r19-deployment-events.jsonl')
    assert deployment.revision_spec(20) == (deployment.R20_HASH, 1127072, 19, 'app-r20-deployment-events.jsonl')
    assert deployment.revision_spec(21) == (deployment.R21_HASH, 1127424, 20, 'app-r21-deployment-events.jsonl')
    for rev in (True, '6', 4, 5, 8, 9, 15, 18, -1):
        with pytest.raises(ValueError): deployment.revision_spec(rev)


@pytest.mark.parametrize('revision', [True, 26, 28, '27'])
def test_second_attempt_cannot_select_another_revision(deployment, tmp_path, revision):
    with pytest.raises(ValueError, match='r27 only'):
        deployment.second_r27_journal(tmp_path, revision)


def test_second_attempt_requires_unchanged_first_failure(deployment, tmp_path):
    private = tmp_path / 'private-backups/controller-20260918-session1'
    private.mkdir(parents=True)
    (private / 'app-r27-deployment-events.jsonl').write_bytes(b'altered')
    with pytest.raises(ValueError, match='hash mismatch'):
        deployment.second_r27_journal(tmp_path, 27)
    assert len(list(private.iterdir())) == 1


def test_second_attempt_uses_exact_separate_journal(deployment, tmp_path, monkeypatch):
    from rocell.application import held_pair_installation_evidence as evidence
    from rocell.application import product_ghost_export_review as reader
    monkeypatch.setattr(deployment, 'checked', lambda *args: b'pinned')
    monkeypatch.setattr(evidence, 'review_pair_installation', lambda *args, **kwargs: {})
    recovery = dict(status='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED', flash_written=False,
                    servo_command_sent=False, settings_written=False,
                    failed_journal_sha256='cd7f3ff5750b08af350afbf7e41f2e92c828f2e991181ef48578050591242042')
    monkeypatch.setattr(reader, '_read', lambda *args: (recovery, None))
    assert deployment.second_r27_journal(tmp_path, 27) == 'app-r27-attempt2-deployment-events.jsonl'
    assert evidence._profile(27)[2] == 'app-r27-attempt2-deployment-events.jsonl'
    recovery['flash_written'] = True
    with pytest.raises(ValueError, match='recovery evidence'):
        deployment.second_r27_journal(tmp_path, 27)


def test_r42_second_attempt_requires_exact_recovery(deployment, tmp_path, monkeypatch):
    from rocell.application import held_pair_installation_evidence as evidence
    from rocell.application import product_ghost_export_review as reader
    monkeypatch.setattr(deployment, 'checked', lambda *args: b'pinned')
    monkeypatch.setattr(evidence, 'review_pair_installation', lambda *args, **kwargs: {})
    recovery = dict(schema='rocell.r42_prewrite_recovery_r41_startup.v1',
        status='ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED',
        failed_journal_sha256='30abc7feff8027500a38c712b3e239be59cb81ae438ca6139495737dd3bde8ea',
        servo_command_sent=False,flash_written=False,settings_written=False,retry_allowed=False)
    monkeypatch.setattr(reader, '_read', lambda *args: (recovery, None))
    assert deployment.second_r42_journal(tmp_path, 42) == 'app-r42-attempt2-deployment-events.jsonl'
    with pytest.raises(ValueError, match='r42 only'):
        deployment.second_r42_journal(tmp_path, 41)
    recovery['retry_allowed'] = True
    with pytest.raises(ValueError, match='recovery evidence'):
        deployment.second_r42_journal(tmp_path, 42)


def test_longer_reset_uses_one_vendor_strategy_without_connecting(deployment, monkeypatch):
    from types import ModuleType, SimpleNamespace
    reset = ModuleType('esptool.reset')
    reset.DEFAULT_RESET_DELAY = 0.05
    reset.ClassicReset = lambda port, delay: (port, delay)
    monkeypatch.setitem(sys.modules, 'esptool.reset', reset)
    class FakeROM:
        def __init__(self, port, baud): self._port = port; assert baud == 115200
    rom = deployment.longer_reset_rom(SimpleNamespace(ESP32ROM=FakeROM), 'fake-port')
    assert rom._construct_reset_strategy_sequence('default_reset') == (('fake-port', 0.55),)
    with pytest.raises(ValueError): rom._construct_reset_strategy_sequence('no_reset')


def test_checked_bytes_and_fixed_stream(deployment, tmp_path):
    path = tmp_path / 'app.bin'; path.write_bytes(b'approved')
    image = deployment.checked(path, hashlib.sha256(b'approved').hexdigest())
    path.write_bytes(b'replaced')
    with deployment.verified_stream(image, path) as stream:
        assert stream.read() == b'approved' and stream.name == str(path)
    with pytest.raises(ValueError): deployment.checked(path, hashlib.sha256(image).hexdigest())


def test_r11_preserves_pair_filesystem_and_requires_r10(deployment,tmp_path,monkeypatch):
    fake_artifacts(deployment,monkeypatch)
    image=b'p'*0x160000
    monkeypatch.setattr(deployment,'pair_settings_filesystem',lambda *args:image)
    def older(*args):raise AssertionError('Older filesystem must not be selected')
    monkeypatch.setattr(deployment,'supported_pose_filesystem',older)
    result=deployment.preflight(tmp_path,11)
    assert result['previous']==b'x'*1103808
    assert result['filesystem_sha256']==hashlib.sha256(image).hexdigest()
    assert result['journal_name']=='app-r11-deployment-events.jsonl'
    def reject(*args):raise ValueError('Invalid retained pair evidence')
    monkeypatch.setattr(deployment,'pair_settings_filesystem',reject)
    with pytest.raises(ValueError):deployment.preflight(tmp_path,11)


def test_r16_requires_r14_and_preserves_pair_filesystem(deployment,tmp_path,monkeypatch):
    fake_artifacts(deployment,monkeypatch)
    image=b'p'*0x160000
    monkeypatch.setattr(deployment,'pair_settings_filesystem',lambda *args:image)
    result=deployment.preflight(tmp_path,16)
    assert result['previous']==b'v'*1106528
    assert result['image']==b'u'*1120240
    assert result['filesystem_sha256']==hashlib.sha256(image).hexdigest()
    assert result['journal_name']=='app-r16-deployment-events.jsonl'
    assert not result['private'].exists()
    result['private'].mkdir(parents=True)
    (result['private']/result['journal_name']).write_text('reserved')
    with pytest.raises(ValueError):deployment.preflight(tmp_path,16)


def test_preflight_reserves_nothing_and_rejects_existing_journal(deployment, tmp_path, monkeypatch):
    seen = fake_artifacts(deployment, monkeypatch)
    result = deployment.preflight(tmp_path, 6)
    assert len(seen) == 5 and not result['private'].exists()
    result['private'].mkdir(parents=True)
    journal = result['private'] / result['journal_name']; journal.write_text('existing')
    with pytest.raises(ValueError, match='reserved'): deployment.preflight(tmp_path, 6)
    assert journal.read_text() == 'existing'


def test_r13_requires_r12_and_retains_pair_settings(deployment, tmp_path, monkeypatch):
    seen = fake_artifacts(deployment, monkeypatch)
    filesystem = b'p' * 0x160000
    monkeypatch.setattr(deployment, 'pair_settings_filesystem', lambda *args: filesystem)
    result = deployment.preflight(tmp_path, 13)
    assert result['previous'] == b'z' * 1103920
    assert result['image'] == b'w' * 1104048
    assert result['filesystem_sha256'] == hashlib.sha256(filesystem).hexdigest()
    assert result['journal_name'] == 'app-r13-deployment-events.jsonl'
    assert seen[-1][1] == deployment.R12_HASH
    assert not result['private'].exists()
    result['private'].mkdir(parents=True)
    journal = result['private'] / result['journal_name']
    journal.write_text('reserved')
    with pytest.raises(ValueError, match='reserved'):
        deployment.preflight(tmp_path, 13)
    assert journal.read_text() == 'reserved'


def test_wrong_image_length_rejected(deployment, tmp_path, monkeypatch):
    fake_artifacts(deployment, monkeypatch, wrong_length=True)
    with pytest.raises(ValueError, match='sizes'): deployment.preflight(tmp_path, 6)


@pytest.mark.parametrize('revision', [6, 10, 11, 12, 13, 14])
def test_preflight_cli_never_imports_device_libraries(deployment, monkeypatch, capsys, revision):
    fake_artifacts(deployment, monkeypatch)
    monkeypatch.setattr(deployment, 'supported_pose_filesystem', lambda *args: b'f' * 0x160000)
    monkeypatch.setattr(deployment, 'pair_settings_filesystem', lambda *args: b'p' * 0x160000)
    # Use a fresh nonexisting local root through __file__; no filesystem writes.
    monkeypatch.setattr(deployment, '__file__', str(Path('offline-fixture/scripts/deploy.py').resolve()))
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name.split('.')[0] not in ('serial', 'esptool')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(sys, 'argv', ['deploy.py', '--revision', str(revision), '--preflight-only'])
    deployment.main()
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'LOCAL_PREFLIGHT_VERIFIED'
    assert result['hardware_access'] is False and result['journal_reserved'] is False
    assert result['deployment_authorized'] is False


def test_r10_uses_latest_filesystem_and_r7(deployment, tmp_path, monkeypatch):
    fake_artifacts(deployment, monkeypatch)
    monkeypatch.setattr(deployment, 'provisioned_filesystem', lambda *args: pytest.fail('Stale r6 image'))
    monkeypatch.setattr(deployment, 'supported_pose_filesystem', lambda *args: b'f' * 0x160000)
    result = deployment.preflight(tmp_path, 10)
    assert result['previous'] == b'7' * 1070912
    assert result['filesystem_sha256'] == hashlib.sha256(b'f' * 0x160000).hexdigest()
    assert result['journal_name'] == 'app-r10-deployment-events.jsonl'
    assert not result['private'].exists()


def test_supported_pose_receipts_before_decryption(deployment, tmp_path, monkeypatch):
    from rocell.application import product_ghost_export_review as reader
    from rocell.providers.windows import diagnostic_image_store as store
    write = dict(schema='rocell.hold_provisioning_result.v1',
        candidate_sha256=deployment.SUPPORTED_FS_HASH,
        source_sha256='0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b',
        plan_export_id='wizard-20260918T212222293772Z-63b5b72a4b0a4cf19da8721aeed006fc',
        configuration_loaded=False, motion_authorized=False,
        protected_regions_unchanged=True, recovery_preserved=True, retry_allowed=False,
        startup_attempted=False, status='FLASH_READBACK_VERIFIED')
    run = dict(write, startup_attempted=True, application_health_verified=False,
        verified_write_export_id='wizard-20260918T213520661096Z-ba47bd4a42bf42a2ba60007158b265e1')
    image = b'f' * 0x160000
    monkeypatch.setattr(deployment, 'SUPPORTED_FS_HASH', hashlib.sha256(image).hexdigest())
    write['candidate_sha256'] = run['candidate_sha256'] = deployment.SUPPORTED_FS_HASH
    monkeypatch.setattr(reader, '_read', lambda root, ident, name:
        (write if name == 'attachment-provisioning-result.json' else run, 'unused'))
    loads = []
    def load(path): loads.append(path); return image
    monkeypatch.setattr(store, 'load_image', load)
    assert deployment.supported_pose_filesystem(tmp_path, tmp_path) == image
    assert loads[0].name == 'hold-r7-supported-replacement-candidate.dpapi'
    run['verified_write_export_id'] = 'wrong'
    with pytest.raises(ValueError, match='receipt differs'):
        deployment.supported_pose_filesystem(tmp_path, tmp_path)
    assert len(loads) == 1
    run['verified_write_export_id'] = 'wizard-20260918T213520661096Z-ba47bd4a42bf42a2ba60007158b265e1'
    monkeypatch.setattr(store, 'load_image', lambda path: b'wrong')
    with pytest.raises(ValueError, match='filesystem differs'):
        deployment.supported_pose_filesystem(tmp_path, tmp_path)


def test_r7_requires_provisioned_filesystem_and_r6_predecessor(deployment, tmp_path, monkeypatch):
    seen = fake_artifacts(deployment, monkeypatch)
    image = b'f' * 0x160000
    calls = []
    def retained(root, private):
        calls.append((root, private))
        return image
    monkeypatch.setattr(deployment, 'provisioned_filesystem', retained)
    result = deployment.preflight(tmp_path, 7)
    assert len(calls) == 1 and len(seen) == 5
    assert result['previous'] == b'6' * 1081872
    assert result['filesystem_sha256'] == hashlib.sha256(image).hexdigest()
    assert result['filesystem_md5'] == hashlib.md5(image).hexdigest()
    assert not result['private'].exists()
    def rejected(*args): raise ValueError('bad filesystem')
    monkeypatch.setattr(deployment, 'provisioned_filesystem', rejected)
    with pytest.raises(ValueError, match='bad filesystem'):
        deployment.preflight(tmp_path, 7)


def test_provisioning_receipt_and_image_rejection(deployment, tmp_path, monkeypatch):
    from rocell.application import product_ghost_export_review as reader
    from rocell.providers.windows import diagnostic_image_store as store
    image = b'f' * 0x160000
    monkeypatch.setattr(deployment, 'R6_FS_HASH', hashlib.sha256(image).hexdigest())
    report = dict(schema='rocell.startup_provisioning_result.v1',
        candidate_sha256=deployment.R6_FS_HASH, source_sha256=deployment.R6_FS_SOURCE,
        plan_export_id='wizard-20260918T160845323205Z-10ea70dd642141d7bb0c1b931c45b865',
        configuration_loaded=False, motion_authorized=False, protected_regions_unchanged=True,
        recovery_preserved=True, retry_allowed=False, startup_attempted=False, status='FLASH_READBACK_VERIFIED')
    monkeypatch.setattr(reader, '_read', lambda *args: (report, 'unused'))
    loads = []
    def load(path): loads.append(path); return image
    monkeypatch.setattr(store, 'load_image', load)
    assert deployment.provisioned_filesystem(tmp_path, tmp_path) == image
    report['protected_regions_unchanged'] = False
    with pytest.raises(ValueError, match='result differs'):
        deployment.provisioned_filesystem(tmp_path, tmp_path)
    assert len(loads) == 1
    report['protected_regions_unchanged'] = True
    monkeypatch.setattr(store, 'load_image', lambda path: b'x' * 0x160000)
    with pytest.raises(ValueError, match='filesystem differs'):
        deployment.provisioned_filesystem(tmp_path, tmp_path)


@pytest.mark.parametrize('failed_check', [None, 0, 1, 2])
def test_prewrite_rejects_changed_app_partition_or_filesystem(deployment, failed_check):
    prepared = dict(previous=b'previous', backup=b'b'*0x400000,
                    filesystem_md5=hashlib.md5(b'provisioned').hexdigest())
    expected = [hashlib.md5(prepared['previous']).hexdigest(),
                hashlib.md5(prepared['backup'][0x8000:0x8c00]).hexdigest(),
                prepared['filesystem_md5']]
    class Stub:
        reads = []
        def flash_md5sum(self, start, size):
            index = len(self.reads); self.reads.append((start, size))
            return 'bad' if index == failed_check else expected[index]
    stub = Stub()
    if failed_check is None:
        deployment.verify_installed_predecessor(stub, prepared)
        assert len(stub.reads) == 3
    else:
        with pytest.raises(ValueError): deployment.verify_installed_predecessor(stub, prepared)
        assert len(stub.reads) == failed_check + 1
