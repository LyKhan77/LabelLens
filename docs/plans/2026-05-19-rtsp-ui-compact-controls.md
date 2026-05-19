# RTSP Hang + Compact Stats + Collapsible Controls Plan

## Summary

- Root cause RTSP: frontend membuat WebSocket lalu `createStreamWS()` set `onopen` untuk kirim config, tetapi `useWebSocket.connect()` menimpa `onopen`. Backend berhenti di `await ws.receive_text()`, jadi socket accepted tapi stream tidak mulai dan tidak ada error log.
- UI: `temp/html.txt` hanya snapshot MetricsBar, jadi dipakai untuk preview compact Inference Stats. Collapsible Controls harus di komponen Vue `Sidebar.vue`.

## Key Changes

- RTSP WebSocket:
  - Pindahkan pengiriman config ke satu tempat saja di `useWebSocket.ts`, atau ubah `createStreamWS()` menjadi hanya membuat socket tanpa handler.
  - Tambah handling payload `{ error }` agar error backend tampil di UI, bukan dianggap frame kosong.
  - Tambah backend log/timeout singkat saat menunggu config WebSocket supaya kasus config tidak terkirim tidak silent lagi.
- Compact Inference Stats:
  - Ubah `StatsGrid.vue` dari 4 kartu besar menjadi bar compact satu baris: `Objects`, `FPS`, `Latency`, `Classes`.
  - Kurangi padding MetricsBar agar viewer lebih luas, Detection Log tetap di bawah/kanan sesuai ruang.
  - Update `temp/html.txt` sebagai preview HTML compact dari MetricsBar.
- Collapsible Controls:
  - Ubah `Sidebar.vue` agar seluruh panel Controls bisa collapse/expand.
  - Collapsed state: sidebar jadi rail sempit dengan tombol icon/text “Controls”; viewer otomatis melebar.
  - Tidak tambah dependency icon baru karena frontend belum punya lucide/icons package.
- Docs:
  - Update `README.md` untuk workflow baru: RTSP connect lebih jelas, stats compact, Controls collapsible.

## Test Plan

- Run `npm run build` di `frontend/`.
- Manual RTSP test:
  - Klik Start RTSP.
  - Confirm backend log menerima config setelah WebSocket accepted.
  - Confirm UI berubah dari “Connecting to stream...” ke frame atau error jelas.
- Manual UI test:
  - Open app desktop width.
  - Collapse Controls, viewer melebar, no overlap.
  - Expand Controls, Grounding/Media/Settings tetap berfungsi.
  - Check `temp/html.txt` preview markup tampil compact.
- Git:
  - Commit RTSP fix terpisah.
  - Commit UI compact/collapse + README update terpisah.

## Assumptions

- “whole section” berarti seluruh Controls sidebar collapse, bukan accordion per Step.
- `temp/html.txt` adalah target preview untuk MetricsBar saja; app nyata tetap perlu perubahan Vue untuk Controls.
- Fokus fix RTSP minimal: kirim config reliably dan tambah diagnosability, bukan redesign protocol streaming.
