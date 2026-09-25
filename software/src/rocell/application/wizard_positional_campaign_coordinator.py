"""Trusted-host staging and final-click execution of two attended wrist legs.

Staging retains reviewed originals but opens no device and signs no live intent.
Only final acceptance starts the fixed lifetime. Browser inputs never select
serial paths, commands, executable files, or evidence originals.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import uuid

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .positional_campaign_reference_reader import ORIGINAL_FILES, PositionalCampaignReferenceReader
from .positional_campaign_launch import reserve_campaign_launch
from .positional_campaign_process_owner import run_campaign_process
from .positional_campaign_native_export import verify_native_retained_export
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, fixed_campaign_limits, CAPACITY_SCHEMA, CORRECTION_SCHEMA, SINGLE_SCHEMA, BASE_SCHEMA
from rocell.providers.windows import positional_campaign_native_package as package
from rocell.safety.positional_campaign_authority import SYNC_BASE_SCHEMA, TWO_DEGREE_BASE_SCHEMA, MIDPOINT_BASE_SCHEMA, BASE_MIDPOINT_TARGETS
from rocell.safety.positional_campaign_authority import BASE_CORRECTION_SCHEMA, BASE_CONTROL_SCHEMA
from rocell.safety.positional_campaign_authority import BASE_SEQUENCE_SCHEMA, BASE_SPEED_SCHEMA, ROLL_PROBE_SCHEMA, ROLL_FIXED_SCHEMA, roll_probe_configuration, roll_fixed_configuration
from rocell.safety.positional_campaign_authority import BASE_CORRECTED_SCHEMAS, BASE_EXPERIMENT_SCHEMAS, DECREASING_BASE_CORRECTION_SCHEMA, DECREASING_BASE_CONTROL_SCHEMA
from rocell.providers.windows import positional_campaign_native_protocol as protocol
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile, WorkerProcessRegistration, owned_registration_document,
)
from rocell.providers.windows.positional_campaign_process_codec import prepare_owned_request


@dataclass(frozen=True)
class StagedPositionalCampaign:
    registration: WorkerProcessRegistration
    root: Path
    template: bytes

    def preview(self):
        """Return a copy; the template's timestamps are inert validation values."""
        body = json.loads(self.template)
        return dict(campaign_id=body['campaign_id'], usb_identity=body['usb_identity'],
            legs=body['legs'], limits=body['limits'], references=body['references'],
            selected_joint=body.get('selected_joint','t'),
            roll_case_id=body.get('roll_probe',{}).get('case_id'),
            start_joints_rad=body['start_joints_rad'],
            experiment_kind=('SPEED_CANDIDATE' if body['schema']==BASE_SPEED_SCHEMA else 'CORRECTED_SEQUENCE' if body['schema']==BASE_SEQUENCE_SCHEMA else 'CORRECTED' if body['schema'] in BASE_CORRECTED_SCHEMAS else
                'UNCORRECTED_CONTROL' if body['schema'] in BASE_EXPERIMENT_SCHEMAS else None),
            experiment_direction='ALTERNATING' if body['schema']==BASE_SEQUENCE_SCHEMA else body.get('base_speed',{}).get('specification',body.get('base_experiment',{})).get('direction'),
            motion_authorized=False, replay_allowed=False)


def stage_positional_campaign(workspace, *, root, session_id, usb_identity,
        start_joints_rad, targets_rad, originals):
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=targets_rad,originals=originals,single=type(targets_rad) is list and len(targets_rad)==1)


def stage_roll_mapping_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, direction, originals):
    """One uncorrected roll degree in a fixed pose context; no arbitrary joint API."""
    config=roll_probe_configuration(direction)
    if type(start_joints_rad) is not list or len(start_joints_rad)!=6:
        raise ValueError('Six reported starting joints required')
    target=start_joints_rad[4]+math.radians(1 if direction=='INCREASING' else -1)
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,targets_rad=[target],
        originals=dict(originals,configuration_sha256=canonical(config)),roll=config,synchronize=True)


