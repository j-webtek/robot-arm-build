"""Durable, process-owned rehearsal sequence records; never native authority.

An exclusive reservation is written before the modeled dispatch boundary.
Reopening a journal permits inspection only, never continuation or replay. These
semantics are exercised without adding a device backend to the sequencer.
"""
import hashlib
import base64
import json
import os
from threading import Lock

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
    publish_bytes, PublicationMode,
)
from rocell.motion.positional_campaign import PositionalCampaign

MAX_RECORD_BYTES = 131072


class PositionalCampaignJournal:
    """One newly created run, owned by its creating process and never resumed.

    The caller supplies a private, existing, empty run directory. Every write
    reserves commands with exclusive final names: a partial file consumes the slot.
    Result commits use immutable atomic publication, after a reservation exists.
    A failed publication poisons this object even if the final file is absent.
    Files and hashes are diagnostic integrity evidence, not authentication.
    """
    def __init__(self, root, plan):
        if type(plan) is not PositionalCampaign:
            raise ValueError('Exact simulation contract required')
        self.root = safe_root(root)
        if any(self.root.iterdir()):
            raise ValueError('New empty campaign directory required; no resume')
        self.plan = plan
        self._pid, self._lock = os.getpid(), Lock()
        self._poisoned, self._pending, self._next = False, None, 1
        self._originals = {}
        self._previous = plan.sha256
        self._header = canonical(dict(schema='rocell.positional_rehearsal_journal.v1',
            plan=plan.to_dict(),plan_sha256=plan.sha256,owner_pid=self._pid,
            physical_authority=False,replay_allowed=False))
        self._publish('campaign.json',self._header)

    def _read(self, name):
        return read_bounded_regular_file(contained_path(self.root,name,label='campaign record'),
            maximum_bytes=MAX_RECORD_BYTES)

    def _publish(self, name, raw, *, commit=False):
        try:
            if commit:
                publish_bytes(self.root,name,raw,mode=PublicationMode.IMMUTABLE,
                    maximum_bytes=MAX_RECORD_BYTES)
            else:
                publish_reservation_bytes(self.root,name,raw,maximum_bytes=MAX_RECORD_BYTES)
            if self._read(name) != raw:
                raise ValueError('Campaign record readback differs')
            self._originals[name] = raw
        except BaseException:
            self._poisoned = True
            raise

    def _require_owner(self):
        if self._poisoned or os.getpid() != self._pid:
            raise ValueError('Campaign owner lost or held; no replay')
        try:
            if {path.name for path in self.root.iterdir()} != set(self._originals):
                raise ValueError('Campaign directory changed')
            for name,raw in self._originals.items():
                if self._read(name) != raw:
                    raise ValueError('Campaign predecessor or original changed')
        except BaseException:
            self._poisoned = True
            raise

    def reserve(self, leg_id, baseline, predecessor_sha256):
        """Bind the exact original baseline and predecessor before any dispatch."""
        with self._lock:
            self._require_owner()
            legs = self.plan.to_dict()['legs']
            if (self._pending is not None or self._next > len(legs)
                    or leg_id != legs[self._next-1]['leg_id']
                    or predecessor_sha256 != self._previous):
                raise ValueError('Leg replay, order or predecessor mismatch')
            # This is a rehearsal storage boundary, not a live admission check.
            # The sequencer validates baseline data before reaching this method.
            body = dict(schema='rocell.positional_rehearsal_reservation.v1',
                plan_sha256=self.plan.sha256,leg=legs[self._next-1],
                predecessor_sha256=predecessor_sha256,baseline_sha256=
                hashlib.sha256(canonical(baseline)).hexdigest(),
                physical_authority=False,dispatch_may_have_occurred=True,replay_allowed=False)
            raw = canonical(body)
            self._publish(leg_id+'-reserved.json',raw)
            self._pending = (leg_id,raw)

    def commit(self, record):
        """Commit the exact sequencer result before permitting another leg.

        This class does not independently certify endpoint accuracy. Its caller
        is the closed rehearsal engine, and exported results are reconstructed
        by that engine. Native result admission needs a separate authority.
        """
        with self._lock:
            self._require_owner()
            if self._pending is None:
                raise ValueError('No reserved leg to commit')
            leg_id, reservation = self._pending
            bound = json.loads(reservation)
            if (record['leg_id'] != leg_id or record['predecessor_sha256'] != self._previous
                    or canonical(record['command']) != canonical(bound['leg']['command'])
                    or hashlib.sha256(canonical(record['baseline'])).hexdigest() != bound['baseline_sha256']
                    or self._read(leg_id+'-reserved.json') != reservation
                    or record['status'] != 'LEG_VERIFIED'
                    or record['endpoint']['endpoint_verified'] is not True
                    or record['incremental_matches_final'] is not True):
                self._poisoned = True
                raise ValueError('Original-bound successful leg required')
            raw = canonical(record)
            self._publish(leg_id+'-result.json',raw,commit=True)
            self._previous = hashlib.sha256(raw).hexdigest()
            self._pending = None
            self._next += 1

    def hold(self):
        """Irrevocable in-process hold; an unresolved reservation remains on disk."""
        with self._lock:
            self._poisoned = True


