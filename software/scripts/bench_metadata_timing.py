"""Finite metadata-only timing probe using the endpoint's shared acquisition path.

Does not construct motion requests, approvals or a qualified controller binding.
Source is checked before acquisition, as in the endpoint reference reader. The
in-window callback checks cancellation only; this is not physical readiness.
"""

import argparse
import json
from pathlib import Path
from threading import Event
import time
import uuid

from rocell.application.endpoint_supervised_metadata import acquire_supervised_metadata
from rocell.application.wizard_diagnostic_coordinator import DiagnosticProcessRunner, source_fingerprint
from rocell.application.wizard_diagnostic_log import WizardDiagnosticLog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=int,choices=range(1,6),default=3)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    source = source_fingerprint(workspace)
    session = 'wizard-'+uuid.uuid4().hex
    log = WizardDiagnosticLog(workspace/'software/runs/wizard-diagnostics',session,
        source_sha256=source,mode='physical')
    log.append('metadata_path_timing_requested',{'samples':args.samples,
        'physical_authority':False,'no_motion_requests':True})
    cancel = Event()
    runner = DiagnosticProcessRunner(workspace,expected_source_sha256=source)
    def current():
        if cancel.is_set(): raise ValueError('Timing probe cancelled')
    def retain(record):
        log.append('metadata_path_original',record)
    results = []
    for index in range(args.samples):
        if source_fingerprint(workspace) != source:
            raise ValueError('Source changed; no automatic restart')
        start = time.monotonic_ns()
        current()
        snapshot = acquire_supervised_metadata(runner=runner,cell_id='metadata-path-timing',
            cancel=cancel,cutoff_ns=start+3_000_000_000,retain=retain,check_current=current)
        current()
        finished = time.monotonic_ns()
        age = finished-snapshot.started_monotonic_ns
        row = {'sample':index+1,'started_ns':start,'finished_ns':finished,
            'snapshot_started_ns':snapshot.started_monotonic_ns,
            'snapshot_finished_ns':snapshot.finished_monotonic_ns,
            'elapsed_ms':(finished-start)/1_000_000,'snapshot_age_ms':age/1_000_000,
            'inside_100ms_at_probe_return':0 <= age <= 100_000_000,
            'physical_authority':False,'endpoint_context_qualified':False}
        log.append('metadata_path_timing_result',row)
        results.append(row)
    checked = WizardDiagnosticLog.verify(log.directory)
    print(json.dumps({'session':session,'log_directory':str(log.directory),
        'verification':checked['status'],'head_sha256':checked['head_sha256'],
        'results':results,'physical_authority':False}))


if __name__ == '__main__':
    main()
