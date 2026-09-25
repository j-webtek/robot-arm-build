"""Inert wire fixtures never register a worker or open a device."""
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import wrist_correction_native_protocol as p
from test_wrist_correction_review_authority import setup
from test_observational_native_protocol import rehash


def fixture(tmp_path):
    auth, context, review, args = setup()
    registration = {'synthetic': 'NOT_LAUNCH_AUTHORITY'}
    context['references']['runtime_sha256'] = p.digest(canonical(registration))
    context['deadline_ns'] = context['issued_ns'] + 30_000_000_000
    plan = auth.seal_plan(context, review, originals=args['originals'],
        now_ns=args['now_ns'], expected_basis=args['expected_basis'])
    payload = dict(schema=p.PAYLOAD_SCHEMA, root=str(tmp_path), context=context,
        launch_sha256='c'*64, registration=registration,
        review_authority_id='local-wrist-correction-review-v1', plan_sha256=p.digest(plan),
        originals=p.evidence_manifest(args['originals']), expected_basis=args['expected_basis'])
    wire = rehash(dict(schema=p.REQUEST_SCHEMA, worker_id=p.WORKER_ID,
        attempt_id=context['attempt_id'], session_id=context['session_id'],
        source_sha256=context['references']['source_sha256'], operation_sha256=p.digest(canonical(payload)),
        selected_identity_sha256=p.digest(canonical(context['usb_identity'])),
        expires_at_monotonic_ns=context['deadline_ns'], parent_deadline_monotonic_ns=context['deadline_ns'],
        payload=payload, registration_sha256=context['references']['runtime_sha256']))
    return wire, args['originals'], plan


def test_closed_handoff_and_original_binding(tmp_path):
    wire, originals, plan = fixture(tmp_path)
    assert p.decode_request(canonical(wire)) == wire
    p.verify_originals(wire['payload'], originals=originals, plan_raw=plan)
    assert p.fixed_budget().process_count == 1


@pytest.mark.parametrize('fault', ['command','plan','evidence','basis','duplicate','runtime',
    'identity','context_only','parent_deadline','worker','root','extra','bool_deadline'])
def test_rehashed_mutations_rejected(tmp_path, fault):
    wire, _, _ = fixture(tmp_path)
    payload = wire['payload']
    if fault == 'command': payload['command'] = {'T':101}
    if fault == 'plan': payload['plan_sha256'] = 'd'*64
    if fault == 'evidence': payload['originals'][0]['trial_sha256'] = 'd'*64
    if fault == 'basis': payload['expected_basis'] = 'RETAINED_PHYSICAL_CAPTURE'
    if fault == 'duplicate': payload['originals'][1] = payload['originals'][0]
    if fault == 'runtime': payload['registration']['changed'] = True
    if fault == 'identity': wire['selected_identity_sha256'] = 'd'*64
    if fault == 'context_only': wire['operation_sha256'] = p.digest(canonical(payload['context']))
    if fault == 'parent_deadline': wire['parent_deadline_monotonic_ns'] += 1
    if fault == 'worker': wire['worker_id'] = 'physical-absolute-wrist-trial'
    if fault == 'root': payload['root'] = '../escape'
    if fault == 'extra': wire['approved'] = True
    if fault == 'bool_deadline': wire['expires_at_monotonic_ns'] = True
    rehash(wire)
    with pytest.raises(ValueError): p.decode_request(canonical(wire))


@pytest.mark.parametrize('fault', ['plan','trial','order'])
def test_resolved_original_changes_rejected(tmp_path, fault):
    wire, originals, plan = fixture(tmp_path)
    if fault == 'plan': plan += b' '
    if fault == 'trial': originals[0] = (originals[0][0], originals[0][1]+b' ')
    if fault == 'order': originals.reverse()
    with pytest.raises(ValueError): p.verify_originals(wire['payload'], originals=originals, plan_raw=plan)
