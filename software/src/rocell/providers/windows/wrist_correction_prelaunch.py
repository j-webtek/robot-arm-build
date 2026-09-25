"""Read-only correction prelaunch validation; not process or motor admission."""
from pathlib import Path
from rocell.application.wrist_correction_reference_reader import WristCorrectionReferenceReader
from rocell.application.wrist_correction_worker_claim import _verify
from rocell.application.physical_onboarding_durability import safe_root,contained_path
from .wrist_correction_native_protocol import validate_payload,require
from .bench_review_key import load_host_wrist_correction_review_authority


def verify_reserved_correction_entry(payload,*,workspace,clock_ns):
    require(callable(clock_ns),'Trusted correction execution clock required')
    request=validate_payload(payload)
    require(payload['expected_basis']=='RETAINED_PHYSICAL_CAPTURE','Native correction requires physical original evidence')
    root=safe_root(Path(payload['root']))
    claimed=contained_path(root,request.to_dict()['attempt_id']+'-wrist-correction-worker-claimed.json',label='correction worker claim')
    require(not claimed.exists(),'Correction attempt already claimed')
    reader=WristCorrectionReferenceReader(request,workspace=workspace,root=root)
    current=dict(reader());authority=load_host_wrist_correction_review_authority(workspace)
    started=clock_ns()
    _verify(payload,root,authority,current['source_sha256'],current['runtime_sha256'],started)
    refreshed=dict(reader());finished=clock_ns()
    require(type(finished) is int and finished>=started and refreshed==current,'Correction current context changed')
    _verify(payload,root,authority,current['source_sha256'],current['runtime_sha256'],finished)
    require(not claimed.exists(),'Correction attempt claimed during prelaunch')
    return request
