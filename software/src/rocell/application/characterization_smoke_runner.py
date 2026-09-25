"""One-shot, injected-transport smoke runner. No discovery, reset or live CLI.

Caller must supply an authenticated fresh session and explicit motion admission.
Stopping host requests does not imply that controller motion has stopped.
"""
import json
import hashlib
import time
from pathlib import Path
from .characterization_challenge import decode_challenge
from .characterization_reference import export_reference
from .characterization_smoke_review import review_smoke_reference
from .characterization_admission import sign_campaign
from .characterization_host_session import CharacterizationHostSession
from .characterization_record_transfer import RecordTransfer
from .characterization_fault_codec import export_fault
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class SmokeRunner:
    def __init__(self, client, root, *, key, boot, sleep=time.sleep, recovery_factory=None):
        self.client, self.root = client, Path(root)
        self.key, self.boot, self.sleep = key, boot, sleep
        self.used = False
        self.recovery_factory = recovery_factory

    def review(self, raw, challenge):
        return review_smoke_reference(raw, reference_sha256=challenge['reference'],
                                      goals=challenge['manifest']['goals'])

    def check_result(self, report, result):
        pass

    def run(self, *, motion_admitted=False):
        if self.used or motion_admitted is not True:
            raise ValueError('Fresh runner and explicit motion admission required')
        self.used = True  # Failures never make this instance reusable.
        exporter = WizardDiagnosticExporter(self.root)
        exporter.prepare(create=True)
        report = dict(status='INCONCLUSIVE', start_attempted=False,
                      retry_allowed=False, controller_stop_confirmed=False, responses=[])
        prefix = '/rocell/characterization/'

        def request(method, suffix, body=b''):
            raw = self.client(method, prefix+suffix, body)
            report['responses'].append(dict(path=suffix, raw_hex=raw.hex()))
            return raw

        def until(expected):
            # Finite requests; each production transport call has its own deadline.
            for _ in range(80):
                state = json.loads(request('GET', 'status'))
                if state.get('state') == 'FAULT':
                    report['fault_export'] = export_fault(self.root,
                        bytes.fromhex(request('GET', 'fault').decode('ascii')))
                    # New candidate retains full terminal assessment records.
                    # Older firmware may return 409; retain the compact fault
                    # regardless, never retry or send a receipt for this record.
                    if report['fault_export']['reason']=='NO_CLEAR_RESPONSE':
                        try:
                            from .characterization_result_codec import export_result
                            info=bytes.fromhex(request('GET','record-info').decode())
                            if len(info)!=35:raise ValueError('Invalid fault record metadata')
                            leg=info[0];size=int.from_bytes(info[1:3],'big')
                            transfer=RecordTransfer(boot=self.boot,campaign=challenge['campaign'],
                                leg=leg,size=size,sha256=info[3:].hex())
                            offset=0
                            while offset<size:
                                body=bytes([leg])+offset.to_bytes(2,'big')+info[3:]
                                chunk=bytes.fromhex(request('POST','record-chunk',body.hex().encode()).decode())
                                transfer.append(boot=self.boot,campaign=challenge['campaign'],
                                    leg=leg,offset=offset,data=chunk)
                                offset+=len(chunk)
                            report['failed_leg_export']=export_result(self.root,transfer.finish())
                        except Exception as history_error:
                            report['failed_leg_export_error']=type(history_error).__name__
                    raise ValueError('Controller fault')
                if state.get('state') == expected:
                    return
                self.sleep(0.15)
            raise TimeoutError('Bounded polling exhausted')

        pending_receipt = None
        try:
            state = json.loads(request('GET', 'status'))
            if state.get('state') != 'NEW' or state.get('writes_attempted') != 0:
                raise ValueError('Fresh unused campaign required')
            request('POST', 'prepare')
            until('AWAITING_AUTHORIZATION')
            challenge = decode_challenge(bytes.fromhex(request('GET', 'challenge').decode()),
                                         expected_boot=self.boot)
            report['challenge'] = challenge
            raw = bytes.fromhex(request('GET', 'reference').decode())
            report['baseline_review'] = self.review(raw, challenge)
            report['reference_export'] = export_reference(self.root, raw,
                expected_sha256=challenge['reference'])
            host = CharacterizationHostSession(self.root, challenge['manifest'], key=self.key,
                boot=self.boot, campaign=challenge['campaign'], reference=challenge['reference'])
            token = sign_campaign(challenge['manifest'], challenge['challenge'], self.key,
                campaign=challenge['campaign'], reference=challenge['reference'])
            report['start_attempted'] = True
            if request('POST', 'start', token.hex().encode()) != b'01':
                raise ValueError('Start not acknowledged')
            report['legs'] = []
            for leg in range(len(challenge['manifest']['goals'])):
                until('AWAITING_EXPORT')
                info = bytes.fromhex(request('GET', 'record-info').decode())
                if len(info) != 35 or info[0] != leg:
                    raise ValueError('Unexpected record metadata')
                size = int.from_bytes(info[1:3], 'big')
                transfer = RecordTransfer(boot=self.boot, campaign=challenge['campaign'],
                                         leg=leg, size=size, sha256=info[3:].hex())
                offset = 0
                while offset < size:  # Bounded by RecordTransfer's 11000-byte limit.
                    body = bytes([leg])+offset.to_bytes(2, 'big')+info[3:]
                    chunk = bytes.fromhex(request('POST', 'record-chunk', body.hex().encode()).decode())
                    transfer.append(boot=self.boot, campaign=challenge['campaign'],
                                    leg=leg, offset=offset, data=chunk)
                    offset += len(chunk)
                result = host.export_and_sign(transfer.finish(), source_boot=self.boot,
                                              source_campaign=challenge['campaign'])
                self.check_result(report, result)
                report['legs'].append(dict(leg=leg, export_path=result['export_path'], assessment=result['assessment']))
                report['result_export'] = result['export_path']
                report['assessment'] = result['assessment']
                pending_receipt = dict(leg=leg, sha256=hashlib.sha256(result['receipt']).hexdigest())
                if request('POST', 'receipt', result['receipt'].hex().encode()) != b'01':
                    raise ValueError('Receipt not acknowledged')
                pending_receipt = None
            until('COMPLETE')
            report['status'] = 'COMPLETE'
        except Exception as error:
            # Do not make further requests after delivery uncertainty or rejection.
            report.update(error_type=type(error).__name__, error_message=str(error))
            if pending_receipt is not None:
                report['uncertain_receipt'] = pending_receipt
                if self.recovery_factory is not None:
                    # Separate authenticated read-only channel; never replay the
                    # uncertain receipt, resume, or claim that motion stopped.
                    try:
                        from .characterization_reconciliation import assess_receipt_reconciliation
                        saved = self.recovery_factory(challenge['campaign']).read_and_export(self.root)
                        report['recovery_export'] = saved['export_path']
                        report['reconciliation'] = assess_receipt_reconciliation(
                            expected_boot=self.boot, expected_campaign=challenge['campaign'],
                            exported_leg=pending_receipt['leg'], receipt_sha256=pending_receipt['sha256'],
                            snapshot=saved['snapshot'], expected_legs=len(challenge['manifest']['goals']))
                    except Exception as recovery_error:
                        report['recovery_error_type'] = type(recovery_error).__name__
        saved = exporter.export({'mode':'single-smoke-run'}, [], attachments={
            'smoke-run.json':json.dumps(report, indent=2).encode()})
        if not verify_export(Path(saved['path']))['valid']:
            raise ValueError('Run export verification failed')
        return dict(export_path=saved['path'], report=report)
