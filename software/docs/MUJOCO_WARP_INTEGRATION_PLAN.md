# MuJoCo Warp secondary-oracle integration plan

- **Document status:** Active architecture plan; implementation not started
- **Audience:** Runtime, simulation, AI, workcell, and repository contributors
- **Owner:** Simulation workstream with AI and arm-runtime review
- **Reviewed:** 2026-10-03
- **Authority:** Planning and software-test guidance only. This plan grants no
  hardware, motion, contact, calibration, model-promotion, or release authority.

## Decision

Integrate MuJoCo Warp as an optional, high-throughput **secondary simulation
oracle** after a bounded pilot. Keep Isaac Sim as the higher-fidelity visual
reference and keep RoCell's deterministic kinematics, admission, collision,
sequencing, and evidence services authoritative for software decisions.

MuJoCo Warp is valuable when many independent worlds, cameras, placements, or
physics variations must be evaluated on NVIDIA GPUs. It is not a substitute
for physical camera measurements, controller/URDF correlation, calibrated
target geometry, measured robot dynamics, or hardware qualification.

The pilot must answer three questions before broader adoption:

1. Does the imported robot and workcell agree with RoCell and Isaac on frames,
   link transforms, target projections, and geometric masks?
2. Does batching materially increase admitted observations per hour without
   buffer overflow, hidden scene changes, or lost evidence identity?
3. Which outputs are trustworthy enough for geometry screening, synthetic data
   generation, or contact sensitivity studies?

## Current fit

The designated workstation has two RTX 3090 GPUs with 24 GiB each and Python
3.12. This is a strong candidate for MuJoCo Warp's NVIDIA-oriented parallel
execution, but it is not compatibility evidence. The exact candidate package,
Warp/CUDA requirements, driver, GPU, and operating system must pass MW0.

The current RoArm URDF is a governed kinematic projection. It lacks enough
validated collision, inertia, drive, compliance, backlash, cable, and contact
properties to be a physical dynamic twin. High throughput cannot repair those
unknowns; the integration must label every added property as upstream,
measured, derived, provisional, or unknown.

## Architectural position

MuJoCo Warp consumes an already admitted runtime artifact. It never interprets
English, identifies a target, changes action order, performs IK silently, emits
controller commands, or grants a permit.

```text
user intent + observed scene
            |
            v
     AI ModelMotionBatch
            |
            v
 strict ingress + catalog + calibration + fresh state
            |
            v
 deterministic plan + IK + collision/smoothness screening
            |
            v
 admitted, hash-bound simulation schedule
            |
       +----+----------------------+----------------------+
       |                           |                      |
       v                           v                      v
 deterministic RoCell       Isaac Sim oracle      MuJoCo Warp oracle
 checks                     visual reference       batched stress path
       |                           |                      |
       +---------------------------+----------------------+
                                   |
                                   v
                    differential advisory evidence

 no serial transport, no wire JSON, no execution permit, no physical authority
```

The existing `ModelMotionBatch` boundary does not change. MuJoCo Warp sits
downstream of deterministic runtime admission and receives no language-model
output directly.

## Division of responsibility

| Need | Primary system | MuJoCo Warp role |
| --- | --- | --- |
| Intent and exact-text preservation | AI intent parser and deterministic compiler | None |
| Target identity and calibrated geometry | Shared catalog and calibration | Consume exact hashes only |
| IK and runtime admission | RoCell arm runtime | Replay admitted states; compare only |
| High-fidelity visual reference | Isaac Sim plus physical B0477 evidence | Paired low-fidelity comparison |
| Large pose and placement sweeps | RoCell policy plus simulation workers | Batched accelerator candidate |
| Segmentation, depth, and occlusion masks | Isaac/analytic geometry | Batched secondary source after parity |
| Contact sensitivity | Measured mechanics plus differential simulation | Provisional sweeps after MW4 |
| Hardware qualification | Physical arm, camera, host outcome evidence | No role |

