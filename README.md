# TTS-F5 — Thai Text-to-Speech API with Emotion Control

Thai TTS API built on [ThonburianTTS](https://github.com/biodatlab/thonburian-tts) (F5-TTS) with voice cloning and emotion blending support.

---

## Features

- 🎙️ **Voice Cloning** — clone any Thai speaker from a short audio clip
- 😊 **Emotion Control** — adjust prosody (pitch + speed) to convey happiness, sadness, anger, frustration
- 🔇 **Auto Noise Reduction** — pedalboard + noisereduce pipeline on input ref audio
- 🚀 **FastAPI** — REST endpoint, returns `.wav` file directly

---

## Requirements

- Python 3.10+
- ffmpeg (system)
- CUDA GPU (recommended) or Apple MPS or CPU

---

## Installation

### 1. Clone this repo

```bash
git clone https://github.com/Nattachai802/TTS-F5.git
cd TTS-F5
```

### 2. Clone ThonburianTTS (required)

```bash
git clone https://github.com/biodatlab/thonburian-tts.git
```

### 3. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

> **macOS (Apple Silicon):** torch จะใช้ MPS โดยอัตโนมัติ  
> **Linux + NVIDIA GPU:** ติดตั้ง torch ที่ตรงกับ CUDA version ก่อน

### 5. Prepare emotion ref audio (ครั้งแรกเท่านั้น)

ดึงไฟล์อ้างอิงอารมณ์จาก THAI-SER dataset (streaming — ไม่โหลดทั้งหมด ~12GB):

```bash
pip install datasets   # ถ้ายังไม่ได้ติดตั้ง
python scripts/prepare_emotion_refs.py
```

Script จะสร้างไฟล์ที่ `assets/emotion_refs/` ประมาณ 10 ไฟล์ (5 อารมณ์ × 2 เพศ)  
ใช้เวลาประมาณ 5–15 นาที ขึ้นกับความเร็ว internet

### 6. Run the API

```bash
python main.py
```

API จะพร้อมใช้งานที่ `http://localhost:5000`

---

## Docker

```bash
# Build & run (ต้องมี NVIDIA GPU + nvidia-container-toolkit)
docker compose up --build
```

---

## API Usage

### Endpoint

```
POST /generate-tts
Content-Type: application/json
```

### Request Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `text` | string | required | ข้อความภาษาไทยที่ต้องการสังเคราะห์ |
| `voice` | string | `null` | path ไปยัง ref audio ของ user (ถ้าไม่ระบุ ใช้ default voice) |
| `ref_text` | string | `null` | คำพูดใน ref audio (ถ้าไม่ระบุ จะ transcribe อัตโนมัติ) |
| `emotion` | string | `"neutral"` | อารมณ์: `neutral` / `happiness` / `sadness` / `anger` / `frustration` |
| `gender` | string | `"female"` | เพศของ emotion ref fallback: `female` / `male` |
| `use_emotion_ref` | bool | `false` | เปิด emotion mode |
| `emotion_strength` | float | `0.5` | ความแรงของ emotion effect (0.0–1.0) |

### Examples

**Normal (clone default voice):**
```bash
curl -X POST http://localhost:5000/generate-tts \
  -H "Content-Type: application/json" \
  -d '{"text": "สวัสดีครับ วันนี้อากาศดีมากเลยนะครับ"}' \
  --output output.wav
```

**Emotion mode (ใช้เสียง default + อารมณ์ดีใจ):**
```bash
curl -X POST http://localhost:5000/generate-tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "สวัสดีครับ วันนี้อากาศดีมากเลยนะครับ",
    "emotion": "happiness",
    "use_emotion_ref": true,
    "emotion_strength": 0.6
  }' \
  --output output.wav
```

**Clone เสียงของ user + อารมณ์:**
```bash
curl -X POST http://localhost:5000/generate-tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "สวัสดีครับ วันนี้อากาศดีมากเลยนะครับ",
    "voice": "/absolute/path/to/my_voice.wav",
    "emotion": "sadness",
    "use_emotion_ref": true,
    "emotion_strength": 0.5
  }' \
  --output output.wav
```

---

## Emotion Mode — How it works

```
use_emotion_ref = true  +  emotion ≠ neutral
        │
        ▼
EmotionBlender.blend(user_voice, emotion, strength)
   → pitch shift + time stretch บน user audio
        │
        ▼
F5-TTS clone timbre จาก user audio ที่ถูก adjust แล้ว
        │
        ▼
Output = เสียงของ user + prosody ของอารมณ์นั้น
```

### Emotion presets

| Emotion | Pitch shift | Speed |
|---|---|---|
| neutral | 0 semitones | 1.00× |
| happiness | +2.5 semitones | 1.08× |
| anger | +2.0 semitones | 1.12× |
| sadness | −2.0 semitones | 0.86× |
| frustration | +0.8 semitones | 1.04× |

---

## Project Structure

```
TTS-F5/
├── main.py                  # FastAPI app
├── emotion_blender.py       # Prosody adjustment (pitch/speed)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── assets/
│   └── emotion_refs/        # THAI-SER ref audio (สร้างโดย prepare script)
│       ├── neutral/
│       ├── happiness/
│       ├── sadness/
│       ├── anger/
│       └── frustration/
├── scripts/
│   └── prepare_emotion_refs.py  # ดึง THAI-SER emotion ref audio
└── thonburian-tts/          # ThonburianTTS repo (clone แยก)
```

---

## Credits

- **ThonburianTTS / F5-TTS**: [biodatlab](https://github.com/biodatlab/thonburian-tts)
- **THAI-SER Dataset**: [VISTEC-AI](https://github.com/vistec-AI/dataset-releases)
- **Whisper (Thai)**: [biodatlab/whisper-th-medium-combined](https://huggingface.co/biodatlab/whisper-th-medium-combined)
