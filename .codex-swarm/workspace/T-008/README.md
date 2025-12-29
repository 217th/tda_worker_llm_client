# T-008: E01 Spike: confirm Gemini endpoint + SDK constraints

## Summary

- Confirmed MVP endpoint remains AI Studio (Gemini Developer API) and documented Google GenAI Python SDK constraints.
- Recorded structured output + image input support and noted the need to validate combined multimodal + schema usage.
- Updated system integration and deploy docs; added a closed decision entry.

## Goal

- Confirm and document the Gemini endpoint choice and SDK capabilities/constraints for structured output and image inputs.

## Scope

- Review official Gemini/GenAI SDK documentation.
- Update @docs/spec/system_integration.md, @docs/spec/deploy_and_envs.md, and @docs/questions/open_questions.md.
- Record a changelog entry for the docs pack.

## Risks

- Structured output and image inputs are documented separately; combined usage could expose SDK limits.
- SDK behavior may change; requires periodic re-validation before production hardening.

## Verify Steps

- Docs-only change; review the updated sections for consistency with Epic 1 requirements.

## Rollback Plan

- Revert the commit containing the doc updates and decision entry.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- docs/spec/system_integration.md
- docs/spec/deploy_and_envs.md
- docs/questions/open_questions.md
- docs/changelog.md
<!-- END AUTO SUMMARY -->
