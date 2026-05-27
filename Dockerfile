FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime

# ติดตั้ง System dependencies สำหรับเสียง
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# คัดลอกและติดตั้ง Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมด (รวมถึงโฟลเดอร์ thonburian-tts)
COPY . .

# กำหนด Port ของ FastAPI
EXPOSE 5000

# รัน API
CMD ["python", "main.py"]
