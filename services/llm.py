# ═══════════════════════════════════════════════════════
# services/llm.py — Appel LLM Ollama centralisé
# ═══════════════════════════════════════════════════════

import requests as http_requests
from config import OLLAMA_URL, OLLAMA_MODEL


def ollama_call(
    prompt: str,
    max_tokens: int = 15,
    temperature: float = 0.0,
    timeout: float = 30,
) -> str:
    """Envoie un prompt à Ollama et retourne la réponse texte."""
    resp = http_requests.post(
        OLLAMA_URL,
        json={
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=timeout,
    )
    if resp.status_code == 200:
        return resp.json().get("response", "").strip()
    return ""
