import os

# Dataset
DATASET_FILE = "dataset_4.json"

# Whisper
WHISPER_MODEL = "base"
SAMPLE_RATE = 16000

# Server
SERVER_PORT = 8081

# Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"
OLLAMA_WARMUP_TIMEOUT_SECONDS = float(
    os.getenv("OLLAMA_WARMUP_TIMEOUT_SECONDS", "60")
)

# Redis
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)
CACHE_TTL_SECONDS = int(
    os.getenv("CACHE_TTL_SECONDS", "3600")
)

# Neo4j
NEO4J_URI = os.getenv(
    "NEO4J_URI",
    "neo4j://127.0.0.1:7687"
)
NEO4J_USER = os.getenv(
    "NEO4J_USER",
    "neo4j"
)
NEO4J_PASSWORD = os.getenv(
    "NEO4J_PASSWORD",
    ""
)
NEO4J_DB = os.getenv(
    "NEO4J_DB",
    "neo4j"
)