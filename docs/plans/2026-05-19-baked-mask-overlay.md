# Baked Backend Mask Overlay Plan

## Summary
- Ubah `Show Masks` jadi render backend seperti `Show Labels` dan `Show Bounding Boxes`.
- Mask digambar langsung ke image/frame hasil inference, jadi tidak bergeser saat sidebar/control panel collapse-expand.
- Backend tetap clip mask ke bbox supaya bentuk mask tidak keluar batas bbox objek.

## Key Changes
- Backend API: tambah `show_masks: bool = Form(False)` di `/detect/image` dan `/detect/video`; tambah `show_masks` di WebSocket stream config.
- Frontend API/store: kirim `showMasks` sebagai `show_masks` untuk image, video, dan RTSP start config.
- Backend drawing: extend `draw_detections()` agar bisa blend mask raster sebelum bbox/label, dengan urutan largest-to-smallest untuk layering.
- Backend mask safety: sebelum RLE/polygon/drawing, binary mask wajib di-threshold stabil dan di-clip ke `det["box"]`.
- Frontend viewer: hapus live canvas mask overlay path untuk result/video/RTSP; `Show Masks` hanya setting inference, bukan redraw live.
- README: update workflow bahwa mask toggle dipakai saat inference/start stream dan perlu rerun untuk image/video.

## API / Types
- Request image/video form: tambah `show_masks`.
- RTSP WebSocket config: tambah `show_masks`.
- Response `detections` boleh tetap membawa `mask_rle`/`mask` untuk debug/future use, tapi UI tidak bergantung pada overlay canvas.
- Tidak ubah shape `Detection` publik.

## Test Plan
- Backend unit/synthetic: mask pixel di luar bbox tidak muncul setelah clip.
- Backend visual helper: `draw_detections(..., show_masks=True)` menghasilkan frame dengan mask blended, bbox/label tetap di atas mask.
- Compile backend: `python -m py_compile backend/**/*.py`.
- Frontend build: `cd frontend && npm run build`.
- Browser verify: run image inference dengan `Show Masks` on, collapse/expand control panel, mask tetap diam karena baked into image.
- RTSP/video verify: stream/frame dengan `show_masks=true` menampilkan mask baked; toggle saat sudah jalan tidak diharapkan mengubah frame sampai rerun/restart stream.

## Assumptions
- User memilih `Baked backend`.
- Stability lebih penting daripada live toggle tanpa rerun.
- Mask wajib tidak melewati bbox, walaupun raw YOLOE mask punya area leak.
