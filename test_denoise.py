import os
import noisereduce as nr
from pedalboard.io import AudioFile
from pedalboard import Pedalboard, NoiseGate, Compressor, LowShelfFilter, Gain

def denoise_audio(input_file, output_file):
    print(f"🎙️ Loading audio: {input_file}")
    
    if not os.path.exists(input_file):
        print(f"❌ Error: File '{input_file}' not found!")
        return

    sr = 44100
    
    try:
        # 1. โหลดไฟล์เสียงและปรับ Sample Rate เป็น 44100Hz
        with AudioFile(input_file).resampled_to(sr) as f:
            audio = f.read(f.frames)

        print("🧹 1/2: Reducing background noise...")
        # 2. ลดเสียงรบกวน (ปรับให้ตัดแบบ 100% เลย จะได้เห็นความต่างชัดเจน)
        reduced_noise = nr.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=1.0)

        print("🎛️ 2/2: Applying studio effects (Gate, Compressor, EQ, Gain)...")
        board = Pedalboard([
            NoiseGate(threshold_db=-25, ratio=2.0, release_ms=150),
            Compressor(threshold_db=-20, ratio=6),
            LowShelfFilter(cutoff_frequency_hz=200.0, gain_db=3.0, q=1.0),
            Gain(gain_db=12)
        ])

        effected = board(reduced_noise, sr)

        print(f"💾 Saving enhanced audio to: {output_file}")
        # 4. บันทึกไฟล์เสียงใหม่
        with AudioFile(output_file, 'w', sr, effected.shape[0]) as f:
            f.write(effected)
            
        print("✅ Done! You can now listen to the enhanced audio.")

    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    input_path = "default_voice.wav"
    output_path = "default_voice_enhanced.wav"
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_full_path = os.path.join(current_dir, input_path)
    output_full_path = os.path.join(current_dir, output_path)
    
    denoise_audio(input_full_path, output_full_path)
