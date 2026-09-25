"""Read-only portable export integrity checks; never follow original root paths.

Hash consistency is not authenticated provenance, endpoint verification or replay
authority. A self-consistent incomplete failure export remains incomplete.
"""
import base64
import re
from pathlib import Path
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wrist_correction_export import correction_artifact_roster
from rocell.providers.windows.wrist_correction_native_protocol import decode_request,digest,require


def validate_correction_export(directory):
    root=safe_root(Path(directory))
    raw=read_bounded_regular_file(contained_path(root,'manifest.json',label='correction manifest'),maximum_bytes=1024*1024)
    body=decode_diagnostic_json(raw,maximum=1024*1024)
    fields={'schema','attempt_id','request_sha256','request','stdout','stderr','process','artifacts',
        'total_artifact_bytes','artifact_roster_complete','physical_accuracy_verified','campaign_advance_allowed','replay_allowed'}
    require(type(body) is dict and set(body)==fields and canonical(body)==raw
        and body['schema'] in ('rocell.wrist_correction_export.v1','rocell.wrist_correction_export.v2'),
        'Exact canonical correction export required')
    require(all(body[name] is False for name in ('physical_accuracy_verified','campaign_advance_allowed','replay_allowed')),
        'Export must not claim authority')
    def sha(value):
        return type(value) is str and re.fullmatch('[a-f0-9]{64}',value) is not None
    def stream(name,maximum):
        value=body[name]
        required={'observed_bytes','observed_sha256','retained_bytes','truncated','base64'}
        require(type(value) is dict and set(value) in (required,required|{'retained_sha256'}),'Exact bounded stream required')
        require(type(value['observed_bytes']) is int and value['observed_bytes']>=0
            and type(value['retained_bytes']) is int and value['retained_bytes']==min(value['observed_bytes'],maximum)
            and type(value['truncated']) is bool and value['truncated']==(value['observed_bytes']>maximum)
            and sha(value['observed_sha256']) and type(value['base64']) is str,'Invalid stream bounds')
        data=base64.b64decode(value['base64'],validate=True)
        require(len(data)==value['retained_bytes'],'Stream retained byte count differs')
        if 'retained_sha256' in value:
            require(sha(value['retained_sha256']) and digest(data)==value['retained_sha256'],'Retained stream hash differs')
        else:
            require(not value['truncated'],'Legacy truncated export lacks retained-prefix hash')
        if not value['truncated']:
            require(digest(data)==value['observed_sha256'],'Stream hash differs')
        return data
    request=stream('request',65536)
    require(body['request']['truncated'] is False,'Complete request required')
    wire=decode_request(request)
    stream('stdout',256*1024);stream('stderr',8192)
    require(body['attempt_id']==wire['attempt_id'] and body['request_sha256']==wire['request_sha256'],
        'Export request association differs')
    require(type(body['process']) is dict and body['process'].get('attempt_id')==wire['attempt_id']
        and body['process'].get('parsed_result') is None,'Process association differs')
    version=2 if body['schema']=='rocell.wrist_correction_export.v2' else 1
    roster=correction_artifact_roster(wire,version=version);rows=body['artifacts']
    require(type(rows) is list and len(rows)==len(roster),'Exact artifact roster required')
    total=0;missing=[]
    for index,(row,(relative,maximum)) in enumerate(zip(rows,roster)):
        require(type(row) is dict and row.get('source_relative')==relative,'Artifact roster name/order differs')
        status=row.get('status')
        if status=='RETAINED':
            require(set(row)=={'source_relative','status','file','bytes','sha256'}
                and row['file']==f'artifact-{index:02d}.original' and type(row['bytes']) is int
                and 0<=row['bytes']<=maximum and sha(row['sha256']),'Invalid retained artifact')
            # Read only the fixed local copy, never source_relative or payload.root.
            data=read_bounded_regular_file(contained_path(root,row['file'],label='export artifact'),maximum_bytes=maximum)
            require(len(data)==row['bytes'] and digest(data)==row['sha256'],'Artifact bytes/hash differ')
            total+=len(data)
            require(total<=16*1024*1024,'Export artifact budget exceeded')
        else:
            require((status=='MISSING' and set(row)=={'source_relative','status'}) or
                (status=='UNREADABLE_OR_UNRETAINED' and set(row)=={'source_relative','status','error_type'}
                 and type(row['error_type']) is str and len(row['error_type'])<=128),'Invalid missing artifact record')
            missing.append(relative)
    require(type(body['total_artifact_bytes']) is int and body['total_artifact_bytes']==total
        and type(body['artifact_roster_complete']) is bool and body['artifact_roster_complete']==(not missing),
        'Export completeness or byte total differs')
    return dict(schema='rocell.wrist_correction_export_integrity.v1',integrity_valid=True,
        manifest_sha256=digest(raw),attempt_id=wire['attempt_id'],artifact_roster_complete=not missing,
        missing_artifacts=missing,streams_complete=not any(body[name]['truncated'] for name in ('stdout','stderr')),
        endpoint_verified=False,physical_provenance_verified=False,replay_allowed=False)


def main(argv=None):
    """Validate a copied directory without creating or updating any files."""
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path,help='Export folder containing manifest.json')
    args=parser.parse_args(argv)
    try:
        result=validate_correction_export(args.directory)
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
        print(json.dumps(dict(integrity_valid=False,error_type=type(error).__name__,
            message=str(error),endpoint_verified=False,replay_allowed=False),indent=2))
        return 1
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
