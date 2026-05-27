import os
import sys
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
from transformers import pipeline
from pedalboard.io import AudioFile
from pedalboard import Pedalboard, NoiseGate, Compressor, LowShelfFilter, Gain, HighpassFilter, HighShelfFilter
import noisereduce as nr

current_dir = os.path.dirname(os.path.abspath(__file__))
thonburian_path = os.path.join(current_dir, "thonburian-tts")
if thonburian_path not in sys.path:
    sys.path.append(thonburian_path)

try:
    from flowtts.inference import FlowTTSPipeline, ModelConfig, AudioConfig
except ImportError as e:
    print("Failed to import FlowTTSPipeline. Please make sure 'thonburian-tts' is cloned.")
    print("Run: git clone https://github.com/biodatlab/thonburian-tts.git")
    raise e

app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    ref_text: Optional[str] = None

# Constants
CHECKPOINT = "hf://biodatlab/ThonburianTTS/megaF5/mega_f5_last.safetensors"
VOCAB = "hf://biodatlab/ThonburianTTS/megaF5/mega_vocab.txt"

if torch.backends.mps.is_available() and torch.backends.mps.is_built():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

print(f"Using device: {device}")

print("Loading Whisper model for transcription...")
whisper_pipe = pipeline(
    task="automatic-speech-recognition",
    model="biodatlab/whisper-th-medium-combined",
    chunk_length_s=30,
    device=device,
)
whisper_pipe.model.config.forced_decoder_ids = whisper_pipe.tokenizer.get_decoder_prompt_ids(
    language="th",
    task="transcribe"
)

print("Loading FlowTTSPipeline...")
model_config = ModelConfig(
    language="th",
    model_type="F5",
    checkpoint=CHECKPOINT,
    vocab_file=VOCAB,
    ode_method="euler",
    use_ema=True,
    vocoder="vocos",
    device=device
)

audio_config = AudioConfig(
    silence_threshold=-45,
    max_audio_length=20000,
    cfg_strength=1.5,
    nfe_step=64,
    target_rms=0.12,
    cross_fade_duration=0.10,
    speed=0.92,
    min_silence_len=500,
    keep_silence=200,
    seek_step=10
)

tts_pipeline = FlowTTSPipeline(
    model_config=model_config,
    audio_config=audio_config,
    temp_dir=os.path.join(current_dir, "temp_f5")
)
print("Models loaded successfully!")

def post_process_output(audio_path: str) -> None:
    """
    Post-process TTS output audio in-place.
    เป้าหมาย: normalize + warm EQ เบาๆ โดยไม่กระทบ intonation
    """
    target_sr = 24000
    import numpy as np

    with AudioFile(audio_path).resampled_to(target_sr) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=80.0),
        LowShelfFilter(cutoff_frequency_hz=250.0, gain_db=1.5, q=0.7),
        HighShelfFilter(cutoff_frequency_hz=5000.0, gain_db=1.8, q=0.8),
        Compressor(threshold_db=-18.0, ratio=1.6, attack_ms=20.0, release_ms=300.0)
    ])

    processed = board(audio, sr)

    peak = np.max(np.abs(processed))
    if peak > 0:
        target_peak = 10 ** (-1.0 / 20)
        processed = processed * (target_peak / peak)

    with AudioFile(audio_path, 'w', sr, processed.shape[0]) as f:
        f.write(processed)

@app.post('/generate-tts')
async def generate_tts(data: TTSRequest):
    gen_text = data.text
    
    if not gen_text:
        raise HTTPException(status_code=400, detail="Missing 'text' parameter in JSON body")

    voice_file = data.voice
    
    if voice_file:
        if os.path.isabs(voice_file):
            ref_audio_path = voice_file
        else:
            ref_audio_path = os.path.join(current_dir, "thonburian-tts", "assets", voice_file)
    else:
        ref_audio_path = os.path.join(current_dir, "thonburian-tts", "assets", "000000.wav")
    
    if not os.path.exists(ref_audio_path):
        raise HTTPException(status_code=404, detail=f"Voice file not found: {ref_audio_path}")

    # ===== ENHANCE AUDIO =====
    temp_dir = tempfile.mkdtemp()
    enhanced_audio_path = os.path.join(temp_dir, "enhanced_ref.wav")
    
    try:
        print(f"Enhancing audio for: {ref_audio_path}")
        sr = 44100
        with AudioFile(ref_audio_path).resampled_to(sr) as f:
            audio = f.read(f.frames)

        reduced_noise = nr.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.3)

        board = Pedalboard([
            NoiseGate(threshold_db=-40, ratio=1.2, release_ms=400),
            Compressor(threshold_db=-12, ratio=2),
            LowShelfFilter(cutoff_frequency_hz=300.0, gain_db=1.0, q=0.7),
            Gain(gain_db=3)
        ])

        effected = board(reduced_noise, sr)

        with AudioFile(enhanced_audio_path, 'w', sr, effected.shape[0]) as f:
            f.write(effected)
            
        ref_audio_path = enhanced_audio_path
        print(f"Audio enhanced and saved to {enhanced_audio_path}")
    except Exception as e:
        print(f"Audio enhancement failed: {str(e)}. Proceeding with original audio.")
    # =========================

    ref_text = data.ref_text

    if not ref_text:
        try:
            print("Transcribing reference audio...")
            import numpy as np
            with AudioFile(ref_audio_path).resampled_to(16000) as f:
                audio_data = f.read(f.frames)
                if audio_data.ndim > 1:
                    audio_data = np.mean(audio_data, axis=0) if audio_data.shape[0] > 1 else audio_data[0]
            output = whisper_pipe({"sampling_rate": 16000, "raw": audio_data})
            ref_text = output["text"]
            print(f"Transcribed ref_text: {ref_text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
            
    if not ref_text:
        raise HTTPException(status_code=400, detail="Could not transcribe reference audio")

    temp_dir = tempfile.mkdtemp()
    output_audio_path = os.path.join(temp_dir, "generated.wav")

    try:
        print(f"Generating TTS for text: '{gen_text}'")
        tts_pipeline(
            text=gen_text,
            ref_voice=ref_audio_path,
            ref_text=ref_text,
            output_file=output_audio_path,
            speed=1.0,
            check_duration=True
        )
        post_process_output(output_audio_path)
        return FileResponse(output_audio_path, media_type='audio/wav', filename="generated.wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Inference failed: {str(e)}")

if __name__ == '__main__':
    os.makedirs(os.path.join(current_dir, "temp_f5"), exist_ok=True)
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
