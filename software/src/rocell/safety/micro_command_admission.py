"""Staged micro-command admission; deliberately has NO native dispatch method.

Validates originals and durably consumes a one-use experimental intent. This
does not prove exclusive actuator ownership, provide a sender, or modify the
existing >0.5-degree live admission. Native dispatch stays disabled.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
from threading import Lock

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.physical_onboarding_durability import (
    safe_root, publish_reservation_bytes, read_bounded_regular_file, contained_path)
from rocell.arm.discrete_endpoint import verify_discrete_endpoint
from rocell.providers.windows.arm_wifi_observation import review_observation
from rocell.providers.windows.arm_wifi_feedback import ADDRESS, MAC

JOINTS=('b','s','e','t','r','g')
COMMAND=dict(T=101,joint=5,rad=math.radians(.90),spd=20,acc=1)


def predecessor(path, expected_sha256, *, require_micro_range=True):
    """Replay exact prior command, endpoint and a full unchanged hold."""
    if type(require_micro_range) is not bool:raise ValueError('Explicit range review mode required')
    path=Path(path).resolve()
    raw=(path/'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256 or not verify_export(path)['valid']:
        raise ValueError('Predecessor integrity mismatch')
    reports=[]
    for item in json.loads(raw)['files']:
        name=item['name']
        if name.startswith('attachment-result-') and name.endswith('.json'):
            reports.extend(s['report'] for s in json.loads((path/name).read_bytes()).get('steps',[])
                           if 'report' in s)
    moves=[r for r in reports if 'outcome' in r]
    holds=[r for r in reports if 'samples' in r]
    if len(moves)!=1 or len(holds)!=1:
        raise ValueError('One predecessor movement and hold required')
    outcome=moves[0]['outcome'];tx=outcome['transaction'];hold=holds[0]
    if (canonical(tx['command'])!=canonical(dict(T=101,joint=5,rad=math.radians(.95),spd=20,acc=1))
            or tx['command_attempts']!=1 or hold.get('status')!='SUCCEEDED'
            or tx['baseline'][4]<=tx['command']['rad']
            or not math.isclose(tx.get('desired_endpoint_rad',float('nan')),math.radians(1.25),abs_tol=1e-12)):
        raise ValueError('Wrong predecessor command or incomplete hold')
    samples=outcome['feedback_originals']
    review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=samples))
    rows=[[round(s['request_started_monotonic_s']*1e9),round(s['response_finished_monotonic_s']*1e9),
           [s['joints_rad'][j] for j in JOINTS]] for s in samples]
    saved=tx['result']
    actual=verify_discrete_endpoint(rows,joint='r',start=tx['baseline'],
        target=tx.get('desired_endpoint_rad',tx['command']['rad']),
        command_finished_ns=saved['command_finished_ns'],
        completion_deadline_ns=saved['completion_deadline_ns'],evaluated_ns=saved['evaluated_ns'],
        **({'command_target':tx['command']['rad']} if 'desired_endpoint_rad' in tx else {}))
    if rows!=tx['rows'] or actual!=saved or not actual['endpoint_verified']:
        raise ValueError('Predecessor endpoint replay mismatch')
    reconstruction=review_observation(hold)
    if (reconstruction!=hold['reconstruction'] or not reconstruction['valid']
            or reconstruction['response_span_s']<34 or reconstruction['maximum_response_gap_ms']>1000):
        raise ValueError('Full bounded predecessor hold required')
    end=rows[-1][1];pose=rows[-1][2]
    for sample in hold['samples']:
        begin=round(sample['request_started_monotonic_s']*1e9)
        finish=round(sample['response_finished_monotonic_s']*1e9)
        if not end<=begin<=finish or [sample['joints_rad'][j] for j in JOINTS]!=pose:
            raise ValueError('Predecessor hold changed or unordered')
        end=finish
    if require_micro_range and not 1.35<=math.degrees(pose[4])<=1.45:
        raise ValueError('Predecessor outside experimental starting range')
    return dict(export_id=path.name,manifest_sha256=expected_sha256,pose=pose,finished_ns=end,
                dispatch_ns=tx['dispatch_started_ns'])


class MicroCommandAdmission:
    """Durable, process-bound one-use intent. Native authority is always false."""
    def __init__(self, *, root, attempt_id, predecessor_path, predecessor_sha256, baseline, now_ns):
        if not isinstance(attempt_id,str) or not re.fullmatch('[0-9a-f]{32}',attempt_id):
            raise ValueError('Unique attempt ID required')
        prior=predecessor(predecessor_path,predecessor_sha256)
        if (baseline.get('status')!='SUCCEEDED' or baseline.get('address')!=ADDRESS
                or baseline.get('expected_mac')!=MAC
                or baseline.get('identity_before_matched') is not True
                or baseline.get('identity_after_matched') is not True
                or baseline.get('cleanup_confirmed') is not True):
            raise ValueError('Pinned original baseline required')
        review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=[baseline]))
        finish=round(baseline['response_finished_monotonic_s']*1e9)
        begin=round(baseline['request_started_monotonic_s']*1e9)
        pose=[baseline['joints_rad'][j] for j in JOINTS]
        if (type(now_ns) is not int or not finish<=now_ns<=finish+1_000_000_000
                or begin<prior['finished_ns'] or begin-prior['finished_ns']>30_000_000_000
                or pose!=prior['pose']):
            raise ValueError('Fresh unchanged baseline after predecessor required')
        self._root=safe_root(root);self._id=attempt_id;self._pid=os.getpid()
        self._used=False;self._lock=Lock();self._created=now_ns;self._expires=finish+1_000_000_000
        self._path=Path(predecessor_path);self._sha=predecessor_sha256
        self._record=dict(schema='rocell.micro_command_admission.staged.v1',attempt_id=attempt_id,
            owner_pid=self._pid,predecessor=prior,baseline=baseline,command=COMMAND,
            previous_command_deg=.95,command_delta_deg=-.05,desired_endpoint_deg=1.25,
            created_ns=now_ns,expires_ns=self._expires,native_enabled=False,
            exclusive_actuator_ownership_proven=False,motion_authorized=False)
        self._raw=canonical(self._record)
        self._name=attempt_id+'-micro-staged.json'
        publish_reservation_bytes(self._root,self._name,self._raw,maximum_bytes=16384)

    def snapshot(self):
        """Detached staged context for offline orchestration, never a permit."""
        return json.loads(self._raw)

    def consumed_receipt(self):
        """Recheck successful consumption bytes; this does not grant native access."""
        with self._lock:
            receipt=getattr(self,'_receipt',None)
            if receipt is None or os.getpid()!=self._pid:
                raise ValueError('No successful consumption in this process')
            raw=read_bounded_regular_file(contained_path(self._root,self._id+'-micro-consumed.json',
                label='micro consumption'),maximum_bytes=4096)
            if raw!=canonical(receipt):raise ValueError('Micro consumption changed')
            return json.loads(raw)

    def consume(self, command, *, now_ns, observed_mac, cancelled=False):
        """Burn intent even on failure; return audit metadata, never sender bytes."""
        with self._lock:
            if self._used:raise ValueError('Micro intent already consumed')
            self._used=True
            if (os.getpid()!=self._pid or type(now_ns) is not int or cancelled
                    or not self._created<=now_ns<=self._expires or observed_mac!=MAC
                    or canonical(command)!=canonical(COMMAND)):
                raise ValueError('Micro intent mismatch or expiry')
            raw=read_bounded_regular_file(contained_path(self._root,self._name,label='micro admission'),maximum_bytes=16384)
            if raw!=self._raw:raise ValueError('Staged admission changed')
            predecessor(self._path,self._sha)
            receipt=dict(attempt_id=self._id,consumed_ns=now_ns,
                         staged_sha256=hashlib.sha256(raw).hexdigest(),
                         native_enabled=False,motion_authorized=False)
            publish_reservation_bytes(self._root,self._id+'-micro-consumed.json',canonical(receipt))
            self._receipt=json.loads(canonical(receipt))
            return receipt
