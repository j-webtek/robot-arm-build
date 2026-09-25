import importlib.util
import json
from pathlib import Path
import pytest


def script():
    path=Path(__file__).resolve().parents[2]/'scripts/run_observed_pose_pair.py'
    spec=importlib.util.spec_from_file_location('observed_pair_cli_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


LINKS=['--startup-export','startup','--stage-export','stage','--installation-export','installed']


def test_preflight_is_public_only(monkeypatch,capsys):
    module=script()
    monkeypatch.setattr(module,'review_observed_pair',lambda *a,**k:
        (dict(expected_boot='12'*16),dict(preparation=dict(illustrative_targets=[2899,2909]))))
    monkeypatch.setattr(module,'run_observed_pair',lambda *a,**k:pytest.fail('No hardware'))
    module.main(LINKS+['--preflight-only','--preparation-export','prep'])
    result=json.loads(capsys.readouterr().out)
    assert result['hardware_access'] is False and result['key_extracted'] is False


@pytest.mark.parametrize('extra',[[],['--prepare-only'],['--preflight-only'],
    ['--authorized-powered-pair','--hold-export','hold']])
def test_invalid_modes_reject_before_review(monkeypatch,extra):
    module=script()
    monkeypatch.setattr(module,'review_observed_pair',lambda *a,**k:pytest.fail('No review'))
    with pytest.raises(SystemExit):module.main(LINKS+extra)


def test_receipt_failure_stops_execution_before_private_access(monkeypatch):
    module=script()
    def reject(*a,**k):raise ValueError('Missing verified hold')
    monkeypatch.setattr(module,'review_observed_pair',reject)
    with pytest.raises(ValueError,match='Missing verified hold'):
        module.main(LINKS+['--authorized-powered-pair','--preparation-export','prep'])
