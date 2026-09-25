"""Correlate a host-owned trial with its retained operator report; never dispatch."""
import base64
import hashlib

from rocell.arm.observational_wrist_analysis import assess_observational_response
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.observational_native_protocol import decode_request
from rocell.providers.windows.observational_native_result import decode_result
from rocell.safety.observational_review_authority import ObservationalIntent
from .first_motion_contract import canonical
from .observational_capture import validate_clean_observational_capture
from .observational_operator_report import export_operator_reports
from .observational_worker_claim import verify_observational_worker_receipt
from .physical_onboarding_durability import contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_observational_coordinator import ObservationalRunOutcome


def assess_retained_observational_trial(request, outcome, receipt, *, review_root, export_root):
    """Rebuild from original bytes, not the displayed summary or operator opinion.

    Roots, request, outcome and receipt are supplied by the wizard host. Missing
    evidence produces a diagnostic hold. A functional pass is not metrology,
    continuous-path qualification, or authorization for another command.
    """
    assessment = dict(schema='rocell.observational_functional_assessment.v1', status='HELD',
        issues=[], analysis=None, observation_sha256=None, request_sha256=None,
        physical_accuracy_verified=False, device_sample_freshness_verified=False,
        physical_stop_verified=False, campaign_advance_allowed=False, motion_authorized=False)
    try:
        if type(request) is not ObservationalIntent or type(outcome) is not ObservationalRunOutcome:
            raise ValueError('Exact host request and outcome required')
        assessment['request_sha256'] = request.request_sha256
        # This re-reads and hashes all three observation originals against the
        # host receipt, without renewing their recording/acceptance times.
        export_operator_reports(root=review_root, receipts=(receipt,))
        observation = receipt['observation']
        assessment['observation_sha256'] = receipt['observation_sha256']
        attempt = request.to_dict()['attempt_id']
        if (observation['request_sha256'] != request.request_sha256
                or observation['attempt_id'] != attempt):
            raise ValueError('Observation/request association changed')
        raw = read_bounded_regular_file(contained_path(export_root,
            attempt+'-observational-report.json', label='observational result'), maximum_bytes=256*1024)
        report = decode_diagnostic_json(raw, maximum=256*1024)
        if (raw != canonical(outcome.report) or hashlib.sha256(raw).hexdigest() != observation['result_sha256']
                or report.get('status') != 'RESULT_RETAINED' or report.get('claim_receipt_verified') is not True):
            raise ValueError('Retained result is changed, rejected or unconfirmed')
        owned = outcome.owned
        if (type(owned) is not OwnedWorkerResult or outcome.stage != 'RETAINED'
                or owned.attempt_id != attempt or owned.status != 'SUCCEEDED'
                or owned.primary_error is not None or owned.cleanup_errors != ()
                or not owned.process_created or not owned.initial_thread_resumed
                or not owned.tree_exit_confirmed or owned.returncode != 0):
            raise ValueError('Clean owned process completion required')
        if observation['recorded_ns'] < owned.finished_monotonic_ns:
            raise ValueError('Observation was recorded before this trial finished')

        def original(name, maximum):
            filename = attempt+'-observational-'+name+'.original.json'
            entry = report['originals'][name]
            if entry['file'] != filename:
                raise ValueError('Unexpected original filename')
            wrapper_raw = read_bounded_regular_file(contained_path(export_root, filename,
                label='observational IPC original'), maximum_bytes=2*maximum+1024)
            wrapper = decode_diagnostic_json(wrapper_raw, maximum=2*maximum+1024)
            if type(wrapper) is not dict or set(wrapper) != {'bytes', 'base64'}:
                raise ValueError('Original wrapper schema changed')
            data = base64.b64decode(wrapper['base64'], validate=True)
            if (len(data) > maximum or wrapper['bytes'] != len(data) or entry['bytes'] != len(data)
                    or hashlib.sha256(data).hexdigest() != entry['sha256']):
                raise ValueError('Original byte accounting changed')
            return data

        wire = decode_request(original('request', 65536))
        stdout, stderr = original('stdout', 256*1024), original('stderr', 8192)
        if (canonical(wire['payload']['observational_intent']) != request.canonical_bytes
                or wire['request_sha256'] != owned.request_sha256
                or stdout != owned.stdout or stderr != owned.stderr):
            raise ValueError('Owned process and retained IPC differ')
        child = decode_result(stdout, wire=wire)['child_result']
        verify_observational_worker_receipt(review_root, request,
            claim_sha256=child['claim_sha256'], launch_sha256=wire['payload']['launch_sha256'],
            owned_process_id=owned.owned_process_id,
            runtime_sha256=hashlib.sha256(canonical(wire['payload']['registration'])).hexdigest(),
            finished_ns=owned.finished_monotonic_ns)
        if child['status'] != 'AWAITING_OPERATOR_OBSERVATION':
            raise ValueError('Trial did not complete the bounded capture sequence')
        trial = child['trial']
        before, after, write = trial['baseline'], trial['post'], trial['write']
        baseline_raw = validate_clean_observational_capture(request, before, phase='baseline')
        post_raw = validate_clean_observational_capture(request, after, phase='post',
            command_completed_ns=write['write_finished_ns'])
        reported = observation['reported']
        analysis = assess_observational_response(baseline_raw, before['read_windows'], post_raw, after['read_windows'],
            baseline_started_ns=before['started_ns'], baseline_finished_ns=before['finished_ns'],
            write_started_ns=write['write_started_ns'], write_finished_ns=write['write_finished_ns'],
            observation_end_ns=after['finished_ns'], direction=request.to_dict()['direction'],
            policy=request.to_dict()['policy'],
            actual_command=child['selection_original']['preview']['candidate_command'],
            operator_outcome=reported['outcome'], operator_covered_trial=reported['covered_trial'],
            transport_clean=True, basis='RETAINED_PHYSICAL_CAPTURE')
        assessment.update(status=analysis['status'], issues=analysis['issues'], analysis=analysis)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        assessment['issues'] = ['EVIDENCE_RECONSTRUCTION_FAILED:'+type(error).__name__]
    return assessment
