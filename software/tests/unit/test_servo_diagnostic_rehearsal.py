from pathlib import Path
import pytest
from rocell.application.servo_diagnostic_simulation import SCENARIOS
from rocell.application.servo_diagnostic_rehearsal import run_rehearsal,replay_rehearsal


@pytest.mark.parametrize('scenario',SCENARIOS)
def test_real_export_and_offline_replay(tmp_path,scenario):
    result=run_rehearsal(tmp_path,scenario)
    path=Path(result['export']['path'])
    assert result['export']['verified'] and result['replay_verified']
    assert replay_rehearsal(tmp_path,path.name)['outcome']==result['outcome']
    assert result['motion_commands']==0
    assert (path/'attachment-servo-write-evidence.json').is_file()
    assert result['write_assessment']['acknowledgment_verified']==(scenario!='bus_failure')
    assert not result['write_assessment']['progression_authority']
    if scenario in ('reboot','stale_sequence'):assert result['outcome']['status']=='TRACE_REJECTED'


def test_tampered_attachment_fails_replay(tmp_path):
    result=run_rehearsal(tmp_path,'arrival')
    path=Path(result['export']['path'])
    (path/'attachment-servo-assessment.json').write_text('{}')
    with pytest.raises(ValueError):replay_rehearsal(tmp_path,path.name)


def test_invalid_scenario_creates_no_export(tmp_path):
    with pytest.raises(ValueError):run_rehearsal(tmp_path,'hardware')
    assert not list(tmp_path.iterdir())


def test_export_failure_cannot_claim_success(tmp_path,monkeypatch):
    from rocell.application import servo_diagnostic_rehearsal as module
    monkeypatch.setattr(module,'verify_export',lambda path:dict(valid=False))
    with pytest.raises(ValueError):run_rehearsal(tmp_path,'arrival')


def test_write_attachment_tamper_fails(tmp_path):
    result=run_rehearsal(tmp_path,'arrival')
    path=Path(result['export']['path'])
    (path/'attachment-servo-write-evidence.json').write_text('{}')
    with pytest.raises(ValueError):replay_rehearsal(tmp_path,path.name)
