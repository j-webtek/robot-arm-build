"""Trusted host attachment tests; all measurements and reviews are synthetic."""
import hashlib
import pytest

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.application.first_motion_reference_reader import ORIGINAL_REFERENCES
from rocell.safety.first_motion_review_authority import ENGINEERING_CHECKS
from test_first_motion_contract import request
from test_first_motion_measurements import values as measurements
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('fault', [None, 'reference', 'measurement', 'review', 'key'])
@pytest.mark.parametrize('retained', [False, True, 'wizard'])
def test_attach_exact_session_material_once_without_launch(make_service, monkeypatch, fault, retained):
    from rocell.providers.windows import bench_review_key
    from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority
    def load_key(_):
        if retained == 'wizard':
            # Public host entry stays idle-only while the ticketed operation
            # uses the private, owned path. Never temporarily clear _running.
            with pytest.raises(Exception):
                service.configure_first_motion(draft=None, reference_originals={},
                    review_operation_ids=(), measurement_operation_id='unused')
        if fault == 'key': raise ValueError('Synthetic missing key')
        return FirstMotionReviewAuthority(b'a'*32)
    monkeypatch.setattr(bench_review_key, 'load_host_first_motion_review_authority', load_key)
    service, runner, _ = make_service(mode='physical')
    operation = _run(service, 'record_first_motion_measurements', measurements())
    measurement_id = operation['operation_id']
    report = operation['result']['steps'][0]['report']
    raw = (service._log.root/report['filename']).read_bytes()
    references = dict.fromkeys(ORIGINAL_REFERENCES, b'{"synthetic":true}')
    references['independent_posture_review_sha256'] = raw
    body = request().to_dict()
    body['references'].update({name: hashlib.sha256(value).hexdigest() for name,value in references.items()})
    body['references']['source_sha256'] = service.source_sha256
    body['independent_start_interval_deg'] = [-1, 1]
    body['distal_radius_mm'] = 175
    draft = FirstMotionDraft.from_request(FirstMotionRequest(canonical(body)))
    if retained:
        import rocell.application.first_motion_draft as assembly
        monkeypatch.setattr(assembly, 'draft_from_originals', lambda *a, **kw: draft)
        support = service.retain_first_motion_support(supporting_originals={
            key: value for key, value in references.items() if key != 'independent_posture_review_sha256'})
        generated = _run(service, 'create_first_motion_draft', dict(
            measurement_operation_id=measurement_id, support_record_id=support['record_id']))
        assert generated['status'] == 'SUCCEEDED'
    ids = []
    for check in sorted(ENGINEERING_CHECKS):
        operation = _run(service, 'record_first_motion_engineering_review',
            dict(draft_json=draft.canonical_bytes.decode(), reviewer_id='synthetic',
                 check=check, decision='APPROVED', detail='Synthetic only, no physical review.'))
        ids.append(operation['operation_id'])
    if fault == 'reference': references['serial_profile_review_sha256'] = b'{}'
    if fault == 'measurement': measurement_id = 'operation-'+'f'*32
    if fault == 'review': ids[-1] = ids[0]
    kwargs = dict(draft=draft, reference_originals=references,
                  review_operation_ids=tuple(ids), measurement_operation_id=measurement_id)
    configure = service.configure_first_motion
    if retained:
        if fault == 'reference':
            (service._log.root/(support['record_id']+'-serial_profile_review_sha256.json')).write_bytes(b'{}')
        if fault == 'measurement':
            (service._log.root/report['filename']).write_bytes(b'{}')
        kwargs = dict(draft_operation_id=generated['operation_id'], review_operation_ids=tuple(ids))
        configure = service.configure_first_motion_from_retained
        if retained == 'wizard':
            def configure(**selected):
                inputs = dict(draft_operation_id=selected['draft_operation_id'],
                    **dict(zip(sorted(ENGINEERING_CHECKS), selected['review_operation_ids'])))
                result = _run(service, 'attach_retained_first_motion', inputs)
                if result['status'] != 'SUCCEEDED':
                    raise RuntimeError('Synthetic attachment action failed as expected')
                assert result['result']['device_open_count'] == 0
                assert result['result']['motion_command_count'] == 0
                return result['result']['steps'][0]['report']
    if fault:
        with pytest.raises(Exception): configure(**kwargs)
        assert service._first_motion_attachment is None
    else:
        result = configure(**kwargs)
        assert not result['motion_authorized']
        assert service._first_motion_attachment['draft'].canonical_bytes == draft.canonical_bytes
        references.clear()
        assert len(service._first_motion_attachment['reference_originals']) == 8
        with pytest.raises(Exception): configure(**kwargs)
    assert not runner.calls
    assert service._first_motion_attempt_id is None
