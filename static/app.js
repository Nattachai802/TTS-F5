// Global Application State
const state = {
    presets: {},
    defaultPreset: null,
    currentTab: 'presets', // presets, upload
    selectedPresetPath: '',
    uploadedFilePath: '',
    uploadedFileName: '',
    outputAudioBlobUrl: null,
    generationInProgress: false
};

// Audio Visualizer State
let audioCtx = null;
let analyser = null;
let source = null;
let animationFrameId = null;
let isPlayingOutput = false;

// DOM Elements
const elements = {
    ttsText: document.getElementById('tts-text'),
    charCount: document.getElementById('char-count'),
    presetEmotion: document.getElementById('preset-emotion'),
    presetVoice: document.getElementById('preset-voice'),
    presetAudioPlayer: document.getElementById('preset-audio-player'),
    
    fileInput: document.getElementById('file-input'),
    dropzone: document.getElementById('dropzone'),
    fileInfoContainer: document.getElementById('file-info-container'),
    uploadedFileNameTxt: document.getElementById('uploaded-file-name'),
    uploadedFileSizeTxt: document.getElementById('uploaded-file-size'),
    uploadAudioPlayer: document.getElementById('upload-audio-player'),
    
    autoTranscribe: document.getElementById('auto-transcribe'),
    refTextGroup: document.getElementById('ref-text-group'),
    refText: document.getElementById('ref-text'),
    
    generateVoiceBtn: document.getElementById('generate-voice-btn'),
    progressContainer: document.getElementById('progress-container'),
    progressStatusTitle: document.getElementById('progress-status-title'),
    progressStatusSub: document.getElementById('progress-status-sub'),
    emptyStateView: document.getElementById('empty-state-view'),
    resultCardView: document.getElementById('result-card-view'),
    
    outputAudioPlayer: document.getElementById('output-audio-player'),
    playerPlayBtn: document.getElementById('player-play-btn'),
    playIcon: document.getElementById('play-icon'),
    playerProgressBar: document.getElementById('player-progress-bar'),
    playerTimeRail: document.getElementById('player-time-rail'),
    currentTimeTxt: document.getElementById('current-time'),
    durationTimeTxt: document.getElementById('duration-time'),
    downloadWavBtn: document.getElementById('download-wav-btn'),
    
    waveformVisualizer: document.getElementById('waveform-visualizer'),
    visualizerFallback: document.getElementById('visualizer-fallback'),
    
    // Steps
    stepEnhance: document.getElementById('step-enhance'),
    stepWhisper: document.getElementById('step-whisper'),
    stepF5: document.getElementById('step-f5')
};

// Initialize Application
window.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    // Character counter listener
    elements.ttsText.addEventListener('input', () => {
        elements.charCount.textContent = elements.ttsText.value.length;
    });

    // Drag and Drop listeners
    setupDragAndDrop();

    // Load presets from server
    await fetchPresets();

    // Set custom visualizer size
    resizeVisualizerCanvas();
    window.addEventListener('resize', resizeVisualizerCanvas);
}

