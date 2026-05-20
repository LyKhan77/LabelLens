# Dataset Manager Preview Adaptation Design

## Intent

Polish Dataset Manager agar mengikuti struktur dan interaksi `temp/interactive_preview_part2.html`, tetapi tetap memakai visual system LabelLens dari `DESIGN.md`. Preview dipakai sebagai referensi untuk component, flow, spacing, modal, dan motion. Warna, radius, typography, surface, dan shadow tetap dari token aplikasi.

## Design Decisions

- Dataset detail mempertahankan shell preview: sticky topbar existing, max-width workspace, hero, metrics row, toolbar, thumbnail gallery, dan pagination.
- Gallery menampilkan 25 item per page, card thumbnail 4:3, mini overlay bbox, status badge tanpa emoji, annotation count, filename, source, dan dimensions.
- Review image memakai centered modal modern dengan header Prev/Next langsung, image stage kiri, inspector kanan, fixed modal height, dan keyboard navigation.
- Auto-label wizard memakai flow existing tetapi dipoles agar stepper, upload area, visual prompt, model state, dan progress preview lebih dekat ke preview.
- Theme final mengikuti `frontend/src/app/style.css` token dari `DESIGN.md`: `bg-canvas`, `bg-canvas-soft`, `border-hairline`, `text-ink`, `text-ink-mute`, `bg-primary`, radius 6-16px.

## Boundaries

- Tidak ada backend API baru.
- Tidak mengubah dataset storage, export API, atau label job API.
- Tidak membuat dark-only premium theme dari preview.
- Tidak menambah dependency UI/animation baru.

## Acceptance Criteria

- `/datasets` tetap bisa dibuka direct dan dari landing.
- Gallery menampilkan thumbnail real dengan pagination 25/page dan counter benar.
- Review modal centered, bisa next/prev via button dan keyboard, dan overlay tetap align dengan annotation metadata.
- Wizard upload/auto-label tetap bekerja dengan flow existing.
- `npm run build` dari `frontend/` dan `git diff --check` pass.
