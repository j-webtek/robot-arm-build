"""Explicit single-leg wizard adapter and exclusive session event journal."""
import hashlib
import os
from pathlib import Path
import platform
import re
import time

from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes, safe_root


class SessionJournal:
    """Exclusive, flushed, hash-linked event files; incomplete tails are fatal.

    No reopening/resuming API. A failed write poisons the writer. Hashes detect
    modifications but are not authentication against a malicious writer.
    """
    def __init__(self,root,session_id):
        if not re.fullmatch('[0-9a-f]{32}',session_id):raise ValueError('Session ID required')
        self.root=safe_root(Path(root).resolve())
        self.session_id=session_id;self._records=[];self._failed=False
        self._prefix='comparison-'+session_id
        self._header=canonical(dict(session_id=session_id,pid=os.getpid(),host=platform.node(),
            clock=time.get_clock_info('perf_counter').implementation,
            clock_scope='SAME_PROCESS_INVOCATION',boot_identity_verified=False,resumable=False))
        self._header_path=publish_reservation_bytes(self.root,self._prefix+'-header.json',self._header)

    def __call__(self,event):
        if self._failed:raise ValueError('Journal unavailable after publication failure')
        try:
            if event.get('session_id')!=self.session_id:raise ValueError('Session mismatch')
            if self._header_path.read_bytes()!=self._header:raise ValueError('Header changed')
            for path,raw in self._records:
                if path.read_bytes()!=raw:raise ValueError('Journal changed')
            previous=self._records[-1][1] if self._records else self._header
            raw=canonical(dict(sequence=len(self._records),previous_sha256=hashlib.sha256(previous).hexdigest(),
                event=event))
            path=publish_reservation_bytes(self.root,
                f'{self._prefix}-{len(self._records):04d}.json',raw,maximum_bytes=128*1024)
            self._records.append((path,raw))
        except Exception:
            self._failed=True
            raise


class WizardComparisonAdapter:
    """One fresh wizard per leg keeps each diagnostic export unambiguous."""
    ACTIONS={name:'run_wifi_roll_'+name+'_trial' for name in
             ('high','zero','center_up','center_down','lookup','sweep_low','sweep_center','sweep_high')}

    def __init__(self,root,*,service_factory,export_observer,clock=time.monotonic,wait=time.sleep):
        self.root=Path(root);self.factory=service_factory;self.export_observer=export_observer
        self.clock=clock;self.wait=wait

    def _action(self,service,name):
        ticket=service.prepare_action(name,{},service.view()['revision'])
        operation=service.execute_action(ticket['ticket_id'])
        deadline=self.clock()+65
        while True:
            result=service.operation(operation['operation_id'])
            if result['status'] not in ('QUEUED','RUNNING'):return result
            if self.clock()>=deadline:raise TimeoutError('Wizard operation deadline')
            self.wait(.05)

    def __call__(self,action):
        if action not in self.ACTIONS:raise ValueError('Enumerated comparison action required')
        service=self.factory(self.root,mode='physical')
        path=None
        try:
            move=self._action(service,self.ACTIONS[action])
            if move['status']=='SUCCEEDED':
                self._action(service,'observe_arm_wifi_bounded')
        finally:
            try:
                exported=self._action(service,'export_logs')
                receipt=(exported.get('result') or {}).get('receipt') or {}
                if exported['status']!='SUCCEEDED' or not receipt.get('path'):
                    raise ValueError('Diagnostic export unavailable')
                path=Path(receipt['path']).resolve()
                # Record the path even if execution/observation raised earlier.
                self.export_observer(path)
            finally:
                service.shutdown()
        return path
