from dataclasses import replace
from threading import Event

import pytest
from rocell.providers.windows.positional_campaign_process_codec import prepare_owned_request
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.providers.windows.positional_campaign_native_registration import validate_registration
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker, owned_request_wire
from test_positional_campaign_native_registration import prepared


@pytest.mark.parametrize('fault', [None, 'wrong_intent', 'late'])
@pytest.mark.parametrize('version',[2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21])
def test_v2_supervisor_dispatch_and_receipt_association(tmp_path, monkeypatch, fault,version):
    """Exercise dispatch with an incapable backend, not physical qualification.

    Prelaunch authentication is covered separately. This test replaces that
    boundary explicitly; no native process or serial handle can be created.
    """
    import json
    import time
    from rocell.application.first_motion_contract import canonical
    from rocell.providers.windows import positional_campaign_prelaunch
    from rocell.providers.windows.positional_campaign_native_protocol import RESULT_SCHEMA
    from test_positional_campaign_native_registration import reseal

    registration, raw = prepared(tmp_path)
    wire = json.loads(raw)
    body = wire['payload']['campaign_intent']
    body['schema'] = 'rocell.attended_positional_intent.v2'
    body['references']['bounded_motion_risk_sha256'] = body['references'].pop('stop_qualification_sha256')
    from rocell.safety.positional_campaign_authority import fixed_campaign_limits
    body['schema']=f'rocell.attended_positional_intent.v{version}'
    body['limits']=fixed_campaign_limits(body['schema'])
    if version==5:
        body['mode']='ATTENDED_ONE_CONTROL'
        body['legs']=body['legs'][:1]
    if version in (6,7,8,9,10,11,12,13):
        from test_base_mapping_campaign import base_body
        probe=base_body()
        if version==8:
            from test_two_degree_base_campaign import two_body
            probe=two_body()
        if version==9:
            from test_base_midpoint_campaign import midpoint_body
            probe=midpoint_body()
        if version in (10,11,12,13):
            import hashlib
            from test_base_compensation_campaign import experiment_body
            probe=experiment_body('CORRECTED' if version in (10,12) else 'UNCORRECTED_CONTROL',
                'DECREASING' if version in (12,13) else 'INCREASING')
            p=probe['base_experiment']
            p['context_references']={k:body['references'][k] for k in p['context_references']}
            body['base_experiment']=p
            body['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
        for key in ('mode','selected_joint','start_joints_rad','legs'):
            body[key]=probe[key]
    if version==4:
        import hashlib
        from test_model_corrected_native_campaign import corrected_body
        correction=corrected_body()
        for key in ('mode','start_joints_rad','legs','correction'):
            body[key]=correction[key]
        p=body['correction']
        p['context_references']={k:body['references'][k] for k in p['context_references']}
        body['references']['configuration_sha256']=hashlib.sha256(canonical(p)).hexdigest()
    if version==14:
        import hashlib
        from test_base_alternating_sequence import sequence_body
        from rocell.providers.windows.positional_campaign_native_protocol import fixed_budget
        probe=sequence_body()
        for key in ('mode','selected_joint','start_joints_rad','legs','base_sequence'):
            body[key]=probe[key]
        for name in ('increasing','decreasing'):
            p=body['base_sequence'][name]
            p['context_references']={k:body['references'][k] for k in p['context_references']}
        body['references']['configuration_sha256']=hashlib.sha256(canonical(body['base_sequence'])).hexdigest()
        registration=replace(registration,budget=fixed_budget(body['schema']))
    if version==15:
        import hashlib
        from test_base_speed_campaign import speed_body
        probe=speed_body()
        for key in ('mode','selected_joint','start_joints_rad','legs','base_speed'):
            body[key]=probe[key]
        p=body['base_speed']['proposal']
        p['context_references']={k:body['references'][k] for k in p['context_references']}
        body['references']['configuration_sha256']=hashlib.sha256(canonical(body['base_speed'])).hexdigest()
    if version in (16,17,18,19,20,21):
        import hashlib
        from test_roll_mapping_campaign import roll_body
        probe=roll_body()
        if version==17:
            from test_roll_fixed_campaign import fixed_roll_body
            probe=fixed_roll_body()
        if version in (18,19,20,21):
            from test_roll_persistence_campaign import persistence_body
            from rocell.providers.windows.positional_campaign_native_protocol import fixed_budget
            from test_roll_long_fixed_campaign import long_fixed_body
            from test_roll_framed_campaign import framed_body
            probe=framed_body() if version==21 else long_fixed_body() if version==20 else persistence_body(version=version)
            registration=replace(registration,budget=fixed_budget(body['schema']))
        for key in ('mode','selected_joint','start_joints_rad','legs','roll_probe'):
            body[key]=probe[key]
        body['references']['configuration_sha256']=hashlib.sha256(canonical(body['roll_probe'])).hexdigest()
    issued = time.monotonic_ns()
    body.update(issued_ns=issued, deadline_ns=issued + body['limits']['maximum_duration_s']*1_000_000_000)
    wire.update(expires_at_monotonic_ns=body['deadline_ns'],
        parent_deadline_monotonic_ns=body['deadline_ns'])
    wire = decode_request(reseal(wire, registration))
    request, raw = prepare_owned_request(registration, wire['payload'])
    clock = issued + ((14_000_000_000 if version in (19,20,21) else 21_000_000_000 if version==14 else 7_000_000_000) if fault == 'late' else 1_000_000_000)
    checks = []
    monkeypatch.setattr(positional_campaign_prelaunch, 'verify_reserved_campaign_entry',
        lambda *args, **kwargs: checks.append('prelaunch'))

    class IncapableBackend:
        created = resumed = tree_exited = False
        returncode = None
        pid = written = peak_handles = peak_processes = 0
        stdout = stderr = b''

        def pin(self, reg):
            assert reg == registration

        def start(self, reg, data, *, check):
            check()
            assert decode_request(data) == wire
            self.created = self.resumed = self.tree_exited = True
            self.pid, self.written, self.returncode = 123, len(data), 0
            self.stdout = canonical(dict(schema=RESULT_SCHEMA,
                intent_sha256='f'*64 if fault == 'wrong_intent' else wire['operation_sha256'],
                claim_sha256='b'*64, trial_sha256='c'*64, trial_bytes=123,
                physical_authority=False))

        def poll(self, budget):
            return True

        def cleanup(self, deadline):
            return ()

    worker = OwnedWindowsWorker(registration,
        authorizer=lambda *args: checks.append('authorize'),
        _backend_factory=IncapableBackend, _clock=lambda: clock)
    result = worker.run(request, cancellation=Event(), deadline_ns=request.expires_at_ns)
    assert not result.cleanup_errors
    if fault == 'late':
        assert result.primary_error == 'LIFETIME_BUDGET_DOES_NOT_FIT'
        assert not result.process_created and checks == ['prelaunch']
    else:
        assert result.process_created
        assert checks == ['prelaunch', 'authorize', 'prelaunch']
        assert (result.status == 'SUCCEEDED') == (fault is None)
        if fault is None:
            assert result.primary_error is None
    assert result.request_sha256 == wire['request_sha256']


def test_real_supervisor_wire_roundtrips_to_campaign_validator(tmp_path):
    registration, raw = prepared(tmp_path)
    expected = decode_request(raw)
    request, wire = prepare_owned_request(registration, expected['payload'])
    assert decode_request(wire) == expected
    assert request.operation_sha256 == expected['operation_sha256']
    assert validate_registration(registration, wire) == expected


@pytest.mark.parametrize('fault', ['operation', 'deadline', 'registration'])
def test_supervisor_mapping_cannot_change_reviewed_campaign(tmp_path, fault):
    registration, raw = prepared(tmp_path)
    request, _ = prepare_owned_request(registration, decode_request(raw)['payload'])
    deadline = request.expires_at_ns
    if fault == 'operation': request = replace(request, operation_sha256='f'*64)
    if fault == 'deadline': deadline -= 1
    if fault == 'registration': registration = replace(registration, worker_id='other-worker')
    wire, _ = owned_request_wire(registration, request, deadline_ns=deadline)
    with pytest.raises(ValueError): decode_request(wire)


def test_format_support_does_not_authorize_native_supervisor_launch(tmp_path):
    registration, raw = prepared(tmp_path)
    request, wire = prepare_owned_request(registration, decode_request(raw)['payload'])
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError('Unregistered campaign must not reach authorization/backend')
    worker = OwnedWindowsWorker(registration, authorizer=forbidden,
        _backend_factory=forbidden, _clock=lambda: 2_000_000_000)
    result = worker.run(request, cancellation=Event(), deadline_ns=request.expires_at_ns)
    assert result.status != 'SUCCEEDED'
    assert result.primary_error == 'CAMPAIGN_BOUNDED_ATTENDED_V2_REQUIRED'
    assert not result.process_created and not calls
    assert worker.status()['consumed']
    assert result.request_sha256 == decode_request(wire)['request_sha256']
    # Exercise real supervisor rejection -> original retention -> independent
    # verification, including absence of a child, claim and serial reader.
    from rocell.application.positional_campaign_native_retention import publish_campaign_process_result
    from rocell.application.positional_campaign_native_export import verify_native_retained_export
    from rocell.providers.windows.positional_campaign_native_protocol import validate_payload
    intent = validate_payload(decode_request(wire)['payload'])
    path, report = publish_campaign_process_result(tmp_path, intent, request_original=wire, receipt=result)
    assert report['status'] == 'DIAGNOSTIC_RETAINED'
    assert not report['endpoint_reported_complete']
    assert verify_native_retained_export(tmp_path, path.name)['valid']
