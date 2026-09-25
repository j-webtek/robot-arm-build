"""Named joint-command identification adapter; preview is the default.

Explicit execute=True sends one named paired (+0.003/-0.003 rad) or wrist-only
(-0.006 rad) target, or the fixed-target T101 wrist comparison. Fresh feedback
required. Not a press, return or general jog API.
"""
import json
from pathlib import Path
import time
import uuid

from rocell.arm.all_joint_transaction import AllJointTransaction
from rocell.application.all_joint_runner import run_all_joint
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.safety.wifi_all_joint_reservation import WifiAllJointReservation, verify_sample
from .wifi_discrete_native import NativeDiscreteTransport, _CommandConnection
from .arm_wifi_deadline import bounded_probe
from .arm_transport_lock import arm_transport_lock


class _AllJointConnection(_CommandConnection):
    _reservation_type = WifiAllJointReservation


class NativeAllJointTransport(NativeDiscreteTransport):
    def __init__(self, reservation):
        if type(reservation) is not WifiAllJointReservation:
            raise ValueError('Exact T102 reservation required')
        self.reservation, self.receipt = reservation, None

    def _connection_type(self, *args, **kwargs):
        return _AllJointConnection(*args, **kwargs)


def run_native_identification(*, reservation_root, export_root, model,
                              execute=False, cancelled=lambda:False,
                              experiment='paired-small-step'):
    if type(execute) is not bool:
        raise ValueError('Explicit execution mode required')
    if experiment not in ('paired-small-step','wrist-minus-006','t101-wrist-fixed-comparison','t101-wrist-response-probe','t101-wrist-opposite-probe','t101-ascending-count-candidate','t101-descending-transfer','pair-up','pair-down','t101-press-elbow-probe','t101-elbow-nearby-probe','t101-local-elbow-candidate','t101-elbow-reverse-probe','t101-elbow-reverse-speed40'):
        raise ValueError('Named identification experiment required')
    # Verify the export directory is usable before even probing the controller.
    exporter=WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=True)

    def publish(report):
        receipt=exporter.export(dict(mode='joint-command-identification' if execute else 'joint-command-preview'),[],
            attachments={'all-joint-trial.json':json.dumps(dict(report,experiment=experiment),allow_nan=False).encode()})
        verification=verify_export(Path(receipt['path']).resolve())
        return dict(verified=verification['valid'] is True,path=receipt['path'])

    with arm_transport_lock():
        baseline=bounded_probe(cancelled=cancelled,retain_response=True)
        try:
            if cancelled():raise ValueError('Cancelled')
            verify_sample(baseline)
            overrides=dict(elbow=baseline['joints_rad']['e']+.003,
                           wrist=baseline['joints_rad']['t']-.003)
            if experiment=='wrist-minus-006':
                overrides=dict(wrist=baseline['joints_rad']['t']-.006)
            wrist_single=experiment in ('t101-wrist-fixed-comparison','t101-wrist-response-probe','t101-wrist-opposite-probe')
            if wrist_single:
                # Fixed target from the failed T102 wrist trial, not a relative
                # retry that would accumulate movement from a changed baseline.
                overrides=dict(wrist=-.071961174)
                if experiment=='t101-wrist-response-probe':overrides=dict(wrist=-.080)
                if experiment=='t101-wrist-opposite-probe':overrides=dict(wrist=-.052)
            normalized=experiment=='t101-ascending-count-candidate'
            if experiment=='t101-descending-transfer':normalized='descending'
            if experiment in ('pair-up','pair-down'):normalized=experiment
            if experiment=='t101-local-elbow-candidate':normalized='elbow'
            if normalized:
                from rocell.application.ascending_wrist_candidate import frozen_candidate
                if normalized in ('descending','pair-down'):
                    from rocell.application.descending_wrist_transfer import frozen_candidate
                if normalized=='elbow':
                    from rocell.application.local_elbow_bias_candidate import frozen_candidate
                overrides={('elbow' if normalized=='elbow' else 'wrist'):frozen_candidate()['command']['rad']}
                wrist_single=normalized!='elbow'
            elbow_single=experiment=='t101-press-elbow-probe'
            if experiment=='t101-elbow-nearby-probe':elbow_single='nearby'
            if experiment=='t101-elbow-reverse-probe':elbow_single='reverse'
            if experiment=='t101-elbow-reverse-speed40':elbow_single='reverse-speed40'
            if elbow_single:
                from rocell.application.press_elbow_probe import frozen_probe
                if elbow_single in ('reverse','reverse-speed40'):
                    from rocell.application.local_elbow_return_probe import frozen_probe
                    overrides=dict(elbow=frozen_probe(speed_comparison=elbow_single=='reverse-speed40')['target_rad'])
                else:overrides=dict(elbow=frozen_probe(nearby=elbow_single=='nearby')['target_rad'])
            if execute:
                reservation=WifiAllJointReservation(root=Path(reservation_root).resolve(),
                    attempt_id=uuid.uuid4().hex,baseline=baseline,
                    now_ns=time.perf_counter_ns(),model=model,overrides=overrides,wrist_single=wrist_single,normalized_candidate=normalized,elbow_single=elbow_single)
            else:
                tx=AllJointTransaction(model,baseline,
                    baseline_finished_s=baseline['response_finished_monotonic_s'],overrides=overrides,wrist_single=wrist_single,normalized_candidate=normalized,elbow_single=elbow_single)
        except (ValueError,KeyError,TypeError):
            report=dict(status='HELD_BEFORE_DISPATCH',baseline=baseline,motion_commands=0,
                reason='BASELINE_OR_PREVIEW_NOT_ADMITTED',physical_accuracy_verified=False)
            return dict(report,export=publish(report))
        if not execute:
            report=dict(status='PREVIEW_ONLY_NOT_EXECUTABLE',transaction=tx.report(),motion_commands=0)
            return dict(report,export=publish(report))
        transport=NativeAllJointTransport(reservation)

        def publish_run(report):
            # Keep the transport receipt in the durable artifact, not only stdout.
            return publish(dict(report,receipt=transport.receipt))

        return run_all_joint(reservation,transport=transport,clock_ns=time.perf_counter_ns,
            wait=time.sleep,cancelled=cancelled,publish_verified=publish_run)
