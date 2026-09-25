"""Policy-only synthetic evidence; no claim of recovery authentication."""
import pytest
from rocell.application.characterization_reconciliation import assess_receipt_reconciliation


def assess(**changes):
    snapshot = dict(boot='boot', campaign='campaign', completed=1,
                    phase='AWAITING_EXPORT', retained_leg=1,
                    last_receipt_sha256='a'*64)
    snapshot.update(changes)
    return assess_receipt_reconciliation(expected_boot='boot', expected_campaign='campaign',
        exported_leg=0, receipt_sha256='a'*64, snapshot=snapshot)


def test_accepted_receipt_never_permits_resume():
    result = assess()
    assert result['state'] == 'RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE'
    assert result['evidence_retrieval_required']
    assert not result['resume_allowed']
    assert not result['physical_pose_verified']


def test_unaccepted_receipt_does_not_allow_replay():
    result = assess(completed=0, retained_leg=0, last_receipt_sha256=None)
    assert result['state'] == 'RECEIPT_NOT_ACCEPTED'
    assert not result['resume_allowed']


@pytest.mark.parametrize('changes', [dict(boot='reboot'), dict(campaign='other'),
    dict(completed=2), dict(completed=True), dict(retained_leg=0),
    dict(retained_leg=None), dict(last_receipt_sha256='b'*64), dict(phase='COMPLETE'),
    dict(completed=0, retained_leg=0)])
def test_inconsistent_evidence_remains_unresolved(changes):
    result = assess(**changes)
    assert result['state'] == 'UNRESOLVED'
    assert not result['resume_allowed']


def test_final_receipt_completion():
    result = assess_receipt_reconciliation(expected_boot='boot', expected_campaign='campaign',
        exported_leg=11, receipt_sha256='a'*64,
        snapshot=dict(boot='boot', campaign='campaign', completed=12, phase='COMPLETE',
                      retained_leg=None, last_receipt_sha256='a'*64))
    assert result['state'] == 'CAMPAIGN_COMPLETE'
    assert not result['resume_allowed']
