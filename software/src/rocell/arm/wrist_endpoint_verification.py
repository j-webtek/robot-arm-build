"""Software-only endpoint evidence from already validated reported joint rows.

No hardware access or motion authority. Arrival tolerance is distinct from a
quiet dwell: repeatedly crossing the target band is not a settled endpoint.
"""
import math

from .first_motion_analysis import TOLERANCE_RAD, DWELL_NS

SETTLE_SPAN_RAD = math.radians(.1)


class ReportedWristMonitor:
    """Constant-memory incremental checker, shared with final reanalysis.

    Snapshots are provisional until complete capture/transport validation. A
    later departure revokes settling; no snapshot can authorize another move.
    """
    def __init__(self, *, start, target, path_target=None):
        if (type(start) not in (tuple,list) or len(start) != 6
                or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in start)
                or type(target) not in (int,float) or not math.isfinite(target) or abs(target)>100):
            raise ValueError('Finite six-joint start and target required')
        self.start, self.target = tuple(start), target
        # Arrival is measured against intent; excursion follows the exact command.
        self.path_target = target if path_target is None else path_target
        if (type(self.path_target) not in (int,float)
                or not math.isfinite(self.path_target) or abs(self.path_target)>100):
            raise ValueError('Finite commanded path target required')
        self.changed = self.reached = self.other_changed = self.excursion = False
        self.quiet = self.low = self.high = self.final_error = None
        self.settled = self.invalid = False
        self.count = 0
        self.previous_bounds = (0,0)

    def push(self, row):
        if self.invalid:
            raise ValueError('Monitor already invalidated')
        try:
            begin, finish, joints = row
            if (self.count >= 4096 or type(begin) is not int or type(finish) is not int
                    or not 0 < begin <= finish or begin < self.previous_bounds[0]
                    or finish < self.previous_bounds[1] or len(joints) != 6
                    or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in joints)):
                raise ValueError('Invalid or unbounded endpoint row')
        except (ValueError, TypeError):
            self.invalid = True
            raise ValueError('Invalid endpoint row') from None
        self.count += 1
        self.previous_bounds = (begin,finish)
        value = joints[3]
        self.final_error = value-self.target
        self.changed |= abs(value-self.start[3]) > TOLERANCE_RAD
        self.reached |= abs(self.final_error) <= TOLERANCE_RAD
        self.other_changed |= any(abs(joints[i]-self.start[i]) > TOLERANCE_RAD for i in (0,1,2,4,5))
        self.excursion |= not min(self.start[3],self.path_target)-TOLERANCE_RAD <= value <= max(self.start[3],self.path_target)+TOLERANCE_RAD
        if abs(self.final_error) > TOLERANCE_RAD:
            self.quiet = None
            self.settled = False
            return
        if self.quiet is None or max(self.high,value)-min(self.low,value) > SETTLE_SPAN_RAD:
            self.quiet, self.low, self.high = (begin,finish), value, value
        else:
            self.low, self.high = min(self.low,value), max(self.high,value)
        self.settled = begin-self.quiet[1] >= DWELL_NS

    def snapshot(self, *, capture_issues=(), transport_clean=True):
        if type(transport_clean) is not bool:
            raise ValueError('Explicit transport status required')
        if not transport_clean:
            status = 'TRANSPORT_FAULT'
        elif self.invalid or capture_issues or not self.count:
            status = 'FEEDBACK_INVALID'
        elif self.other_changed:
            status = 'OTHER_JOINT_CHANGED'
        elif self.excursion:
            status = 'WRIST_EXCURSION'
        elif not self.changed:
            status = 'NO_RESPONSE'
        elif abs(self.final_error) > TOLERANCE_RAD:
            status = 'TARGET_MISSED'
        elif not self.settled:
            status = 'NOT_SETTLED'
        else:
            status = 'REPORTED_SETTLED'
        return dict(schema='rocell.reported_wrist_endpoint.v1',status=status,
            movement_detected=self.changed,target_band_entered=self.reached,
            final_in_target_band=self.final_error is not None and abs(self.final_error)<=TOLERANCE_RAD,
            endpoint_verified=status == 'REPORTED_SETTLED',final_error_rad=self.final_error,
            arrival_tolerance_rad=TOLERANCE_RAD,settling_span_rad=SETTLE_SPAN_RAD,
            required_dwell_ns=DWELL_NS,
            quiet_dwell_entry_bounds_ns=list(self.quiet) if self.settled and status == 'REPORTED_SETTLED' else None,
            other_joint_changed=self.other_changed,wrist_excursion=self.excursion,
            physical_accuracy_verified=False,device_sample_freshness_verified=False,
            motion_authorized=False,automatic_next_command_allowed=False)


def verify_reported_wrist(rows, *, start, target, capture_issues, transport_clean, path_target=None):
    monitor = ReportedWristMonitor(start=start,target=target,path_target=path_target)
    for row in rows:
        try:
            monitor.push(row)
        except ValueError:
            break
    return monitor.snapshot(capture_issues=capture_issues,transport_clean=transport_clean)
