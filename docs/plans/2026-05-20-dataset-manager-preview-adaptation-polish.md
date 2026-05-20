# Dataset Manager Preview Adaptation Polish Plan

## Summary

Adapt component, flow, spacing, modal structure, and animation from `temp/interactive_preview_part2.html`. Keep all theme choices aligned with `DESIGN.md` and the existing LabelLens app tokens.

## Implementation Steps

1. Set dataset image pagination default to 25.
2. Polish `DatasetDetail` gallery: project-level metrics, correct `Showing start-end of total` text, consistent cards, no emoji badges, less non-brand color.
3. Polish `ReviewPanel`: centered modal, compact header with Prev/Next, fixed review stage, inspector sidebar, concise footer, and preserved overlay mapping.
4. Polish `BatchUploadDialog`: clearer stepper, better spacing, preview-like upload/config/progress layout, and token-consistent controls.
5. Update README and project-doc section of AGENTS to reflect the standalone Dataset Manager and polished gallery/review workflow.
6. Verify with frontend build and diff checks, then commit the functional slice.

## Verification

- `npm run build` from `frontend/`
- `git diff --check`
- Manual UI pass for `/datasets` at 375px, 768px, 1024px, and 1440px
