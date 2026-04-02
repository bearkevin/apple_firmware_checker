# Todo

## Specification

- [x] Add email notification to `.github/workflows/firmware_check.yml` only.
- [x] Send email only when a `*_updates.txt` file is created or changed by the current run.
- [x] Allow manual resend of an existing `*_updates.txt` file from `workflow_dispatch`.
- [x] Use SMTP delivery with recipients configured in GitHub secrets/variables.
- [x] Keep SMTP host and port public in the workflow, with credentials stored only in GitHub secrets.
- [x] Attach the generated `*_updates.txt` file to the email.
- [x] Keep existing auto-commit behavior for `*.db`, `*.xml`, `*.txt`.
- [x] If email sending fails, still commit changes and mark the workflow as failed at the end.

## Implementation

- [x] Add a manual workflow input for selecting a historical `*_updates.txt` file.
- [x] Split workflow behavior between normal checks and manual resend mode.
- [x] Keep email failure handling aligned with the mode that ran.
- [x] Replace `MAIL_CONNECTION` with explicit SMTP settings and secret-backed credentials.
- [x] Validate the workflow syntax and review the final diff.

## Review

- [x] Workflow logic matches the agreed trigger and failure behavior.
- [x] Required repository configuration is clearly reflected in the workflow.

### Result

- Added conditional SMTP email sending for changed `*_updates.txt` files.
- Added manual resend support for an existing `*_updates.txt` file from `workflow_dispatch`.
- Replaced URL-style SMTP configuration with explicit SMTP host, port, and secret-backed credentials.
- Kept auto-commit in place and fail the workflow after commit when email delivery fails.
- Verified the workflow file parses as YAML and the diff is clean.
