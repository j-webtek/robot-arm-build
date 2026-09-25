"""Check observed isolated-child invocation against the signed runtime reference.

Inputs are process observations supplied by the fixed entry, not wire fields.
Current source, authority, launch reservation and process ownership are separate
required gates. This function never loads a device API or opens a COM port.
"""
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from .owned_worker_process import PinnedWorkerFile,WorkerProcessBudget,WorkerProcessRegistration,owned_registration_document
from .wrist_correction_native_protocol import decode_request,require,digest,WORKER_ID,REQUEST_SCHEMA,RESULT_SCHEMA,fixed_budget


def verify_actual_invocation(request_raw,*,entry_path,executable,argv,working_directory):
    wire=decode_request(request_raw);payload=wire['payload'];document=payload['registration']
    def pin(value):
        require(type(value) is dict and set(value)=={'path','sha256','maximum_bytes'},'Exact invocation pin required')
        return PinnedWorkerFile(Path(value['path']),value['sha256'],value['maximum_bytes'])
    require(set(document)=={'worker_id','executable','argv','package_files','working_directory','budget',
        'composition','request_schema','result_schema'},'Exact invocation registration required')
    registration=WorkerProcessRegistration(document['worker_id'],pin(document['executable']),tuple(document['argv']),
        tuple(pin(value) for value in document['package_files']),Path(document['working_directory']),
        WorkerProcessBudget(**document['budget']),document['composition'],document['request_schema'],document['result_schema'])
    require(canonical(owned_registration_document(registration))==canonical(document),'Invocation registration changed during decoding')
    directory=Path(payload['root'])/(wire['attempt_id']+'-wrist-correction-native-child')
    pins=registration.package_files
    require(registration.worker_id==WORKER_ID and registration.request_schema==REQUEST_SCHEMA
        and registration.result_schema==RESULT_SCHEMA and registration.composition=='PHYSICAL_UNQUALIFIED'
        and registration.budget==fixed_budget() and registration.working_directory==directory
        and Path(working_directory)==directory and registration.executable.path==Path(executable)
        and len(pins)==4,'Actual correction runtime/domain differs')
    require(pins[0].path==Path(entry_path) and pins[0].path.name=='_wrist_correction_native_child.py'
        and pins[1].path==directory/'wrist-correction-native.zip'
        and pins[2].path==directory/'controller.original.json'
        and pins[3].path==directory/'protocol.original.json'
        and registration.argv==('-I','-S',str(entry_path),str(pins[1].path),pins[1].sha256,'execute-one')
        and tuple(argv)==registration.argv,'Actual correction arguments or file pins differ')
    # Hard limits are independent of caller-declared maximum_bytes.
    for item,limit in zip((registration.executable,)+pins,(32*1024*1024,2*1024*1024,8*1024*1024,128*1024,128*1024)):
        original=read_bounded_regular_file(item.path,maximum_bytes=min(limit,item.maximum_bytes))
        require(digest(original)==item.sha256,'Actual correction executable/package bytes changed')
    for item,reference in ((pins[2],'native_controller_review_sha256'),(pins[3],'protocol_review_sha256')):
        require(item.sha256==payload['context']['references'][reference],'Correction reference pin differs')
    return wire
