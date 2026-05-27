"""
prepare_emotion_refs.py
------------------------
ดึง THAI-SER จาก HuggingFace (streaming) → filter → save emotion ref files

Field names จริงที่ใช้:
  session_id   → filter studio (startswith "studio")
  majority_emo → emotion label (capitalized: Neutral, Happy, Sad, Angry, Frustrated)
  agreement    → float 0–1 (ใช้ ≥ 0.7)
  actor_gender → "Male" / "Female"
  mic_con      → AudioDecoder object (condenser mic, best quality in studio)
"""

import os
import sys
import soundfile as sf
import numpy as np

try:
    from datasets import load_dataset
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

try:
    import librosa
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "librosa"])
    import librosa

# ============================================================
# Config
# ============================================================
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "emotion_refs")
TARGET_SR = 22050
MIN_AGREEMENT = 0.7
MIN_DURATION_SEC = 3.0
MAX_DURATION_SEC = 9.0
TOP_N_PER_EMOTION_GENDER = 5   # เก็บ candidates N ตัว, อันดับ 1 = best

# Map THAI-SER label → folder name
EMOTION_MAP = {
    "neutral":    "neutral",
    "happy":      "happiness",
    "happiness":  "happiness",
    "sad":        "sadness",
    "sadness":    "sadness",
    "angry":      "anger",
    "anger":      "anger",
    "frustrated": "frustration",
    "frustration":"frustration",
}

GENDER_MAP = {
    "male":   "male",
    "female": "female",
}

# ============================================================

def decode_audio(decoder) -> tuple[np.ndarray, int]:
    """แปลง torchcodec AudioDecoder → numpy array (mono)"""
    samples = decoder.get_all_samples()
    data = samples.data  # torch.Tensor shape: (channels, n_samples)
    sr = int(samples.sample_rate)
    audio = data.numpy()
    if audio.ndim > 1:
        audio = audio.mean(axis=0)  # mono
    return audio.astype(np.float32), sr


def duration_score(duration_sec: float) -> float:
    if MIN_DURATION_SEC <= duration_sec <= MAX_DURATION_SEC:
        return 1.0
    return 0.4


def main():
    print("Loading THAI-SER in streaming mode...")
    ds = load_dataset("airesearch/thai-ser", split="train", streaming=True)

    # bucket: {emotion_folder: {gender_key: [(score, audio, sr, audio_id), ...]}}
    buckets: dict[str, dict[str, list]] = {}
    for emo in set(EMOTION_MAP.values()):
        buckets[emo] = {"male": [], "female": []}

    processed = 0
    saved_count = 0

    for item in ds:
        # --- filter studio ---
        if not str(item.get("session_id", "")).lower().startswith("studio"):
            continue

        # --- filter agreement ---
        agreement = float(item.get("agreement", 0))
        if agreement < MIN_AGREEMENT:
            continue

        # --- map emotion ---
        raw_emo = str(item.get("majority_emo", "")).lower().strip()
        emotion_folder = EMOTION_MAP.get(raw_emo)
        if emotion_folder is None:
            continue

        # --- map gender ---
        raw_gender = str(item.get("actor_gender", "")).lower().strip()
        gender_key = GENDER_MAP.get(raw_gender)
        if gender_key is None:
            continue

        # --- ถ้า bucket เต็มแล้ว skip (ประหยัด bandwidth) ---
        bucket = buckets[emotion_folder][gender_key]
        if len(bucket) >= TOP_N_PER_EMOTION_GENDER:
            continue

        # --- decode audio ---
        decoder = item.get("mic_con")
        if decoder is None:
            decoder = item.get("mic_clip")
        if decoder is None:
            continue

        try:
            audio, sr = decode_audio(decoder)
        except Exception as e:
            print(f"  [SKIP] decode error {item.get('audio_id')}: {e}")
            continue

        duration = len(audio) / sr

        # --- filter duration ---
        if duration < MIN_DURATION_SEC or duration > MAX_DURATION_SEC:
            continue

        # --- resample ---
        if sr != TARGET_SR:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR)

        score = agreement * duration_score(duration)
        bucket.append((score, audio, TARGET_SR, item.get("audio_id", "unknown"), agreement, duration))
        saved_count += 1
        print(f"  ✔ [{emotion_folder}/{gender_key}] {item.get('audio_id')} | agree={agreement:.2f} dur={duration:.1f}s score={score:.3f}")

        processed += 1

        # หยุดเมื่อ bucket ทุกช่องเต็ม
        all_full = all(
            len(buckets[e][g]) >= TOP_N_PER_EMOTION_GENDER
            for e in buckets for g in buckets[e]
        )
        if all_full:
            print("\nAll buckets full — stopping early.")
            break

    # ============================================================
    # Save files
    # ============================================================
    print("\nSaving files...")
    for emotion_folder, genders in buckets.items():
        for gender_key, items in genders.items():
            if not items:
                print(f"  [WARNING] No candidates for {emotion_folder}/{gender_key}")
                continue

            # sort by score desc
            items.sort(key=lambda x: x[0], reverse=True)

            # สร้าง dir
            cand_dir = os.path.join(OUTPUT_DIR, emotion_folder, "candidates")
            os.makedirs(cand_dir, exist_ok=True)

            for rank, (score, audio, sr, audio_id, agreement, duration) in enumerate(items):
                cand_path = os.path.join(cand_dir, f"{gender_key}_{rank+1}.wav")
                sf.write(cand_path, audio, sr)
                print(f"  saved: {cand_path}  (agree={agreement:.2f} dur={duration:.1f}s score={score:.3f})")

            # best = rank 0
            best_audio = items[0][1]
            best_sr = items[0][2]
            best_path = os.path.join(OUTPUT_DIR, emotion_folder, f"{gender_key}_best.wav")
            sf.write(best_path, best_audio, best_sr)
            print(f"  ★ best: {best_path}")

    print(f"\nDone. Processed {processed} items, collected {saved_count} candidates.")
    print(f"Output dir: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
