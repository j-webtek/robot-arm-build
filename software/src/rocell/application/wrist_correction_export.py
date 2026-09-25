"""Copy a closed roster of correction originals into an assigned export folder.

Export is diagnostic retention, not replay authority. Missing or unreadable
artifacts remain listed. No directory scan or caller-selected artifact path.
"""
import base64
from dataclasses import replace
from pathlib import Path
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file,publish_reservation_bytes,publish_bytes,PublicationMode
from rocell.providers.windows.wrist_correction_native_protocol import decode_request,digest,require
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def correction_artifact_roster(wire,*,version=1):
    """Derive the closed names and limits from an already validated request."""
    require(type(version) is int and version in (1,2),'Known correction export version required')
    payload=wire['payload'];attempt=wire['attempt_id']
    prefix=attempt+'-wrist-correction-'
    roster=[(prefix+suffix+'.json',maximum) for suffix,maximum in (
        ('plan-review',65536),('launch',65536),('worker-claimed',8192),('worker-consumed',8192),
        ('opening-reservation',65536),('open-claim',65536),('owned-selection',65536),
        ('reservation',16384),('consumed',16384),('trial.original',160*1024),('result',65536),
        ('outcome.original',512*1024),('parent-process.original',1024*1024),('parent-verdict.original',256*1024))]
    if version==2:
        # New trials consume the final review, not the legacy baseline review.
        # Keep v1's closed roster unchanged for previously copied exports.
        roster=[row for row in roster if row[0]!=prefix+'consumed.json']
        roster.extend((prefix+suffix+'.json',maximum) for suffix,maximum in (
            ('final-capture-claim',65536),('final-capture.original',128*1024),
            ('final-reservation',65536),('final-consumed',65536)))
    for pair in payload['originals']:
        roster.extend(((attempt+'-evidence-'+pair['request_sha256']+'.request.json',8192),
                       (attempt+'-evidence-'+pair['trial_sha256']+'.trial.json',512*1024)))
    directory=attempt+'-wrist-correction-native-child'
    roster.extend((directory+'/'+name,maximum) for name,maximum in (
        ('runtime.original.json',32768),('controller.original.json',128*1024),
        ('protocol.original.json',128*1024),('wrist-correction-native.zip',8*1024*1024)))
    return tuple(roster)


def export_correction_run(request_raw,process_result,*,export_root):
    wire=decode_request(request_raw);payload=wire['payload'];attempt=wire['attempt_id']
    require(type(process_result) is OwnedWorkerResult and process_result.attempt_id==attempt,
        'Exact associated correction process result required')
    root=safe_root(Path(payload['root']));destination=contained_path(safe_root(Path(export_root)),
        attempt+'-wrist-correction-export',label='correction export')
    destination.mkdir(exist_ok=False)
    roster=correction_artifact_roster(wire,version=2)
    artifacts=[];total=0
    for index,(relative,maximum) in enumerate(roster):
        item=dict(source_relative=relative,status='MISSING')
        try:
            path=contained_path(root,relative,label='correction export original')
            if path.exists():
                raw=read_bounded_regular_file(path,maximum_bytes=maximum)
                require(total+len(raw)<=16*1024*1024,'Correction export total byte budget exceeded')
                name=f'artifact-{index:02d}.original'
                publish_bytes(destination,name,raw,mode=PublicationMode.IMMUTABLE,maximum_bytes=maximum)
                total+=len(raw)
                item.update(status='RETAINED',file=name,bytes=len(raw),sha256=digest(raw))
        except Exception as error:
            item.update(status='UNREADABLE_OR_UNRETAINED',error_type=type(error).__name__)
        artifacts.append(item)
    def stream(raw,limit):
        require(type(raw) is bytes,'Immutable process stream required')
        return dict(observed_bytes=len(raw),observed_sha256=digest(raw),
            retained_sha256=digest(raw[:limit]),
            retained_bytes=min(len(raw),limit),truncated=len(raw)>limit,
            base64=base64.b64encode(raw[:limit]).decode('ascii'))
    process=replace(process_result,parsed_result=None).to_dict()
    report=dict(schema='rocell.wrist_correction_export.v2',attempt_id=attempt,request_sha256=wire['request_sha256'],
        request=stream(request_raw,65536),stdout=stream(process_result.stdout,256*1024),stderr=stream(process_result.stderr,8192),
        process=process,artifacts=artifacts,total_artifact_bytes=total,
        artifact_roster_complete=all(item['status']=='RETAINED' for item in artifacts),
        physical_accuracy_verified=False,campaign_advance_allowed=False,replay_allowed=False)
    raw=canonical(report)
    path=publish_reservation_bytes(destination,'manifest.json',raw,maximum_bytes=1024*1024)
    return path,report