// ----------------------------------------------------
// Core Routing & Tab Logic
// ----------------------------------------------------
function switchTab(tabName) {
    if (state.generationInProgress) return;
    
    state.currentTab = tabName;
    
    // Update button styling
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tabName}-btn`).classList.add('active');
    
    // Update panel visibility
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    document.getElementById(`panel-${tabName}`).classList.add('active');
}

function toggleRefTextInput() {
    if (elements.autoTranscribe.checked) {
        elements.refTextGroup.style.display = 'none';
    } else {
        elements.refTextGroup.style.display = 'flex';
    }
}

// ----------------------------------------------------
// Presets Logic
// ----------------------------------------------------
async function fetchPresets() {
    try {
        const response = await fetch('/api/presets');
        if (!response.ok) throw new Error('Failed to load presets');
        const data = await response.json();
        
        state.presets = data.presets;
        state.defaultPreset = data.default;
        
        // Populate emotion select first
        loadPresetGenderOptions();
    } catch (e) {
        console.error('Error fetching presets:', e);
        showNotification('Failed to load voice presets from backend.', 'error');
    }
}

function loadPresetGenderOptions() {
    const emotion = elements.presetEmotion.value;
    const voiceSelect = elements.presetVoice;
    voiceSelect.innerHTML = '';
    
    if (state.presets[emotion] && state.presets[emotion].length > 0) {
        state.presets[emotion].forEach((preset, index) => {
            const opt = document.createElement('option');
            opt.value = index;
            // Clean up name display (e.g. female_best.wav -> Female Best)
            const readableName = preset.name
                .replace('_best.wav', '')
                .replace('.wav', '')
                .replace(/^\w/, c => c.toUpperCase());
            opt.textContent = readableName;
            voiceSelect.appendChild(opt);
        });
        updatePresetPreview();
    } else {
        const opt = document.createElement('option');
        opt.value = "";
        opt.textContent = "No voices found";
        voiceSelect.appendChild(opt);
        elements.presetAudioPlayer.src = '';
        state.selectedPresetPath = '';
    }
}

function updatePresetPreview() {
    const emotion = elements.presetEmotion.value;
    const index = elements.presetVoice.value;
    
    if (index !== "" && state.presets[emotion] && state.presets[emotion][index]) {
        const preset = state.presets[emotion][index];
        elements.presetAudioPlayer.src = preset.url;
        state.selectedPresetPath = preset.path;
    } else {
        elements.presetAudioPlayer.src = '';
        state.selectedPresetPath = '';
    }
}

// ----------------------------------------------------
// File Upload Logic
// ----------------------------------------------------
function triggerFileInput() {
    if (state.generationInProgress) return;
    elements.fileInput.click();
}

function setupDragAndDrop() {
    const dropzone = elements.dropzone;
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (state.generationInProgress) return;
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        if (state.generationInProgress) return;
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            processSelectedFile(files[0]);
        }
    });
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        processSelectedFile(files[0]);
    }
}

function processSelectedFile(file) {
    if (!file.name.endsWith('.wav')) {
        showNotification('Please upload a .wav audio file.', 'error');
        return;
    }

    // Display file name and size
    elements.uploadedFileNameTxt.textContent = file.name;
    elements.uploadedFileSizeTxt.textContent = formatBytes(file.size);
    elements.fileInfoContainer.style.style = 'flex';
    elements.fileInfoContainer.style.display = 'flex';
    elements.dropzone.style.display = 'none';
    
    // Create local object URL for preview
    elements.uploadAudioPlayer.src = URL.createObjectURL(file);
    
    // Convert to base64 and upload
    const reader = new FileReader();
    reader.onload = async (e) => {
        const base64Data = e.target.result;
        await uploadReferenceAudio(file.name, base64Data);
    };
    reader.readAsDataURL(file);
}

async function uploadReferenceAudio(filename, base64Data) {
    try {
        const response = await fetch('/api/upload-ref-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                file_data: base64Data
            })
        });

        if (!response.ok) throw new Error('Upload failed');
        const data = await response.json();
        state.uploadedFilePath = data.path;
        state.uploadedFileName = filename;
        showNotification('Reference voice uploaded successfully.');
    } catch (e) {
        console.error('Error uploading voice:', e);
        showNotification('Failed to upload audio to server.', 'error');
        clearUploadedFile();
    }
}

function clearUploadedFile() {
    state.uploadedFilePath = '';
    state.uploadedFileName = '';
    elements.fileInput.value = '';
    elements.uploadAudioPlayer.src = '';
    elements.fileInfoContainer.style.display = 'none';
    elements.dropzone.style.display = 'flex';
}



// ----------------------------------------------------
// Generation Logic
// ----------------------------------------------------
async function startGeneration() {
    if (state.generationInProgress) return;

    // Check script
    const textVal = elements.ttsText.value.trim();
    if (!textVal) {
        showNotification('Please enter a target script text to generate.', 'error');
        return;
    }

    // Get voice path
    let voicePath = '';
    if (state.currentTab === 'presets') {
        voicePath = state.selectedPresetPath;
    } else if (state.currentTab === 'upload') {
        voicePath = state.uploadedFilePath;
    }

    if (!voicePath) {
        showNotification('Please configure or upload a reference voice first.', 'error');
        return;
    }

    // Check ref_text if manual
    let referenceText = null;
    if (!elements.autoTranscribe.checked) {
        referenceText = elements.refText.value.trim();
        if (!referenceText) {
            showNotification('Please enter the manual reference script or enable Auto-transcribe.', 'error');
            return;
        }
    }

    // Transition UI to Generating State
    state.generationInProgress = true;
    elements.generateVoiceBtn.disabled = true;
    elements.generateVoiceBtn.classList.add('loading');
    elements.generateVoiceBtn.querySelector('.btn-text').textContent = 'Generating...';
    
    // Toggle containers
    elements.emptyStateView.style.display = 'none';
    elements.resultCardView.style.display = 'none';
    elements.progressContainer.style.display = 'flex';
    
    // Stop playing old audio if any
    resetOutputAudio();

    // Step Progress Handling
    setStepStatus('step-enhance', 'active');
    setStepStatus('step-whisper', 'pending');
    setStepStatus('step-f5', 'pending');
    elements.progressStatusTitle.textContent = "Enhancing Audio Reference...";
    elements.progressStatusSub.textContent = "Removing background noise & adjusting room EQ.";

    // Start checking time
    const startTime = Date.now();
    
    // Simulated steps changes since we don't have SSE, but we can update steps based on typical durations
    const stepTimer1 = setTimeout(() => {
        setStepStatus('step-enhance', 'completed');
        setStepStatus('step-whisper', 'active');
        elements.progressStatusTitle.textContent = elements.autoTranscribe.checked 
            ? "Transcribing voice using Whisper..." 
            : "Processing reference script...";
        elements.progressStatusSub.textContent = "Aligning characters and phonemes.";
    }, 4500);

    const stepTimer2 = setTimeout(() => {
        setStepStatus('step-whisper', 'completed');
        setStepStatus('step-f5', 'active');
        elements.progressStatusTitle.textContent = "Running F5-TTS Synthesis Inference...";
        elements.progressStatusSub.textContent = "Solving flow-matching ODE steps (Euler 64).";
    }, 11000);

    try {
        const speedVal = parseFloat(document.getElementById('speech-speed').value);
        const payload = {
            text: textVal,
            voice: voicePath,
            ref_text: referenceText,
            speed: speedVal
        };

        const response = await fetch('/generate-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // Clear timers
        clearTimeout(stepTimer1);
        clearTimeout(stepTimer2);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({ detail: 'Unknown error occurred during inference.' }));
            throw new Error(errData.detail || 'Synthesis failed');
        }

        // Complete all steps in UI
        setStepStatus('step-enhance', 'completed');
        setStepStatus('step-whisper', 'completed');
        setStepStatus('step-f5', 'completed');
        
        elements.progressStatusTitle.textContent = "Finalizing output audio...";

        // Read response audio binary blob
        const audioBlob = await response.blob();
        
        // Save to state URL
        state.outputAudioBlobUrl = URL.createObjectURL(audioBlob);
        
        // Show result
        elements.outputAudioPlayer.src = state.outputAudioBlobUrl;
        elements.downloadWavBtn.href = state.outputAudioBlobUrl;
        
        // Display result container
        elements.progressContainer.style.display = 'none';
        elements.resultCardView.style.display = 'block';
        showNotification('Speech synthesized successfully!');
    } catch (e) {
        console.error('TTS Generation error:', e);
        clearTimeout(stepTimer1);
        clearTimeout(stepTimer2);
        
        elements.progressContainer.style.display = 'none';
        elements.emptyStateView.style.display = 'flex';
        showNotification(`Generation Failed: ${e.message}`, 'error');
    } finally {
        state.generationInProgress = false;
        elements.generateVoiceBtn.disabled = false;
        elements.generateVoiceBtn.classList.remove('loading');
        elements.generateVoiceBtn.querySelector('.btn-text').textContent = 'Generate Speech';
    }
}

function setStepStatus(stepId, status) {
    const el = document.getElementById(stepId);
    if (!el) return;
    
    el.classList.remove('active', 'completed');
    if (status === 'active') {
        el.classList.add('active');
    } else if (status === 'completed') {
        el.classList.add('completed');
    }
}

// ----------------------------------------------------
// Custom Audio Player Control Panel
// ----------------------------------------------------
function toggleOutputAudio() {
    const player = elements.outputAudioPlayer;
    if (!player.src) return;

    if (player.paused) {
        player.play();
    } else {
        player.pause();
    }
}

function onAudioPlay() {
    isPlayingOutput = true;
    elements.playIcon.className = 'fa-solid fa-pause';
    elements.visualizerFallback.style.opacity = '0';
    elements.visualizerFallback.style.pointerEvents = 'none';
    
    // Initialize Web Audio API Analyser
    initVisualizer(elements.outputAudioPlayer, elements.waveformVisualizer);
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    
    // Trigger visualizer loop
    drawVisualizer(elements.waveformVisualizer);
    
    // Start track bar updater
    updateProgressBar();
}

function onAudioPause() {
    isPlayingOutput = false;
    elements.playIcon.className = 'fa-solid fa-play';
}

function onAudioEnded() {
    isPlayingOutput = false;
    elements.playIcon.className = 'fa-solid fa-play';
    elements.playerProgressBar.style.width = '0%';
    elements.currentTimeTxt.textContent = '00:00';
    
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
}

function updateProgressBar() {
    const player = elements.outputAudioPlayer;
    if (!isPlayingOutput) return;

    const current = player.currentTime;
    const duration = player.duration || 0;
    
    if (duration > 0) {
        const percentage = (current / duration) * 100;
        elements.playerProgressBar.style.width = `${percentage}%`;
        elements.currentTimeTxt.textContent = formatTime(current);
        elements.durationTimeTxt.textContent = formatTime(duration);
    }
    
    requestAnimationFrame(updateProgressBar);
}

function seekAudio(e) {
    const player = elements.outputAudioPlayer;
    if (!player.src || !player.duration) return;

    const rect = elements.playerTimeRail.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;
    
    const percentage = clickX / width;
    player.currentTime = percentage * player.duration;
    
    // Force immediate progress bar update
    elements.playerProgressBar.style.width = `${percentage * 100}%`;
    elements.currentTimeTxt.textContent = formatTime(player.currentTime);
}

function resetOutputAudio() {
    const player = elements.outputAudioPlayer;
    player.pause();
    player.src = '';
    elements.playerProgressBar.style.width = '0%';
    elements.currentTimeTxt.textContent = '00:00';
    elements.durationTimeTxt.textContent = '00:00';
    onAudioEnded();
    
    if (state.outputAudioBlobUrl) {
        URL.revokeObjectURL(state.outputAudioBlobUrl);
        state.outputAudioBlobUrl = null;
    }
}

// ----------------------------------------------------
// Web Audio API Canvas Visualizer
// ----------------------------------------------------
function initVisualizer(audioElement, canvasElement) {
    if (audioCtx) return;
    
    try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        
        source = audioCtx.createMediaElementSource(audioElement);
        source.connect(analyser);
        analyser.connect(audioCtx.destination);
    } catch (e) {
        console.warn("Could not init AudioContext visualizer:", e);
    }
}

function drawVisualizer(canvasElement) {
    if (!analyser) return;
    
    const ctx = canvasElement.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    const width = canvasElement.width;
    const height = canvasElement.height;
    
    function draw() {
        if (!isPlayingOutput) return;
        animationFrameId = requestAnimationFrame(draw);
        
        analyser.getByteFrequencyData(dataArray);
        
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);
        
        const barWidth = (width / bufferLength) * 1.5;
        let barHeight;
        let x = 0;
        
        for(let i = 0; i < bufferLength; i++) {
            barHeight = (dataArray[i] / 255) * height * 0.85;
            
            // Generate glowing amber to yellow gradient bar
            const grad = ctx.createLinearGradient(0, height, 0, height - barHeight);
            grad.addColorStop(0, '#b45309');
            grad.addColorStop(0.5, '#d97706');
            grad.addColorStop(1, '#f59e0b');
            
            ctx.fillStyle = grad;
            ctx.fillRect(x, height - barHeight, barWidth, barHeight);
            
            x += barWidth + 3;
        }
    }
    
    draw();
}

function resizeVisualizerCanvas() {
    const canvas = elements.waveformVisualizer;
    const wrapper = canvas.parentElement;
    canvas.width = wrapper.clientWidth * window.devicePixelRatio;
    canvas.height = wrapper.clientHeight * window.devicePixelRatio;
    
    // Scale context back to normal pixels
    const ctx = canvas.getContext('2d');
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    
    // Redraw blank screen
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, wrapper.clientWidth, wrapper.clientHeight);
}

// ----------------------------------------------------
// Utility Functions
// ----------------------------------------------------
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatTime(secs) {
    const m = String(Math.floor(secs / 60)).padStart(2, '0');
    const s = String(Math.floor(secs % 60)).padStart(2, '0');
    return `${m}:${s}`;
}

// Premium Notification Toast system
function showNotification(message, type = 'success') {
    const existing = document.querySelector('.toast-container');
    if (existing) existing.remove();
    
    const container = document.createElement('div');
    container.className = `toast-container ${type}`;
    
    const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
    
    container.innerHTML = `
        <i class="fa-solid ${icon} toast-icon"></i>
        <span class="toast-message">${message}</span>
    `;
    
    document.body.appendChild(container);
    
    // CSS inline styling for premium Toast notification
    Object.assign(container.style, {
        position: 'fixed',
        bottom: '2rem',
        right: '2rem',
        background: type === 'success' ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)',
        color: '#ffffff',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '0.9rem 1.5rem',
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'center',
        gap: '0.8rem',
        zIndex: '1000',
        fontFamily: "'Inter', sans-serif",
        fontSize: '0.85rem',
        fontWeight: '500',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.25)',
        animation: 'slideInUp 0.35s cubic-bezier(0.4, 0, 0.2, 1) forwards',
        backdropFilter: 'blur(8px)'
    });
    
    // Add animations
    const styleSheet = document.createElement("style");
    styleSheet.innerText = `
        @keyframes slideInUp {
            from { transform: translateY(100px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
    `;
    document.head.appendChild(styleSheet);
    
    setTimeout(() => {
        container.style.animation = 'fadeOut 0.4s forwards';
        setTimeout(() => container.remove(), 400);
    }, 4000);
}
