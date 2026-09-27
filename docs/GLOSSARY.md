# Tactevra glossary

- **Document status:** Current reference
- **Audience:** All readers
- **Authority:** Terminology only; it does not define hardware permission

| Term | Meaning |
| --- | --- |
| **Tactevra** | The product, project, and canonical repository identity. |
| **Tactevra AI** | Intent, scene-assessment, localization, and proposal-producing components. It has no controller write authority. |
| **Tactevra Runtime** | Deterministic arm-facing validation, planning, permit, controller, and evidence components. Its compatible Python and schema namespace remains `rocell`. |
| **Tactevra Workcell** | The physical assembly integrating the robot, board, fixtures, camera, devices, and tool. |
| **Tactevra Studio** | The intended public name for the local setup and review interface. Existing launch commands remain unchanged until separately migrated. |
| **`rocell`** | Retained compatibility identifier used by Python packages, commands, schemas, configuration, and historical records. It is not a second current product brand. |
| **RoArm-M3** | The Waveshare robot-arm platform used by this project. It is a third-party product. |
| **Action plan** | Deterministically compiled ordered semantic actions, identified by a content hash. It contains no controller authority. |
| **Motion proposal** | A model-produced named target and coordinate candidate in a declared frame, with evidence and uncertainty. It is not a servo command. |
| **Admission** | Deterministic checks that either reject an input or allow it to proceed to another bounded stage. Admission is not execution. |
| **Trajectory envelope** | A sealed description of a proposed path and the evidence, policy, and identities used to screen it. |
| **Motion permit** | A single-use, exact-goal authorization produced only after required checks. It is narrower than general permission to move. |
| **Acknowledgment** | A lifecycle record such as accepted, started, completed, failed, or uncertain. Controller acknowledgment is not independent task verification. |
| **Observation lease** | The bounded time and identity conditions under which an observation may be reused. |
| **Configuration epoch** | A content-bound set of installed configuration and review identities used for a controller session. |
| **Simulation evidence** | Results under modeled inputs or geometry. It is not a physical measurement. |
| **Controller feedback** | State reported by the controller, such as joint positions. It does not independently measure tool-tip position or device input. |
| **Verified device input** | Independent evidence that the intended key, screen target, or other device action actually occurred. |
| **Zero-write** | A path that can inspect or encode proposed commands but has no writable controller transport. |
| **Ghost typing** | Noncontact movement rehearsed above keyboard regions. It is not proof of typing. |

When a document uses “success,” it should name the stage that succeeded—for
example, “proposal admitted,” “controller acknowledged,” or “device input
verified.” Avoid using one success label for the entire pipeline.
