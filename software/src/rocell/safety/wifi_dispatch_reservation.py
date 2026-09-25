"""Durable exact-command Wi-Fi dispatch latch; not physical commissioning.

Only the owning process may consume it once. The native composition must still
own the transport lock, obtain its own fresh baseline, and recheck device identity.
Reservations never restore after a crash, even if dispatch might not have occurred.
"""
from copy import deepcopy
import hashlib
import os
import re
from threading import Lock

from rocell.application.first_motion_contract import canonical
from rocell.application.move_request import describe_request
from rocell.application.physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file)
from rocell.arm.discrete_transaction import DiscreteTransaction
from rocell.providers.windows.arm_wifi_feedback import ADDRESS, MAC
from rocell.providers.windows.arm_wifi_observation import review_observation


class WifiDispatchReservation:
    def __init__(self, *, root, attempt_id, baseline, target, now_ns, completion_budget_ns,
                 desired_endpoint=None):
        if type(attempt_id) is not str or not re.fullmatch(r'[a-f0-9]{32}',attempt_id):
            raise ValueError('Unique hexadecimal attempt id required')
        if (baseline.get('status')!='SUCCEEDED' or baseline.get('address')!=ADDRESS
                or baseline.get('expected_mac')!=MAC or not baseline.get('identity_before_matched')
                or not baseline.get('identity_after_matched') or not baseline.get('cleanup_confirmed')):
            raise ValueError('Verified pinned baseline required')
        review_observation(dict(schema='rocell.arm_wifi_observation.v4',samples=[baseline]))
        finish=round(baseline['response_finished_monotonic_s']*1e9)
        if type(now_ns) is not int or not finish<=now_ns<=finish+1_000_000_000:
            raise ValueError('Fresh baseline required')
        self.transaction=DiscreteTransaction(baseline=[baseline['joints_rad'][k] for k in ('b','s','e','t','r','g')],
            baseline_finished_ns=finish,target=target,completion_budget_ns=completion_budget_ns,
            desired_endpoint=desired_endpoint)
        self._publish(root=root,attempt_id=attempt_id,baseline=baseline,now_ns=now_ns,
            finish=finish,completion_budget_ns=completion_budget_ns,desired_endpoint=desired_endpoint)

    def _publish(self, *, root, attempt_id, baseline, now_ns, finish,
                 completion_budget_ns, desired_endpoint=None, request=None):
        """Shared durable latches; concrete constructors validate their own scope."""
        self._command=self.transaction.snapshot()['command']
        self._root=safe_root(root);self._id=attempt_id;self._pid=os.getpid()
        self._lock=Lock();self._used=False;self._consumed=False;self._native_claimed=False;self._expires=finish+1_000_000_000
        self._created=now_ns
        record=dict(schema='rocell.wifi_dispatch_reservation.v1',attempt_id=attempt_id,
            owner_pid=self._pid,address=ADDRESS,mac=MAC,baseline=baseline,command=self._command,
            created_ns=now_ns,expires_ns=self._expires,completion_budget_ns=completion_budget_ns)
        if desired_endpoint is not None:
            record.update(schema='rocell.wifi_dispatch_reservation.v2',desired_endpoint_rad=desired_endpoint)
        self._request = request if request is not None else describe_request(attempt_id=attempt_id,
            transaction=self.transaction.snapshot(), address=ADDRESS, mac=MAC)
        record['move_request'] = self._request
        self._raw=canonical(record)
        self._name=attempt_id+'-wifi-reserved.json'
        publish_reservation_bytes(self._root,self._name,self._raw,maximum_bytes=16384)

    def consume(self, command, *, now_ns, observed_mac, cancelled=False):
        """Persist consumed state BEFORE returning bytes to a future native sender."""
        with self._lock:
            if self._used:raise ValueError('Wi-Fi attempt already consumed')
            # Any failed consumption burns this process object too.
            self._used=True
            if (os.getpid()!=self._pid or type(now_ns) is not int
                    or not self._created<=now_ns<=self._expires or cancelled
                    or observed_mac!=MAC or canonical(command)!=canonical(self._command)):
                raise ValueError('Wi-Fi dispatch binding mismatch or expiry')
            raw=read_bounded_regular_file(contained_path(self._root,self._name,label='Wi-Fi reservation'),maximum_bytes=16384)
            if raw!=self._raw:raise ValueError('Wi-Fi reservation changed')
            publish_reservation_bytes(self._root,self._id+'-wifi-consumed.json',
                canonical(dict(attempt_id=self._id,consumed_ns=now_ns,
                    reservation_sha256=hashlib.sha256(raw).hexdigest())),maximum_bytes=4096)
            self._consumed=True
            return canonical(self._command)

    def claim_native_send(self, payload, *, now_ns, observed_mac):
        """Second one-use latch at the native socket boundary; no reissue."""
        with self._lock:
            if self._native_claimed or not self._consumed:
                raise ValueError('Native dispatch unavailable')
            self._native_claimed=True
            if (os.getpid()!=self._pid or type(now_ns) is not int
                    or not self._created<=now_ns<=self._expires
                    or observed_mac!=MAC or payload!=canonical(self._command)):
                raise ValueError('Native dispatch binding changed')
            raw=read_bounded_regular_file(contained_path(self._root,self._name,label='Wi-Fi reservation'),maximum_bytes=16384)
            if raw!=self._raw:raise ValueError('Reservation changed before native send')
            publish_reservation_bytes(self._root,self._id+'-wifi-native-send.json',
                canonical(dict(attempt_id=self._id,claimed_ns=now_ns,
                    payload_sha256=hashlib.sha256(payload).hexdigest())),maximum_bytes=4096)

    def command(self):
        return deepcopy(self._command)

    def request(self):
        """Return the pre-dispatch description, never a resumable reservation."""
        return deepcopy(self._request)
