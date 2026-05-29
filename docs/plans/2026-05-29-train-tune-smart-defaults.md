# Train Tune Smart Defaults Plan

## Summary
- Add `patience` end-to-end for Ultralytics early stopping.
- Add Auto Batch support using Ultralytics `batch=-1`.
- Add recommended training settings based on Dataset Version image count.

## Key Changes
- Backend exposes `/training/recommend` and persists `patience` in training jobs.
- Worker passes `patience` and `batch=-1` through to `model.train()`.
- Frontend shows recommended settings and lets users apply them without removing manual override.

## Tests
- Backend service/router/worker tests cover recommendation buckets, `patience`, and auto batch forwarding.
- Frontend build validates API types and Train Tune UI bindings.
