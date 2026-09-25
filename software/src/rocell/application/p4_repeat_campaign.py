"""Finite campaign host protocol; live use requires reviewed r72 startup binding."""
import hashlib
import time
from pathlib import Path

from .first_motion_contract import canonical
from .large_pose_relief_record import decode_large_pose_relief_record, _stable, _valid
from .p4_repeat_campaign_review import GOALS, POSITIONS, TARGETS
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def assess_leg(raw, *, boot, leg, previous=None):
    if type(leg) is not int or not 1 <= leg <= 12:
        raise ValueError('Invalid leg ordinal')
    if type(raw) is not bytes or len(raw)!=1130 or raw[:10]!=b'RCWRREP001' or raw[26]!=leg:
        raise ValueError('Wrong campaign record or leg')
    target = int.from_bytes(raw[27:29], 'big')
    if target != TARGETS[leg-1]:
        raise ValueError('Wrong fixed target')
    # Reuse only the existing binary pose decoder, not its fixed-P4 assessment.
    framed = b'RCP4WRST01'+raw[10:26]+(1980).to_bytes(2,'big')+raw[29:]
    record = decode_large_pose_relief_record(framed, profile='P4')
    record['targets'] = [target]
    if record['boot']!=boot:
        raise ValueError('Wrong boot')
    before, pre, after = record['start'], record['prewrite'], record['endpoint']
    _stable(before); _valid(pre); _stable(after, record['sent_us'])
    if not before[-1]['finished_us'] < pre['started_us'] <= pre['finished_us'] <= record['sent_us']:
        raise ValueError('Prewrite chronology invalid')
    if record['sent_us']-pre['finished_us']>100000:
        raise ValueError('Prewrite expired')
    if leg==1:
        if previous is not None: raise ValueError('Unexpected preceding result')
        expected_positions, expected_goals, tolerance = POSITIONS, GOALS, 3
    else:
        if (previous is None or previous.get('boot')!=boot or previous.get('leg')!=leg-1):
            raise ValueError('Missing preceding verified leg')
        expected_positions, expected_goals, tolerance = previous['final_positions'], previous['final_goals'], 1
        if before[0]['started_us'] <= previous['finished_us']:
            raise ValueError('Replayed preceding samples')
    initial = before[-1]['joints']
    for i,j in enumerate(initial):
        if j['goal']!=expected_goals[i] or abs(j['position']-expected_positions[i])>tolerance:
            raise ValueError('Source changed')
        if pre['joints'][i]['goal']!=j['goal'] or abs(pre['joints'][i]['position']-j['position'])>1:
            raise ValueError('Prewrite changed')
    sign = 1 if target>expected_goals[4] else -1
    for sample in (*before, pre, *after):
        for i,j in enumerate(sample['joints']):
            if i!=4 and (abs(j['position']-POSITIONS[i])>2 or j['goal']!=GOALS[i]):
                raise ValueError('Global passive drift')
    for sample in after:
        for i,j in enumerate(sample['joints']):
            if i!=4 and abs(j['position']-initial[i]['position'])>2:
                raise ValueError('Passive leg drift')
        j=sample['joints'][4]; travel=j['position']-initial[4]['position']
        if j['goal']!=target or travel*sign < -1 or abs(travel)>80:
            raise ValueError('Direction or travel invalid')
    final=after[-1]['joints']; travel=final[4]['position']-initial[4]['position']
    error=final[4]['position']-target
    if travel*sign<2 or abs(error)>12:
        raise ValueError('Endpoint not verified')
    return dict(boot=boot, leg=leg, target=target, direction=sign,
        movement_counts=travel, endpoint_error_counts=error,
        final_positions=[j['position'] for j in final], final_goals=[j['goal'] for j in final],
        finished_us=after[-1]['finished_us'], record_sha256=hashlib.sha256(raw).hexdigest(),
        status='LEG_ENDPOINT_VERIFIED', physical_accuracy_verified=False)


class P4RepeatHost:
    """Requires an admitted transport; construction grants no hardware authority.

    The release runner supplies authentication and reviewed startup binding.
    """
    def __init__(self, transport, *, boot, export_root, source_kind='unverified'):
        if source_kind not in ('simulation','unverified','controller_feedback'):
            raise ValueError('Unknown source kind')
        self.source_kind=source_kind
        self.transport=transport; self.boot=boot
        self.root=Path(export_root).resolve(); self.used=False

    def run_once(self, *, clock=time.monotonic, pause=time.sleep):
        if self.used: raise ValueError('Campaign already consumed')
        self.used=True
        exporter=WizardDiagnosticExporter(self.root); exporter.prepare(create=True)
        rows=[]; exports=[]; leg=0; raw=b''
        def call(method, suffix, body=b''):
            return self.transport(method, '/rocell/p4-repeat/'+suffix, body)
        try:
            if call('POST','start',b'P4R12')!=b'CAPTURING_START':
                raise ValueError('Start uncertain; no retry')
            for leg in range(1,13):
                raw=b''; end=clock()+14
                while True:
                    if clock()>=end: raise TimeoutError('Leg timeout')
                    status=call('GET','status')
                    if status==f'AWAITING_EXPORT|{leg}'.encode(): break
                    if status not in [f'{s}|{leg}'.encode() for s in
                                      ('CAPTURING_START','PREWRITE','CAPTURING_ENDPOINT')]:
                        raise ValueError('Unexpected campaign status')
                    pause(0.1)
                encoded=call('GET','record')
                if type(encoded) is not bytes or len(encoded)!=2260:
                    raise ValueError('Record framing invalid')
                raw=bytes.fromhex(encoded.decode('ascii'))
                row=assess_leg(raw,boot=self.boot,leg=leg,previous=rows[-1] if rows else None)
                row['source_kind']=self.source_kind
                saved=exporter.export({'mode':'p4-repeat-leg'},[],attachments={
                    'p4-repeat-record.hex.txt':raw.hex().encode(), 'p4-repeat-assessment.json':canonical(row)})
                if not verify_export(Path(saved['path']))['valid']:
                    raise ValueError('Leg export verification failed')
                exports.append(saved['path'])
                receipt=f'{leg}:{row["record_sha256"]}'.encode()
                expected=b'COMPLETE' if leg==12 else f'READY|{leg+1}'.encode()
                if call('POST','receipt',receipt)!=expected:
                    raise ValueError('Receipt uncertain; no retry')
                rows.append(row)
                # Receipt acceptance alone must never authorize another write.
                if leg<12 and call('POST','next',str(leg+1).encode())!=b'CAPTURING_START':
                    raise ValueError('Next-leg admission uncertain; no retry')
            return dict(status='CAMPAIGN_COMPLETE',rows=rows,exports=exports,continuation_authorized=False)
        except Exception as error:
            # Preserve invalid evidence too, without issuing further controller calls.
            saved=exporter.export({'mode':'p4-repeat-fault'},[],attachments={
                'p4-repeat-fault.json':canonical(dict(boot=self.boot,leg=leg,
                    error_type=type(error).__name__, completed_legs=len(rows),
                    prior_exports=exports, source_kind=self.source_kind, retry_allowed=False)),
                'p4-repeat-fault-record.hex.txt':raw.hex().encode()})
            if not verify_export(Path(saved['path']))['valid']:
                raise ValueError('Fault export failed; no continuation') from error
            raise ValueError('Campaign stopped; evidence: '+saved['path']) from error
