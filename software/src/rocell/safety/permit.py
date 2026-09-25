"""Short-lived, consumable capabilities for the live arm boundary.

The permits in this module are deliberately opaque to transport callers. A
motion permit enumerates exact goals; a feedback permit authorizes exactly one
T=105 request. Both are issued through :class:`SafetySupervisor`, consumed at
the transport boundary, and fail closed on expiry or revocation.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import threading
import time
from typing import Any, Iterable, Mapping

from rocell.rc03.build_snapshot import Capability


class MotionPermitError(RuntimeError):
    """A short-lived exact-goal permit is invalid or cannot be issued."""


class FeedbackPermitError(RuntimeError):
    """A one-shot arm-feedback permit is invalid or cannot be issued."""


_ISSUER = object()


def _checked_clock(value: object | None) -> float:
    """Reject invalid clocks before any capability can be consumed or issued."""
    if value is None:
        value = time.monotonic()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Monotonic clock must be numeric")
    now = float(value)
    if not math.isfinite(now):
        raise ValueError("Monotonic clock must be finite")
    return now


class FeedbackPermit:
    """One-use capability for the live arm's documented T=105 query.

    The permit carries the immutable build snapshot hash that authorized it.
    The transport consumes it before attempting a write, so failures cannot be
    retried accidentally with the same authorization.
    """

    def __init__(
        self,
        *,
        _issuer: object,
        snapshot_hash: str,
        expires_at_monotonic: float,
    ) -> None:
        if _issuer is not _ISSUER:
            raise FeedbackPermitError(
                "Feedback permits may only be issued by SafetySupervisor"
            )
        if not isinstance(snapshot_hash, str) or not snapshot_hash.strip():
            raise FeedbackPermitError("snapshot_hash must be a non-empty string")
        if not math.isfinite(expires_at_monotonic):
            raise FeedbackPermitError("Feedback permit expiry must be finite")
        self.snapshot_hash = snapshot_hash
        self.expires_at_monotonic = float(expires_at_monotonic)
        self._consumed = False
        self._revoked = False
        self._lock = threading.Lock()

    @classmethod
    def _issue(
        cls,
        *,
        snapshot_hash: str,
        ttl_s: float,
        now_monotonic: float | None = None,
    ) -> "FeedbackPermit":
        if isinstance(ttl_s, bool) or not isinstance(ttl_s, (int, float)):
            raise FeedbackPermitError("ttl_s must be numeric")
        ttl = float(ttl_s)
        if not math.isfinite(ttl) or ttl <= 0:
            raise FeedbackPermitError("ttl_s must be positive and finite")
        try:
            now = _checked_clock(now_monotonic)
        except (ValueError, OverflowError) as exc:
            raise FeedbackPermitError("now_monotonic must be a finite numeric clock") from exc
        return cls(
            _issuer=_ISSUER,
            snapshot_hash=snapshot_hash,
            expires_at_monotonic=now + ttl,
        )

    def revoke(self) -> None:
        with self._lock:
            self._revoked = True

    @property
    def revoked(self) -> bool:
        with self._lock:
            return self._revoked

    @property
    def consumed(self) -> bool:
        with self._lock:
            return self._consumed

    def consume(self, *, now_monotonic: float | None = None) -> bool:
        """Atomically consume this capability once if it is still valid."""

        try:
            now = _checked_clock(now_monotonic)
        except (ValueError, OverflowError):
            return False
        with self._lock:
            if (
                self._revoked
                or self._consumed
                or not math.isfinite(now)
                or now >= self.expires_at_monotonic
            ):
                return False
            self._consumed = True
            return True


def _goal_message(goal: object) -> Mapping[str, Any]:
    if isinstance(goal, Mapping):
        return goal
    method = getattr(goal, "to_message", None)
    if not callable(method):
        raise MotionPermitError("Goal must be a mapping or provide to_message()")
    message = method()
    if not isinstance(message, Mapping):
        raise MotionPermitError("Goal to_message() did not return a mapping")
    return message


def goal_hash(goal: object) -> str:
    try:
        payload = json.dumps(
            dict(_goal_message(goal)),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MotionPermitError(f"Goal is not canonical JSON: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()


class MotionPermit:
    """Callable permit compatible with ``RoArmM3(permit_motion=permit)``."""

    def __init__(
        self,
        *,
        _issuer: object,
        capability: Capability,
        snapshot_hash: str,
        plan_hash: str,
        allowed_goal_hashes: Iterable[str],
        expires_at_monotonic: float,
    ) -> None:
        if _issuer is not _ISSUER:
            raise MotionPermitError("Motion permits may only be issued by SafetySupervisor")
        if capability not in (
            Capability.EMPTY_CELL_MOTION,
            Capability.KEYBOARD_CONTACT,
            Capability.PHONE_CONTACT,
        ):
            raise MotionPermitError("Capability cannot authorize motion")
        if not math.isfinite(expires_at_monotonic):
            raise MotionPermitError("Permit expiry must be finite")
        hashes = tuple(allowed_goal_hashes)
        if not hashes:
            raise MotionPermitError("A motion permit must enumerate at least one exact goal")
        self.capability = capability
        self.snapshot_hash = snapshot_hash
        self.plan_hash = plan_hash
        self.expires_at_monotonic = expires_at_monotonic
        self._remaining = Counter(hashes)
        self._revoked = False
        self._lock = threading.Lock()

    @classmethod
    def _issue(
        cls,
        *,
        capability: Capability,
        snapshot_hash: str,
        plan_hash: str,
        goals: Iterable[object],
        ttl_s: float,
        now_monotonic: float | None = None,
    ) -> "MotionPermit":
        if isinstance(ttl_s, bool) or not isinstance(ttl_s, (int, float)):
            raise MotionPermitError("ttl_s must be numeric")
        ttl = float(ttl_s)
        if not math.isfinite(ttl) or ttl <= 0:
            raise MotionPermitError("ttl_s must be positive and finite")
        try:
            now = _checked_clock(now_monotonic)
        except (ValueError, OverflowError) as exc:
            raise MotionPermitError("now_monotonic must be a finite numeric clock") from exc
        return cls(
            _issuer=_ISSUER,
            capability=capability,
            snapshot_hash=snapshot_hash,
            plan_hash=plan_hash,
            allowed_goal_hashes=(goal_hash(goal) for goal in goals),
            expires_at_monotonic=now + ttl,
        )

    def revoke(self) -> None:
        with self._lock:
            self._revoked = True
            self._remaining.clear()

    @property
    def revoked(self) -> bool:
        with self._lock:
            return self._revoked

    @property
    def remaining_uses(self) -> int:
        with self._lock:
            return sum(self._remaining.values())

    def allows(self, goal: object, *, now_monotonic: float | None = None) -> bool:
        try:
            now = _checked_clock(now_monotonic)
        except (ValueError, OverflowError):
            return False
        with self._lock:
            if self._revoked or not math.isfinite(self.expires_at_monotonic) or now >= self.expires_at_monotonic:
                return False
            try:
                digest = goal_hash(goal)
            except MotionPermitError:
                return False
            if self._remaining[digest] <= 0:
                return False
            self._remaining[digest] -= 1
            if self._remaining[digest] == 0:
                del self._remaining[digest]
            return True

    def __call__(self, goal: object) -> bool:
        return self.allows(goal)
