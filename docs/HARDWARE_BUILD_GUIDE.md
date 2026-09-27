# Building the Tactevra RC03 workcell

**Document status:** Current builder guide  
**Audience:** Hardware builders and reviewers  
**Authority:** Explanatory; controlled RC03 records determine print and build eligibility

This page is the public entry point for the current Tactevra workcell design. The
controlled hardware package remains in `active-project/RoCell_v0_3` under its
historical RoCell name so existing paths, scripts, and release records continue
to work. RoCell is a compatibility name here, not a separate product.

## Current release position

| Item | Current state |
| --- | --- |
| Controlled design revision | `RC03-INT-R1` |
| Digital consistency checks | Passing in the controlled readiness record |
| Physical release | **Blocked** pending the recorded measurements and qualification evidence |
| Production printing | **Not authorized** |
| Final anchor drilling | **Not authorized** |
| Powered robot motion | **Not authorized** |
| Print jobs marked `READY` | 5 diagnostic jobs; this does not release production parts |

These statements summarize the checked-in controlled records. Before acting,
read the generated [pre-hardware readiness report](../active-project/RoCell_v0_3/PREHARDWARE_READINESS.md)
and [print-readiness report](../active-project/RoCell_v0_3/PRINT_READINESS.md), which
are authoritative for their respective gates.

## Choose your next step

| If you want to… | Use this record |
| --- | --- |
| Understand the package and revision | [RC03 introduction](../active-project/RoCell_v0_3/README_FIRST.md) |
| Find out what may be printed | [Print readiness](../active-project/RoCell_v0_3/PRINT_READINESS.md) |
| See the blocking evidence and safety gates | [Pre-hardware readiness](../active-project/RoCell_v0_3/PREHARDWARE_READINESS.md) |
| Check the lifecycle state of each job | [Build tracker](../active-project/RoCell_v0_3/BUILD_TRACKER.md) |
| Begin an approved diagnostic or assembly step | [Build-by-step dashboard](../active-project/RoCell_v0_3/BUILD_BY_STEP/README.md) |
| Understand project-wide capability limits | [Project status](../PROJECT_STATUS.md) |

Do not start from an STL filename alone. Start from print readiness, confirm the
exact job and profile, and then use the build-by-step instructions associated
with that job.

## What the status words mean

- `READY` in **print readiness** means the exact print job has complete release
  prerequisites for its recorded printer profile. It does not authorize later
  kitting, assembly, installation, drilling, or powered movement.
- `READY_TO_SLICE`, `PRINTED`, and `POSTPRINT_PASS` in the **build tracker** are
  lifecycle states. Each later state still requires its own evidence and review.
- `WAITING` or `UNRELEASED` means a named prerequisite is incomplete. Do not
  substitute a nominal dimension or a similar-looking part.
- `NOT_SELECTED` means the route is intentionally outside the current build; it
  is not an invitation to choose that route independently.
- A digital `PASS` establishes internal file consistency only. It does not prove
  physical fit, anchor strength, robot reach, camera stability, or safe motion.

## Controlled builder workflow

1. Confirm that every planned job is selected and eligible in
   [print readiness](../active-project/RoCell_v0_3/PRINT_READINESS.md).
2. Complete the exact measurements, coupons, and evidence named by any open gate.
3. Use the specified material, profile, plate, and revision without substitution.
4. Record each lifecycle transition in the controlled build record; do not infer
   progress merely because a part exists.
5. Follow the [build-by-step dashboard](../active-project/RoCell_v0_3/BUILD_BY_STEP/README.md)
   only for steps whose prerequisites have passed.
6. Stop at the production-printing, drilling, and powered-motion gates until the
   controlled reports explicitly authorize them.

The generated reports and build packages should be updated through their
repository scripts, not edited by hand. This guide intentionally sits outside
the controlled package so clearer navigation does not change package hashes or
release evidence.

## Getting help or contributing evidence

Use [support](../SUPPORT.md) when a procedure or status is unclear. Use the
[contribution guide](../CONTRIBUTING.md) before proposing documentation, scripts,
measurements, or sanitized build evidence. Never publish credentials, private
device data, or unsanitized lab exports in an issue or pull request.
