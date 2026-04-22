# ═══════════════════════════════════════════════════════
# services/tts.py — Text-To-Speech (PowerShell)
# ═══════════════════════════════════════════════════════

import subprocess


def speak(text: str, lang: str = "en"):
    """Prononce le texte via PowerShell System.Speech (Windows)."""
    try:
        short = text[:300].replace('"', '').replace("'", "")
        subprocess.Popen(
            ['PowerShell', '-Command',
             f'Add-Type -AssemblyName System.Speech; '
             f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
             f'$s.Speak("{short}")'],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception as e:
        print(f"   ⚠️  TTS error : {e}")