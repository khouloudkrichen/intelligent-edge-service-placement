import json

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"


def generate_with_ollama(user_message: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_message,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        return f"Ollama fallback failed: {str(e)}"


def stream_with_ollama(user_message: str):
    """Yield Ollama text chunks as soon as they are generated."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_message,
        "stream": True,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.2,
            "num_predict": 180,
        },
    }

    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=(5, 60)) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                data = json.loads(line)
                chunk = data.get("response", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
    except Exception as exc:
        yield f"Ollama fallback failed: {exc}"
