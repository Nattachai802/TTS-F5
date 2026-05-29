# TTS-F5 — Thai Text-to-Speech API with Voice Cloning

ระบบสังเคราะห์เสียงภาษาไทย (Thai TTS) พัฒนาบนพื้นฐานของ [ThonburianTTS](https://github.com/biodatlab/thonburian-tts) (F5-TTS) รองรับการโคลนเสียง (Voice Cloning) และระบบตัดเสียงรบกวนอัตโนมัติ พร้อมด้วยหน้าจอ Web UI สำเร็จรูป

---

## ฟีเจอร์หลัก (Features)

- 🎙️ **Voice Cloning** — โคลนเสียงภาษาไทยจากไฟล์เสียงอ้างอิงความยาวสั้น ๆ (WAV)
- 🔇 **Auto Noise Reduction** — ระบบลดเสียงรบกวนและปรับแต่ง EQ อัตโนมัติด้วย Pedalboard + Noisereduce ก่อนนำเสียงไปโคลน
- 🌐 **Modern Web UI** — หน้าจอเว็บใช้งานง่าย สำหรับกรอกข้อความ อัปโหลดไฟล์เสียงอ้างอิง และกดทดลองฟังเสียงที่สร้างเสร็จ
- 🚀 **FastAPI Backend** — ส่งผ่าน REST API รองรับการนำไปเชื่อมต่อกับระบบอื่น ๆ

---

## ความต้องการของระบบ (Requirements)

- Python 3.10+
- FFmpeg (ติดตั้งในระดับ OS)
- CUDA GPU (แนะนำสำหรับการทำงานแบบ Real-time) หรือ Apple Silicon (MPS) หรือ CPU

---

## วิธีการติดตั้งและรันใช้งาน (Installation & Setup)

### 1. โคลนโปรเจกต์
```bash
git clone https://github.com/Nattachai802/TTS-F5.git
cd TTS-F5
```

### 2. โคลนโปรเจกต์ ThonburianTTS (จำเป็น)
```bash
git clone https://github.com/biodatlab/thonburian-tts.git
```

### 3. สร้าง Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate      # สำหรับ macOS / Linux
# venv\Scripts\activate       # สำหรับ Windows
```

### 4. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```
*(หมายเหตุ: หากต้องการรันผ่าน GPU แนะนำให้ติดตั้ง PyTorch เวอร์ชันที่ตรงกับ CUDA บนเครื่องของคุณก่อน)*

### 5. สตาร์ทระบบ
```bash
python main.py
```
*ระบบจะเปิดทำงานที่ `http://localhost:5000` โดยคุณสามารถเข้าใช้งานผ่านหน้าจอ Web UI หรือเรียกใช้ผ่าน API ก็ได้*

---

## วิธีการใช้ผ่าน API (API Usage)

### Endpoint
```http
POST /generate-tts
Content-Type: application/json
```

### รายละเอียด Request Body
| Field | Type | Default | Description |
|---|---|---|---|
| `text` | string | (บังคับ) | ข้อความภาษาไทยที่ต้องการให้ระบบสังเคราะห์เสียง |
| `voice` | string | `null` | Path ของไฟล์เสียงอ้างอิง (ถ้าเป็น `null` จะใช้เสียงดีฟอลต์ `000000.wav`) |
| `ref_text` | string | `null` | ข้อความพูดในไฟล์เสียงอ้างอิง (ถ้าเป็น `null` ระบบจะทำ Automatic Transcription ด้วย Whisper ให้เอง) |

### ตัวอย่างคำสั่ง Curl
```bash
curl -X POST http://localhost:5000/generate-tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "สวัสดีครับ วันนี้อากาศดีมากเลยนะครับ",
    "voice": "/absolute/path/to/my_voice.wav"
  }' \
  --output output.wav
```

---

## โครงสร้างโปรเจกต์ (Project Structure)

```
TTS-F5/
├── main.py                  # ไฟล์หลักของ FastAPI Backend
├── requirements.txt         # ไฟล์รายการ Python dependencies
├── Dockerfile               # สำหรับสร้าง Docker Image
├── docker-compose.yml       # สำหรับรันบริการด้วย Docker Compose
├── static/                  # ไฟล์ UI (HTML, CSS, JS) ของหน้าเว็บ
│   ├── index.html
│   ├── style.css
│   └── app.js
└── thonburian-tts/          # โค้ดของโมเดล F5-TTS (โคลนมาแยกต่างหาก)
```
