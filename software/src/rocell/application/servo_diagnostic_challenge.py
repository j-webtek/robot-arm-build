"""Explicit challenge discovery; unlike telemetry GETs, this can arm a listener.

No motion is sent. Never called by the generic read-only diagnostic collector.
The expected boot must come from the reviewed current device status, not a guess.
"""
import hashlib

from .servo_diagnostic_http import DiagnosticHTTPReader
from .servo_start_authorization import _challenge_bytes, _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json

CHALLENGE='/rocell/diagnostics/challenge'


class DiagnosticChallengeReader(DiagnosticHTTPReader):
    def __init__(self,address,port=80):
        super().__init__(address,port)
        self.attempted=False

    def discover(self,expected_boot):
        if self.attempted or self.failed:
            raise ValueError('Challenge discovery consumed; do not re-arm automatically')
        self.attempted=True
        try:
            _hex(expected_boot,16)
            raw=self._get(CHALLENGE,maximum_bytes=512,timeout_seconds=3)
            challenge=decode_diagnostic_json(raw,maximum=512)
            _challenge_bytes(challenge)
            if challenge['boot_id']!=expected_boot:
                raise ValueError('Challenge belongs to another controller boot')
            return dict(schema='rocell.host_challenge_discovery.v1',challenge=challenge,
                response_body=raw.decode('ascii'),response_sha256=hashlib.sha256(raw).hexdigest(),
                boot_matches=True,provenance_verified=False,progression_authority=False)
        except (OSError,ValueError,TypeError,UnicodeError):
            self.failed=True
            raise
