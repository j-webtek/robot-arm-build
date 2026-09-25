"""Trusted-host assembly of a wizard endpoint attachment; never opens a port.

Inputs are retained originals and explicit review receipts, not browser claims
of readiness. Assembly checks integrity, not engineering truth. Current native
metadata is acquired only later when the existing coordinator requests context.
"""

import hashlib
from pathlib import Path
import time

from .endpoint_trial_draft import EndpointTrialDraft
from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_reference_reader import EndpointReferenceReader, ORIGINAL_REFERENCES, MAX_ORIGINAL_BYTES
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .wizard_engineering_review_intake import load_engineering_review_reader
from .wizard_endpoint_coordinator import EndpointWizardBinding
from .physical_onboarding_durability import safe_root
from rocell.rc03.importer import import_build_snapshot
from rocell.providers.windows.endpoint_child_execution import decode_controller_binding
from rocell.providers.windows.endpoint_current_context import EndpointCurrentContextReader


def _require_final_confirmation(request):
    raise ValueError('The public wizard must supply its recorded final operator confirmation')


def assemble_endpoint_binding(*, workspace, draft, reference_originals, review_root,
                              review_selections, check_current, metadata_factory,
                              clock_ns=time.monotonic_ns):
    """Build an attachment without installing it, signing reviews or enumerating.

    metadata_factory is a trusted host dependency for process-supervised,
    bounded read-only metadata, not browser input. There is deliberately no
    unsupervised native-call fallback in this UI-parent assembly function.
    The eight originals must already contain actual supporting evidence. This
    function does not generate firmware, geometry or baseline qualifications.
    """
    if (type(draft) is not EndpointTrialDraft or type(reference_originals) is not tuple
            or len(reference_originals) != len(ORIGINAL_REFERENCES)
            or any(type(row) is not tuple or len(row)!=2 or type(row[0]) is not str
                   or type(row[1]) is not bytes for row in reference_originals)
            or set(dict(reference_originals)) != ORIGINAL_REFERENCES
            or not callable(check_current) or not callable(clock_ns)
            or not callable(metadata_factory)):
        raise ValueError('Complete trusted endpoint assembly inputs required')
    workspace,root = safe_root(Path(workspace)),safe_root(Path(review_root))
    def current():
        if check_current() is not None:
            raise ValueError('Endpoint assembly context changed')
    current()
    selection = decode_diagnostic_json(draft.canonical_bytes,maximum=16384)['selection']
    refs = selection['references']
    originals = dict(reference_originals)
    for name,raw in originals.items():
        value = decode_diagnostic_json(raw,maximum=MAX_ORIGINAL_BYTES)
        if type(value) is not dict or not value or hashlib.sha256(raw).hexdigest()!=refs[name]:
            raise ValueError('Endpoint original does not match the reviewed draft')
    source = source_fingerprint(workspace)
    if source != refs['source_sha256'] or import_build_snapshot(workspace).snapshot_hash != refs['build_snapshot_sha256']:
        raise ValueError('Endpoint source or build snapshot changed')
    engineering = load_engineering_review_reader(root=root,draft=draft,
        selections=review_selections,source_sha256=source,check_current=current,clock_ns=clock_ns)
    current()

    def context_factory(request):
        current()
        if (type(request) is not EndpointTrialRequest
                or EndpointTrialDraft.from_request(request).canonical_bytes != draft.canonical_bytes):
            raise ValueError('Endpoint request differs from assembled draft')
        # Decode against the actual timed request, never a fabricated preflight
        # request. The existing context reader rejects nonphysical/changed USB.
        binding = decode_controller_binding(originals['native_controller_review_sha256'],request)
        metadata = metadata_factory(request)
        if not callable(metadata):
            raise ValueError('Bounded metadata reader required')
        def acquire():
            current()
            result = metadata()
            current()
            return result
        return EndpointCurrentContextReader(request,binding=binding,
            connection_id=request.to_dict()['attempt_id'],metadata_reader=acquire,
            references_reader=EndpointReferenceReader(request,workspace=workspace,reference_root=root),
            clock_ns=clock_ns)

    return EndpointWizardBinding(draft,tuple(sorted(originals.items())),
        _require_final_confirmation,engineering,context_factory)
