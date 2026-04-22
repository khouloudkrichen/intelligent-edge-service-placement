# ═══════════════════════════════════════════════════════
# services/transcription.py — Whisper + noisereduce + VAD
# ═══════════════════════════════════════════════════════

import tempfile, os, warnings
import numpy as np
import whisper
from scipy.io.wavfile import write as wav_write
from config import WHISPER_MODEL, SAMPLE_RATE

warnings.filterwarnings("ignore")

# ── Import optionnel noisereduce ─────────────────────────
try:
    import noisereduce as nr
    NOISEREDUCE_OK = True
except ImportError:
    NOISEREDUCE_OK = False
    print("⚠️  noisereduce non installé — pip install noisereduce")

# ── Import optionnel webrtcvad ───────────────────────────
try:
    import webrtcvad
    WEBRTCVAD_OK = True
except ImportError:
    try:
        import webrtcvad_wheels as webrtcvad
        WEBRTCVAD_OK = True
    except ImportError:
        WEBRTCVAD_OK = False
        print("⚠️  webrtcvad non installé — pip install webrtcvad-wheels")

# ── Chargement modèle Whisper ────────────────────────────
print(f"⏳ Chargement Whisper '{WHISPER_MODEL}'...")
_whisper_model = whisper.load_model(WHISPER_MODEL)
print("✅ Whisper prêt")


def remove_noise(audio: np.ndarray) -> np.ndarray:
    if not NOISEREDUCE_OK:
        return audio
    try:
        audio_f = audio.flatten().astype(np.float32)
        reduced = nr.reduce_noise(
            y=audio_f, sr=SAMPLE_RATE,
            y_noise=audio_f[:int(SAMPLE_RATE * 0.5)],
            prop_decrease=0.85, stationary=False,
        )
        return reduced.reshape(audio.shape)
    except Exception as e:
        print(f"   ⚠️  noisereduce error : {e}")
        return audio


def detect_voice_activity(audio: np.ndarray) -> np.ndarray:
    if not WEBRTCVAD_OK:
        return audio
    try:
        vad        = webrtcvad.Vad(2)
        audio_i16  = (audio.flatten() * 32767).astype(np.int16)
        frame_size = int(SAMPLE_RATE * 0.030)
        frames, voiced = [], []
        for i in range(0, len(audio_i16) - frame_size, frame_size):
            frame = audio_i16[i:i + frame_size]
            try:
                is_speech = vad.is_speech(frame.tobytes(), SAMPLE_RATE)
            except Exception:
                is_speech = True
            frames.append(frame)
            voiced.append(is_speech)
        keep = set()
        for i, v in enumerate(voiced):
            if v:
                for j in range(max(0, i - 3), min(len(voiced), i + 4)):
                    keep.add(j)
        if not keep:
            print("   ⚠️  VAD : aucune voix, audio original gardé")
            return audio
        audio_clean = (
            np.concatenate([frames[i] for i in sorted(keep)])
            .astype(np.float32) / 32767.0
        )
        print(f"   🎙️  VAD : {len(keep)/max(len(frames),1)*100:.0f}% de voix détectée")
        return audio_clean.reshape(-1, 1)
    except Exception as e:
        print(f"   ⚠️  webrtcvad error : {e}")
        return audio


def transcribe(audio_array: np.ndarray) -> tuple[str, str]:
    print("   🔊 Traitement audio...")
    audio = audio_array.astype(np.float32)
    if audio.max() > 1.0:
        audio /= 32768.0
    if NOISEREDUCE_OK:
        audio = remove_noise(audio)
        print("   ✅ noisereduce appliqué")
    if WEBRTCVAD_OK:
        audio = detect_voice_activity(audio)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    wav_write(tmp.name, SAMPLE_RATE, audio)
    result = _whisper_model.transcribe(
        tmp.name, fp16=False,
        initial_prompt=(
            "IBN technician commands: deploy AR service, voice conversion, "
            "anomaly analyzer, error detector, motor fault, belt replacement, "
            "vibration analysis, hydraulic leak, sensor calibration, "
            "AR guidance, predictive maintenance, detect fault."
        ),
        language="en",
        temperature=0.0,
    )
    try:
        os.remove(tmp.name)
    except Exception:
        pass

    text = result["text"].strip()
    lang = result.get("language", "en")

    if len(text.split()) < 2:
        print("   ⚠️  Transcription trop courte — ignorée")
        return "", lang
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii > len(text) * 0.3:
        print(f"   ⚠️  Transcription rejetée ({non_ascii} caractères non-ASCII)")
        return "", lang

    return text, lang