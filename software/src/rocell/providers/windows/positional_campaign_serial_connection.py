"""One owned connection across enumerated legs; no reopen or implicit commands.

Only the campaign facade consumes the final submission claim. This owner tracks
phase-local and aggregate IO accounting, using the existing pending-IO cleanup.
It is not registered in a native worker or wizard action yet.
"""
from copy import deepcopy
import time

from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from .positional_campaign_serial_api import WindowsPositionalCampaignSerialApi
from .endpoint_serial_connection import EndpointSerialConnection
from .nonpurging_serial_api import _int


class PositionalCampaignSerialConnection(EndpointSerialConnection):
    def __init__(self, request, api, *, clock_ns=time.monotonic_ns):
        if (type(request) is not PositionalCampaignIntent
                or type(api) is not WindowsPositionalCampaignSerialApi
                or api.admitted_request_sha256 != request.sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted campaign connection required')
        self._initialize_owned_state(request, api, clock_ns)
        self._legs = []

    def _runtime_body(self):
        return self._request.runtime_body()

    def _active(self):
        self._check_cancelled()
        if self._phase != 'OPEN' or self._pending is not None or not self._legs:
            raise ValueError('Open idle uncancelled campaign leg required')
        return self._legs[-1]

    def _check_cancelled(self):
        if self._api._cancellation.is_set():
            self._phase = 'FAILED'
            self._api._permit.revoke()
            raise ValueError('Campaign cancelled; connection cannot rearm')

    def begin_leg(self, leg_id):
        with self._lock:
            self._check_cancelled()
            if (self._phase != 'OPEN' or self._pending is not None
                    or len(self._legs) >= self._request.to_dict()['limits']['maximum_writes'] or any(leg['leg_id'] == leg_id for leg in self._legs)):
                raise ValueError('Campaign leg cannot begin or replay')
            self._api._permit.require_leg_start(leg_id, self._now())
            self._legs.append(dict(leg_id=leg_id, submission_attempted=False,
                confirmed_write_bytes=0, read_calls=dict(baseline=0, post=0),
                read_bytes=dict(baseline=0, post=0)))

    def read(self, maximum_bytes, timeout_ms):
        with self._lock:
            leg = self._active()
            _int(maximum_bytes, 1, 256, 'campaign_read_size')
            _int(timeout_ms, 1, 100, 'campaign_read_timeout')
            phase = 'post' if leg['submission_attempted'] else 'baseline'
            limits = self._runtime_body()['limits']
            if (leg['read_calls'][phase] >= limits[f'maximum_{phase}_reads']
                    or leg['read_bytes'][phase] + maximum_bytes > limits[f'maximum_{phase}_bytes']
                    or sum(self._read_bytes.values()) + maximum_bytes > self._request.to_dict()['limits']['maximum_total_raw_bytes']):
                self._phase = 'FAILED'
                self._api._permit.revoke()
                raise ValueError('Campaign phase or aggregate read budget exhausted')
            leg['read_calls'][phase] += 1
            self._read_calls[phase] += 1
            available = self._queue().input_bytes
            if not available:
                return b''
            result = self._io('read', min(maximum_bytes, available), b'', timeout_ms)
            leg['read_bytes'][phase] += result.transferred
            self._read_bytes[phase] += result.transferred
            return result.data

    def _motion_payload(self):
        return self._api._motion_payload()

    def write_once(self, payload):
        with self._lock:
            leg = self._active()
            if leg['submission_attempted']:
                raise ValueError('One submission per campaign leg; no retry')
            leg['submission_attempted'] = True
            try:
                if type(payload) is not bytes or payload != self._motion_payload():
                    raise ValueError('Exact reserved campaign payload required')
                self._queue()
                self._check_cancelled()
                # The inherited cleanup stores a late completion here. Start
                # this leg's slot at zero, never at the prior leg's byte count.
                self._write_bytes = 0
                result = self._io('write', len(payload), payload, 1000)
                self._write_bytes = leg['confirmed_write_bytes'] = result.transferred
                return result.transferred
            except Exception:
                self._phase = 'FAILED'
                self._api._permit.revoke()
                raise

    def close(self, timeout_ms):
        with self._lock:
            pending_write = self._pending is not None and self._pending.kind == 'write'
            result = super().close(timeout_ms)
            if pending_write and self._legs:
                self._legs[-1]['confirmed_write_bytes'] = self._write_bytes
            return result

    def snapshot(self):
        with self._lock:
            result = super().snapshot()
            result['schema'] = 'rocell.positional_campaign_connection_lifecycle.v1'
            result['legs'] = deepcopy(self._legs)
            result['confirmed_write_bytes'] = sum(leg['confirmed_write_bytes'] for leg in self._legs)
            return result
