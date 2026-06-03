FROM python:3.11-slim

# ติดตั้ง System dependencies สำหรับเสียง
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ติดตั้ง PyTorch แบบ CPU-only (เล็กกว่า GPU version มาก: ~200MB vs ~2GB)
# สำหรับ EC2 ที่ไม่มี GPU เช่น t3.small
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# คัดลอกและติดตั้ง Python dependencies ที่เหลือ
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมด (รวมถึงโฟลเดอร์ thonburian-tts)
COPY . .

# กำหนด Port ของ FastAPI
EXPOSE 5000

# รัน API
CMD ["python", "main.py"]