## Simulator-neutral contract

The first implementation should define a compact simulator-neutral envelope
rather than passing Isaac USD fields into MuJoCo Warp or MuJoCo XML fields into
core runtime code.

### Request

`rocell.simulation_oracle_request.v1` should bind:

- source commit, system manifest, target catalog, camera, robot, tool, and
  workcell hashes;
- exact admitted schedule hash and ordered timestamped joint states;
- named frames, units, transforms, and requested observations;
- backend ID and a backend-specific lock hash;
- seed set, world count, camera count, precision mode, and buffer limits;
- explicit `hardware_access=false`, empty transport capability, and
  `physical_authority=false`.

The request contains semantic labels only as trace metadata. Neither simulator
may use them to replan or generate a different target sequence.

### Receipt

`rocell.simulation_oracle_receipt.v1` should bind:

- the exact request and backend lock;
- loaded robot, scene, mesh, texture, and compiled-model hashes;
- GPU, driver, CUDA, Warp, MuJoCo, MuJoCo Warp, renderer, and precision details;
- world/step/camera counts, wall time, compilation time, throughput, and peak
  device memory;
- every overflow bit, dropped world, invalid value, and warning;
- FK, projection, segmentation, depth, collision, tracking, or contact metrics
  that were requested;
- per-world seeds and artifact-manifest hashes;
- repeated-run comparison and known nondeterminism;
- `PASS`, `REJECT`, or `ERROR`, limitations, zero hardware operations, and no
  gate promotion.

GPU pixel or contact bytes need not be byte identical across runs. Input
manifests must be identical, and numerical/reported differences must remain
inside thresholds frozen before the comparison.

## Planned repository boundary

```text
software/
  src/rocell/integrations/
    simulation_oracle/          # backend-neutral request/receipt and diff rules
    mujoco_warp/                 # optional adapter contract; no eager dependency
  integrations/mujoco_warp/
    README.md                    # external environment and evidence commands
    host_probe.py                # imports/version/GPU only
    asset_parity_probe.py        # URDF/MJCF mapping and frozen-pose comparison
    batch_probe.py               # throughput, overflow, repeatability
    render_parity_probe.py       # paired RGB/depth/segmentation comparison
    contact_probe.py             # added only after MW4 prerequisites pass
  config/
    mujoco_warp_toolchain_lock.json
  schemas/
    simulation_oracle_request_v1.schema.json
    simulation_oracle_receipt_v1.schema.json
  tests/fixtures/mujoco_warp/    # compact hardware-free fixtures only
```

MuJoCo, MuJoCo Warp, Warp, CUDA caches, compiled kernels, converted assets,
rendered datasets, checkpoints, videos, and full logs remain outside Git. Only
small reviewed fixtures and hash manifests may enter the source tree.

Ordinary unit tests must run without importing MuJoCo Warp. The adapter uses a
lazy external-runner boundary like the Isaac integration.

## Work packages

### MW0 — governance and isolated toolchain

**Objective:** establish whether the host can run one pinned candidate without
changing the existing Isaac or project Python environments.

**Deliverables**

- Apache-2.0 license and redistribution record;
- exact package/version candidate, hashes, Python, CUDA/driver, Warp, MuJoCo,
  GPU, and operating-system receipt;
