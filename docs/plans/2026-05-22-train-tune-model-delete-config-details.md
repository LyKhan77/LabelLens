# Train Tune Model Delete and Configuration Details

## Summary
- Remove duplicate builder summary refresh controls and keep estimate refresh in Training Preview.
- Surface Dataset Version and training-run configuration on Live Progress and Result.
- Add modal-based Train Tune delete flows including Model Version deletion with linked Training Job cleanup.

## Key Changes
- Rename summary recompute action to `Refresh Estimate` and remove `Refresh Summary` from the stepper footer.
- Show checkpoint, architecture, epochs, image size, batch, workers, compute mode, Dataset Version split/preprocessing/augmentation details on monitor/result views.
- Replace browser confirms for Dataset Version and failed Training Job delete with the shared modal pattern.
- Add Model Version delete API and frontend action; deleting a model removes the registered model metadata, linked Training Job metadata, metrics, and output folder.

## Tests
- Service/router tests cover Model Version deletion and linked Training Job cleanup.
- Frontend build/typecheck and rendered checks cover modal delete affordances and configuration panels.

## Assumptions
- A Model Version is registered only after its linked training job completes.
- Failed Training Job delete keeps its existing failed-only service rule.
- Dataset Version delete remains blocked while referenced by any remaining Training Job or Model Version.
