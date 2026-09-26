# Model-command runtime implementation plan

**Status:** active, incremental implementation  
**Scope:** model proposal ingress through verified arm outcomes  
**Authority:** this plan and its current coordinator are zero-hardware artifacts

## Objective

Turn a validated model request into efficient physical work without allowing a
learned component to write directly to a servo. The runtime should move quickly
when evidence is complete and stop immediately when identity, freshness,
geometry, transport, or outcome evidence is incomplete.

The core rule is: **one admitted action, one fresh arm state, one screened
trajectory, one single-use execution result, one independently verified
outcome.** Only then may the next action be considered.

## Runtime pipeline

```text
ModelMotionBatch
  -> deterministic ingress and provenance binding
  -> sequential coordinator selects action N only
  -> fresh authenticated joint read
  -> measured reprojection, IK, limits, and continuous collision screen
  -> single-action execution admission
  -> durable pre-dispatch journal boundary
  -> one controller writer sends a correlation-bound trajectory
  -> feedback, settle check, and independent device outcome
  -> verified result returns to coordinator
  -> action N+1 begins with a new joint read
```

No component may precompute action N+1 from action N's starting state. No
uncertain action may be retried automatically.

## Implemented now

- Strict ordered `ModelMotionBatch` and deterministic ingress bind intent,
  image, scene, precision, fusion, model, frame, target catalog, and build.
- `ModelMotionSequenceCoordinator` selects exactly one action and accepts one
  never-reused `ObservedPlannerStartState`.
- Planner reports must remain zero-command and bind the exact candidate and
  observed state.
- The coordinator advances only from an exact `VerifiedActionResult` bound to
  the batch, action index, proposal, planner gate, execution receipt, and
  independent outcome evidence.
- Planner rejection, pre-dispatch failure, and uncertain outcome are terminal.
  Lookahead and automatic retry are explicitly false in every snapshot.
- The snapshot is canonical and hash-bound for later persistence and replay.

The current measured planner does not yet emit
`READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION`; it correctly stops at remaining
calibration or collision-screening blockers. Therefore the production runtime
cannot mistake this orchestration work for physical readiness.

## Next implementation slices

### R1 — durable coordinator journal — initial implementation complete

- Persist every phase transition with an append-only hash chain.
- Reopen after process restart without repeating a possibly dispatched action.
- Treat any missing post-dispatch evidence as `OUTCOME_UNCERTAIN`.
- Bind journal identity to batch, build, controller session, and configuration
  epoch vector.

The initial implementation now persists a canonical header, append-only
hash-chained events, and an atomically replaced high-water head. It binds the
batch and ingress records, detects altered/truncated histories, enforces action
order, and assigns a retry-forbidden recovery disposition to an interrupted
dispatch. Binding the future writable executor's controller session and full
configuration epoch vector remains part of R3.

### R2 — typed trajectory execution envelope — initial implementation complete

- Define controller-independent waypoints with joint positions, velocity,
  acceleration, jerk, settle tolerance, deadline, and correlation ID.
- Require continuous-limit and full installed-geometry screening over the exact
  envelope bytes.
- Keep Waveshare JSON/serial encoding behind the sole writable adapter.

The initial envelope is now implemented as strict, duplicate-free,
content-hashed JSON. It carries exactly five planner joints in radians with
monotonic nanosecond timing, calibrated position bounds, velocity,
acceleration, and jerk limits, settling tolerances/dwell, deadline, correlation
identity, and all planner/build/session evidence hashes. Construction verifies
finite values, position bounds, timing, deadline, and discrete dynamics. The
coordinator and durable journal can bind dispatch to the exact envelope hash.
It intentionally contains no gripper operation, Waveshare encoding, writable
transport, or physical authority.

### R3 — single writer and controller receipts

- One process owns the writable serial transport.
- Reject stale session IDs, duplicate correlation IDs, expired admissions, and
  altered trajectories.
- Record submitted bytes, acknowledgements, feedback samples, timeouts, and
  transport closure in one execution receipt.
- Never resend when submission or outcome is ambiguous.

### R4 — smooth motion and settling

- Parameterize measured joint velocity, acceleration, and jerk limits.
- Use time-parameterized trajectories instead of isolated endpoint jumps.
- Monitor tracking error throughout motion and require bounded settling before
  contact or successor motion.
- Prefer safe hover-to-hover transitions while preserving retract clearance.

### R5 — independent task verification

- Keyboard: verify the resulting character/event outside the command path.
- Phone: capture a new scene after each state-changing action and verify the
  expected state transition.
- Feed only verified outcomes back to the sequence coordinator.

### R6 — performance qualification

- Measure model-to-ingress, planning, dispatch, travel, settling, observation,
  and total action latency separately.
- Optimize cached immutable geometry and planner warm-up, never freshness or
  safety checks.
- Qualify throughput, p95/p99 latency, tracking error, abstention, transport
  faults, and restart recovery on held-out missions.

## Completion gates

A model-driven command path is operational only when it demonstrates:

1. exact intent/provenance binding and no direct model-to-servo path;
2. measured calibration and continuous installed-geometry screening;
3. fresh feedback for every action and no lookahead from stale state;
4. a durable pre-dispatch boundary with no ambiguous retry;
5. one writable controller owner and correlation-bound receipts;
6. bounded tracking/settling under measured motion limits;
7. independent outcome confirmation before the next action;
8. safe restart recovery and explicit watchdog behavior;
9. measured latency targets without weakening admission rules;
10. held-out physical qualification for each supported device/task class.

## Immediate work order

1. Keep AI output at `ModelMotionBatch`; do not add servo fields to that schema.
2. Finish measured collision geometry so the planner can earn the reserved
   ready status.
3. Implement a zero-write Waveshare encoder that accepts only the sealed
   trajectory envelope and produces reviewable JSON command bytes.
4. Place that encoder behind a sole-writer transport with a separate
   single-use execution permit and correlated receipts.
5. Connect independent outcome verification and qualify one key before strings.
