"""Host-owned campaign reader construction, without serial access or dispatch.

Runtime invocation and physical-release evidence semantics remain separate
gates. This authenticates associations, not the physical truth of every record.
Only the fixed parent/child composition may supply workspace and clock.
"""
from pathlib import Path
from threading import Event
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import safe_root
from rocell.application.positional_campaign_reference_reader import PositionalCampaignReferenceReader, FrozenPositionalCampaignReferences
from .positional_campaign_native_protocol import decode_request, validate_payload
from .positional_current_context import PositionalCurrentContextReader, AuthenticatedPositionalReader
from .endpoint_child_execution import decode_controller_binding
from .bench_review_key import load_host_positional_campaign_review_authority
from .controller_metadata import WindowsControllerMetadataAcquirer


def prepare_authenticated_campaign_reader(workspace, request_raw, *, cancellation,
        clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned cancellation and clock required')
    if cancellation.is_set():
        raise ValueError('Campaign cancelled before bootstrap')
    payload = decode_request(request_raw)['payload']
    request = validate_payload(payload)
    request.require_start_time(clock_ns())
    root = safe_root(Path(payload['root']))
    references = FrozenPositionalCampaignReferences(PositionalCampaignReferenceReader(
        request, workspace=workspace, root=root))
    if references.original('runtime_sha256') != canonical(payload['registration']):
        raise ValueError('Campaign runtime original differs from wire')
    binding = decode_controller_binding(references.original('native_controller_review_sha256'), request)
    authority = load_host_positional_campaign_review_authority(workspace)
    if cancellation.is_set():
        raise ValueError('Campaign cancelled before metadata')
    request.require_start_time(clock_ns())
    # Repeated checks are bounded across bootstrap, process claim, open and
    # two legs. The immutable campaign deadline also bounds every acquisition.
    metadata = WindowsControllerMetadataAcquirer(deadline_ns=request.to_dict()['deadline_ns']-2_000_000_000,
        cancellation=cancellation, monotonic_ns=clock_ns, maximum_acquisitions=32)
    context = PositionalCurrentContextReader(request, binding=binding,
        connection_id=request.to_dict()['campaign_id'], metadata_reader=metadata,
        references_reader=references, clock_ns=clock_ns)
    reader = AuthenticatedPositionalReader(request, root=root, authority=authority,
        context_reader=context, clock_ns=clock_ns)
    reader.verify_endpoint()
    if cancellation.is_set():
        raise ValueError('Campaign cancelled during bootstrap')
    return reader
