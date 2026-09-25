# Camera v2 scoped execution and output ownership

2026-09-10. Next implementation after the
[original-retention checkpoint](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md).
This work advances the full camera/arm onboarding application; it is not a new
definition of completion or permission to connect hardware during development.

Implementation update: the scoped campaign, receipt builder, fresh Windows
directory ownership and final rejection handoff are installed. See the
[campaign checkpoint](CAMERA_ACTIVATION_CAMPAIGN_CHECKPOINT.md) for exact tests
and remaining original/runtime/UI work. Runtime approval is a software gate;
received-hardware qualification must not be a circular prerequisite for its first
supervised diagnostic probe.

## Verified starting state

- Current application source is `457e9586ecc197d244efe3eebe9f786dd3e2df154eff1bd05290335ce3f25cad`.
- The v1 `PhysicalNativeCameraCampaign` is explicitly held and creates no output
  directories. Its runtime/preparation/evidence types remain historical contracts.
- The v2 supervisor, bounded paired evidence, core result handling and original
  M1 part/index retention are installed and tested, but no v2 campaign calls them.
- The native capture worker requires an already existing empty output directory;
  it uses exclusive new-file creation and does not create directories itself.
- The Win32 owner pins existing working/package ancestry and accounts for pin
  cleanup. It does not currently create/pin a per-attempt capture subdirectory.
- The runtime v2 object is a build-review candidate, not approval. Public original
  acquisition, runtime approval and the wizard dispatch path remain unfinished.

## Implementation

1. Add an exact v2 campaign plan binding the selected current metadata review,
   its activation expectation, source/workspace, session, purpose-specific runtime,
   native mode/controls/budgets and derived per-attempt output policy. Preparation,
   plan restoration and registration must remain filesystem/device inert.
2. Derive the expectation from the existing reviewed enrollment bridge at the
   application boundary. Never infer a camera from an index, friendly name or
   old receipt alone. Pure plan validation is not authentication of original
   enrollment or approval of a runtime.
3. Supply a mandatory process-local application guard. The eventual original
   service must bind it to accepted runtime/identity/plan/stage/currentness and
   pre-effect storage-capacity checks. It returns no permission object and cannot
   replace the exact consumed commissioning scope or its revalidation calls.
4. Execute once: verify exact plan/permit/scope, acknowledge the already-consumed
   permit, recheck current application/source, then call the installed supervisor.
   Its after-pin and final-release callbacks compare the entire preparation and
   revalidate the same active scope. No retry, new deadline or second consumption.
5. Extend only the new v2 Win32 camera owner with a closed fresh-directory policy
   for `native-camera-attempt-<32 hex>` and, for capture, its matching
   `capture-attempt-<32 hex>` child. Pin existing ancestry before creation; pin
   the new directories while the child may write. Existing directories are an
   error, not reusable scratch. Keep their handles in the existing owner cleanup
   accounting and retain files/directories on success or failure. Preserve legacy
   owners and the existing generic v2 contained-process test path.
6. Add a pure production receipt builder using the already installed full evidence
   and native-accounting contract. Missing native receipts remain absent. The core
   retains the returned pair before uncertainty, including a failed final scope.
7. Verify the campaign/core/supervisor join with modeled owners and actual scoped
   protocol checks; verify fresh-directory creation/pinning/refusal/cleanup with
   real Windows filesystem handles and no process/device execution. Include
   mutation, Stop, source drift, wrong scope/deadline, repeated use, changed
   expectation, occupied paths and unchanged legacy behavior.

## Still required after this component

The application must independently approve/install the purpose-specific native
runtime, authenticate current original inputs, admit pre-effect storage capacity,
add the original stage-5 acquisition successor, verify captured image bytes, and
connect the existing UI/Stop/private export/reopen flow. This internal campaign
must not be exposed by removing an unrelated hold or inventing permissive facts.
Arm identity/startup/feedback and later separately qualified motion/contact remain
part of the full objective. Received-hardware validation stays explicitly pending.

Use fresh test/report paths and preserve originals in the confirmed
`software/runs/wizard-exports` folder. The previous goal turn made concrete
progress; agent subtasks are currently terminal with usage-limit errors, so the
root continues implementation without restarting those agents.
