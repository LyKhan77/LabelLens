# Dataset Manager UI Polish — Design Spec

**Date:** 2026-05-20
**Status:** Draft
**Reference Preview:** `temp/interactive_preview_part2.html`

## Context

Dataset Manager UI functional but visually cramped. Elements too tight, modals lack polish, visual prompt annotation editor image too wide. User provided a premium interactive preview (`temp/interactive_preview_part2.html`) with dark theme — this spec adapts those layout patterns and components to LabelLens's existing light-first Supabase-inspired design system.

## Design Decisions

- **Full adapt** from user's preview, mapped to existing LabelLens design tokens
- **Light theme primary** with dark mode CSS variable overrides already in `style.css`
- **Generous spacing** — gap-3→gap-4/5, card padding p-4→p-5/p-6, modal padding p-5→p-6
- **Modern dialog** pattern — backdrop-blur-sm, shadow-xl, fade+scale animation
- **Compact annotation editor** — max-w-[480px] centered + sidebar for annotation list
- **Layout patterns from preview:** dashboard metrics row, filter bar with search+segments, gallery with bbox overlays on thumbnails

## Theme Token Mapping

| Preview (dark) | LabelLens (light) | CSS Variable |
|---|---|---|
| `#09090b` canvas | `#ffffff` canvas | `--color-canvas` |
| `#121216` canvas-soft | `#fafafa` canvas-soft | `--color-canvas-soft` |
| `#18181b` canvas-card | `#ffffff` (same as canvas) | — |
| `#10b981` primary | `#3ecf8e` primary | `--color-primary` |
| `#f4f4f5` ink | `#171717` ink | `--color-ink` |
| `#a1a1aa` ink-secondary | `#707070` ink-mute | `--color-ink-mute` |
| `#71717a` ink-mute | `#b2b2b2` ink-faint | `--color-ink-faint` |
| `#27272a` hairline | `#dfdfdf` hairline | `--color-hairline` |
| `#3f3f46` hairline-strong | `#c7c7c7` hairline-strong | `--color-hairline-strong` |

## Components to Modify

### 1. DatasetDetail.vue — Add Dashboard Metrics Row

**New section** between header and gallery grid.

4-column responsive grid with stat cards:
- Total Images count
- Annotations count with accept %
- Active Review Queue (amber accent)
- Distinct Classes (primary accent)

Each card: `border border-hairline rounded-(--radius-md) p-5 bg-canvas` with optional left accent border via `border-l-3`.

**Files:** `frontend/src/pages/datasets/DatasetDetail.vue`

### 2. DatasetDetail.vue — Add Filter Bar

**New section** between metrics and gallery.

Single row: search input + segment controls (All/Review/Accepted/Unlabeled) + sort button.

Segment controls: flex row of buttons with active state using `bg-primary text-on-primary`.

**Files:** `frontend/src/pages/datasets/DatasetDetail.vue`

### 3. DatasetDetail.vue — Gallery Cards with Bbox Overlays

Current gallery cards show status badge and annotation count. Add:
- Thin bbox overlay rectangles on thumbnail (positioned absolutely, derived from first 2 detections)
- Slight hover lift animation: `hover:-translate-y-1`

Change grid gap: `gap-3` → `gap-4` (16px)
Change card footer padding: `p-2` → `p-3` (12px)

**Files:** `frontend/src/pages/datasets/DatasetDetail.vue`

### 4. DatasetList.vue — Generous Spacing

- Card grid: `gap-3` → `gap-5` (20px)
- Card padding: `p-4` → `p-5` (24px)
- Icon container: `w-9 h-9` → `w-10 h-10`
- Tag spacing: `gap-1.5` → `gap-2`
- Section header margin: `mb-(--spacing-xl)` → `mb-(--spacing-xxl)` (32px)

**Files:** `frontend/src/pages/datasets/DatasetList.vue`

### 5. All Modals — Modern Dialog Pattern

Apply to all modals: Create Dataset, Export, BatchUploadDialog, ReviewPanel.

**Backdrop:** `bg-black/30 backdrop-blur-sm` (was `bg-black/45` or `bg-black/60`)
**Shadow:** `shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]` (was lighter)
**Padding:** `p-5` → `p-6` (24px) for modal body
**Header:** Add subtitle text below title
**Close button:** 32x32px with hover state
**Animation:** Vue `<Transition>` with `enter-active-class="transition ease-out duration-200"` + scale from 0.96

