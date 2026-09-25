"""Offline checks for the one-use r52 session entry point."""
import importlib.util
from pathlib import Path

import pytest

from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign


@pytest.fixture
def cli(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('ghost_transition_cli_test',
                                              scripts/'run_ghost_pair_transition_session.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault',[None,'plan','reserved','other_session','read_capture','pose_reserved','index'])
def test_preflight_binds_frozen_plan_and_unused_boot(cli,tmp_path,monkeypatch,fault):
    boot='ab'*16
    seen=[]

    def startup(*args,**kwargs):
        seen.append(kwargs['revision'])
        return {'expected_boot':boot,'address':'127.0.0.1'}

    monkeypatch.setattr(cli,'review_recovery_startup',startup)
    saved=plan_ghost_pair_transition_campaign()
    if fault=='plan':
        saved=dict(saved,plan_sha256='00'*32)
    monkeypatch.setattr(cli,'_read',lambda *args:(saved,'verified'))
    exports=tmp_path/'runs/wizard-exports'
    exports.mkdir(parents=True)
    if fault=='reserved':
        (exports/f'r53-session-1-capture-{boot}.json').write_text('{}')
    if fault=='other_session':
        (exports/f'r53-session-2-capture-{boot}.json').write_text('{}')
    if fault=='read_capture':
        (exports/f'r53-capture-{boot}.json').write_text('{}')
    if fault=='pose_reserved':
        (exports/f'pose-observation-{boot}.json').write_text('{}')
    if fault:
        with pytest.raises(ValueError):
            cli.preflight(tmp_path,'startup',4 if fault=='index' else 1)
    else:
        binding,root,claim=cli.preflight(tmp_path,'startup',1)
        assert binding['transition_plan']==plan_ghost_pair_transition_campaign()
        assert root==exports
        assert claim.name==f'r53-session-1-capture-{boot}.json'
    if fault!='index':
        assert seen==[53]


def test_r52_installation_edge_matches_reviewed_image():
    from rocell.application.held_pair_installation_evidence import _profile
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    spec=importlib.util.spec_from_file_location('ghost_transition_deployment_test',
                                              scripts/'deploy_reviewed_diagnostic_app.py')
    deployment=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    revision_spec,R52_HASH=deployment.revision_spec,deployment.R52_HASH

    assert revision_spec(52)==(R52_HASH,1159328,51,
                               'app-r52-deployment-events.jsonl')
    assert _profile(52)==(R52_HASH,1159328,
        'app-r52-deployment-events.jsonl',
        'wizard-20260921T095000154047Z-7509bcd94555463a86eae274d9e8b6f0')


def test_r53_installation_edge_matches_reviewed_image():
    from rocell.application.held_pair_installation_evidence import _profile
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    spec=importlib.util.spec_from_file_location('ghost_window_deployment_test',
                                              scripts/'deploy_reviewed_diagnostic_app.py')
    deployment=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    assert deployment.revision_spec(53)==(deployment.R53_HASH,1159392,52,
                                           'app-r53-deployment-events.jsonl')
    assert _profile(53)==(deployment.R53_HASH,1159392,
        'app-r53-deployment-events.jsonl',
        'wizard-20260921T192611219874Z-692de670df434dc5a509ea921aa22b0a')
