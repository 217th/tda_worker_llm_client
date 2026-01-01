# T-102: Log Gemini API error details for 400 diagnosis

## Summary

- Add minimal error detail logging (status/code) for Gemini API failures to diagnose 400 Bad Request during prod smoke.

## Goal

- Make Gemini request failures actionable by surfacing provider status/code in logs without exposing payloads.

## Scope

- Update Gemini error mapping and ensure `llm_request_finished` logs include the enriched message.

## Risks

- Risk of logging overly verbose provider messages; keep details sanitized.

## Verify Steps

- `python3 -m pytest -q`

## Rollback Plan

- Revert the commit(s) for T-102.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Created T-102 task README.
- Added sanitized Gemini API error details to RequestFailed messages.
<!-- END AUTO SUMMARY -->