def inspect_campaign_journal(root):
    """Read-only crash disposition. Even a clean prefix never grants resume."""
    root = safe_root(root)
    names = {p.name for p in root.iterdir()}
    if len(names) > 17 or 'campaign.json' not in names:
        raise ValueError('Invalid or oversized campaign directory')
    header_raw = read_bounded_regular_file(root/'campaign.json',maximum_bytes=MAX_RECORD_BYTES)
    header = json.loads(header_raw)
    plan = PositionalCampaign(canonical(header['plan']))
    if (set(header) != {'schema','plan','plan_sha256','owner_pid','physical_authority','replay_allowed'}
            or header['schema'] != 'rocell.positional_rehearsal_journal.v1'
            or header['physical_authority'] is not False or header['replay_allowed'] is not False
            or type(header['owner_pid']) is not int or header['owner_pid'] <= 0
            or canonical(header) != header_raw or header['plan_sha256'] != plan.sha256):
        raise ValueError('Changed campaign header')
    expected = {'campaign.json'}
    committed, pending = [], []
    for leg in plan.to_dict()['legs']:
        leg_id = leg['leg_id']
        reservation, result = leg_id+'-reserved.json', leg_id+'-result.json'
        expected.update((reservation,result))
        if result in names and reservation not in names:
            raise ValueError('Result without reservation')
        if reservation in names:
            # Incomplete reservation/result bytes intentionally remain held.
            (committed if result in names else pending).append(leg_id)
    if names-expected:
        raise ValueError('Unexpected campaign entries')
    return dict(status='REVIEW_REQUIRED_NO_RESUME',committed_file_legs=committed,
        unresolved_reservations=pending,physical_authority=False,replay_allowed=False,
        contents_verified=False)


def export_campaign_journal(root, report):
    """Retain exact journal originals and check them against the replayable run."""
    disposition = inspect_campaign_journal(root)
    files = []
    for path in sorted(safe_root(root).iterdir()):
        raw = read_bounded_regular_file(path,maximum_bytes=MAX_RECORD_BYTES)
        files.append(dict(name=path.name,raw_base64=base64.b64encode(raw).decode(),
            sha256=hashlib.sha256(raw).hexdigest()))
    bundle = dict(schema='rocell.positional_rehearsal_journal_export.v1',files=files,
        physical_authority=False,replay_allowed=False)
    verify_campaign_journal_export(bundle,report)
    return dict(bundle=bundle,recovery=disposition)


def verify_campaign_journal_export(bundle, report):
    """Original-bound comparison, not trust in saved success flags or filenames."""
    from .positional_campaign_rehearsal import verify_rehearsal_report
    verify_rehearsal_report(report)
    if (type(bundle) is not dict or set(bundle) != {'schema','files','physical_authority','replay_allowed'}
            or bundle['schema'] != 'rocell.positional_rehearsal_journal_export.v1'
            or bundle['physical_authority'] is not False or bundle['replay_allowed'] is not False
            or type(bundle['files']) is not list or not 1 <= len(bundle['files']) <= 17):
        raise ValueError('Invalid journal export')
    originals = {}
    for item in bundle['files']:
        if type(item) is not dict or set(item) != {'name','raw_base64','sha256'}:
            raise ValueError('Exact journal original required')
        if not isinstance(item['raw_base64'],str) or len(item['raw_base64']) > MAX_RECORD_BYTES*2:
            raise ValueError('Oversized journal original')
        raw = base64.b64decode(item['raw_base64'],validate=True)
        if (len(raw) > MAX_RECORD_BYTES or hashlib.sha256(raw).hexdigest() != item['sha256']
                or item['name'] in originals):
            raise ValueError('Journal digest, size or duplicate name mismatch')
        originals[item['name']] = raw
    header = json.loads(originals.get('campaign.json',b'{}'))
    expected_header = dict(schema='rocell.positional_rehearsal_journal.v1',
        plan=report['plan'],plan_sha256=report['plan_sha256'],owner_pid=header.get('owner_pid'),
        physical_authority=False,replay_allowed=False)
    if type(header.get('owner_pid')) is not int or header['owner_pid'] <= 0:
        raise ValueError('Journal owner missing')
    expected = {'campaign.json':canonical(expected_header)}
    for index,record in enumerate(report['legs']):
        if record['command'] is None:
            continue
        leg_id = record['leg_id']
        reservation = dict(schema='rocell.positional_rehearsal_reservation.v1',
            plan_sha256=report['plan_sha256'],leg=report['plan']['legs'][index],
            predecessor_sha256=record['predecessor_sha256'],
            baseline_sha256=hashlib.sha256(canonical(record['baseline'])).hexdigest(),
            physical_authority=False,dispatch_may_have_occurred=True,replay_allowed=False)
        expected[leg_id+'-reserved.json'] = canonical(reservation)
        if record['status'] == 'LEG_VERIFIED':
            expected[leg_id+'-result.json'] = canonical({k:v for k,v in record.items() if k != 'record_sha256'})
    if originals != expected:
        raise ValueError('Journal originals disagree with reconstructed run')
    return dict(valid=True,physical_authority=False,replay_allowed=False)
