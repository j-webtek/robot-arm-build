"""Source-linked token release from saved receipts. Does not send or load keys."""
from pathlib import Path
from .first_motion_contract import canonical
from .held_pair_challenge_http import replay_pair_challenge
from .held_pair_preparation import replay_held_pair_preparation
from .held_pair_prepared_authorization import authorize_prepared_held_pair,replay_initial_pair_authorization
from .held_pair_return_authorization import authorize_observed_pair_return,replay_pair_return_authorization
from .held_pair_observed_forward import replay_observed_pair_forward
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _receipt(root,receipt_id,leg):
    expected={'forward':'prepare','return':'return'}
    if leg not in expected:raise ValueError('Named leg required')
    receipt=replay_pair_challenge(root,receipt_id)
    if (receipt['intent']['operation']!=expected[leg] or
            receipt['report']['result']['category']!='CHALLENGE_RECEIVED'):
        raise ValueError('Confirmed challenge receipt for this operation required')
    return receipt


def authorize_pair_from_receipt(root,receipt_id,source_export_id,key,*,leg,forward_delivery_export_id=None):
    """Release token only after linked workflow export reopens successfully.

    A workflow-export failure after signing leaves the signer claim consumed.
    A received challenge is historical evidence, not proof its lease is live now.
    """
    root=Path(root).resolve();receipt=_receipt(root,receipt_id,leg)
    challenge=receipt['report']['result']['challenge']
    if leg=='forward':
        if forward_delivery_export_id is not None:raise ValueError('Unexpected forward delivery dependency')
        source=replay_held_pair_preparation(root,source_export_id)
        boot=source['preparation']['pair_plan']['boot_id']
    else:
        source=replay_observed_pair_forward(root,source_export_id)
        boot=source['authorization']['preparation']['pair_plan']['boot_id']
    if boot!=challenge['boot_id']:raise ValueError('Receipt and source boot differ')
    if leg=='forward':
        authorization=authorize_prepared_held_pair(root,source_export_id,challenge,key)
    else:
        authorization=authorize_observed_pair_return(root,source_export_id,challenge,key,
            forward_delivery_export_id=forward_delivery_export_id)
    report=dict(schema='rocell.pair_receipt_workflow.v1',leg=leg,
                receipt_export_id=receipt_id,receipt_sha256=receipt['export_sha256'],
                authorization_context_id=authorization.context_export_id,
                source_export_id=source_export_id,progression_authority=False,retry_allowed=False)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'pair-receipt-workflow'},[],
        attachments={'pair-receipt-workflow.json':canonical(report)})
    replay=replay_pair_receipt_workflow(root,Path(saved['path']).name)
    return dict(authorization=authorization,export_path=saved['path'],**replay)


def replay_pair_receipt_workflow(root,export_id):
    root=Path(root).resolve();report,digest=_read(root,export_id,'attachment-pair-receipt-workflow.json')
    if (type(report) is not dict or set(report)!={'schema','leg','receipt_export_id','receipt_sha256',
            'authorization_context_id','source_export_id','progression_authority','retry_allowed'} or
            report['schema']!='rocell.pair_receipt_workflow.v1' or
            report['progression_authority'] is not False or report['retry_allowed'] is not False):
        raise ValueError('Invalid receipt workflow')
    receipt=_receipt(root,report['receipt_export_id'],report['leg'])
    reviewer=replay_initial_pair_authorization if report['leg']=='forward' else replay_pair_return_authorization
    context=reviewer(root,report['authorization_context_id'])['context']
    source_key='preparation_export_id' if report['leg']=='forward' else 'forward_export_id'
    if (receipt['export_sha256']!=report['receipt_sha256'] or
            canonical(context['challenge'])!=canonical(receipt['report']['result']['challenge']) or
            context[source_key]!=report['source_export_id']):
        raise ValueError('Receipt workflow source mismatch')
    return dict(replay_verified=True,report=report,export_sha256=digest,progression_authority=False)
