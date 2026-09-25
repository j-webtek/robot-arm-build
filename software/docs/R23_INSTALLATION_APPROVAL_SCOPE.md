# r23 app-only installation — approved scope completed

The user explicitly approved this scope. One installation and one startup
completed, with exact application readback and unchanged protected regions.
Read-only idle checks passed. Approval is consumed; no repeat installation,
startup, hold or movement is authorized by this document.

- Installation export: `wizard-20260919T184819223012Z-cb87d6db097f4b4295c9ea658c40d94a`.
- Startup export: `wizard-20260919T184819488795Z-a3b00dfe774340749e3ac636aa903a03`.
- New boot: `6053f8c5292f9b6b4d59f2f690241314`.

## Purpose

Install the reviewed shoulder-session firmware without starting a hold or moving
to the upright pose. This is an installation/startup step, not joint initialization.
The previous r22 application was replaced only after explicit approval.

## Exact artifact and preserved state

- Application SHA256: `9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b`.
- Application bytes: 1141360; destination offset: `0x10000`.
- Expected predecessor: r22 SHA256 `047beb3ac792a2c5f85c2b10138d0ca9bd47ae80359af7312138e56f0d132679`.
- Expected filesystem SHA256: `45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267`.
- Preserve settings, keys, credentials, partition table and all non-application regions.
- One-use journal: `software/private-backups/controller-20260918-session1/app-r23-deployment-events.jsonl`.

Offline preflight passed against retained artifacts and the pinned compatibility
review. It did not open USB, access the LAN, reserve the deployment journal or
verify current device bytes. Those device checks occur before an approved write.

## Authorized procedure to request

1. One app-only installation on the expected controller, MAC `fc:e8:c0:f8:d5:38`.
2. Verify controller identity, expected predecessor and protected regions before
   writing. Stop on mismatch; no fallback image, provisioning or settings change.
3. Write the pinned application once, verify full application readback and
   unchanged protected regions. No automatic retry after uncertain delivery.
4. One application startup after verified installation.
5. Read-only idle startup observation: status, resource/capability snapshot and
   status again; export results. Do not request a challenge or prepare a session.

Excluded: shoulder prepare/start, hold, target preload, torque changes, recovery
movement, homing, filesystem provisioning and automatic second startup.

The firmware setup sends no servo read/write commands. The flashing procedure
still resets the controller; that is not a guarantee of mechanically unchanged
behavior. Existing servo torque is not deliberately disabled. This proposal does
not instruct the user to disconnect power or reposition the arm.

## Approval text

“Approve one r23 app-only installation and one startup, preserving settings and
credentials, followed by read-only idle startup checks. No hold, torque changes
or movement commands.”

After successful idle/resource evidence, powered shoulder initialization requires
its own defined approval and fresh all-joint checks. It is not a lift and will not
by itself establish the final upright reference or physical clearance.
