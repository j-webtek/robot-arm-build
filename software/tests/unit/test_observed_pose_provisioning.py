"""Synthetic flash and storage: exact two-file orchestration, no real device."""
import pytest
import json
import copy
from test_observed_pose_image import fixture
from test_diagnostic_provisioning_image import library
from rocell.application.diagnostic_provisioning_image import replace_observed_pose_image
from rocell.application import startup_provisioning_run as runner
from rocell.application import startup_provisioning_execution as core
from rocell.application import observed_pose_provisioning as profile


@pytest.mark.parametrize('fault', [None, 'app', 'write', 'export'])
def test_observed_provisioning_lifecycle(tmp_path, monkeypatch, library, fault):
    source, stage = fixture(library)
    candidate, image_review = replace_observed_pose_image(source, **stage)
    memory = bytearray(core.FLASH_SIZE)
    memory[core.FS_START:core.FS_END] = source
    monkeypatch.setattr(profile, 'APP_SHA256', core.digest(memory[core.APP_START:core.APP_START+profile.APP_SIZE]))
    monkeypatch.setattr(core, 'PARTITION_SHA256', core.digest(memory[0x8000:0x8c00]))
    if fault == 'app': memory[core.APP_START] = 1
    private = tmp_path/'private'; private.mkdir()
    exports = tmp_path/'exports'; retained = {}
    def save(root, name, data):
        assert name not in retained
        retained[name] = data
        return dict(image_sha256=core.digest(data))
    class Device:
        writes = starts = 0
        closed = False
        def identity(self):
            assert (private/profile.ObservedPoseJournal.NAME).exists()
            return dict(mac=core.MAC, flash_id=0x164020, secure_boot=False,
                flash_encryption=False, secure_download_mode=False)
        def read_flash(self, offset, length): return bytes(memory[offset:offset+length])
        def write_flash_once(self, offset, data):
            assert retained['observed-pose-install-prewrite-source.dpapi'] == source
            self.writes += 1
            memory[offset:offset+len(data)] = data
            if fault == 'write': raise OSError('Synthetic uncertain write')
            return True
        def startup_once(self):
            assert list(exports.glob('*/attachment-provisioning-result.json'))
            self.starts += 1
        def close(self): self.closed = True
    if fault == 'export':
        original = runner.WizardDiagnosticExporter.export
        def fail(self, *a, **kw):
            if 'provisioning-result.json' in kw.get('attachments', {}): raise OSError('Synthetic export failure')
            return original(self, *a, **kw)
        monkeypatch.setattr(runner.WizardDiagnosticExporter, 'export', fail)
    device = Device()
    args = dict(source=source, source_sha256=core.digest(source), candidate=candidate,
        candidate_sha256=core.digest(candidate), policy=dict(hold=stage['hold'], pair=stage['pair']),
        previous_policy=dict(hold=stage['previous_hold'], pair=stage['previous_pair']),
        key=None, littlefs=library, validate_policy=stage['validate_pair'],
        validate_existing_policy=stage['validate_hold'], private_root=private, export_root=exports,
        device=device, save_private_image=save, startup_authorized=True)
    if fault:
        with pytest.raises((ValueError, OSError)): runner._run_provisioning('observed-pose', **args)
        assert device.starts == 0
        assert device.writes == (0 if fault == 'app' else 1)
    else:
        result = runner._run_provisioning('observed-pose', **args)
        assert result['status'] == 'FLASH_READBACK_VERIFIED'
        assert device.writes == device.starts == 1
        assert result['schema'] == 'rocell.observed-pose_provisioning_result.v1'
        assert not result['configuration_loaded'] and not result['motion_authorized']
        from rocell.application import observed_pose_installation as verification
        monkeypatch.setattr(verification, 'SOURCE_SHA', core.digest(source))
        monkeypatch.setattr(verification, 'APP_SHA256', profile.APP_SHA256)
        read = lambda ident, name: json.loads((exports/ident/name).read_bytes())
        final = read(result['export_id'], 'attachment-provisioning-run.json')
        plan = read(final['plan_export_id'], 'attachment-provisioning-review.json')
        written = read(final['verified_write_export_id'], 'attachment-provisioning-result.json')
        rows = [json.loads(line) for line in (private/profile.ObservedPoseJournal.NAME).read_bytes().splitlines()]
        staged = dict(review=image_review)
        assert verification.validate_installation_chain(staged, final, plan, written, rows) == core.digest(candidate)
        for fault_name in ('candidate','hold','app','repeat','write','startup','protected'):
            s,f,p,w,r = copy.deepcopy((staged,final,plan,written,rows))
            if fault_name=='candidate': s['review']['candidate_sha256']='a'*64
            if fault_name=='hold': p['hold_policy_sha256']='b'*64
            if fault_name=='app': r[0]['app_sha256']='c'*64
            if fault_name=='repeat': r.append(r[-1])
            if fault_name=='write': w['candidate_sha256']='d'*64
            if fault_name=='startup': f['startup_attempted']=False
            if fault_name=='protected': r[3]['protected_regions_unchanged']=False
            with pytest.raises(ValueError): verification.validate_installation_chain(s,f,p,w,r)
    assert device.closed
    with pytest.raises(ValueError, match='Existing provisioning attempt'):
        runner._run_provisioning('observed-pose', **args)
