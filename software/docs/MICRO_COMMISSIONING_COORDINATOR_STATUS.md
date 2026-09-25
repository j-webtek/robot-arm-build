# Predecessor-to-micro commissioning coordinator

Implemented `application/micro_commissioning_coordinator.py` and the explicit
native composition in `providers/windows/micro_commissioning_native.py`.
**57 focused tests passed. No real arm commands were sent.**

## Workflow

The native composition prepares the assigned existing export folder and acquires
the real cooperative Windows transport lease for the complete workflow:

1. Record predecessor intent; invoke one existing descending 0.95-degree trial.
2. If it succeeds, collect the existing bounded passive hold.
3. Export predecessor evidence and replay its original endpoint and unchanged hold.
4. If reported roll is within 0.05 degrees of 1.25, finish NO_CORRECTION_NEEDED.
5. Otherwise require reported roll in 1.35–1.45 degrees. Any other result stops.
6. Obtain fresh pinned feedback, create the staged admission, and bind the session.
7. Execute at most one fixed 0.90-degree micro command through the dedicated native
   binding and deadline-driven runner. Verify endpoint and passive hold; export.
8. Retain a final coordinator report before releasing the participating-process lease.

There is no automatic high-positioning move, predecessor retry, return or repeated
correction. Starting pose must already satisfy the existing predecessor admission.
A failed predecessor is exported and never followed by a micro-command. Missing
or changed evidence, cancellation, admission failure and export failure stop
progression. The coordinator object is single-use.

## Ownership and exports

The native entry point requires an explicit exclusive-controller declaration;
absence rejects before native providers or filesystem preparation. This is an
operator assumption, not proof that other clients are excluded. The named mutex
only coordinates participating local processes. The native component rechecks
source through a supplied callback before predecessor, baseline and transport
construction. No source or ownership claim is silently inferred from old exports.

Predecessor, micro and final outcomes use the existing diagnostic exporter with
verified manifests in the assigned folder. The predecessor attachment conforms
to the existing original-evidence replay layout. Export receipts are retained in
the coordinator result. The final saved report is pre-export evidence; its own
write success appears only in the returned receipt/result.

## Validation scope

Coordinator tests use fake providers for deterministic ordering and failures.
Native-composition tests replace the coordinator and exercise the real diagnostic
exporter, without calling native movement functions. Lower-layer fake-socket,
admission and polling tests were rerun. This is not a successful physical micro
experiment and does not establish improved physical accuracy.

## Next step

The native entry point is callable and potentially moves the arm, but is **not
registered in the wizard and was not invoked against hardware**. Add a separate
explicit wizard action with a clear two-command-maximum preview, exclusive-client
declaration, source recheck, cancellation and service-owned result publication.
Test preview inertness, required declaration, result rejection, timeout budget and
export retention before using it. Existing larger-move admissions remain unchanged.
