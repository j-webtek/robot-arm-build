"""Load explicitly selected saved absolute trials; no directory scan or IO."""
import base64
import re
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wrist_correction_proposal import propose_wrist_correction
from rocell.providers.windows.absolute_wrist_native_protocol import decode_request,validate_payload
from rocell.providers.windows.absolute_wrist_native_result import decode_result,validate_result
from rocell.providers.windows.wrist_correction_native_protocol import digest,require


def load_saved_absolute_trial(root,attempt):
    require(type(attempt) is str and re.fullmatch('operation-[a-f0-9]{32}',attempt),'Exact saved operation ID required')
    root=safe_root(root)
    def read(kind,maximum):
        path=contained_path(root,attempt+'-absolute-wrist-'+kind+'.original.json',label='saved absolute original')
        wrapper=read_bounded_regular_file(path,maximum_bytes=2*maximum+1024)
        body=decode_diagnostic_json(wrapper,maximum=2*maximum+1024)
        require(type(body) is dict and set(body)=={'bytes','base64'} and type(body['bytes']) is int
            and 0<=body['bytes']<=maximum and type(body['base64']) is str,'Exact saved byte wrapper required')
        raw=base64.b64decode(body['base64'],validate=True)
        require(len(raw)==body['bytes'] and len(raw)<=maximum,'Saved original byte count differs')
        return raw,digest(wrapper)
    request_raw,request_hash=read('request',65536)
    stdout,stdout_hash=read('stdout',256*1024)
    wire=decode_request(request_raw)
    require(wire['attempt_id']==attempt,'Saved absolute attempt differs')
    decoded=decode_result(stdout,wire=wire)
    summary=validate_result(decoded,wire=wire)
    require(summary['status']=='COMPLETED_DATA_CONSISTENT','Saved trial is not complete endpoint evidence')
    request=validate_payload(wire['payload'])
    raw=canonical(decoded['child_result']['result']['trial'])
    return (request,raw),dict(attempt_id=attempt,request_wrapper_sha256=request_hash,
        stdout_wrapper_sha256=stdout_hash,trial_sha256=digest(raw),physical_provenance_verified=False)


def assess_saved_correction_sources(root,attempts):
    require(type(attempts) is list and 2<=len(attempts)<=8 and len(set(attempts))==len(attempts),
        'Two to eight distinct saved operation IDs required')
    originals=[];references=[]
    for attempt in attempts:
        original,reference=load_saved_absolute_trial(root,attempt)
        originals.append(original);references.append(reference)
    proposal=propose_wrist_correction(originals,expected_basis='RETAINED_PHYSICAL_CAPTURE')
    return dict(schema='rocell.saved_wrist_correction_assessment.v1',selected_originals=references,
        proposal=proposal,proposal_sha256=digest(canonical(proposal)),motion_authorized=False,
        fresh_baseline_required=True,physical_provenance_verified=False)
