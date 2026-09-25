"""Parent-side current-runtime validation; no dispatch or release authority."""
import hashlib
from pathlib import Path
import sys

from rocell.application.first_motion_contract import canonical
from .owned_worker_process import WorkerProcessRegistration, owned_registration_document
from .positional_campaign_native_protocol import decode_request
from .positional_campaign_invocation import verify_actual_invocation


def validate_registration(registration, request_raw):
    """Validate supervisor pins against wire, actual files, and current source.

    Kept separate from the child invocation check: only the parent has the
    workspace package builder. Successful validation is not permission to run.
    """
    from .positional_campaign_native_package import CHILD, expected_archive
    if type(registration) is not WorkerProcessRegistration:
        raise ValueError('Exact campaign supervisor registration required')
    registration.__post_init__()
    wire = decode_request(request_raw)
    if canonical(owned_registration_document(registration)) != canonical(wire['payload']['registration']):
        raise ValueError('Campaign supervisor registration differs from request')
    if (registration.executable.path != Path(getattr(sys, '_base_executable', sys.executable))
            or registration.package_files[0].path != CHILD):
        raise ValueError('Campaign runtime is not the fixed host interpreter/entry')
    # This independently checks all pin bytes, evidence associations, schemas,
    # arguments and fixed budgets using the same rules the child will apply.
    verify_actual_invocation(request_raw, entry_path=CHILD,
        executable=registration.executable.path, argv=registration.argv,
        working_directory=registration.working_directory)
    if registration.package_files[1].sha256 != hashlib.sha256(expected_archive()).hexdigest():
        raise ValueError('Campaign archive differs from current source')
    return wire