def stage_roll_persistence_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, direction, originals):
    """One roll command, then 35 seconds on the same connection; no return."""
    from rocell.safety.positional_campaign_authority import roll_persistence_configuration
    config=roll_persistence_configuration(direction)
    target=start_joints_rad[4]+math.radians(1 if direction=='INCREASING' else -1)
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,targets_rad=[target],
        originals=dict(originals,configuration_sha256=canonical(config)),roll=config,synchronize=True)


def stage_roll_long_fixed_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, direction, originals, framed=False):
    from rocell.safety.positional_campaign_authority import roll_long_fixed_configuration
    config=roll_long_fixed_configuration(direction, framed=framed)
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,targets_rad=[config['target_rad']],
        originals=dict(originals,configuration_sha256=canonical(config)),roll=config,synchronize=True)


def stage_roll_target_variation(workspace, *, root, session_id, usb_identity,
        start_joints_rad, case_id, originals):
    """Stage one named case; return cases require their own measured baseline."""
    from rocell.safety.positional_campaign_authority import roll_variation_configuration
    config=roll_variation_configuration(case_id)
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,targets_rad=[config['target_rad']],
        originals=dict(originals,configuration_sha256=canonical(config)),roll=config,synchronize=True)


def stage_roll_fixed_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, direction, originals):
    """One enumerated raw roll target with a measured-start anchor."""
    config=roll_fixed_configuration(direction)
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[config['target_rad']],
        originals=dict(originals,configuration_sha256=canonical(config)),roll=config,synchronize=True)


def stage_base_midpoint_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, target_name, originals):
    """Two enumerated absolute targets; no free-form midpoint command API."""
    if type(target_name) is not str or target_name not in BASE_MIDPOINT_TARGETS:
        raise ValueError('Known fixed midpoint required')
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[BASE_MIDPOINT_TARGETS[target_name]],originals=originals,
        base=True,synchronize=True,midpoint=True)


def stage_base_mapping_probe(workspace, *, root, session_id, usb_identity,
        start_joints_rad, delta_deg, originals, synchronize=False):
    """One versioned local base probe; no arbitrary axis or angle dispatch API."""
    if type(delta_deg) not in (int,float) or delta_deg not in (-2,-1,1,2):
        raise ValueError('Base mapping supports only signed one/two-degree probes')
    if type(synchronize) is not bool:
        raise ValueError('Explicit synchronization profile required')
    if abs(delta_deg)==2 and not synchronize:
        raise ValueError('Two-degree base probes require synchronization')
    if type(start_joints_rad) is not list or len(start_joints_rad)!=6:
        raise ValueError('Six starting joint angles required')
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[start_joints_rad[0]+math.radians(delta_deg)],
        originals=originals,base=True,synchronize=synchronize,two_degree=abs(delta_deg)==2)


def stage_model_corrected_campaign(workspace, *, root, session_id, usb_identity,
        start_joints_rad, originals, model_raw, expected_model_sha256, exports):
    """Reverify original model evidence before staging one corrected command.

    This trusted-host entry point is not a browser-provided angle interface.
    Staging opens no device. Execution uses the ordinary reviewed, owned native
    campaign path, including its fresh baseline and one-use write boundaries.
    """
    from .wrist_model_correction import propose_model_correction
    proposal=propose_model_correction(model_raw,expected_model_sha256=expected_model_sha256,
        exports=exports,start_joints_rad=start_joints_rad)
    p=proposal.to_dict()
    supplied=dict(originals)
    supplied['configuration_sha256']=proposal.original
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[math.radians(p['nominal_target_deg'])],
        originals=supplied,correction=p)


