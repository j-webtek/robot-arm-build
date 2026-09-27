# Tactevra documentation standard

- **Document status:** Current policy
- **Audience:** Contributors and maintainers

Documentation should help a reader distinguish current instructions from plans,
historical evidence, and unreleased research. A technically accurate page can
still be harmful if its status or audience is unclear.

## Document classes

| Class | Purpose | Required treatment |
| --- | --- | --- |
| Current guide | A supported path a reader can follow now | State prerequisites, expected result, limitations, and support route |
| Current reference | Authoritative terminology, contract, or repository policy | Identify its authority and compatibility scope |
| Active plan | Proposed or in-progress work | State owner, status, completion criteria, and that it grants no hardware authority |
| Evidence record | A dated result tied to exact inputs | Preserve outcome, source identity, commands, and limitations |
| Historical reference | Superseded material retained for provenance | Label it historical and link to the current replacement |
| Release draft | Preparation for an unpublished candidate | Name the exact candidate, approval state, blockers, and supersession status |

## Required reader context

New or substantially revised plans, evidence records, and release documents
should state near the top:

- document status;
- intended audience;
- reviewed date or exact source identity when the claim is time-sensitive;
- whether the document is explanatory, normative, or evidentiary; and
- the current replacement when the document is historical.

Do not rewrite historical outcomes to match newer architecture. Add a clear
disposition and forward link instead.

## Naming rules

- Use **Tactevra** for the current product and repository.
- Use **Tactevra Runtime** and **Tactevra AI** in current explanatory prose.
- Preserve `rocell` in commands, code, schemas, configuration, and historical
  evidence.
- Preserve RoCell-named hardware release directories until a separately reviewed
  compatibility migration changes them.
- Use **RoArm-M3** only for the third-party robot platform.
- Never replace identifiers mechanically across source or evidence records.

See the [glossary](GLOSSARY.md) and [brand guide](brand/BRAND_GUIDE.md).

## Capability language

Separate these statements:

- a parser accepted a request;
- a proposal passed admission;
- a planner found a candidate route;
- a command was encoded;
- a controller accepted or completed a command;
- an independent observer verified the intended device effect.

Simulation, controller feedback, external measurement, and verified device input
must remain distinct. State negative and failed results plainly.

## Navigation and maintenance

- Link beginner pages to [getting started](GETTING_STARTED.md),
  [project status](../PROJECT_STATUS.md), [support](../SUPPORT.md), and the
  [system overview](SYSTEM_OVERVIEW.md).
- Put detailed workstream evidence behind concise summaries.
- Prefer relative links for repository files so documentation survives branch,
  fork, and repository-name changes.
- Do not commit credentials, private session URLs, raw private captures, or bulk
  generated evidence. Follow [evidence retention](EVIDENCE_RETENTION.md).
- Run `python scripts/ci/check_docs.py` before requesting review.

Documentation checks catch selected structural errors; they do not verify every
technical claim, external URL, screenshot, or physical procedure. Review remains
required.
