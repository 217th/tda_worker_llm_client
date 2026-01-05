# T-108: Switch UserInput to XML context blocks

## Summary

- Switch UserInput assembly to XML-tagged context blocks for OHLCV, charts, and previous reports.
- Align tests and specs with the new format.

## Goal

- Provide a deterministic XML-based UserInput structure matching the requested template, including previous report support.

## Scope

- Update UserInput assembly code and adjust related docs/tests.

## Risks

- Prompt format change may affect downstream model behavior or prompt parsing.

## Verify Steps

- python3 -m pytest -q

## Rollback Plan

- Revert the commit(s) for T-108.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
