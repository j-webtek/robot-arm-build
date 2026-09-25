"""Fresh endpoint context via existing persistent-controller metadata checks.

No COM opening. Metadata is not an atomic binding to a subsequent open handle,
nor proof of arm model, power, firmware, or clearance. The parent must contain
native acquisition and provide independent current reference reconstruction.
"""

import time
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_controller_resolution import ControllerMetadataSnapshot, resolve_controller_metadata
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
from rocell.safety.bench_review_authority import BenchReviewCurrentContext


class EndpointCurrentContextReader:
    """Coordinator-wired readers only; never construct from browser callbacks."""

    @staticmethod
    def _accept_request(request):
        return type(request) is EndpointTrialRequest

    @staticmethod
    def _make_context(connection, identity, references, observed_ns, port):
        return BenchReviewCurrentContext(connection, identity, references, observed_ns, port)

    @staticmethod
    def _context_body(request):
        """Internal projection hook; it does not convert or authorize requests."""
        return request.to_dict()

    def __init__(self,request,*,binding,connection_id,metadata_reader,references_reader,
                 clock_ns=time.monotonic_ns):
        if not self._accept_request(request) or type(binding) is not ReviewedControllerBinding:
            raise ValueError('Exact request and reviewed persistent binding required')
        binding.__post_init__()
        if binding.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION:
            raise ValueError('Physical metadata binding required')
        body = self._context_body(request)
        identity = body['usb_identity']
        if (binding.binding_sha256!=body['references']['native_controller_review_sha256']
                or (binding.identity.vid,binding.identity.pid,binding.identity.unit_serial)!=
                   (f"{identity['vid']:04x}",f"{identity['pid']:04x}",identity['serial_number'])):
            raise ValueError('Reviewed controller does not match endpoint request')
        if type(connection_id) is not str or not 1<=len(connection_id)<=80:
            raise ValueError('Owned connection identity required')
        if not all(callable(v) for v in (metadata_reader,references_reader,clock_ns)):
            raise ValueError('Trusted current context readers required')
        self._request,self._binding,self._connection = request,binding,connection_id
        self._metadata,self._references,self._clock = metadata_reader,references_reader,clock_ns

    def __call__(self):
        body = self._context_body(self._request)
        started = self._clock()
        if type(started) is not int or not body['issued_monotonic_ns']<=started<body['deadline_monotonic_ns']:
            raise ValueError('Endpoint context outside request lifetime')
        # Source/build reconstruction can be slower than USB metadata. Perform
        # it before acquiring the fresh snapshot, not inside its 100 ms age.
        references = self._references()
        snapshot = self._metadata()
        if type(snapshot) is not ControllerMetadataSnapshot:
            raise ValueError('Exact controller snapshot required')
        resolution = resolve_controller_metadata(self._binding,snapshot)
        if resolution.identity is None:
            raise ValueError('Current persistent controller metadata did not match')
        finished = self._clock()
        if (type(finished) is not int or not started<=snapshot.started_monotonic_ns
                <=snapshot.finished_monotonic_ns<=finished<body['deadline_monotonic_ns']
                or finished-snapshot.started_monotonic_ns>100_000_000):
            raise ValueError('Endpoint metadata acquisition stale or clock changed')
        expected = tuple(sorted(body['references'].items()))
        if references!=expected or self._binding.binding_sha256!=dict(expected)['native_controller_review_sha256']:
            raise ValueError('Current endpoint references changed')
        identity = body['usb_identity']
        return self._make_context(self._connection,
            (identity['vid'],identity['pid'],identity['serial_number']),references,
            snapshot.started_monotonic_ns,resolution.identity.port_name)
