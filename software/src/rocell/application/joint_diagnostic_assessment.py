"""Explain retained transaction evidence; never authorize motion or diagnose mechanics.

HTTP acknowledgment is a transport receipt, not a servo execution acknowledgment.
Identical position packets alone do not establish stale encoder acquisition.
"""


def assess_joint_run(report):
    tx=report.get('transaction') or {}
    attempted=report.get('command_send_attempted')
    receipt=report.get('acknowledgment_received')
    rows=tx.get('rows') or []
    reason=tx.get('reason')
    state=tx.get('state')
    if attempted is not True:
        category='NO_SEND_ATTEMPT_RECORDED'
    elif receipt is not True:
        category='COMMAND_DELIVERY_UNCERTAIN'
    elif state in ('REPORTED_SETTLED_PENDING_EXPORT','VERIFIED_AND_EXPORTED'):
        category='REPORTED_ENDPOINT_CRITERIA_MET'
    elif reason=='TRANSACTION_INTERRUPTED_OR_UNCERTAIN':
        category='OBSERVATION_OR_EXECUTION_UNCERTAIN'
    elif rows:
        category='REPORTED_ENDPOINT_NOT_VERIFIED'
    else:
        category='NO_USABLE_POST_COMMAND_OBSERVATION'
    # This is a descriptive comparison only. The runner validates the raw packets;
    # an offline caller must verify its source export before using this assessment.
    keys=('b','s','e','t','r','g')
    baseline=(tx.get('baseline') or {}).get('joints_rad') or {}
    unchanged=None
    if rows and all(k in baseline for k in keys):
        start=[baseline[k] for k in keys]
        unchanged=all(row.get('reported_joints_rad')==start for row in rows)
    return dict(schema='rocell.joint_diagnostic_assessment.v1',category=category,
        original_state=state,original_reason=reason,observation_count=len(rows),
        reported_positions_unchanged=unchanged,
        transport_receipt_observed=receipt is True,
        servo_target_acceptance='UNAVAILABLE',encoder_acquisition_freshness='UNAVAILABLE',
        physical_cause='UNDETERMINED',physical_accuracy_verified=False,
        export_verification='SEPARATE_VERIFIER_REQUIRED',
        progression_authority=False,automatic_retry_allowed=False)
