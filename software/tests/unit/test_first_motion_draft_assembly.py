"""Synthetic original assembly; no substituted measurements or live authority."""
import json
import pytest
from rocell.application.first_motion_draft import draft_from_originals
from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_reference_reader import ORIGINAL_REFERENCES
from test_first_motion_worker_preparation import setup
from test_first_motion_measurement_binding import SESSION, OPERATION


@pytest.mark.parametrize('fault', [None, 'bounds', 'session', 'missing', 'expired'])
def test_derive_exact_measurement_or_refuse(tmp_path, monkeypatch, fault):
    workspace, request, _ = setup(tmp_path, monkeypatch)
    prefix = request.to_dict()['attempt_id']
    originals = {name:(tmp_path/(prefix+'-'+name+'.original.json')).read_bytes() for name in ORIGINAL_REFERENCES}
    if fault == 'bounds':
        value = json.loads(originals['independent_posture_review_sha256'])
        value['derived']['reported_distal_radius_upper_bound_mm'] = 100
        originals['independent_posture_review_sha256'] = canonical(value)
    if fault == 'missing': originals.pop('serial_profile_review_sha256')
    kwargs = dict(reference_originals=originals,
        session_id='wizard-'+'f'*32 if fault=='session' else SESSION,
        measurement_operation_id=OPERATION, check_current=lambda:None,
        clock_ns=lambda:400_000_000_000 if fault=='expired' else 2_000_000_000)
    if fault:
        with pytest.raises(ValueError): draft_from_originals(workspace, **kwargs)
    else:
        draft = draft_from_originals(workspace, **kwargs)
        assert draft.selection_sha256 == request.selection_sha256
        assert not draft.preview()['motion_authorized']
