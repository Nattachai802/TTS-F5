import os
import sys
import torch
import base64
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
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
    speed: Optional[float] = 1.0




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

    gen_text = gen_text.strip()
    if not gen_text.endswith(('.', '!', '?', '。')):
        gen_text += '.'

    temp_dir = tempfile.mkdtemp()

    # ===== หา user voice path =====
    voice_file = data.voice
    if voice_file:
        user_voice_path = voice_file if os.path.isabs(voice_file) else \
            os.path.join(current_dir, "thonburian-tts", "assets", voice_file)
    else:
        user_voice_path = os.path.join(current_dir, "thonburian-tts", "assets", "000000.wav")

    if not os.path.exists(user_voice_path):
        raise HTTPException(status_code=404, detail=f"Voice file not found: {user_voice_path}")

    ref_audio_path = user_voice_path

    # ===== ENHANCE AUDIO (Noise Reduction & EQ) =====
    enhanced_audio_path = os.path.join(temp_dir, "enhanced_ref.wav")
    try:
        print(f"Enhancing audio for: {ref_audio_path}")
        sr = 44100
        with AudioFile(ref_audio_path).resampled_to(sr) as f:
            audio = f.read(f.frames)

        reduced_noise = nr.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.75)

        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=80.0),                                        # ตัด sub-bass rumble
            NoiseGate(threshold_db=-35, ratio=2.5, release_ms=200),                         # gate แน่นขึ้น
            Compressor(threshold_db=-14, ratio=2.5, attack_ms=10.0, release_ms=150.0),
            LowShelfFilter(cutoff_frequency_hz=300.0, gain_db=-3.0, q=0.7),                 # cut low end แทน boost
            Gain(gain_db=2)
        ])

        effected = board(reduced_noise, sr)

        import numpy as np
        silence_sec = 2.0
        silence_samples = int(silence_sec * sr)
        if effected.ndim == 1:
            silence = np.zeros(silence_samples, dtype=np.float32)
            effected = np.concatenate([effected, silence])
        elif effected.ndim == 2:
            silence = np.zeros((effected.shape[0], silence_samples), dtype=np.float32)
            effected = np.concatenate([effected, silence], axis=1)

        with AudioFile(enhanced_audio_path, 'w', sr, effected.shape[0]) as f:
            f.write(effected)

        ref_audio_path = enhanced_audio_path
        print(f"Audio enhanced → {enhanced_audio_path}")
    except Exception as e:
        print(f"Audio enhancement failed: {str(e)}. Proceeding with original audio.")

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

    output_audio_path = os.path.join(temp_dir, "generated.wav")

    try:
        print(f"Generating TTS for text: '{gen_text}'")
        
        # Split text by [pause]
        text_segments = [s.strip() for s in gen_text.split("[pause]") if s.strip()]
        inference_speed = data.speed if data.speed is not None else 1.0
        
        if len(text_segments) <= 1:
            tts_pipeline(
                text=gen_text,
                ref_voice=ref_audio_path,
                ref_text=ref_text,
                output_file=output_audio_path,
                speed=inference_speed,
                check_duration=True
            )
        else:
            import numpy as np
            combined_audio = None
            sr = 24000
            
            for i, seg in enumerate(text_segments):
                seg_path = os.path.join(temp_dir, f"seg_{i}.wav")
                if not seg.endswith(('.', '!', '?', '。')):
                    seg += '.'
                
                # Prevent voice slowdown (0.3 speed override) for short segments
                if len(seg.encode("utf-8")) < 12:
                    seg = seg + "   "
                
                tts_pipeline(
                    text=seg,
                    ref_voice=ref_audio_path,
                    ref_text=ref_text,
                    output_file=seg_path,
                    speed=inference_speed,
                    check_duration=False
                )
                
                with AudioFile(seg_path).resampled_to(sr) as f:
                    audio_data = f.read(f.frames)
                
                if combined_audio is None:
                    combined_audio = audio_data
                else:
                    # Insert 300ms of silence between segments
                    silence_samples = int(0.3 * sr)
                    if audio_data.ndim == 1:
                        silence = np.zeros(silence_samples, dtype=np.float32)
                        combined_audio = np.concatenate([combined_audio, silence, audio_data])
                    else:
                        silence = np.zeros((audio_data.shape[0], silence_samples), dtype=np.float32)
                        combined_audio = np.concatenate([combined_audio, silence, audio_data], axis=1)
            
            with AudioFile(output_audio_path, 'w', sr, combined_audio.shape[0]) as f:
                f.write(combined_audio)
                
        post_process_output(output_audio_path)
        return FileResponse(output_audio_path, media_type='audio/wav', filename="generated.wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Inference failed: {str(e)}")

class UploadRequest(BaseModel):
    filename: str
    file_data: str

@app.get('/api/presets')
async def get_presets():
    presets = {}
    ref_dir = os.path.join(current_dir, "assets", "emotion_refs")
    if os.path.exists(ref_dir):
        for emotion in os.listdir(ref_dir):
            emo_path = os.path.join(ref_dir, emotion)
            if os.path.isdir(emo_path):
                wavs = [f for f in os.listdir(emo_path) if f.endswith('.wav')]
                presets[emotion] = [
                    {
                        "name": wav,
                        "path": os.path.abspath(os.path.join(emo_path, wav)),
                        "url": f"/assets/emotion_refs/{emotion}/{wav}"
                    }
                    for wav in sorted(wavs)
                ]
    return JSONResponse(content={
        "presets": presets,
        "default": {
            "name": "000000.wav",
            "path": os.path.abspath(os.path.join(current_dir, "thonburian-tts", "assets", "000000.wav")),
            "url": "/thonburian-assets/000000.wav"
        }
    })

@app.post('/api/upload-ref-audio')
async def upload_ref_audio(data: UploadRequest):
    try:
        header, encoded = data.file_data.split(",", 1) if "," in data.file_data else ("", data.file_data)
        file_bytes = base64.b64decode(encoded)
        
        temp_dir = os.path.join(current_dir, "temp_f5", "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        
        ext = os.path.splitext(data.filename)[1] or ".wav"
        unique_name = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join(temp_dir, unique_name)
        
        with open(save_path, "wb") as f:
            f.write(file_bytes)
            
        return JSONResponse(content={"path": save_path})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")

# Serve static UI files
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/assets", StaticFiles(directory=os.path.join(current_dir, "assets")), name="assets")
app.mount("/thonburian-assets", StaticFiles(directory=os.path.join(current_dir, "thonburian-tts", "assets")), name="thonburian-assets")

@app.get("/")
async def read_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return PlainTextResponse("UI files are not generated yet.", status_code=404)

if __name__ == '__main__':
    os.makedirs(os.path.join(current_dir, "temp_f5"), exist_ok=True)
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
