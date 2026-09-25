"""Finite-cycle progression rule, not a sender or permission to replay exports."""


def clean_compensated_completion(run):
    """Only a clean live-task outcome may advance; historical timeouts cannot."""
    tx=run.get('transaction') or {}
    samples=run.get('feedback_originals') or []
    return (run.get('status')=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
            and tx.get('state')=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
            and run.get('error') is None
            and run.get('command_send_attempted') is True
            and run.get('acknowledgment_received') is True
            and tx.get('command_attempts')==1
            and (tx.get('policy') or {}).get('compensated_endpoint') is True
            and (tx.get('desired_endpoint_result') or {}).get('status')=='DESIRED_REPORTED_ENDPOINT_VERIFIED'
            and len(samples)>=3
            and all(s.get('status')=='SUCCEEDED' and s.get('cleanup_confirmed') is True
                    and s.get('identity_before_matched') is True and s.get('identity_after_matched') is True
                    for s in samples))
