# Todo

## Specification

- [x] Add email notification to `.github/workflows/firmware_check.yml` only.
- [x] Send email only when a `*_updates.txt` file is created or changed by the current run.
- [x] Use SMTP delivery with recipients configured in GitHub secrets/variables.
- [x] Attach the generated `*_updates.txt` file to the email.
- [x] Keep existing auto-commit behavior for `*.db`, `*.xml`, `*.txt`.
- [x] If email sending fails, still commit changes and mark the workflow as failed at the end.

## Implementation

- [x] Detect changed `*_updates.txt` files after `firmware_checker.py` runs.
- [x] Send notification email conditionally with the changed file attached.
- [x] Preserve auto-commit and add a final failure gate for email errors.
- [x] Validate the workflow syntax and review the final diff.

## Review

- [x] Workflow logic matches the agreed trigger and failure behavior.
- [x] Required repository configuration is clearly reflected in the workflow.

### Result

- Added conditional SMTP email sending for changed `*_updates.txt` files.
- Kept auto-commit in place and fail the workflow after commit when email delivery fails.
- Verified the workflow file parses as YAML and the diff is clean.
