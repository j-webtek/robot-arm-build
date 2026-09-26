# Getting help with Tactevra

Tactevra is an experimental project, not a ready-to-use autonomous typing product.
Start with [getting started](docs/GETTING_STARTED.md),
[current capabilities](PROJECT_STATUS.md), and [offline verification](docs/CI.md).
You do not need an arm or a running model service for the introductory offline
examples.

## Choose the right channel

| Need | Where to go |
| --- | --- |
| Installation or a reproducible non-sensitive defect | [Open a bug report](https://github.com/j-webtek/robot-arm-build/issues/new?template=bug_report.md) |
| Unclear, outdated, or missing guidance | [Report a documentation problem](https://github.com/j-webtek/robot-arm-build/issues/new?template=documentation.md) |
| A capability suggestion or workflow improvement | [Request a feature](https://github.com/j-webtek/robot-arm-build/issues/new?template=feature_request.md) |
| A suspected vulnerability, leaked secret, or execution-gate bypass | Follow [private security reporting](SECURITY.md); do not use public issues |
| Development coordination between AI and arm contributors | Use the [shared workplan](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md) and a topic-branch PR |

GitHub issues are public. This project does not promise response times, emergency
support, or compatibility with an unqualified hardware setup.

## Help us reproduce a problem

Include the software commit (`git rev-parse HEAD`), OS, Python version, exact
command, expected result, and sanitized error text. Say whether the problem
occurred during installation, offline simulation, model inference, or an already
authorized physical test. Include relevant dependency versions and whether any
native helper was built. A folder named `unit` does not mean every test is
portable; see the [test tiers](docs/CI.md).

Share only the smallest useful example. Remove credentials, authorization
headers, private configuration, personal images, and identifying device details
that are not needed. Inspect archive contents too. Keep original evidence locally
and describe what you removed; follow the [export-sharing guide](CONTRIBUTING.md#export-sharing).
Do not upload full device backups or raw diagnostic folders to an issue.

## If physical behavior is unexpected

Do not repeat a movement merely to reproduce a bug. Pause further commands and
follow the existing procedure for your exact hardware setup. Do not improvise a
restart or torque-off step: an unsupported arm may fall. A GitHub issue is not a
live incident-response channel. Once the setup is safe, report the existing
observations and logs, separating commanded targets, controller feedback, and
what you actually saw.

Passing CI or receiving a suggested code change is not permission to install
firmware or run a physical test. Hardware work needs its own reviewed procedure.
