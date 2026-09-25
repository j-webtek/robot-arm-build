from dataclasses import replace
import pytest
from test_wrist_correction_saved_sources import saved
from test_endpoint_current_context import fixture
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_saved_sources import assess_saved_correction_sources
from rocell.application.wrist_correction_assessment_binding import bind_saved_correction_assessment
from rocell.providers.windows.wrist_correction_native_protocol import digest


def setup(tmp_path,monkeypatch,fault='miss'):
    attempts=saved(tmp_path,monkeypatch,fault=fault)
    assessment=assess_saved_correction_sources(tmp_path,attempts)
    _,_,_,controller=fixture()
    return canonical(assessment),controller,attempts


def test_repeatable_miss_binds_to_reviewed_unit_without_authority(tmp_path,monkeypatch):
    raw,controller,_=setup(tmp_path,monkeypatch)
    bound=bind_saved_correction_assessment(raw,expected_sha256=digest(raw),export_root=tmp_path,controller=controller)
    assert len(bound.originals)==2
    assert bound.to_dict()['proposal']['status']=='OFFLINE_EXPERIMENT_CANDIDATE'
    assert not bound.to_dict()['motion_authorized'] and not bound.to_dict()['current_connection_verified']


@pytest.mark.parametrize('fault',['assessment','original','unit','ineligible'])
def test_changed_or_ineligible_assessment_refused(tmp_path,monkeypatch,fault):
    raw,controller,attempts=setup(tmp_path,monkeypatch,None if fault=='ineligible' else 'miss')
    expected=digest(raw)
    if fault=='assessment': raw+=b' '
    if fault=='original': (tmp_path/(attempts[0]+'-absolute-wrist-stdout.original.json')).write_bytes(b'{}')
    if fault=='unit': controller=replace(controller,identity=replace(controller.identity,unit_serial='B'*32))
    with pytest.raises(ValueError):
        bind_saved_correction_assessment(raw,expected_sha256=expected,export_root=tmp_path,controller=controller)