**Files:**
- `frontend/src/pages/datasets/DatasetList.vue` (create modal)
- `frontend/src/pages/datasets/ExportDialog.vue`
- `frontend/src/pages/datasets/BatchUploadDialog.vue`
- `frontend/src/pages/datasets/ReviewPanel.vue`

### 6. ReviewPanel.vue — Inspector Sidebar Polish

- Sidebar width: `340px` → `360px`
- Overlay controls padding: `p-3` → `p-4`
- Button padding: `px-2 py-1.5` → `px-3 py-2`
- Class filter: pill-shaped tags with `rounded-full` instead of `rounded-(--radius-sm)`
- Detection rows: `px-3 py-2` → `px-4 py-3`
- Action buttons: `w-7 h-7` → `w-8 h-8`
- Accept/reject button text: `✓`/`✕` → `OK`/`NO` (clearer)
- Nav footer: add `←`/`→` arrows to Previous/Next
- Add keyboard shortcuts hint in footer: `Esc close · ← → navigate`

**Files:** `frontend/src/pages/datasets/ReviewPanel.vue`

### 7. BBoxAnnotation.vue — Compact Centered Editor

When used inside BatchUploadDialog (visual prompt mode):
- Container: `max-w-[480px] mx-auto` to constrain image width
- Two-column layout: canvas left (max 480px) + annotation list sidebar right (flex-1, min-w-[180px])
- Annotation sidebar: border, rounded, p-4, with label list and remove buttons
- "Change reference" link at bottom of sidebar

**Files:**
- `frontend/src/shared/components/BBoxAnnotation.vue`
- `frontend/src/pages/datasets/BatchUploadDialog.vue` (layout wrapper)

### 8. BatchUploadDialog.vue — Visual Prompt Mode Layout

When `promptType === 'visual'` and `referPreview` exists:
- Wrap in flex layout: annotation canvas (max-w-480px) + sidebar (annotation list)
- Remove tag list from below canvas, move to sidebar
- Add "Change reference" link in sidebar

**Files:** `frontend/src/pages/datasets/BatchUploadDialog.vue`

### 9. ExportDialog.vue — Polish

- Backdrop: add `backdrop-blur-sm`
- Shadow: increase to `shadow-xl`
- Body padding: `p-(--spacing-xxl)` → `p-6` (24px)
- Add subtitle under title
- Button padding: `px-4 py-2` → `px-5 py-2.5`
- Footer gap: `gap-3` → `gap-4`

**Files:** `frontend/src/pages/datasets/ExportDialog.vue`

### 10. Create Dataset Modal (in DatasetList.vue) — Polish

Same modern dialog pattern as above.
- Increase max-width: `max-w-[420px]` → `max-w-[440px]`
- Add subtitle: "Create a new labeling project"
- Input padding: `px-3 py-2` → `px-3.5 py-2.5`
- Label margin: `mb-3` → `mb-4`
- Footer: align cancel left, create right with `justify-between`

**Files:** `frontend/src/pages/datasets/DatasetList.vue`

## Spacing Changes Summary

| Element | Before | After |
|---|---|---|
| Dataset list grid gap | `gap-3` (12px) | `gap-5` (20px) |
| Dataset card padding | `p-4` | `p-5` or `p-6` |
| Gallery grid gap | `gap-3` (12px) | `gap-4` (16px) |
| Gallery card footer | `p-2` | `p-3` |
| Modal body padding | `p-5` | `p-6` |
| Modal backdrop | `bg-black/45` | `bg-black/30 backdrop-blur-sm` |
| Review sidebar controls | `p-3` | `p-4` |
| Review detection rows | `px-3 py-2` | `px-4 py-3` |
| Section margins | `mb-xl` (24px) | `mb-xxl` (32px) |
| Form input padding | `px-3 py-2` | `px-3.5 py-2.5` |

## New Components to Extract

### FilterBar (inline in DatasetDetail)
- Search input with icon
- Segment control buttons
- Sort dropdown/button

Not extracted as separate component — keep inline per YAGNI, unless reused elsewhere.

## Verification

1. Run `pnpm dev` and open Dataset Manager tab
2. Verify Dataset List cards have more breathing room
3. Click into a dataset → verify metrics row renders, filter bar works
4. Verify gallery grid spacing and hover animations
5. Click "New Dataset" → verify modern dialog with blur backdrop
6. Click "Export" → verify polished modal
7. Click "Upload + Auto-Label" → step through wizard, select "visual" mode → verify compact annotation editor with sidebar
8. Click a gallery image → verify review panel with better spacing
9. Test keyboard: Escape closes modals, arrow keys navigate review
10. Verify no regressions in dark mode if toggled
