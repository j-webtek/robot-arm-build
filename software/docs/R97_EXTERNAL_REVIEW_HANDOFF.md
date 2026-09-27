# r97 external-review handoff

This handoff closes the filesystem boundary around the existing r97 review
packet. It does not perform or impersonate independent review and grants no
installation, startup, transport, execution, hardware, or physical authority.

## Frozen identities

- Packet SHA-256: `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`
- Manifest SHA-256: `e7c67071d0485b016cf44e0158fddb92edc0373e1e73532a3b1847f976d5117e`
- App SHA-256: `7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d`
- Decision schema: `rocell.r97_independent_review_decision.v1`

The reviewer must receive the packet unchanged, independently verify all
eleven closed checks in its instructions, and return one standalone decision
JSON matching
`software/ai/schemas/r97_independent_review_decision_v1.schema.json`. The
reviewer must control their own identity, evidence custody, attestation digest,
timestamps, findings, and disposition. Repository automation cannot supply
those facts.

## Owner-side intake

Place the returned decision in a new local intake path and run:

```powershell
$env:PYTHONPATH='software/src'
python software/scripts/assess_r97_external_review_decision.py `
  <returned-decision.json> `
  <new-empty-output-directory> `
  --received-utc <YYYY-MM-DDTHH:MM:SSZ>
```

The command rejects symlinks, duplicate JSON fields, unknown fields, oversized
input, content-hash mismatches, packet/manifest/app mismatches, synthetic
origin, incomplete checks, author conflict, open findings, and non-approved
disposition. It writes normalized decision, assessment report, and intake
summary once into a new directory and refuses overwrite.

A passing result means only `ready_for_configuration_epoch_intake=true`. It
does not authorize firmware installation or startup. The next independent
dependency remains physical measurement and review of all eight controlled
workcell components.