def stage_base_compensation_experiment(workspace, *, root, session_id, usb_identity,
        start_joints_rad, originals, model_raw, expected_model_sha256,
        training_exports, held_out, experiment_kind, direction='INCREASING'):
    """Rebuild evidence before either member of the fixed correction/control pair.

    Trusted-host intake only: neither a browser angle API nor a serial connection.
    A control uses the same proposal provenance without applying its inverse.
    """
    if experiment_kind not in ('CORRECTED','UNCORRECTED_CONTROL'):
        raise ValueError('Explicit base correction or matched control required')
    if direction not in ('INCREASING','DECREASING'):
        raise ValueError('Known frozen base direction required')
    from .base_correction_proposal import propose_base_correction, propose_decreasing_base_correction
    proposer=propose_decreasing_base_correction if direction=='DECREASING' else propose_base_correction
    proposal=proposer(model_raw,expected_model_sha256=expected_model_sha256,
        training_exports=training_exports,held_out=held_out,start_joints_rad=start_joints_rad)
    supplied=dict(originals)
    supplied['configuration_sha256']=proposal.original
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[proposal.to_dict()['nominal_target_rad']],originals=supplied,
        base=True,synchronize=True,base_experiment=proposal.to_dict(),experiment_kind=experiment_kind)


def stage_base_speed_experiment(workspace, *, root, session_id, usb_identity,
        start_joints_rad, originals, model_raw, expected_model_sha256,
        training_exports, held_out, direction='INCREASING'):
    """Stage one fixed speed-10 candidate; no arbitrary speed or recovery API."""
    from .base_correction_proposal import propose_base_correction, propose_decreasing_base_correction
    from .base_speed_experiment import speed_experiment_spec
    spec=speed_experiment_spec(direction=direction,speed=10)
    proposer=propose_decreasing_base_correction if direction=='DECREASING' else propose_base_correction
    proposal=proposer(model_raw,expected_model_sha256=expected_model_sha256,
        training_exports=training_exports,held_out=held_out,start_joints_rad=start_joints_rad).to_dict()
    config=dict(schema='rocell.base_speed_configuration.v1',specification=spec,proposal=proposal)
    supplied=dict(originals,configuration_sha256=canonical(config))
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[spec['desired_rad']],originals=supplied,base=True,synchronize=True,
        base_speed=config)


def stage_base_alternating_sequence(workspace, *, root, session_id, usb_identity,
        start_joints_rad, originals, model_raw, expected_model_sha256, training_exports, held_out):
    """Rebuild both frozen directions; stage only the fixed four-leg route."""
    from .base_correction_proposal import propose_base_correction, propose_decreasing_base_correction
    from .first_motion_contract import canonical
    evidence=dict(expected_model_sha256=expected_model_sha256,training_exports=training_exports,held_out=held_out)
    up_start=list(start_joints_rad);up_start[0]=.007669904
    down_start=list(start_joints_rad);down_start[0]=.018407769
    up=propose_base_correction(model_raw,start_joints_rad=up_start,**evidence).to_dict()
    down=propose_decreasing_base_correction(model_raw,start_joints_rad=down_start,**evidence).to_dict()
    config=dict(schema='rocell.base_alternating_configuration.v1',increasing=up,decreasing=down)
    supplied=dict(originals,configuration_sha256=canonical(config))
    return _stage_positional_campaign(workspace,root=root,session_id=session_id,
        usb_identity=usb_identity,start_joints_rad=start_joints_rad,
        targets_rad=[math.radians(1),math.radians(.4)]*2,originals=supplied,
        base=True,synchronize=True,base_sequence=config)


