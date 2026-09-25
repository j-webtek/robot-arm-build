"""Offline, replay-linked pair preparation; never loads keys or opens devices."""
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .held_elbow_trial_draft import draft_held_elbow_trial
from .held_pair_command_contract import freeze_held_pair_plan
from .hold_started_review import _prepared
from .product_ghost_export_review import _read
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _build(root, hold_export_id, forward_command_id, return_command_id, offset, tolerance):
    draft=draft_held_elbow_trial(root,hold_export_id,offset_counts=offset,tolerance_counts=tolerance)
    link,source_hash=_read(root,hold_export_id,'attachment-observed-hold.json')
    _,prepared_hash,hold_plan,policy,_=_prepared(root,link['prepared_export_id'])
    if hold_plan['boot_id']!=draft['source_boot_id'] or source_hash!=draft['source_sha256']:
        raise ValueError('Hold reference changed during preparation')
    hold_hash=hashlib.sha256(canonical(hold_plan)).hexdigest()
    frozen=freeze_held_pair_plan(policy,boot_id=hold_plan['boot_id'],hold_plan_sha256=hold_hash,
        forward_command_id=forward_command_id,return_command_id=return_command_id,
        offset_counts=offset,tolerance_counts=tolerance)
    return dict(schema='rocell.held_pair_preparation.v1',origin='OFFLINE_PREPARATION',
        hold_export_id=hold_export_id,hold_observation_sha256=source_hash,
        prepared_hold_export_id=link['prepared_export_id'],prepared_hold_sha256=prepared_hash,
        pair_plan=decode_diagnostic_json(frozen.encoded,maximum=1536),
        pair_plan_sha256=hashlib.sha256(frozen.encoded).hexdigest(),policy=policy,
        historical_anchor=draft['historical_anchor'],illustrative_targets=draft['illustrative_targets'],
        fresh_same_boot_handoff_required=True,challenge_required=True,
        progression_authority=False,retry_allowed=False)


def prepare_held_pair(root,hold_export_id,*,forward_command_id,return_command_id,
                      offset_counts=6,tolerance_counts=2):
    """Retain a plan derived only from a verified hold chain, then reopen it.

    An old boot's plan cannot authorize a new boot. This is preparation only;
    installed capability, fresh challenge and the native handoff remain required.
    """
    root=Path(root).resolve()
    report=_build(root,hold_export_id,forward_command_id,return_command_id,offset_counts,tolerance_counts)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'held-pair-preparation'},[],
                         attachments={'held-pair-preparation.json':canonical(report)})
    replay=replay_held_pair_preparation(root,Path(saved['path']).name)
    return dict(export_path=saved['path'],**replay)


def replay_held_pair_preparation(root,export_id):
    root=Path(root).resolve()
    report,digest=_read(root,export_id,'attachment-held-pair-preparation.json')
    if type(report) is not dict or type(report.get('pair_plan')) is not dict:
        raise ValueError('Pair preparation document required')
    try:
        plan=report['pair_plan']
        rebuilt=_build(root,report['hold_export_id'],plan['forward_command_id'],plan['return_command_id'],
                       plan['offset_counts'],plan['tolerance_counts'])
    except (KeyError,TypeError) as exc:
        raise ValueError('Incomplete pair preparation') from exc
    if canonical(rebuilt)!=canonical(report):
        raise ValueError('Pair preparation/source linkage does not replay')
    return dict(replay_verified=True,preparation_sha256=digest,preparation=rebuilt,
                progression_authority=False,retry_allowed=False)
