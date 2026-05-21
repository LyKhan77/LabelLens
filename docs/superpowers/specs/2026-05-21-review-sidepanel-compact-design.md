# ReviewPage Side Panel — Compact Redesign

> Redesign the `<aside class="dataset-inspector">` in [ReviewPage.vue](file:///home/gspe-ai3/project_cv/LabelLens/frontend/src/pages/datasets/ReviewPage.vue) to maximize detection list visibility. All secondary controls are compacted; Visual Assist is relocated to a floating bar on the canvas stage.

## Goal

Make the Detection List the dominant element of the side panel by:

1. Shrinking all non-list sections (stats, layer controls, class filters)
2. Relocating Visual Assist out of the sidebar entirely
3. Reducing detection row height from 58px → 38px with icon-only action controls

**Panel width stays at 350px.** No layout changes to the overall `dataset-review-body` grid.

---

## Section-by-Section Changes

### 1. Stats Summary (`.dataset-inspector-summary`)

| Property | Current | New |
|---|---|---|
| Card `min-height` | 42px | 28px |
| Card `padding` | 6px 8px | 4px 6px |
| Number font-size | 14px | 12px |
| Number font-weight | 500 | 600 |
| Label font-size | 8px | 7px |
| Label `margin-top` | 4px | 2px |
| Section padding | 12px | 10px |
| Grid gap | 6px | 4px |

### 2. Layer Controls (`.dataset-layer-controls`)

| Property | Current | New |
|---|---|---|
| Button height | 28px | 24px |
| Button font-size | 11px | 10px |
| Grid gap | 6px | 4px |

### 3. Class Filters (`.dataset-class-filters`)

| Property | Current | New |
|---|---|---|
| Pill height | 22px | 18px |
| Pill font-size | 10px | 9px |
| Pill padding | 0 7px | 0 5px |
| Color dot size | 6px | 5px |
| Wrap gap | 4px | 3px |
| Max-height | 62px | 48px |
| Margin-top | 10px | 6px |

### 4. Section padding (`.dataset-inspector-section`)

| Property | Current | New |
|---|---|---|
| Padding | 12px | 10px |

### 5. Visual Assist — Relocated to Floating Stage Bar

**Removed from sidebar entirely.** The `.dataset-assist-panel` and its children are removed from the `<aside>`.

**New element:** A floating action bar anchored to the bottom-center of the `.dataset-review-stage` (the image canvas area). It appears only when `selectedPromptDetections.length > 0`.

#### Floating bar specification

- **Position:** `position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%)`
- **Container:** The `.dataset-review-stage` becomes `position: relative` to anchor the bar
- **Appearance:** Pill-shaped bar with `background: var(--color-canvas)`, `border: 1px solid var(--color-hairline)`, `border-radius: var(--radius-md)`, `box-shadow: 0 4px 16px rgba(0,0,0,0.10)`, `padding: 6px 12px`
- **Layout:** Horizontal flex — `"{N} prompts selected"` text (12px, ink-mute) + action button
- **Action button:** 
  - If model not loaded: `[Load Model]` secondary button (24px height)
  - If model loaded: `[Infer Next ▸]` primary button (24px height)
- **Error text:** Shown as a second line below the bar content (11px, red)
- **Transition:** Uses Vue `<Transition name="prompt-bar">` with `opacity` + `transform: translateY(8px)` fade-slide on enter/leave (CSS-only, ~200ms ease)
- **CSS class:** `.dataset-prompt-action-bar`
- **z-index:** Above the image but below modals — `z-index: 10`

### 6. Detection List Rows (`.dataset-detection-row`)

#### Layout changes

| Property | Current | New |
|---|---|---|
| Grid columns | `auto 32px minmax(0,1fr) auto 32px` | `20px 24px minmax(0,1fr) auto 24px` |
| Min-height | 58px | 38px |
| Padding | 12px 16px | 6px 10px |
| Gap | 12px | 6px |

#### Prompt checkbox

**Current:** A styled `<label class="dataset-prompt-checkbox">` wrapping a checkbox + "Prompt" text, with 28px height, 8px padding, border, and background.

**New:** Bare checkbox only. Remove the `<label>` wrapper and "Prompt" text span. Just render:
```html
<input type="checkbox" class="dataset-prompt-check" :checked="..." @change="..." @click.stop title="Use as Visual Assist prompt" />
```

Checkbox styling:
- `width: 14px; height: 14px`
- `accent-color: var(--color-primary)`
- `cursor: pointer`
- Remove all `.dataset-prompt-checkbox` styles

#### Visibility toggle (`.dataset-detection-toggle`)

| Property | Current | New |
|---|---|---|
| Width/height | 28px | 24px |
| Icon class | `w-3.5 h-3.5` (14px) | `w-3 h-3` (12px) |

#### Label + confidence text

| Property | Current | New |
|---|---|---|
| Label font-size | 13px | 12px |
| Sub-line font-size | 11px | 10px |

#### Accept/Reject button — Icon toggle

**Current:** Text button showing "Accepted" or "Rejected" (`.dataset-accept-button`).

**New:** A 24×24px icon-only toggle button. Uses a checkmark (✓) SVG icon.

- **Accepted state:** Green-tinted background (`rgba(62,207,142,0.1)`), green border, green icon
- **Rejected state:** Default muted style (same as current non-accepted `.dataset-accept-button`)
- **Tooltip:** `title="Accepted"` or `title="Rejected"` for discoverability
- CSS class: `.dataset-status-toggle`

SVG icon (simple checkmark, 12px):
```html
<svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
  <polyline points="20 6 9 17 4 12" />
</svg>
```

#### Delete button (`.dataset-row-delete-button`)

| Property | Current | New |
|---|---|---|
| Width/height | 28px | 24px |
| Icon class | `w-3.5 h-3.5` (14px) | `w-3 h-3` (12px) |

#### Selected/Prompt row indicators

No change — keep `box-shadow: inset 3px 0 0 var(--color-primary)` for prompt-selected rows, and `background: var(--color-canvas-soft)` on hover.

### 7. Candidate Rows (`.dataset-candidate-row`)

Apply proportional shrink to match detection rows:

| Property | Current | New |
|---|---|---|
| Min-height | 50px | 38px |
| Padding | 8px 12px | 6px 10px |
| Gap | 8px | 6px |
| Action button height | 28px | 24px |
| Label font-size | 13px | 12px |
| Sub-line font-size | 11px | 10px |

Candidate header padding: `10px 12px` → `8px 10px`.

### 8. Footer

| Property | Current | New |
|---|---|---|
| Padding | `px-5 py-3` (20px/12px) | `px-4 py-2` (16px/8px) |

---

## Files Changed

### [MODIFY] [ReviewPage.vue](file:///home/gspe-ai3/project_cv/LabelLens/frontend/src/pages/datasets/ReviewPage.vue)

**Template changes:**
- Remove `.dataset-assist-panel` block from `<aside>` (lines 681-705)
- Add floating `.dataset-prompt-action-bar` inside `.dataset-review-stage` (after the `EditableAnnotationOverlay`)
- Replace Prompt `<label>` wrapper with bare `<input type="checkbox">` in detection rows
- Replace Accept/Reject text button with icon-only `.dataset-status-toggle` button
- Shrink SVG icon classes from `w-3.5 h-3.5` to `w-3 h-3` on visibility toggle and delete button
- Update footer padding classes

**Script changes:** None — all existing computed properties and methods stay. The floating bar uses the same `promptModelReady`, `selectedPromptDetections`, `canInferNext`, `runInferNext`, `loadPromptModel`, `inferNextError` refs.

### [MODIFY] [style.css](file:///home/gspe-ai3/project_cv/LabelLens/frontend/src/app/style.css)

**CSS changes:**
- Update `.dataset-inspector-summary` and children: smaller heights, padding, fonts
- Update `.dataset-inspector-section`: 10px padding
- Update `.dataset-layer-controls button`: 24px height, 10px font
- Update `.dataset-class-filters`: 18px pill height, 9px font, 48px max-height, 6px margin-top
- Remove `.dataset-assist-panel`, `.dataset-assist-main`, `.dataset-assist-action`, `.dataset-assist-error` styles (or leave orphaned — they're not used elsewhere)
- Remove `.dataset-prompt-checkbox` styles
- Add `.dataset-prompt-check` (bare checkbox styles)
- Add `.dataset-prompt-action-bar` (floating bar on canvas)
- Add `.dataset-status-toggle` (icon-only accept/reject)
- Update `.dataset-detection-row`: 38px min-height, 6px 10px padding, tighter grid columns
- Update `.dataset-detection-toggle`, `.dataset-row-delete-button`: 24px size
- Update `.dataset-candidate-row`: 38px min-height, tighter padding
- Add `.dataset-review-stage` `position: relative` for floating bar anchor

---

## Vertical Space Budget (approximate)

| Section | Before | After | Saved |
|---|---|---|---|
| Stats summary | ~66px | ~38px | 28px |
| Inspector section padding | 12px | 10px | 2px |
| Layer controls | ~34px | ~28px | 6px |
| Visual Assist panel | ~62px | 0px | 62px |
| Class filters + margin | ~72px | ~54px | 18px |
| Footer | ~30px | ~24px | 6px |
| **Total non-list area** | **~276px** | **~154px** | **~122px** |

Each detection row drops from 58px → 38px, gaining **~3.2 extra rows** visible in the same viewport.

---

## No Changes

- Panel width: stays 350px
- `dataset-review-body` grid: stays `minmax(0,1fr) 350px`
- Candidate panel: same structure, just proportionally shrunk
- All script logic, computed properties, watchers: unchanged
- Delete confirmation modals: unchanged
- Keyboard navigation: unchanged
- Overlay component interface: unchanged
