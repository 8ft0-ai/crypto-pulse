# Configure main branch protection

> **Mode:** How-to  
> **Audience:** CryptoPulse repository administrators  
> **Outcome:** Require pull-request review and the existing CryptoPulse validation check before normal changes can merge into `main`.

## Open the branch rule

In GitHub, open:

```text
Settings → Branches → Branch protection rules → Add rule
```

Set the branch name pattern to:

```text
main
```

## Require pull requests

Enable **Require a pull request before merging**.

Use the repository's normal issue → branch → pull request → merge path for feature, site, workflow, process and documentation changes.

## Require validation

Enable **Require status checks to pass before merging** and select the check:

```text
Build site and check generated output
```

The check is produced by [`.github/workflows/pr-validation.yml`](../../.github/workflows/pr-validation.yml). It installs the required Python dependencies, runs the unit-test suite, validates repository documentation, rejects tracked `_site/` output, builds the static site and checks expected artefacts.

Enable **Require branches to be up to date before merging** when the resulting update frequency is acceptable for the repository.

## Restrict bypass and direct pushes

Where practical:

- enable **Do not allow bypassing the above settings**;
- restrict who can push to matching branches;
- leave force pushes and branch deletion disabled;
- use the repository's preferred squash-merge model.

A repository administration or emergency exception should be narrow, explicitly authorised and recorded. Generated report recovery is not a general exemption for implementation changes.

## Verify the rule

Open or inspect a pull request that changes a path covered by the validation workflow. Confirm that:

1. the `Build site and check generated output` check appears;
2. the pull request cannot merge while the check is pending or failing;
3. a successful check reports unit-test, documentation-validation and site-build evidence;
4. tracked `_site/` content causes failure;
5. normal branch deletion or squash behaviour matches repository policy.

## Keep workflow names stable

Required checks are associated with their workflow/job identity. When changing `.github/workflows/pr-validation.yml`, verify that branch protection still recognises the expected check before relying on the new name.

For normal delivery steps, see [Deliver a repository slice](deliver-a-repository-slice.md). For generated output boundaries, see [Generated site artefacts](../reference/generated-site-artefacts.md).
