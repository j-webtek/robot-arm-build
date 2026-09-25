"""Offline export/signing coordinator; contains no network or movement API.

Future transport must authenticate the source boot/campaign before calling this
object: binary result records themselves do not carry those identities.
"""
import copy
import hashlib
import hmac
from .characterization_admission import encode_manifest
from .characterization_result_codec import decode_result, export_result
from .compensated_shoulder_contract import Pose
from .shoulder_characterization import assess_leg
from .shoulder_movement_matrix import (matrix_anchor,is_mapping_batch,
    is_ghost_pair_transition,classify_observation)
from .servo_start_authorization import _hex, _key


def _pose(record):
    rows = record['joints']
    feedback = [bytes.fromhex(row['feedback_hex']) for row in rows]
    return Pose(tuple(row['position'] for row in rows), tuple(row['goal'] for row in rows),
                tuple(row['torque'] for row in rows),
                tuple(bool(raw[2] or raw[3] or raw[10]) for raw in feedback),
                record['started_us'], record['finished_us'])


class CharacterizationHostSession:
    def __init__(self, root, manifest, *, key, boot, campaign, reference):
        _key(key); _hex(boot, 16)
        encode_manifest(manifest, campaign=campaign, reference=reference)
        self._manifest = copy.deepcopy(manifest)
        self._root, self._key, self._boot, self._campaign = root, key, boot, campaign
        self._next = 0
        self._failed = False
        self._matrix_anchor = matrix_anchor(manifest['goals'])
        self._retained_small_response = (self._matrix_anchor is not None or
                                         is_mapping_batch(manifest['goals']))
        self._ghost_pair_transition=is_ghost_pair_transition(manifest['goals'])
        self._consecutive_small = 0
        self._direct_small_streak = 0

    def export_and_sign(self, raw, *, source_boot, source_campaign):
        """Issue at most one receipt per leg; any rejected attempt ends this session.

        Source identity arguments must come from authenticated transport context,
        not from untrusted response fields. Lost replies require reconciliation,
        not replay through this method.
        """
        if self._failed:
            raise ValueError('Host session stopped')
        try:
            if source_boot != self._boot or source_campaign != self._campaign:
                raise ValueError('Source identity mismatch')
            record = decode_result(raw)
            if (record['leg'] != self._next or record['legs'] != len(self._manifest['goals'])
                    or any(record[name] != self._manifest[name] for name in ('goals', 'bounds', 'maximum_us'))):
                raise ValueError('Result manifest or sequence mismatch')
            saved = export_result(self._root, raw)
            before = _pose(record['baseline'])
            samples = [_pose(p) for p in record['observations']]
            if self._matrix_anchor is not None and self._next == 0:
                if tuple(before.goals[1:3]) != self._matrix_anchor:
                    raise ValueError('Matrix anchor changed')
            assessment = assess_leg(_pose(record['baseline']), record['goals'][self._next],
                                    [_pose(p) for p in record['observations']],
                                    bounds=record['bounds'], delivery_confirmed=True, export_verified=True)
            direct=self._ghost_pair_transition and (
                2<=self._next<=5 or 8<=self._next<=10)
            if self._ghost_pair_transition:
                # Mirror the native endpoint and direction checks before a
                # durable receipt can unlock the next physical write.
                primary=record['goals'][self._next][0]
                expected={2377:(2385,1730),2386:(2388,1727),
                          2388:(2390,1725),2389:(2391,1724)}[primary]
                final=samples[-1].positions
                if any(abs(final[j+1]-expected[j])>2 for j in range(2)):
                    raise ValueError('Ghost endpoint outside frozen window')
                if direct:
                    if samples[-1].finished_us-samples[0].started_us<2000000:
                        raise ValueError('Ghost direct transition observation too short')
                    command=primary-before.goals[1]
                    primary_delta=final[1]-before.positions[1]
                    paired_delta=final[2]-before.positions[2]
                    if (primary_delta*(1 if command>0 else -1)<1 or
                            paired_delta*(1 if command<0 else -1)<0):
                        raise ValueError('Ghost direct transition direction unverified')
                    if self._direct_small_streak>=4:
                        raise ValueError('Ghost direct small-response streak exceeded')
                    if (assessment['reason']=='NO_CLEAR_RESPONSE' and
                            samples[-1].finished_us-samples[0].started_us>=2000000):
                        assessment=dict(assessment,status='SETTLED_SMALL_RESPONSE',
                            reason='GHOST_VERIFIED_SMALL_RESPONSE',
                            continuation_eligible=True)
            if (self._retained_small_response and not direct and
                    assessment['reason'] == 'NO_CLEAR_RESPONSE'):
                summary = classify_observation(before, record['goals'][self._next], samples,
                    bounds=record['bounds'], delivery_confirmed=True, export_verified=True,
                    consecutive_small=self._consecutive_small)
                # Result v1 lacks sent_us. Require a conservative two seconds
                # after the first post-write sample, which cannot predate send.
                if (summary['candidate_progression_eligible'] and
                        samples[-1].finished_us-samples[0].started_us >= 2000000):
                    assessment = dict(assessment, status='SETTLED_SMALL_RESPONSE',
                        reason='SMALL_RESPONSE_RETAINED', continuation_eligible=True,
                        motion_summary=summary)
            if assessment['status'] != record['outcome'] or not assessment['continuation_eligible']:
                raise ValueError('Independent result assessment rejected')
            unsigned = (b'RCSHEX01' + bytes.fromhex(self._boot)
                        + hashlib.sha256(self._campaign.encode('ascii')).digest()
                        + self._next.to_bytes(4, 'little') + hashlib.sha256(raw).digest())
            receipt = unsigned + hmac.digest(self._key, unsigned, 'sha256')
            self._consecutive_small = (self._consecutive_small+1
                if assessment['status']=='SETTLED_SMALL_RESPONSE' else 0)
            if self._ghost_pair_transition:
                self._direct_small_streak=(self._direct_small_streak+1 if direct and
                    assessment['status']=='SETTLED_SMALL_RESPONSE' else 0)
            self._next += 1
            return dict(export_path=saved['export_path'], receipt=receipt, assessment=assessment,
                        receipt_issued=True, controller_acceptance_confirmed=False)
        except Exception:
            self._failed = True
            raise
