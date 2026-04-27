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