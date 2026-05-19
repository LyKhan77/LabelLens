Berikut adalah komprehensif *Product Requirements Document* (PRD) untuk web app **LabelLens**.

---

# 📄 Product Requirements Document (PRD): LabelLens

## 1. Ringkasan Eksekutif (Executive Summary)

**LabelLens** adalah prototipe aplikasi web berbasis antarmuka visual yang dirancang untuk melakukan deteksi objek (object detection) menggunakan model **YOLOE-26s**. Aplikasi ini memungkinkan pengguna untuk mengunggah gambar, memutar video, atau menyambungkan *real-time streaming* (RTSP) untuk diproses oleh model kecerdasan buatan, dan menghasilkan output visual berupa kotak pembatas (*bounding boxes*) dengan label yang dapat disesuaikan (opsional).

## 2. Tujuan Produk (Product Goals)

* Menyediakan antarmuka yang cepat dan responsif untuk pengujian model YOLOE-26s.
* Mendukung berbagai fleksibilitas input: Gambar statis, Video (VOD), dan *Live Stream* (RTSP).
* Memisahkan beban kerja komputasi *Computer Vision* di backend (FastAPI) dan presentasi visual di frontend (Vue.js).

---

## 3. Alur Kerja Utama (Core Workflow)

Sesuai dengan spesifikasi, alur kerja sistem adalah:
**`Input Media (Image/Video/RTSP) ➔ Proses Inference (YOLOE-26s) ➔ Output Media + Label (Opsional)`**

---

## 4. Spesifikasi Teknis & Tech Stack

Pemisahan arsitektur (*Decoupled Architecture*) digunakan untuk memastikan skalabilitas:

| Komponen | Teknologi Pilihan | Fungsi Utama |
| --- | --- | --- |
| **Frontend** | Vue.js (Vue 3, Composition API) | Antarmuka pengguna, manajemen *state* input media, rendering hasil (*Canvas* / Video Player). |
| **Backend** | FastAPI (Python) | Menerima *request*, memproses dekode RTSP/Video, menangani antrian (*queue*), dan *routing*. |
| **AI/ML Engine** | YOLOE-26s (PyTorch/ONNX) | Menjalankan *inference* pada *frame* yang dikirim oleh backend. |
| **Komunikasi** | REST API & WebSockets | REST API untuk *upload* gambar. WebSockets / WebRTC untuk transmisi *streaming* video dan RTSP dengan latensi rendah. |
| **Media Handler** | FFmpeg / OpenCV | Ekstraksi *frame* dari video dan *decoding* protokol RTSP di sisi backend. |

---

## 5. Kebutuhan Fungsional (Functional Requirements)

### 5.1. Modul Input Media

Pengguna dapat memilih salah satu dari tiga mode input:

* **Mode Gambar:** Mengunggah file `.jpg`, `.png`, atau `.jpeg` (Maks 10MB).
* **Mode Video:** Mengunggah file video `.mp4`, `.avi`, atau `.mov` (Maks 100MB).
* **Mode RTSP:** Memasukkan URL *stream* RTSP (contoh: `rtsp://admin:password@192.168.1.100:554/stream`).

### 5.2. Konfigurasi Inference (Pengaturan Parameter)

Sebelum atau saat proses *inference* berjalan, pengguna dapat mengatur parameter berikut via UI:

* **Confidence Threshold:** *Slider* (0.0 - 1.0) untuk menyaring deteksi dengan tingkat kepercayaan rendah.
* **Toggle Label Output (Optional):** Sakelar (*switch*) untuk menyembunyikan atau menampilkan teks label (nama objek dan persentase) di atas *bounding box*. Jika dimatikan, hanya kotak pembatas yang muncul, atau gambar asli tanpa coretan tergantung pilihan.

### 5.3. Modul Inference Backend (FastAPI)

* **Gambar Statis:** FastAPI menerima gambar via *multipart/form-data*, menjalankan inferensi YOLOE-26s, dan mengembalikan gambar hasil (base64/URL) beserta payload JSON (koordinat *bounding box*).
* **Video & RTSP:**
* FastAPI menangkap *stream* menggunakan OpenCV.
* *Frame* diekstrak secara berkala (contoh: 15-30 FPS).
* Menjalankan YOLOE-26s pada setiap *frame*.
* Mengirim kembali *frame* hasil deteksi ke Vue.js secara *real-time* menggunakan protokol **WebSocket** (dalam bentuk *Motion JPEG / MJPEG* atau data JSON untuk di-render di Canvas Frontend).



### 5.4. Modul Output (Dashboard)

* Menampilkan media asli bersanding dengan (atau digantikan oleh) media hasil deteksi.
* Menampilkan panel analitik ringan di sisi layar: total objek yang terdeteksi, FPS (*Frames Per Second*) *inference*, dan latensi.

---

## 6. Kebutuhan Non-Fungsional (Non-Functional Requirements)

* **Performa Terukur:** Proses *inference* RTSP harus berjalan asinkron. Backend tidak boleh mengalami *blocking* (*bottleneck*) saat melayani *stream* video.
* **Manajemen Memori:** Backend (OpenCV/FFmpeg) harus memiliki sistem *timeout* atau pemutusan koneksi otomatis jika URL RTSP terputus atau *tab browser* Vue.js ditutup, untuk mencegah kebocoran memori (*memory leak*).
* **Responsivitas UI:** Vue.js harus merender *streaming* WebSocket tanpa *lag* atau *flicker* pada layar pengguna.

---

## 7. Desain Antarmuka Pengguna (UI/UX Draft)

Struktur tata letak (Layout) Halaman Utama **LabelLens**:

1. **Header:** Logo LabelLens, Status Koneksi Backend (Hijau/Merah).
2. **Sidebar Kiri (Kontrol):**
* *Tab Menu:* Image | Video | Live RTSP.
* *Input Field:* Tombol *Upload* atau Kolom Input Teks untuk URL RTSP.
* *Settings:* Slider *Confidence* (default: 0.5), Toggle *Show Labels* (On/Off).
* *Action:* Tombol "Start Inference" dan "Stop".


3. **Main Content (Visualizer):**
* Kotak Media Player berukuran besar di tengah.
* Menampilkan progres *loading* saat model sedang memproses (*cold start*).


4. **Panel Bawah/Kanan (Metrik):**
* Menampilkan Log Deteksi (Contoh: "Person: 0.89", "Car: 0.92").
* *Inference Speed* (ms/frame).



---

## 8. Rencana Implementasi (Fase Pengembangan)

* **Fase 1 (Proof of Concept):** Setup Vue.js dan FastAPI. Integrasi YOLOE-26s hanya untuk input gambar statis via REST API.
* **Fase 2 (Video Processing):** Penambahan fitur unggah video. Backend memproses video secara sekuensial dan mengirimkan file hasil akhirnya (VOD).
* **Fase 3 (Real-Time RTSP & WebSockets):** Implementasi transmisi *live frame* dari OpenCV di FastAPI ke komponen `<canvas>` atau `<img src="data:image/jpeg;base64,...">` di Vue.js menggunakan WebSockets.
* **Fase 4 (Optimasi UI & Deployment):** Penambahan fitur Toggle Label, *error handling* URL RTSP yang mati, dan deployment menggunakan Docker (Frontend, Backend, Container AI).

# References 
- `https://www.youtube.com/watch?v=yNPwsKa52zs`
- `https://docs.ultralytics.com/models/yoloe`