# Tactevra project governance

**Document status:** Current governance policy

**Authority:** Repository decision process only. This document does not authorize
hardware operation, release publication, credential access, or action on a
private security report.

Tactevra is presently maintained as an independent open-source project. It does
not currently have a foundation, steering committee, paid support organization,
or elected governance body. This page makes the current decision process
explicit so contributors can see how work is proposed, reviewed, accepted, and
superseded without inferring authority from code ownership or test results.

## Current roles

| Role | Current responsibility | Decision authority |
| --- | --- | --- |
| Accountable maintainer | `@j-webtek` maintains the repository, settings, issue routing, and merge path | Final repository merge and publication decisions within the boundaries below |
| Workstream contributor | Proposes and implements bounded AI, runtime, arm, hardware, documentation, or repository work | Technical recommendation for the contributed work; no automatic authority over another workstream |
| Affected-workstream reviewer | Reviews shared contracts, evidence, compatibility, or safety implications for a named workstream | Records a disposition for that workstream; does not merge or publish by that fact alone |
| Security reporter/reviewer | Uses the private reporting channel for vulnerabilities and sensitive evidence | Private coordination only; public issue comments do not substitute for this role |

The [CODEOWNERS map](.github/CODEOWNERS) routes review to the current accountable
maintainer. It does not prove independent review or create technical expertise.
New maintainers or specialist owners are recorded only after they accept the
responsibility and the relevant ownership documentation is updated.

## Decision classes

| Change class | Minimum path |
| --- | --- |
| Routine documentation, tests, or repository maintenance | Bounded pull request, completed template, relevant checks, maintainer review |
| Workstream-local implementation | Owning workstream evidence, compatibility statement, relevant checks, maintainer review |
| Shared AI/arm schema, command, coordinate-frame, evidence, or compatibility change | Public proposal or linked plan entry, explicit affected-workstream dispositions at an exact revision, migration/rollback notes, relevant checks |
| Public breaking change, governance change, or durable architectural choice | Public proposal, a decision record, affected-owner review, migration or supersession path |
| Release, hardware operation, credential/settings change, licensing disposition, or private security action | Separate explicit authority for the exact action plus the applicable specialist review; ordinary merge approval is insufficient |

A green check proves only the check's documented scope. It does not establish
physical success, independent review, release approval, redistribution rights,
or permission to operate hardware.

## How a decision is made

1. **State the outcome and boundary.** Open the most specific issue form. Use a
   [decision proposal](https://github.com/j-webtek/tactevra/issues/new?template=decision_proposal.yml)
   for a durable cross-workstream, compatibility, governance, or architectural
   choice. Security-sensitive material stays in private reporting.
2. **Name the affected work.** Identify the primary lane, affected contracts,
   alternatives, evidence needed, and what is explicitly out of scope. Do not
   name another person as owner or reviewer without their agreement.
3. **Review evidence at an exact revision.** Separate software tests,
   simulation, controller feedback, physical measurement, and verified device
   input. Unavailable evidence remains an open dependency.
4. **Record dispositions.** The maintainer and each required affected-workstream
   reviewer record accept, request changes, abstain, or defer with a reason.
   Silence, issue assignment, CODEOWNERS routing, and an approving check are not
   consent.
5. **Merge through protected `main`.** Required checks, conversation resolution,
   and the normal squash-merge path apply. Administrator bypass is not the
   ordinary decision mechanism.
6. **Close only proven scope.** Record the merge commit, unresolved dependencies,
   public-documentation impact, and next owner if one has agreed. A merge is not
   a release.

The accountable maintainer resolves ordinary repository decisions after the
required evidence and dispositions are present. When qualified reviewers
disagree, the change remains open or is narrowed; the maintainer does not record
another workstream's approval on its behalf. There is no vote-count rule while
the project has a single accountable maintainer.

## Durable decision records

Use a lightweight decision record when a choice:

- changes a public or cross-workstream contract;
- introduces an intentional breaking change or compatibility promise;
- changes governance, release boundaries, or evidence requirements;
- selects between architectural alternatives that future contributors would
  otherwise need to rediscover; or
- reverses an earlier recorded decision.

The [decision-record index](docs/decisions/README.md) defines statuses, naming,
required content, and the template. Accepted records are historical evidence:
supersede them with a later record instead of rewriting their rationale or
outcome. Routine implementation detail and temporary experiments belong in the
PR, issue, shared workplan, or evidence ledger rather than a decision record.

## Protected boundaries

- **Security:** report vulnerabilities and exposed secrets through
  [private security reporting](SECURITY.md). Public governance discussion must
  not reveal private findings, credentials, or exploit details.
- **Physical operation:** repository governance never authorizes a startup,
  firmware installation, torque change, movement, contact test, or retry. Those
  require a separately reviewed procedure and exact user authority.
- **Release:** tags, release notes, candidate commits, and included assets need
  separate exact-scope approval under the [release procedure](docs/RELEASING.md).
- **Licensing:** an unanswered vendor inquiry, attribution entry, or maintainer
  merge does not establish redistribution rights.
- **Support:** participation is voluntary. The project currently promises no
  response time, compatibility window, emergency service, or continued roadmap.

## Changing this policy or maintainership

Governance changes use a public decision proposal and pull request. Explain the
problem, alternatives, transition effect, and any new authority. A change that
adds a maintainer or specialist owner must record their acceptance and update
CODEOWNERS and the relevant operations documentation in the same reviewed
increment.

If the accountable maintainer becomes unavailable, existing contributors may
propose a successor or fork under the Apache-2.0 license. Repository access
cannot be transferred by this document alone; GitHub ownership and any external
accounts require their own authorized transfer. Until such a transfer is
recorded, no contributor should imply control of the canonical repository,
security channel, trademark position, or unpublished release materials.
