"""Exact staging with synthetic original measurements and current source/build."""
import pytest

from rocell.application.first_motion_staging import stage_first_motion_originals
from rocell.application.first_motion_reference_reader import ORIGINAL_REFERENCES
from test_first_motion_worker_preparation import setup
from test_first_motion_measurement_binding import SESSION,OPERATION


@pytest.mark.parametrize('fault',[None,'posture','original','missing','context'])
def test_stage_exact_originals_or_refuse_before_publication(tmp_path,monkeypatch,fault):
    workspace,request,_=setup(tmp_path,monkeypatch)
    prefix=request.to_dict()['attempt_id']
    originals={name:(tmp_path/(prefix+'-'+name+'.original.json')).read_bytes() for name in ORIGINAL_REFERENCES}
    measurement=(tmp_path/(OPERATION+'-first-motion-measurement-original.json')).read_bytes()
    if fault=='posture': originals['independent_posture_review_sha256']=b'{}'
    if fault=='original': originals['swept_clearance_review_sha256']=b'{}'
    if fault=='missing': originals.pop('power_and_shutdown_review_sha256')
    destination=tmp_path/'staged'; destination.mkdir()
    kwargs=dict(root=destination,reference_originals=originals,measurement_raw=measurement,
        session_id=SESSION,operation_id=OPERATION,check_current=lambda:True if fault=='context' else None,
        clock_ns=lambda:2_000_000_000)
    if fault:
        with pytest.raises(ValueError): stage_first_motion_originals(workspace,request,**kwargs)
        assert list(destination.iterdir())==[]
    else:
        report=stage_first_motion_originals(workspace,request,**kwargs)
        assert report['original_count']==8 and not report['physical_authority']
        for name,raw in originals.items(): assert (destination/(prefix+'-'+name+'.original.json')).read_bytes()==raw
        with pytest.raises(Exception): stage_first_motion_originals(workspace,request,**kwargs)


@pytest.mark.parametrize('failure', ['publication', 'final_context'])
def test_partial_or_late_failure_keeps_attempt_reserved(tmp_path, monkeypatch, failure):
    """A failed staging attempt must retain its artifacts and cannot be replayed."""
    import rocell.application.first_motion_staging as staging

    workspace, request, _ = setup(tmp_path, monkeypatch)
    prefix = request.to_dict()['attempt_id']
    originals = {
        name: (tmp_path / (prefix + '-' + name + '.original.json')).read_bytes()
        for name in ORIGINAL_REFERENCES
    }
    measurement = (tmp_path / (OPERATION + '-first-motion-measurement-original.json')).read_bytes()
    destination = tmp_path / 'staged'
    destination.mkdir()
    real_publish = staging.publish_reservation_bytes
    publications = 0
    checks = 0

    def publish(*args, **kwargs):
        nonlocal publications
        publications += 1
        if failure == 'publication' and publications == 3:
            raise OSError('Injected publication failure')
        return real_publish(*args, **kwargs)

    def current():
        nonlocal checks
        checks += 1
        if failure == 'final_context' and checks == 3:
            raise ValueError('Injected late context change')

    monkeypatch.setattr(staging, 'publish_reservation_bytes', publish)
    kwargs = dict(root=destination, reference_originals=originals,
                  measurement_raw=measurement, session_id=SESSION,
                  operation_id=OPERATION, check_current=current,
                  clock_ns=lambda: 2_000_000_000)
    with pytest.raises((OSError, ValueError)):
        stage_first_motion_originals(workspace, request, **kwargs)
    retained = {p.name: p.read_bytes() for p in destination.iterdir()}
    assert retained[prefix + '-first-motion-staged-request.json'] == request.canonical_bytes
    monkeypatch.setattr(staging, 'publish_reservation_bytes', real_publish)
    kwargs['check_current'] = lambda: None
    with pytest.raises(Exception):
        stage_first_motion_originals(workspace, request, **kwargs)
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == retained


@pytest.mark.parametrize('change_at', [2, 3])
def test_source_drift_before_or_after_publication_is_rejected(tmp_path, monkeypatch, change_at):
    import rocell.application.first_motion_staging as staging
    import rocell.application.endpoint_reference_reader as reader
    workspace, request, _ = setup(tmp_path, monkeypatch)
    prefix = request.to_dict()['attempt_id']
    originals = {name:(tmp_path/(prefix+'-'+name+'.original.json')).read_bytes()
                 for name in ORIGINAL_REFERENCES}
    measurement = (tmp_path/(OPERATION+'-first-motion-measurement-original.json')).read_bytes()
    destination = tmp_path/'drift'; destination.mkdir()
    calls = 0
    def current():
        nonlocal calls
        calls += 1
    def source(_):
        return 'f'*64 if calls >= change_at else request.to_dict()['references']['source_sha256']
    monkeypatch.setattr(staging, 'source_fingerprint', source)
    monkeypatch.setattr(reader, 'source_fingerprint', source)
    with pytest.raises(ValueError):
        stage_first_motion_originals(workspace, request, root=destination,
            reference_originals=originals, measurement_raw=measurement, session_id=SESSION,
            operation_id=OPERATION, check_current=current, clock_ns=lambda:2_000_000_000)
    assert bool(list(destination.iterdir())) == (change_at == 3)
