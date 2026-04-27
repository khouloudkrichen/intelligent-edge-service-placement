from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question")


class ChatResponse(BaseModel):
    answer: str
    category: str | None = None
    risk: str | None = None
    follow_up: str | None = None
    confidence: float
    language: str
    suggestions: list[str] = []
    source: str
    fallback_used: bool
    matched_question: str | None = None


class HealthResponse(BaseModel):
    status: str
    questions: int
    indexed_items: int
    rag_available: bool
    model: str
