"""Registration data validation never enables a physical process launch."""

from dataclasses import replace
import hashlib
import base64
import json
from pathlib import Path
import sys
from threading import Event

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.providers.windows import endpoint_native_registration as protocol
from rocell.providers.windows import endpoint_native_package as package
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile, WorkerProcessRegistration, OwnedWorkerRequest, OwnedWindowsWorker,
    owned_registration_document,
)
from test_endpoint_trial_contract import request
from rocell.application.endpoint_evidence_snapshot import SCHEMA as SNAPSHOT_SCHEMA, FILENAME, ORIGINAL_REFERENCES
from rocell.application.physical_onboarding_durability import publish_bytes,PublicationMode


def registration(tmp_path):
    data = request().to_dict()
    data['deadline_monotonic_ns'] = 31_000_000_000
    # Synthetic retained snapshot, never a workspace/physical qualification.
    build = {'schema':'test.synthetic.build.v1','contact_enabled':False}
    data['references']['build_snapshot_sha256']=hashlib.sha256(_canonical(build)).hexdigest()
    originals = {}
    for name in ORIGINAL_REFERENCES:
        raw = _canonical({'schema':'test.synthetic.original.v1','name':name})
        data['references'][name]=hashlib.sha256(raw).hexdigest()
        originals[name]=base64.b64encode(raw).decode('ascii')
    for name in ('configuration_sha256','firmware_review_sha256','geometry_sha256'):
        data['campaign']['evidence'][name]=data['references'][name]
    req = EndpointTrialRequest(_canonical(data))
    wd = tmp_path/(data['attempt_id']+'-endpoint-native-child')
    wd.mkdir()
    archive = package.prepare(wd)
    evidence = publish_bytes(wd,FILENAME,_canonical({'schema':SNAPSHOT_SCHEMA,
        'request':req.to_dict(),'request_sha256':req.request_sha256,'build_snapshot':build,
        'originals':originals,'physical_authority':False}),mode=PublicationMode.IMMUTABLE)
    executable = Path(getattr(sys,'_base_executable',sys.executable))
    def pin(path): return PinnedWorkerFile(path,hashlib.sha256(path.read_bytes()).hexdigest())
    pins = (pin(package.CHILD),pin(archive),pin(evidence))
    reg = WorkerProcessRegistration(protocol.WORKER_ID,pin(executable),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),pins,wd,
        protocol.fixed_budget(),'PHYSICAL_UNQUALIFIED',protocol.REQUEST_SCHEMA,protocol.RESULT_SCHEMA)
    payload = {'schema':protocol.PAYLOAD_SCHEMA,'root':str(tmp_path),
        'session_id':'wizard-'+'c'*32,'endpoint_request':req.to_dict(),'launch_sha256':'b'*64,
        'registration':owned_registration_document(reg),'review_authority_id':'local-bench-review-v1'}
    outer = OwnedWorkerRequest(req.to_dict()['attempt_id'],payload['session_id'],
        req.to_dict()['references']['source_sha256'],req.request_sha256,protocol.identity_hash(req),
        req.to_dict()['deadline_monotonic_ns'],_canonical(payload))
    return reg,outer


def test_exact_current_registration_is_recognized_but_not_launched(tmp_path):
    reg,outer = registration(tmp_path)
    payload = protocol.validate_registration(reg,outer)
    assert payload['endpoint_request']['physical_authority'] is False
    def forbidden(*args): pytest.fail('Physical endpoint launching remains held')
    worker = OwnedWindowsWorker(reg,authorizer=forbidden,_backend_factory=forbidden,_clock=lambda:1_000_000_000)
    result = worker.run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
    assert result.status=='FAILED' and not result.process_created and not result.initial_thread_resumed


@pytest.mark.parametrize('field', ['argv','budget','working_directory','worker_id','request_schema','package_files'])
def test_registration_cannot_widen_execution(tmp_path,field):
    reg,outer = registration(tmp_path)
    changes = {'argv':reg.argv[:-1]+('observe',),
               'budget':replace(reg.budget,process_count=2),
               'working_directory':tmp_path,
               'worker_id':'other-worker','request_schema':'other.schema',
               'package_files':(reg.package_files[0],replace(reg.package_files[1],sha256='f'*64))}
    with pytest.raises(ValueError): protocol.validate_registration(replace(reg,**{field:changes[field]}),outer)


@pytest.mark.parametrize('field', ['operation_sha256','source_sha256','selected_identity_sha256','session_id','expires_at_ns'])
def test_outer_request_must_match_endpoint(tmp_path,field):
    reg,outer = registration(tmp_path)
    changed = 30_000_000_000 if field=='expires_at_ns' else ('wizard-'+'d'*32 if field=='session_id' else 'f'*64)
    with pytest.raises(ValueError): protocol.validate_registration(reg,replace(outer,**{field:changed}))


def test_raw_commands_keys_and_short_lifetime_are_not_handoff_fields(tmp_path):
    reg,outer = registration(tmp_path)
    for key in ('raw_command','signing_key','port','resume'):
        payload = json.loads(outer.payload_json)
        payload[key] = 'untrusted'
        with pytest.raises(ValueError): protocol.validate_payload(payload)
    payload = json.loads(outer.payload_json)
    payload['endpoint_request']['deadline_monotonic_ns']=21_000_000_000
    with pytest.raises(ValueError): protocol.validate_payload(payload)


def test_evidence_pin_is_mandatory_and_original_bound(tmp_path):
    reg,outer = registration(tmp_path)
    with pytest.raises(ValueError): protocol.validate_registration(replace(reg,package_files=reg.package_files[:2]),outer)
    publish_bytes(reg.working_directory,FILENAME,b'{"changed":true}',mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): protocol.validate_registration(reg,outer)