def _stage_positional_campaign(workspace, *, root, session_id, usb_identity,
        start_joints_rad, targets_rad, originals, correction=None, single=False, base=False, synchronize=False, two_degree=False, midpoint=False,
        base_experiment=None, experiment_kind=None, base_sequence=None, base_speed=None, roll=None):
    """Retain host-reviewed records; do not infer their physical truth.

    Start joints and both targets are host-selected. A fresh six-joint baseline
    must match at execution; historical start angles cannot authorize a write.
    """
    files = dict(ORIGINAL_FILES)
    files.pop('stop_qualification_sha256')
    files['bounded_motion_risk_sha256'] = 'bounded-motion-risk.original.json'
    required = set(files) - {'runtime_sha256'}
    if type(originals) is not dict or set(originals) != required:
        raise ValueError('Exact host-reviewed campaign originals required')
    if type(targets_rad) is not list or len(targets_rad) != (4 if base_sequence is not None else 1 if correction is not None or single or base or roll is not None else 2):
        raise ValueError('Exactly two explicit wrist targets required')
    if type(start_joints_rad) is not list or len(start_joints_rad) != 6:
        raise ValueError('Six host-reviewed starting joint angles required')
    refs = {}
    for name, raw in originals.items():
        limit = 2_097_152 if name == 'owned_baseline_sha256' else 131072
        if type(raw) is not bytes:
            raise ValueError('Immutable original bytes required')
        value = decode_diagnostic_json(raw, maximum=limit)
        if type(value) is not dict or not value or canonical(value) != raw:
            raise ValueError('Canonical structured originals required')
        refs[name] = hashlib.sha256(raw).hexdigest()
    root, workspace = safe_root(Path(root)), safe_root(Path(workspace))
    refs.update(source_sha256=source_fingerprint(workspace), runtime_sha256='a'*64)
    campaign_id = 'campaign-' + uuid.uuid4().hex
    legs, previous = [], start_joints_rad[4 if roll is not None else 0 if base else 3]
    for index, target in enumerate(targets_rad):
        legs.append(dict(leg_id=f'leg-{index+1:02d}', expected_start_rad=previous,
            target_rad=target, command=dict(T=101, joint=5 if roll is not None else 1 if base else 4, rad=target, spd=20, acc=1)))
        previous = target
    schema=BASE_SCHEMA if base else CORRECTION_SCHEMA if correction is not None else SINGLE_SCHEMA if single else CAPACITY_SCHEMA
    if synchronize:
        if not base and roll is None:raise ValueError('Synchronization requires a versioned joint probe')
        schema=SYNC_BASE_SCHEMA
    if two_degree:
        if not base or not synchronize:raise ValueError('Two-degree profile requires synchronized base')
        schema=TWO_DEGREE_BASE_SCHEMA
    if midpoint:
        if not base or not synchronize or two_degree:raise ValueError('Fixed midpoint requires synchronized base')
        schema=MIDPOINT_BASE_SCHEMA
    if correction is not None:
        legs[0]['command']['rad']=correction['proposed_command_target_rad']
    if base_experiment is not None:
        if not base or not synchronize or two_degree or midpoint or correction is not None or single:
            raise ValueError('Base experiment requires its own synchronized single-command profile')
        if experiment_kind not in ('CORRECTED','UNCORRECTED_CONTROL'):
            raise ValueError('Unknown base experiment kind')
        schema=BASE_CORRECTION_SCHEMA if experiment_kind=='CORRECTED' else BASE_CONTROL_SCHEMA
        if base_experiment['direction']=='DECREASING':
            schema=DECREASING_BASE_CORRECTION_SCHEMA if experiment_kind=='CORRECTED' else DECREASING_BASE_CONTROL_SCHEMA
        if experiment_kind=='CORRECTED':
            legs[0]['command']['rad']=base_experiment['proposed_command_target_rad']
    if roll is not None:
        schema=ROLL_FIXED_SCHEMA if roll['schema']=='rocell.roll_fixed_configuration.v1' else ROLL_PROBE_SCHEMA
        if roll['schema']=='rocell.roll_persistence_configuration.v1':
            from rocell.safety.positional_campaign_authority import ROLL_PERSISTENCE_SCHEMA
            schema=ROLL_PERSISTENCE_SCHEMA
        if roll['schema']=='rocell.roll_long_fixed_configuration.v1':
            from rocell.safety.positional_campaign_authority import ROLL_LONG_FIXED_SCHEMA
            schema=ROLL_LONG_FIXED_SCHEMA
        if roll['schema']=='rocell.roll_long_fixed_configuration.v2':
            from rocell.safety.positional_campaign_authority import ROLL_FRAMED_SCHEMA
            schema=ROLL_FRAMED_SCHEMA
        if roll['schema']=='rocell.roll_target_variation_configuration.v1':
            from rocell.safety.positional_campaign_authority import ROLL_VARIATION_SCHEMA
            schema=ROLL_VARIATION_SCHEMA
    body = dict(schema=schema, mode='ATTENDED_ONE_ROLL_PROBE' if roll is not None else 'ATTENDED_ONE_BASE_PROBE' if base else 'ATTENDED_ONE_CORRECTION' if correction is not None else 'ATTENDED_ONE_CONTROL' if single else 'ATTENDED_TWO_LEG',
        session_id=session_id, campaign_id=campaign_id, usb_identity=dict(usb_identity),
        references=refs, start_joints_rad=list(start_joints_rad), legs=legs,
        limits=fixed_campaign_limits(schema), issued_ns=1,
        deadline_ns=1+fixed_campaign_limits(schema)['maximum_duration_s']*1_000_000_000)
    if base:
        body['selected_joint']='b'
    if roll is not None:
        body.update(selected_joint='r',roll_probe=roll)
    if correction is not None:
        body['correction']=correction
    if base_experiment is not None:
        body['base_experiment']=base_experiment
    if base_sequence is not None:
        from .base_alternating_sequence import _assemble_template
        body=_assemble_template(body,base_sequence['increasing'],base_sequence['decreasing']).to_dict()
        # Assembly copies the references; retain the live runtime association.
        refs=body['references']
        schema=BASE_SEQUENCE_SCHEMA
    if base_speed is not None:
        from .base_speed_experiment import assemble_speed_template
        body=assemble_speed_template(body,base_speed['proposal']).to_dict()
        refs=body['references']
        schema=BASE_SPEED_SCHEMA
    PositionalCampaignIntent(canonical(body))  # Reject invalid routes before writing.
    directory = contained_path(root, campaign_id+'-positional-native-child', label='campaign staging')
    directory.mkdir(exist_ok=False)
    for name, raw in originals.items():
        publish_reservation_bytes(directory, files[name], raw, maximum_bytes=2_097_152)
    archive = package.prepare(directory)
    def pin(path):
        raw = read_bounded_regular_file(path, maximum_bytes=32*1024*1024)
        return PinnedWorkerFile(path, hashlib.sha256(raw).hexdigest())
    pins = tuple(pin(path) for path in (package.CHILD, archive,
        directory/'controller.original.json', directory/'protocol.original.json'))
    registration = WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys, '_base_executable', sys.executable))),
        ('-I', '-S', str(package.CHILD), str(archive), pins[1].sha256, 'execute-campaign'),
        pins, directory, protocol.fixed_budget(schema), 'PHYSICAL_UNQUALIFIED',
        protocol.REQUEST_SCHEMA, protocol.RESULT_SCHEMA)
    runtime = canonical(owned_registration_document(registration))
    publish_reservation_bytes(directory, files['runtime_sha256'], runtime, maximum_bytes=32768)
    refs['runtime_sha256'] = hashlib.sha256(runtime).hexdigest()
    intent = PositionalCampaignIntent(canonical(body))
    PositionalCampaignReferenceReader(intent, workspace=workspace, root=root)()
    # Decode the original binding now, not only after the operator clicks Start.
    from rocell.providers.windows.endpoint_child_execution import decode_controller_binding
    binding = decode_controller_binding(originals['native_controller_review_sha256'], intent)
    from .physical_connection_contracts import EvidenceOrigin
    if (binding.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION
            or (binding.identity.vid, binding.identity.pid, binding.identity.unit_serial)
            != (f"{usb_identity['vid']:04x}", f"{usb_identity['pid']:04x}", usb_identity['serial_number'])):
        raise ValueError('Controller original must describe the selected physical arm')
    return StagedPositionalCampaign(registration, root, intent.canonical_bytes)


