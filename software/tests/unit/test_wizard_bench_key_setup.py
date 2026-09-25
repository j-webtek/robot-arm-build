"""Wizard setup integration with isolated host directories; no hardware."""

import pytest
import os
from pathlib import Path
from rocell.application import wizard_bench_key_setup as setup
from rocell.providers.windows import bench_review_key as key_store
from rocell.application.wizard_worker import run
from rocell.application.wizard_actions import ACTION_BY_ID,validate_action_input


def test_action_requires_confirmation_and_rejects_uploaded_key_or_path():
    action = ACTION_BY_ID['bench_review_key_setup']
    assert not action.view(mode='simulation',busy=False)['enabled']
    for values in ({},{'operation':'PROVISION','acknowledge':False},
                   {'operation':'PROVISION','acknowledge':True,'key':'x'},
                   {'operation':'CHECK','acknowledge':True,'path':'x'}):
        with pytest.raises(ValueError): validate_action_input(action,values)


def test_check_is_read_only_and_public_worker_routes_setup(tmp_path,monkeypatch):
    base = tmp_path/'private-host'
    base.mkdir()
    workspace = tmp_path/'workspace'
    workspace.mkdir()
    monkeypatch.setattr(key_store,'_local_base',lambda:base)
    monkeypatch.setattr(setup,'provision_bench_review_key',lambda *a:pytest.fail('CHECK must not provision'))
    result = run(workspace,'bench_review_key_setup',{'operation':'CHECK','acknowledge':True},'cell')
    report = result['steps'][0]['report']
    assert report['status']=='KEY_NOT_CONFIGURED' and report['motion_approved'] is False
    assert list(base.iterdir())==[]


def test_workspace_key_location_refused(tmp_path,monkeypatch):
    monkeypatch.setattr(key_store,'_local_base',lambda:tmp_path)
    with pytest.raises(ValueError):
        setup.run_key_setup(tmp_path,{'operation':'PROVISION','acknowledge':True})


@pytest.mark.parametrize('destination', ['virtualized', 'outside', 'workspace'])
def test_virtualized_private_folder_stays_local_and_outside_workspace(tmp_path, monkeypatch, destination):
    base = tmp_path/'host'
    base.mkdir()
    workspace = base/'workspace'
    workspace.mkdir()
    logical = base/'RoCell'
    logical.mkdir()
    target = {'virtualized':base/'package-cache'/'RoCell',
              'outside':tmp_path/'outside', 'workspace':workspace/'RoCell'}[destination]
    target.mkdir(parents=True)
    original_resolve = Path.resolve
    monkeypatch.setattr(key_store, '_local_base', lambda: base)
    def resolve(path, *args, **kwargs):
        return target if path == logical else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    if destination != 'virtualized':
        with pytest.raises(ValueError, match='escaped'):
            key_store.host_key_root(workspace, create=True)
    else:
        root = key_store.host_key_root(workspace, create=True)
        assert root == target/'private'/'bench-review-v1'
        assert key_store.host_key_root(workspace) == root
        assert list(root.iterdir()) == []  # Directory setup never creates a key.


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI integration')
def test_wizard_provision_then_check_keeps_same_protected_key(tmp_path,monkeypatch):
    base,workspace = tmp_path/'host',tmp_path/'workspace'
    base.mkdir()
    workspace.mkdir()
    monkeypatch.setattr(key_store,'_local_base',lambda:base)
    def invoke(operation):
        return run(workspace,'bench_review_key_setup',
                   {'operation':operation,'acknowledge':True},'cell')['steps'][0]['report']
    report = invoke('PROVISION')
    path = base/'RoCell'/'private'/'bench-review-v1'/setup.FILENAME
    original = path.read_bytes()
    assert report['status']=='KEY_AVAILABLE_NO_MOTION_APPROVAL'
    assert invoke('CHECK')==report and invoke('PROVISION')==report
    assert path.read_bytes()==original
    assert 'base64' not in str(report) and str(base) not in str(report)
