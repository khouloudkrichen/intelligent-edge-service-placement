import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ChatLogger:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_chat(
        self,
        *,
        user_message: str,
        detected_language: str,
        confidence: float,
        source: str,
        ollama_model: str | None,
        matched_question: str | None,
        category: str | None,
        risk: str | None,
        fallback_used: bool,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_message": user_message,
            "detected_language": detected_language,
            "confidence": confidence,
            "source": source,
            "ollama_model": ollama_model,
            "matched_question": matched_question,
            "category": category,
            "risk": risk,
            "fallback_used": fallback_used,
        }

        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