def run_staged_positional_campaign(*args, **kwargs):
    """Exclude participating Wi-Fi sessions throughout owned USB execution."""
    from rocell.providers.windows.arm_transport_lock import arm_transport_lock
    with arm_transport_lock():
        return _run_staged_positional_campaign(*args, **kwargs)


def _run_staged_positional_campaign(workspace, staged, *, operator_id, checks,
        accepted_ns, cancellation, export_root, check_current, clock_ns=time.monotonic_ns):
    """Seal once, reserve once, run once, then copy verified original diagnostics.

    A cancelled/failed run is never retried. Export failure preserves its original
    session files and is not permission to repeat motion.
    """
    from threading import Event
    from rocell.providers.windows.bench_review_key import load_host_positional_campaign_review_authority
    from rocell.providers.windows.positional_campaign_bootstrap import prepare_authenticated_campaign_reader
    if (type(staged) is not StagedPositionalCampaign or type(cancellation) is not Event
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact host campaign and cancellation required')
    def current():
        if cancellation.is_set() or check_current() is not None:
            raise ValueError('Campaign cancelled or wizard context changed')
    current()
    export_root = safe_root(Path(export_root))  # Check destination before any motion.
    body = json.loads(staged.template)
    body.update(issued_ns=accepted_ns, deadline_ns=accepted_ns+body['limits']['maximum_duration_s']*1_000_000_000)
    intent = PositionalCampaignIntent(canonical(body))
    intent.require_start_time(clock_ns())
    authority = load_host_positional_campaign_review_authority(workspace)
    signed = authority.seal(intent, dict(operator_id=operator_id, recorded_ns=accepted_ns,
        checks=dict(checks)), now_ns=clock_ns())
    publish_reservation_bytes(staged.root, body['campaign_id']+'-positional-review.json',
        signed, maximum_bytes=24576)
    payload = dict(schema=protocol.PAYLOAD_SCHEMA, root=str(staged.root), campaign_intent=body,
        registration=owned_registration_document(staged.registration), launch_sha256='a'*64,
        review_authority_id='local-positional-campaign-review-v1')
    # Bootstrap checks originals/current USB without needing a launch reservation.
    _, raw = prepare_owned_request(staged.registration, payload)
    reader = prepare_authenticated_campaign_reader(workspace, raw,
        cancellation=cancellation, clock_ns=clock_ns)
    current()
    payload['launch_sha256'] = reserve_campaign_launch(staged.root, reader,
        runtime_original=canonical(payload['registration']))
    current()
    outcome = run_campaign_process(staged.registration, payload,
        cancellation=cancellation, clock_ns=clock_ns)
    # Copy only the finite report manifest, never arbitrary session directories.
    source = contained_path(staged.root, outcome['report_file'], label='campaign report')
    report_raw = read_bounded_regular_file(source, maximum_bytes=65536)
    report = decode_diagnostic_json(report_raw, maximum=65536)
    destination = contained_path(safe_root(Path(export_root)), body['campaign_id'], label='campaign export')
    destination.mkdir(exist_ok=False)
    for item in report['originals'].values():
        raw = read_bounded_regular_file(contained_path(staged.root, item['file'],
            label='campaign export original'), maximum_bytes=4*1024*1024)
        publish_reservation_bytes(destination, item['file'], raw, maximum_bytes=4*1024*1024)
    publish_reservation_bytes(destination, source.name, report_raw, maximum_bytes=65536)
    verified = verify_native_retained_export(destination, source.name)
    if not verified['valid'] or verified['report_sha256'] != outcome['report_sha256']:
        raise ValueError('Copied campaign export failed verification; do not replay')
    # Publish derived display diagnostics, never mutate the retained originals.
    return dict(outcome, export_directory=str(destination),
        endpoint_diagnostics=verified['endpoint_diagnostics'])
