"""
emotion_blender.py
-------------------
ปรับ prosody ของ user audio ตาม emotion โดยใช้ librosa
เป้าหมาย: คงเสียง (timbre) ของ user ไว้ แต่เพิ่ม intonation pattern ของอารมณ์

เสียงที่ได้จะถูกส่งเป็น ref_voice เข้า F5-TTS → F5 clone timbre จาก user
"""

import numpy as np
import librosa
import soundfile as sf
from pathlib import Path


class EmotionBlender:
    """
    ปรับ pitch + speed ของ user audio ตาม emotion + strength
    strength=0.0 → ไม่เปลี่ยน, strength=1.0 → ปรับเต็มที่ตาม preset
    """

    # pitch shift (semitones) ต่ออารมณ์ที่ strength=1.0
    EMOTION_PITCH: dict[str, float] = {
        "neutral":     0.0,
        "happiness":  +2.5,   # เสียงสูงขึ้น — ร่าเริง
        "anger":      +2.0,   # เสียงสูง + ตึง
        "sadness":    -2.0,   # เสียงต่ำลง — อ้อยอิ่ง
        "frustration": +0.8,  # เล็กน้อย — อึดอัด
    }

    # time stretch rate ต่ออารมณ์ที่ strength=1.0
    # > 1.0 = เร็วขึ้น, < 1.0 = ช้าลง
    EMOTION_SPEED: dict[str, float] = {
        "neutral":     1.00,
        "happiness":   1.08,
        "anger":       1.12,
        "sadness":     0.86,
        "frustration": 1.04,
    }

    TARGET_SR = 22050

    def __init__(self):
        pass

    def blend(
        self,
        user_audio_path: str,
        emotion: str,
        strength: float = 0.5,
    ) -> tuple[np.ndarray, int]:
        """
        รับ user audio path + emotion + strength
        คืน (audio_array, sample_rate) ที่ถูก adjust prosody แล้ว

        Args:
            user_audio_path: path ไปยังไฟล์เสียงของ user
            emotion: ชื่ออารมณ์ (neutral/happiness/sadness/anger/frustration)
            strength: ความแรงของ effect (0.0–1.0)
        """
        emotion = emotion.lower().strip()
        if emotion not in self.EMOTION_PITCH:
            print(f"[EmotionBlender] Unknown emotion '{emotion}', using neutral")
            emotion = "neutral"

        strength = max(0.0, min(1.0, strength))

        # โหลด user audio
        audio, sr = librosa.load(user_audio_path, sr=self.TARGET_SR, mono=True)

        # --- Step 1: Pitch Shift ---
        n_steps = self.EMOTION_PITCH[emotion] * strength
        if abs(n_steps) > 0.05:
            audio = librosa.effects.pitch_shift(
                audio,
                sr=self.TARGET_SR,
                n_steps=n_steps,
                bins_per_octave=24,   # ละเอียดขึ้น → artifact น้อยลง
            )
            print(f"[EmotionBlender] pitch_shift {n_steps:+.2f} semitones")

        # --- Step 2: Time Stretch ---
        base_rate = self.EMOTION_SPEED[emotion]
        rate = 1.0 + (base_rate - 1.0) * strength
        if abs(rate - 1.0) > 0.01:
            audio = librosa.effects.time_stretch(audio, rate=rate)
            print(f"[EmotionBlender] time_stretch rate={rate:.3f}")

        # --- Step 3: Normalize ---
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.9

        return audio.astype(np.float32), self.TARGET_SR

    def save(self, audio: np.ndarray, sr: int, output_path: str) -> None:
        sf.write(output_path, audio, sr)
        print(f"[EmotionBlender] saved → {output_path}")
