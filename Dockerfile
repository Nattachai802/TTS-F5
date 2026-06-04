FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# ติดตั้ง Python + System dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    curl \
    ffmpeg \
    libsndfile1 \
    libatomic1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

WORKDIR /app

# ติดตั้ง PyTorch แบบ CUDA 12.8
RUN python3.11 -m pip install --no-cache-dir --timeout 1000 --retries 20 torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128

# ติดตั้ง torchcodec (transformers/Whisper ใช้ decode เสียง) — แยก layer ไม่ให้ torch โดนโหลดใหม่
RUN python3.11 -m pip install --no-cache-dir --timeout 1000 --retries 20 torchcodec \
    --index-url https://download.pytorch.org/whl/cu128

# คัดลอกและติดตั้ง Python dependencies ที่เหลือ
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

# คัดลอกโค้ดทั้งหมด (รวมถึงโฟลเดอร์ thonburian-tts)
COPY . .

# กำหนด Port ของ FastAPI
EXPOSE 5000

# รัน API
CMD ["python", "main.py"]
