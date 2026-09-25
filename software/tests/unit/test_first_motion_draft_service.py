"""Actual receipt selection with an incapable draft assembler double."""
import hashlib
import pytest
from rocell.application.first_motion_draft import FirstMotionDraft
from rocell.application.first_motion_reference_reader import ORIGINAL_REFERENCES
from test_first_motion_contract import request
from test_first_motion_measurements import values
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('fault', [None, 'other_session', 'changed_file', 'posture_override'])
def test_host_resolves_original_without_caller_measurement_bytes(make_service, monkeypatch, fault):
    import rocell.application.first_motion_draft as assembly
    service, runner, _ = make_service(mode='physical')
    operation = _run(service, 'record_first_motion_measurements', values())
    operation_id = operation['operation_id']
    report = operation['result']['steps'][0]['report']
    support = dict.fromkeys(ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}, b'{"synthetic":true}')
    expected = FirstMotionDraft.from_request(request())
    calls = []
    def assemble(workspace, **kwargs):
        kwargs['check_current']()
        raw = kwargs['reference_originals']['independent_posture_review_sha256']
        assert hashlib.sha256(raw).hexdigest() == report['original_sha256']
        assert kwargs['session_id'] == service.session_id
        assert kwargs['measurement_operation_id'] == operation_id
        calls.append(raw)
        return expected
    monkeypatch.setattr(assembly, 'draft_from_originals', assemble)
    target = service
    if fault == 'other_session': target, _, _ = make_service(mode='physical')
    if fault == 'changed_file': (service._log.root/report['filename']).write_bytes(b'{}')
    if fault == 'posture_override': support['independent_posture_review_sha256'] = b'{}'
    if fault:
        with pytest.raises(Exception): target.create_first_motion_draft(measurement_operation_id=operation_id, supporting_originals=support)
        assert calls == []
    else:
        assert target.create_first_motion_draft(measurement_operation_id=operation_id, supporting_originals=support) is expected
        assert len(calls) == 1
        assert service._first_motion_attachment is None
    assert not runner.calls


@pytest.mark.parametrize('fault', [None, 'changed_draft', 'other_session'])
def test_retained_draft_review_without_copied_json(make_service, monkeypatch, fault):
    import rocell.application.first_motion_draft as assembly
    from rocell.application.first_motion_contract import FirstMotionRequest, canonical
    from rocell.safety.first_motion_review_authority import ENGINEERING_CHECKS
    service, runner, _ = make_service(mode='physical')
    measurement = _run(service, 'record_first_motion_measurements', values())
    receipt = service.retain_first_motion_support(supporting_originals=dict.fromkeys(
        ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}, b'{"synthetic":true}'))
    body = request().to_dict()
    body['references']['source_sha256'] = service.source_sha256
    draft = FirstMotionDraft.from_request(FirstMotionRequest(canonical(body)))
    monkeypatch.setattr(assembly, 'draft_from_originals', lambda *a, **kw: draft)
    generated = _run(service, 'create_first_motion_draft', dict(
        measurement_operation_id=measurement['operation_id'], support_record_id=receipt['record_id']))
    assert generated['status'] == 'SUCCEEDED'
    draft_id = generated['operation_id']
    target = service
    if fault == 'changed_draft':
        (service._log.root/(draft_id+'-first-motion-generated-draft.json')).write_bytes(b'{}')
    if fault == 'other_session': target, _, _ = make_service(mode='physical')
    reviews = []
    for check in sorted(ENGINEERING_CHECKS):
        inputs = dict(draft_operation_id=draft_id, reviewer_id='synthetic', check=check,
                      decision='APPROVED', detail='Synthetic only, not a physical review.')
        if fault == 'other_session':
            with pytest.raises(Exception): _run(target, 'review_retained_first_motion_draft', inputs)
            break
        operation = _run(target, 'review_retained_first_motion_draft', inputs)
        if fault:
            assert operation['status'] == 'FAILED'
            break
        assert operation['status'] == 'SUCCEEDED'
        report = operation['result']['steps'][0]['report']
        assert report['draft_operation_id'] == draft_id
        assert report['selection_sha256'] == draft.selection_sha256
        reviews.append(operation['operation_id'])
    if not fault:
        originals = service.select_first_motion_reviews(draft=draft, review_operation_ids=tuple(reviews))
        assert set(originals) == ENGINEERING_CHECKS
    assert not runner.calls
    assert service._first_motion_attachment is None


