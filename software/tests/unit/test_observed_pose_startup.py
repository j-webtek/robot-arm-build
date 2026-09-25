"""Reject app-only health evidence for the new settings; all boundaries synthetic."""
import copy
import subprocess
import sys
from pathlib import Path
import pytest
from rocell.application import observed_pose_installation as module
from rocell.application import supported_recovery_installation as startup_module


@pytest.mark.parametrize('fault', [None, 'missing', 'other_install', 'changed_hash'])
def test_exact_startup_settings_link(tmp_path, monkeypatch, fault):
    settings = dict(installation_export='filesystem-run', candidate_sha256='a'*64)
    monkeypatch.setattr(module, 'review_observed_installation', lambda *a, **kw: settings)
    def startup(*a, **kw):
        assert kw['revision']==21
        return dict(expected_boot='11'*16, motion_authorized=False)
    monkeypatch.setattr(startup_module, 'review_recovery_startup', startup)
    report = dict(observed_pose_installation=copy.deepcopy(settings))
    if fault=='missing': report.clear()
    if fault=='other_install': report['observed_pose_installation']['installation_export']='other'
    if fault=='changed_hash': report['observed_pose_installation']['candidate_sha256']='b'*64
    monkeypatch.setattr(module, '_read', lambda *a: (report, 'c'*64))
    def run():
        return module.review_observed_startup(tmp_path, startup_export='startup',
            stage_export='stage', installation_export='filesystem-run')
    if fault:
        with pytest.raises(ValueError, match='not linked'): run()
    else:
        result=run()
        assert not result['recovery_authorized'] and not result['current_pose_verified']


@pytest.mark.parametrize('arguments', [
    ['--revision','21','--observed-pose-stage-export','missing'],
    ['--revision','20','--observed-pose-stage-export','missing','--observed-pose-installation-export','missing']])
def test_bad_cli_combination_stops_before_evidence_or_network(arguments):
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([sys.executable,str(root/'scripts/observe_r10_startup.py'),*arguments],
        capture_output=True,text=True,timeout=10)
    assert result.returncode==2
    assert 'error:' in result.stderr and 'Traceback' not in result.stderr