- isolated external environment, initially under `C:\MuJoCoWarp\`;
- CPU debug import and single-GPU CUDA import smoke;
- installation inventory and uninstall/rebuild instructions;
- hardware-free fake-adapter fixtures for CI.

**Exit gate**

- exact version and dependency hashes reproduce;
- both RTX 3090 devices enumerate independently;
- one minimal world steps on CPU and each GPU;
- a mismatched lock rejects before model load;
- no package, cache, or large generated file enters the repository;
- hardware writes and physical movements remain zero.

**MW0 result (2026-10-03): `PASS`.** The isolated candidate is MuJoCo Warp
3.13.0, MuJoCo 3.14.0, Warp 1.17.0, NumPy 2.5.3, and Python 3.12.0. One
16-step pendulum world passed on CPU, `cuda:0`, and `cuda:1`; every result had
finite state, changed state, and `overflow=[0]`. The exact lock and a
standard-library-only pre-import host validator are now repository controlled.
This advances only to MW1 asset/FK work. It does not validate RoArm import,
rendering, contact, throughput, training value, or physical transfer. Evidence
is `E-20261003-AI-561`.

### MW1 — asset import and kinematic parity

**Objective:** prove that the governed robot projection means the same thing in
RoCell, Isaac, standard MuJoCo, and MuJoCo Warp.

**Deliverables**

- exact URDF/mesh import or governed URDF-to-MJCF conversion receipt;
- joint/link/axis/limit/unit mapping;
- property-provenance inventory for collision, inertia, damping, actuator, and
  contact fields;
- replay of the existing frozen pose corpus;
- four-way transform and tool-point differential report.

**Exit gate**

- every expected joint and link maps exactly once;
- no importer default is accepted without being reported;
- fixed-pose link transforms satisfy the parity limits frozen for the Isaac
  import campaign, initially 0.1 mm translation and 0.05 degrees rotation;
- standard MuJoCo and MuJoCo Warp agree inside a separately frozen float32
  tolerance;
- any unknown property blocks its associated dynamic or contact claim.

### MW2 — batch throughput, overflow, and repeatability

**Objective:** determine whether MuJoCo Warp provides enough acceleration to
justify maintaining the backend.

**Deliverables**

- fixed benchmark matrix at 1, 32, 256, 1,024, and 4,096 worlds, bounded by
  available memory;
- separate device-0, device-1, and explicitly sharded dual-GPU runs;
- compile time, steady-state steps/s, observations/hour, memory, transfer time,
  and overflow inventory;
- repeat runs with identical manifests and predeclared numerical tolerances;
- equivalent low-fidelity Isaac or CPU-MuJoCo comparison where meaningful.

**Exit gate**

- zero unhandled overflow bits, invalid values, lost worlds, or silent warnings;
- repeated aggregate metrics remain within frozen tolerances;
- the target workload achieves at least three times the admitted
  observations/hour of its comparison path after excluding one-time compile
  cost, or a documented capability unavailable from the comparison path;
- multi-GPU results remain separate evidence shards unless explicit aggregation
  rules pass.

Failure closes the acceleration path without affecting Isaac or RoCell.

### MW3 — camera and geometry parity

**Objective:** decide which rendered outputs can supplement the Isaac corpus.

**Deliverables**

- paired scene, pose, camera, target, light, mesh, and seed identities;
- RGB, depth, segmentation, safe-region, and parked-arm mask comparisons;
- target projection and mask-overlap error by target, camera, and scene;
- low-contrast cable/edge audit against lossless Isaac reference renders;
- renderer-domain label in every data row.

**Exit gate**

- camera transforms and target projections pass thresholds frozen before paired
  pixels are inspected;
- segmentation and depth differences are bounded and attributed;
- parked-arm occlusion decisions agree on the frozen target set;
- no RGB training use is allowed merely because geometric parity passes;
- visual-model use additionally passes the applicable lossless/YUY2
  detectability and measured camera-noise rules.

Isaac remains the visual reference if MuJoCo Warp's low-fidelity renderer cannot
preserve dark-cable, glare, material, or lighting signals.

### MW4 — collision and contact differential

**Objective:** use batched physics only after the modeled properties support the
claim being tested.

**Prerequisites**

- complete collision geometry for every required body;
- measured or explicitly provisional mass, inertia, damping, friction, drive,
  tool, key travel, spring, activation, and surface parameters;
- approved intended-contact policy and collision exclusions;
- MW1 parity and MW2 overflow gates passed.

**Deliverables**

- replay of already-admitted noncontact and representative contact schedules;
- MuJoCo CPU, MuJoCo Warp, Isaac, and deterministic-screen differential;
- parameter sensitivity ranges rather than one asserted value;
- contact order, penetration, impulse/force, travel, settle, and disagreement
  evidence.

**Exit gate**

- no prohibited contact is hidden by filtering;
- intended contacts occur only in declared phases and target regions;
- engine disagreements are reported per event;
- provisional parameters produce sensitivity evidence only;
- no simulation contact result authorizes hardware contact.

### MW5 — synthetic-data admission

**Objective:** admit only the MuJoCo Warp outputs that passed the relevant
parity gates.

**Permitted first uses**

- geometry masks and target visibility;
- placement and pose stress cases;
- collision-negative mining;
- balanced rare-case sampling for later Isaac rendering;
- exploratory depth/segmentation training with backend labels.

**Rules**

- train, development, and evaluation identities remain disjoint by scene,
  target, obstruction asset, lighting, and backend where applicable;
- the renderer family and exact lock are features in the manifest;
- a MuJoCo Warp frame cannot be relabeled as Isaac or physical data;
- the load-time camera model applies the same delivered-YUY2 conversion and
  measured noise contract when the model is meant to consume B0477-like input;
- existing v5.5 identities and gates do not change silently;
- synthetic success remains a simulation claim.

**Exit gate**

- independent admission reproduces every identity and source hash;
- no truth channel reaches model input;
- the candidate beats its frozen baseline and passes backend-specific hard-case
  diagnostics;
- physical transfer remains separately unopened or explicitly reported.

### MW6 — optional policy-learning research

Reinforcement learning or learned motion refinement is deferred until MW0-MW5,
physical calibration, measured dynamics, and a separate shared contract are
complete. A learned policy may propose bounded research outputs only. It may
not bypass `ModelMotionBatch`, deterministic planning, collision screening,
fresh-state checks, execution authorization, or hardware transport controls.

## Adoption decisions

After each work package, record one disposition:

- `ADOPT_FOR_DECLARED_SCOPE` — list the exact outputs and downstream consumers;
- `RESEARCH_ONLY` — retain results but prohibit qualification or selection use;
- `REJECT_BACKEND` — preserve failed evidence and stop dependent packages;
- `BLOCKED` — name the missing external evidence or upstream contract.

Scopes are cumulative only through explicit review. Passing FK parity does not
admit rendered RGB; passing renderer geometry does not admit contact physics;
passing synthetic model gates does not qualify physical transfer.

## Interaction with current priorities

The pilot runs in parallel with target-catalog completion and B0477 work. It
must not delay:

1. direct Grave measurement and the shared 80-target catalog;
2. v5.5 lossless Isaac rendering and load-time camera model;
3. physical camera calibration and measured noise;
4. deterministic planner/compiler and arm-runtime integration.

MW0 and MW1 are useful while physical measurements are pending. MW3 may inform
future corpus production, but the current v5.5 campaign remains on its existing
Isaac path unless a separate pre-render amendment is reviewed.

## Initial execution order

1. Record the candidate version and external-environment lock without installing
   into the repository environment.
2. Run host compatibility and minimal CPU/GPU smokes.
3. Convert/load the governed RoArm asset and compare frozen poses.
4. Benchmark batch sizes and inspect every overflow field.
5. Build a small paired Isaac/MuJoCo Warp geometry-render corpus.
6. Decide permitted scopes before adding contact models or training data.
7. Add contact sensitivity only after measured property prerequisites exist.

## Upstream references

- [MuJoCo Warp repository](https://github.com/google-deepmind/mujoco_warp)
- [MuJoCo Warp documentation](https://mujoco.readthedocs.io/en/latest/mjwarp/)
- [MuJoCo Warp API](https://mujoco.readthedocs.io/en/3.13.0/mjwarp/api.html)
- [Existing Isaac Sim integration plan](ISAAC_SIM_INTEGRATION_PLAN.md)
