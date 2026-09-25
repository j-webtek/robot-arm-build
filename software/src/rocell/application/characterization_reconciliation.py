"""Offline receipt reconciliation policy; no networking or movement permission.

Inputs must come from a separately authenticated, fresh recovery snapshot and
verified local evidence. This function does not authenticate caller dictionaries.
Even a consistent result cannot establish physical pose or authorize resumption.
"""
import re


def assess_receipt_reconciliation(*, expected_boot, expected_campaign, exported_leg,
                                  receipt_sha256, snapshot, expected_legs=12):
    """Compare retained receipt identity and progress, never infer from targets.

    completed means receipts accepted, not movements physically completed.
    None for last_receipt_sha256 is allowed when no receipt has been accepted.
    """
    result = dict(state='UNRESOLVED', resume_allowed=False,
                  physical_pose_verified=False, evidence_retrieval_required=False)

    def unresolved(reason):
        return {**result, 'reason': reason}

    if (type(expected_legs) is not int or not 1 <= expected_legs <= 12
            or type(exported_leg) is not int or not 0 <= exported_leg < expected_legs
            or type(receipt_sha256) is not str
            or not re.fullmatch('[0-9a-f]{64}', receipt_sha256)
            or not expected_boot or not expected_campaign):
        return unresolved('INVALID_LOCAL_EVIDENCE')
    if type(snapshot) is not dict:
        return unresolved('INVALID_SNAPSHOT')
    if snapshot.get('boot') != expected_boot:
        return unresolved('BOOT_CHANGED')
    if snapshot.get('campaign') != expected_campaign:
        return unresolved('CAMPAIGN_CHANGED')
    completed = snapshot.get('completed')
    if type(completed) is not int or completed not in (exported_leg, exported_leg+1):
        return unresolved('UNEXPECTED_PROGRESSION')
    phase = snapshot.get('phase')
    retained = snapshot.get('retained_leg')
    if retained is not None and (type(retained) is not int or retained != completed):
        return unresolved('RETAINED_EVIDENCE_MISMATCH')
    if completed == exported_leg:
        if phase not in ('AWAITING_EXPORT', 'FAULT') or retained != exported_leg:
            return unresolved('UNACCEPTED_RECEIPT_EVIDENCE_MISSING')
        if snapshot.get('last_receipt_sha256') == receipt_sha256:
            return unresolved('RECEIPT_PROGRESS_CONTRADICTION')
        return {**result, 'state': 'RECEIPT_NOT_ACCEPTED',
                'reason': 'DO_NOT_REPLAY;_REVIEW_RETAINED_RESULT',
                'evidence_retrieval_required': True}
    if snapshot.get('last_receipt_sha256') != receipt_sha256:
        return unresolved('ACCEPTED_RECEIPT_MISMATCH')
    if completed == expected_legs:
        if phase != 'COMPLETE' or retained is not None:
            return unresolved('FINAL_STATE_MISMATCH')
        return {**result, 'state': 'CAMPAIGN_COMPLETE', 'reason': 'NO_RESUMPTION'}
    if phase not in ('BASELINE', 'PREWRITE', 'OBSERVE', 'AWAITING_EXPORT', 'FAULT'):
        return unresolved('INVALID_PHASE')
    if phase == 'AWAITING_EXPORT' and retained != completed:
        return unresolved('NEXT_RESULT_MISSING')
    return {**result, 'state': 'RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE',
            'reason': 'RECONCILE_NEXT_LEG_AND_FRESH_POSE',
            'evidence_retrieval_required': True}
