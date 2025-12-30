# T-053: E07 Deviation: chart manifest uses png_gcs_uri key

## Summary

- UserInputAssembler expects `gcs_uri` for chart images; current manifest uses `png_gcs_uri`, causing context resolution failure.

## Scope

- Accept `png_gcs_uri` (and possibly other aliases) when parsing chart manifests.
- Add tests for manifest parsing with `gcs_uri` and `png_gcs_uri` keys.

## Risks

- Be explicit about allowed aliases to avoid silently accepting malformed manifests.

## Verify Steps

- Use a charts manifest containing `png_gcs_uri` and confirm context resolves.
- Ensure normal `gcs_uri` manifests still work.

## Rollback Plan

- Revert manifest parsing changes if parsing becomes ambiguous.
