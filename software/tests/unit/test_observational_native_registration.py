from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from threading import Event

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.providers.windows import observational_native_package as package
from rocell.providers.windows import observational_native_protocol as protocol
from rocell.providers.windows.observational_native_registration import validate_registration
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile, WorkerProcessRegistration, OwnedWorkerRequest, OwnedWindowsWorker, owned_registration_document,
)
from test_observational_review_authority import intent


def registration(tmp_path):
    body = intent()
    body['deadline_ns'] = body['issued_ns'] + 30_000_000_000
    directory = tmp_path/(body['attempt_id']+'-observational-native-child')
    directory.mkdir()
    archive = package.prepare(directory)
    controller, review = directory/'controller.original.json', directory/'protocol.original.json'
    controller.write_bytes(b'{"synthetic":"controller-not-physical-evidence"}')
    review.write_bytes(b'{"synthetic":"protocol-not-an-approval"}')
    def pin(path):
        return PinnedWorkerFile(path, hashlib.sha256(path.read_bytes()).hexdigest())
    pins = (pin(package.CHILD), pin(archive), pin(controller), pin(review))
    reg = WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),
        pins, directory, protocol.fixed_budget(), 'PHYSICAL_UNQUALIFIED', protocol.REQUEST_SCHEMA, protocol.RESULT_SCHEMA)
    runtime = canonical(owned_registration_document(reg))
    (directory/'runtime.original.json').write_bytes(runtime)
    body['references'].update(runtime_sha256=hashlib.sha256(runtime).hexdigest(),
        native_controller_review_sha256=pins[2].sha256, protocol_review_sha256=pins[3].sha256)
    request = ObservationalIntent(canonical(body))
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(tmp_path), observational_intent=body,
        launch_sha256='a'*64, registration=owned_registration_document(reg),
        review_authority_id='local-observational-review-v1')
    outer = OwnedWorkerRequest(body['attempt_id'],body['session_id'],body['references']['source_sha256'],
        request.request_sha256, hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        body['deadline_ns'], canonical(payload))
    return reg, outer, request


def test_exact_registration_consistent_without_launch(tmp_path):
    reg, outer, request = registration(tmp_path)
    assert validate_registration(reg, outer)['observational_intent'] == request.to_dict()


def test_missing_reservation_prevents_supervisor_launch(tmp_path):
    reg, outer, _ = registration(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail('Unregistered observational launch reached backend/authorizer')
    result = OwnedWindowsWorker(reg, authorizer=forbidden, _backend_factory=forbidden,
        _clock=lambda: 2_000_000_000).run(outer, cancellation=Event(), deadline_ns=outer.expires_at_ns)
    assert result.status == 'FAILED'
    assert result.process_created is False


@pytest.mark.parametrize('change_review', [False, True])
def test_supervisor_rechecks_prepared_review_before_resume(tmp_path, monkeypatch, change_review):
    """Exercise real admission records with a backend incapable of opening devices."""
    from test_observational_worker_preparation import fixture
    from rocell.application.observational_worker_preparation import prepare_observational_worker
    from rocell.providers.windows import observational_prelaunch, bench_review_key
    from rocell.providers.windows import owned_worker_process as supervisor

    # The supervisor's cleanup deadline also uses its monotonic clock directly.
    monkeypatch.setattr(supervisor.time, 'monotonic_ns', lambda: 2_000_000_000)
    monkeypatch.setattr(supervisor, '_UNRESOLVED_BACKEND', None)

    workspace, staged, intent_request, signed, _, _ = fixture(tmp_path, monkeypatch)
    prepared = prepare_observational_worker(workspace, staged, intent_request,
        review_original=signed, clock_ns=lambda: 2_000_000_000)
    monkeypatch.setattr(observational_prelaunch, 'load_host_observational_review_authority',
        bench_review_key.load_host_observational_review_authority)
    calls = []

    class IncapableBackend:
        created = resumed = tree_exited = False
        returncode = None
        pid = written = peak_handles = peak_processes = 0
        stdout = stderr = b''

        def pin(self, registration):
            calls.append('pin')

        def start(self, registration, wire, *, check):
            calls.append('start')
            if change_review:
                (tmp_path/(prepared.request.attempt_id+'-observational-reviews.json')).write_bytes(b'{}')
            check()
            calls.append('checked')
            # Deliberately stop here: no process, serial handle, or motion exists.
            raise ValueError('INCAPABLE_TEST_BOUNDARY')

        def cleanup(self, deadline):
            calls.append('cleanup')
            return ()

    def authorize(*args):
        calls.append('authorize')

    result = OwnedWindowsWorker(prepared.registration, authorizer=authorize,
        _backend_factory=IncapableBackend, _clock=lambda: 2_000_000_000).run(
            prepared.request, cancellation=Event(), deadline_ns=prepared.request.expires_at_ns)
    assert calls == (['pin', 'authorize', 'start', 'cleanup'] if change_review
        else ['pin', 'authorize', 'start', 'checked', 'cleanup'])
    assert result.status == 'FAILED'
    assert result.process_created is False


@pytest.mark.parametrize('fault', ['argv','budget','directory','pins','identity','source','controller','archive'])
def test_changed_registration_or_original_rejected(tmp_path, fault):
    reg, outer, _ = registration(tmp_path)
    if fault == 'argv': reg = replace(reg, argv=reg.argv[:-1]+('check-imports',))
    if fault == 'budget': reg = replace(reg, budget=replace(reg.budget, process_count=2))
    if fault == 'directory': reg = replace(reg, working_directory=tmp_path)
    if fault == 'pins': reg = replace(reg, package_files=reg.package_files[:2])
    if fault == 'identity': outer = replace(outer, selected_identity_sha256='f'*64)
    if fault == 'source': outer = replace(outer, source_sha256='f'*64)
    if fault == 'controller': reg.package_files[2].path.write_bytes(b'{}')
    if fault == 'archive': reg.package_files[1].path.write_bytes(b'changed')
    with pytest.raises(ValueError): validate_registration(reg, outer)
