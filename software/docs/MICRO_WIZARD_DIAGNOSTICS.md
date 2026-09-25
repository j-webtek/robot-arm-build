# Micro-correction diagnostics in the wizard

The Arm section now offers **Test micro-correction policies (simulation only)**
(`simulate_micro_correction`). Preview explicitly states that it accesses no
hardware. Execution runs nine synthetic policy cases and eight command-strategy
comparisons, retains the service-owned result, and displays a dedicated panel
with check counts and the disabled live-micro status. The existing Export logs
action includes the detailed synthetic results.

21 focused tests passed covering the diagnostic suite, wizard preview/execution/
export, staged transaction simulation and existing discrete transaction action.
`node --check software/src/rocell/ui/static/app.js` passed. No browser visual
inspection was performed.

The workspace wizard service was also exercised directly (not just its test
fixture): simulation and export both succeeded. All 17 expected scenario outcomes
passed. Hardware motion commands: zero. Export integrity was independently checked.

Export directory:
`software/runs/wizard-exports/wizard-20260917T111744846320Z-652ee08604384c1ba2c4b858b21e3d04`

Result attachment:
`attachment-result-ab859f7de5c94a59991d30ae097840ea.json`

## Scope and remaining work

This action exposes the policy/strategy simulations, not a real transport test or
physical qualification. The integrated staged transaction remains separately
unit-tested. No native sender type checks, movement envelope, admission rules or
compensation settings were relaxed. The native sender still accepts only its
existing exact reservation type; staged micro intent does not satisfy it.

Live micro-command integration still requires the continuous-session ownership
contract, dedicated one-use native boundary, actual deadline-enforced polling,
passive hold and a separately reviewed wizard movement action. An already-running
wizard server may need restart to load the new action. Restart only while idle;
do not interrupt a hardware transaction. No server was restarted by this work.
