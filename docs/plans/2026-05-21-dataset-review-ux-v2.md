# Dataset Review UX V2 Plan

## Summary
Improve Dataset Review Visual Assist for faster sequential labeling: support multiple prompt annotations, auto-save accepted candidates, provide Save & Continue, and add direct delete for all saved annotations.

## Implementation
- Add prompt checkboxes to saved detection rows and send all selected prompts to the existing Infer Next endpoint.
- Replace manual candidate batching with one-click auto-save: Accept saves immediately, Reject removes locally, Save & Continue saves then runs Infer Next again.
- Add direct delete controls on every saved detection row; deletion works for Rapid/Batch, Manual, and Visual Assist annotations through the existing detection delete endpoint.
- Keep candidate duplicate hiding at IoU >= 0.7 and keep rejected candidates local-only.
- Update README, AGENTS, and CLAUDE to reflect the workflow.

## Verification
- Frontend production build verifies Vue/TypeScript integration.
- Backend dataset tests verify saved annotation deletion and export behavior.
- End-to-end YOLOE behavior still needs testing with actual prompt weights.
