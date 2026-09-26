# Brand adoption and repository migration plan

Status: Tactevra selected by owner, September 26, 2026. No live rename or runtime changes.
See the [brand guide](BRAND_GUIDE.md) and [name review](NAMING_REVIEW.md).

## Stages and completion criteria

| Stage | Owner | Complete when |
| --- | --- | --- |
| 1. Positioning and shortlist | Documentation lane | Draft guide and dated preliminary search are published for review |
| 2. Name and clearance decision | Project owner with qualified adviser | Preferred name, market scope, legal owner, and clearance decision are recorded |
| 3. Visual identity | Design/documentation lane | Approved wordmark, monochrome assets, tokens, licenses, and usage examples exist |
| 4. Public-facing adoption | AI and arm maintainers | README, docs, UI labels, metadata, and screenshots use the same name with tests passing |
| 5. GitHub rename | Repository owner | Exact destination approved, rename completed, links and integrations verified |
| 6. Optional technical rename | Both maintainers | Separately versioned compatibility plan and import/CLI/protocol tests pass |

Stage 1 is documented. Stage 2 name selection is complete: **Tactevra**; market
scope, legal owner, and clearance remain pending. Stages 3 onward remain pending. No hardware
test, firmware installation, torque change, or model retraining is required for
branding work.

## Before changing names

Record the old and proposed URLs, branch/PR state, deployment links, package
identifiers, and collaborators' active worktrees. Coordinate a short rename
window with both AI and arm workers. Inspect references using `rg` and classify
them as active branding, executable identifiers, external integration settings,
or immutable historical evidence. Do not use global search-and-replace.

Keep shared AI/arm plans in place; add a name-transition note rather than moving
them during active integration work. Retain vendor names and attribution.

## Public-facing adoption

Update public prose and visible UI labels first. During transition, use
“<approved name>, formerly RoCell” in one prominent location, substituting the
actual approved name. Leave `rocell` imports, CLI entry points, configuration
paths, schema IDs, model manifests, evidence hashes, and firmware identities
unchanged. They are compatibility surfaces, not cosmetic strings.

Do not rewrite frozen CAD/release packages or historical exports just to replace
their branding. New releases can carry the new identity with an explicit lineage.

## GitHub rename checklist

- [ ] Confirm exact owner and destination slug with the project owner.
- [ ] Verify destination availability and preserve a local record of current settings.
- [ ] Inventory Actions references, Pages/custom domains, badges, webhooks,
  submodules, clone URLs, and any external automation.
- [ ] Rename through GitHub without deleting/recreating the repository.
- [ ] Update each collaborator's remote and active documentation links.
- [ ] Verify old URL behavior and the new repository, PRs, issues, Actions,
  integrations, and any published site. Do not reuse the old repository name.
- [ ] Run a fresh-clone install, offline examples, and selected hardware-free tests.
- [ ] Publish a migration note stating what changed and what stayed compatible.

GitHub documents redirects and exceptions, including Pages and hosted Actions;
do not assume every integration follows the rename automatically. Consult the
[current rename instructions](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository)
at execution time.

If adoption needs to be postponed, revert cosmetic changes through an ordinary
commit; do not rewrite shared history. A repository-name rollback requires the
owner to check availability and redirect consequences again. Preserve working
clones and use the recorded remote URL if redirects fail.

## Release review

Documentation owner checks names, links, claims, and accessibility. AI maintainer
checks model attribution and manifests. Arm maintainer checks that control
identifiers and authorization semantics did not change. Repository owner checks
external integrations. Record commands, outcomes, unresolved issues, and approver
in the release PR. A branding release must not imply new physical capabilities.