@pytest.mark.parametrize('fault', [None, 'changed_file', 'other_session', 'caller_receipt_edit', 'unknown_id'])
def test_retained_support_selection(make_service, monkeypatch, fault):
    """Real exclusive file retention; assembler cannot authorize or access USB."""
    service, runner, _ = make_service(mode='physical')
    names = ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}
    support = {name: ('{ "synthetic": "'+name+'" }').encode() for name in names}
    receipt = service.retain_first_motion_support(supporting_originals=support)
    assert receipt['motion_authorized'] is False
    assert receipt['semantic_compatibility_verified'] is False
    calls = []
    def assemble(**kwargs):
        calls.append(kwargs)
        assert kwargs['supporting_originals'] == support
        return 'incapable-draft'
    monkeypatch.setattr(service, 'create_first_motion_draft', assemble)
    target = service
    record_id = receipt['record_id']
    if fault == 'changed_file':
        name = sorted(names)[0]
        (service._log.root/(record_id+'-'+name+'.json')).write_bytes(b'{"changed":true}')
    if fault == 'other_session': target, _, _ = make_service(mode='physical')
    if fault == 'caller_receipt_edit': receipt['original_sha256'].clear()
    if fault == 'unknown_id': record_id = '../other-session'
    if fault in ('changed_file', 'other_session', 'unknown_id'):
        with pytest.raises(Exception):
            target.create_first_motion_draft_from_retained(measurement_operation_id='unused', support_record_id=record_id)
        assert calls == []
    else:
        assert target.create_first_motion_draft_from_retained(measurement_operation_id='unused', support_record_id=record_id) == 'incapable-draft'
        assert len(calls) == 1
    assert not runner.calls
    assert service._first_motion_attachment is None


@pytest.mark.parametrize('fault', ['missing', 'posture_override', 'nonbytes', 'oversize', 'empty_object', 'array'])
def test_invalid_support_does_not_publish(make_service, fault):
    service, runner, _ = make_service(mode='physical')
    support = dict.fromkeys(ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}, b'{"synthetic":true}')
    name = sorted(support)[0]
    if fault == 'missing': support.pop(name)
    if fault == 'posture_override': support['independent_posture_review_sha256'] = b'{}'
    if fault == 'nonbytes': support[name] = '{}'
    if fault == 'oversize': support[name] = b' '*(128*1024+1)
    if fault == 'empty_object': support[name] = b'{}'
    if fault == 'array': support[name] = b'[]'
    with pytest.raises(Exception): service.retain_first_motion_support(supporting_originals=support)
    assert not list(service._log.root.glob('support-*'))
    assert not service._first_motion_support_receipts
    assert not runner.calls


@pytest.mark.parametrize('fault', ['publication', 'log'])
def test_partial_support_is_not_selectable(make_service, monkeypatch, fault):
    import rocell.application.physical_onboarding_durability as durability
    service, runner, _ = make_service(mode='physical')
    support = dict.fromkeys(ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}, b'{"synthetic":true}')
    if fault == 'publication':
        real = durability.publish_reservation_bytes
        calls = []
        def fail_after_first(*args, **kwargs):
            if calls: raise OSError('synthetic disk failure')
            calls.append(True)
            return real(*args, **kwargs)
        monkeypatch.setattr(durability, 'publish_reservation_bytes', fail_after_first)
    else:
        real_append = service._append_event
        monkeypatch.setattr(service, '_append_event', lambda kind, details:
            False if kind == 'first_motion_support_retained' else real_append(kind, details))
    with pytest.raises(Exception): service.retain_first_motion_support(supporting_originals=support)
    assert list(service._log.root.glob('support-*'))  # Evidence remains for diagnosis.
    assert not service._first_motion_support_receipts
    assert not runner.calls


@pytest.mark.parametrize('changed', [False, True])
def test_browser_draft_action_uses_retained_choices(make_service, monkeypatch, changed):
    import rocell.application.first_motion_draft as assembly
    from rocell.application.wizard_actions import ACTIONS
    service, runner, _ = make_service(mode='physical')
    measurement = _run(service, 'record_first_motion_measurements', values())
    support = dict.fromkeys(ORIGINAL_REFERENCES-{'independent_posture_review_sha256'}, b'{"synthetic":true}')
    receipt = service.retain_first_motion_support(supporting_originals=support)
    action = service._action_view(next(item for item in ACTIONS if item.action_id == 'create_first_motion_draft'))
    options = {field['name']: [item['value'] for item in field['options']] for field in action['fields']}
    assert tuple(options['measurement_operation_id']) == (measurement['operation_id'],)
    assert tuple(options['support_record_id']) == (receipt['record_id'],)
    calls = []
    expected = FirstMotionDraft.from_request(request())
    def assemble(workspace, **kwargs):
        kwargs['check_current']()
        assert kwargs['measurement_operation_id'] == measurement['operation_id']
        calls.append(True)
        return expected
    monkeypatch.setattr(assembly, 'draft_from_originals', assemble)
    if changed:
        name = sorted(support)[0]
        (service._log.root/(receipt['record_id']+'-'+name+'.json')).write_bytes(b'{"changed":true}')
    operation = _run(service, 'create_first_motion_draft', dict(
        measurement_operation_id=measurement['operation_id'], support_record_id=receipt['record_id']))
    if changed:
        assert operation['status'] == 'FAILED'
        assert not calls
    else:
        assert operation['status'] == 'SUCCEEDED'
        report = operation['result']['steps'][0]['report']
        assert report['draft_json'] == expected.canonical_bytes.decode('ascii')
        assert report['preview']['motion_authorized'] is False
        assert calls == [True]
    assert service._first_motion_attachment is None
    assert not runner.calls
