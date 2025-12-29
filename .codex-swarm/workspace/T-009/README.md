# T-009: E01 Spike: define model allowlist policy

## Summary

- Defined and documented the Gemini model allowlist policy for MVP.
- Added validation rules for `GEMINI_ALLOWED_MODELS` and error mapping.

## Goal

- Specify and document the model allowlist format, enforcement, and error behavior.

## Scope

- Update @docs/spec/deploy_and_envs.md and @docs/spec/system_integration.md.
- Record the decision in @docs/questions/open_questions.md and changelog.

## Risks

- Incorrect allowlist configuration can fail otherwise valid steps; defaults must remain permissive.

## Verify Steps

- Docs-only change; review updated sections for consistency with Epic 1 requirements.

## Rollback Plan

- Revert the commit containing the allowlist documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- docs/spec/deploy_and_envs.md
- docs/spec/system_integration.md
- docs/questions/open_questions.md
- docs/changelog.md
<!-- END AUTO SUMMARY -->
