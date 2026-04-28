# core/detection.py - generic dataset-driven intention detection

import hashlib
import json
import os
import re
from collections import OrderedDict
from difflib import SequenceMatcher

from data.dataset import INTENTIONS_BY_ID, SERVICES_BY_ID, intentions
from services.llm import ollama_call

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - fallback for minimal environments
    fuzz = None


SEMANTIC_WEIGHT = 0.50
FUZZY_WEIGHT = 0.30
KEYWORD_WEIGHT = 0.20
DETECTION_THRESHOLD = 0.55
DETECTION_CACHE_MAX = 128
EMBED_DIM = 384
OLLAMA_MAX_TOKENS = 350

STOP_WORDS = {
    "a", "an", "and", "are", "be", "before", "do", "for", "from", "give", "how",
    "i", "in", "is", "it", "me", "need", "of", "on", "or", "please", "show",
    "the", "to", "use", "with", "you",
    "je", "la", "le", "les", "un", "une", "de", "des", "du", "et", "pour",
    "sur", "dans", "svp",
}

ACTION_WORDS = {
    "retrieve", "get", "show", "display", "highlight", "detect", "check", "verify",
    "analyze", "analyse", "monitor", "provide", "generate", "perform", "capture",
    "send", "alert", "keep", "deploy", "activate", "inspect", "replace", "run",
    "start", "enable", "open", "prepare", "study", "launch",
}

TOKEN_ALIASES = {
    "abnormal": {"anomaly", "anomalous", "fault"},
    "all": {"everything", "services"},
    "analyse": {"analysis", "analyze", "analyzer", "study"},
    "analysis": {"analyse", "analyze", "analyzer", "study"},
    "analyze": {"analysis", "analyse", "analyzer", "study"},
    "analyzer": {"analysis", "analyze", "analyse"},
    "anomalous": {"abnormal", "anomaly"},
    "anomaly": {"abnormal", "anomalous", "fault"},
    "ar": {"augmented", "reality", "guidance"},
    "augmented": {"ar", "reality", "workflow", "pipeline"},
    "behavior": {"analysis", "analyze"},
    "command": {"request", "instruction"},
    "content": {"display", "show"},
    "convert": {"conversion", "converter"},
    "converter": {"convert", "conversion"},
    "conversion": {"convert", "converter"},
    "detect": {"detection", "detector"},
    "detection": {"detect", "detector"},
    "detector": {"detect", "detection"},
    "display": {"content", "show"},
    "errors": {"error", "fault"},
    "error": {"errors", "fault"},
    "complete": {"pipeline", "workflow", "full"},
    "everything": {"all", "complete", "services", "heavy", "workload"},
    "fault": {"error", "errors", "anomaly"},
    "generate": {"generation", "generator"},
    "generation": {"generate", "generator"},
    "generator": {"generate", "generation"},
    "guidance": {"ar", "instructions", "generation"},
    "full": {"complete", "pipeline", "workflow"},
    "heavy": {"workload", "all"},
    "instruction": {"instructions", "guidance"},
    "instructions": {"instruction", "guidance", "content"},
    "pipeline": {"workflow", "complete", "full"},
    "protocol": {"conversion", "converter"},
    "reality": {"ar", "augmented"},
    "repair": {"maintenance", "instructions"},
    "service": {"services"},
    "services": {"service", "all"},
    "spoken": {"voice", "vocal", "audio"},
    "speech": {"voice", "vocal", "audio"},
    "study": {"analysis", "analyze", "analyse"},
    "temperature": {"anomaly", "analysis"},
    "vibration": {"anomaly", "analysis"},
    "voice": {"spoken", "vocal", "audio"},
    "workflow": {"pipeline", "complete", "full"},
    "workload": {"heavy", "all", "services"},
}

AR_TERMS = {"ar", "augmented", "reality", "workflow", "pipeline"}
VOICE_TERMS = {"voice", "speech", "spoken", "audio", "transcribe", "transcription", "vocal"}

CLAUSE_CONNECTOR_PATTERN = re.compile(
    r"\s*(?:,|\b(?:after\s+that|and\s+then|then|also|finally|next|and)\b)\s*",
    flags=re.IGNORECASE,
)

_DETECTION_CACHE: OrderedDict[str, list[str]] = OrderedDict()
_INTENTION_PROFILES: list[dict] = []
_PROFILE_BY_ID: dict[str, dict] = {}


def _humanize(value: object) -> str:
    return re.sub(r"[_\-]+", " ", str(value or "")).strip()


def normalize_text(text: str) -> str:
    text = _humanize(text).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in normalize_text(text).split():
        if not word or word in STOP_WORDS:
            continue
        variants = {word}
        if len(word) > 4 and word.endswith("s"):
            variants.add(word[:-1])
        if len(word) > 5 and word.endswith("ing"):
            variants.add(word[:-3])
        variants.update(TOKEN_ALIASES.get(word, set()))
        for variant in sorted(variants):
            if variant and variant not in STOP_WORDS:
                tokens.append(variant)
    return tokens


def _cache_key(text: str) -> str:
    return normalize_text(text)


def _get_cached_detection(text: str) -> list[dict] | None:
    key = _cache_key(text)
    if not key or key not in _DETECTION_CACHE:
        return None
    ids = _DETECTION_CACHE.pop(key)
    _DETECTION_CACHE[key] = ids
    print(f"Detection cache hit -> {ids}")
    return [INTENTIONS_BY_ID[iid] for iid in ids if iid in INTENTIONS_BY_ID]


def _store_cached_detection(text: str, detected: list[dict]):
    key = _cache_key(text)
    if not key:
        return
    if key in _DETECTION_CACHE:
        _DETECTION_CACHE.pop(key)
    _DETECTION_CACHE[key] = [intent["id"] for intent in detected]
    while len(_DETECTION_CACHE) > DETECTION_CACHE_MAX:
        _DETECTION_CACHE.popitem(last=False)


def _hash_index(feature: str) -> int:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "little") % EMBED_DIM


def _add_feature(vector: list[float], feature: str, weight: float):
    if feature:
        vector[_hash_index(feature)] += weight


def _local_embedding(text: str) -> list[float]:
    """Fast local embedding used for semantic-style similarity.

    It is dataset-agnostic and precomputed for every intention. Token, prefix,
    phrase, and character n-gram features make related wording score closer
    without requiring a model download at request time.
    """
    tokens = tokenize(text)
    vector = [0.0] * EMBED_DIM

    for token in tokens:
        _add_feature(vector, f"tok:{token}", 1.0)
        if len(token) >= 5:
            _add_feature(vector, f"prefix:{token[:6]}", 0.45)

    for left, right in zip(tokens, tokens[1:]):
        _add_feature(vector, f"bi:{left}_{right}", 1.25)

    compact = "".join(tokens)
    for n in (3, 4):
        for i in range(max(0, len(compact) - n + 1)):
            _add_feature(vector, f"char:{compact[i:i+n]}", 0.12)

    norm = sum(v * v for v in vector) ** 0.5
    if norm:
        vector = [v / norm for v in vector]
    return vector


def _cosine(left: list[float], right: list[float]) -> float:
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def _service_search_text(service_id: str) -> str:
    service = SERVICES_BY_ID.get(service_id, {})
    name = _humanize(service.get("name", service_id))
    resources = service.get("resources", {}) or {}
    resource_text = " ".join(f"{key} {value}" for key, value in resources.items())
    return f"{service_id} {name} {resource_text}"


def _qos_search_text(intent: dict) -> str:
    qos = intent.get("QoS", {}) or {}
    return " ".join(f"qos {key} {value}" for key, value in qos.items())


def build_intention_search_text(intent: dict) -> str:
    service_text = " ".join(_service_search_text(sid) for sid in intent.get("services", []))
    description = _humanize(intent.get("description", ""))
    return " ".join([
        str(intent.get("id", "")),
        description,
        description,  # description is the strongest generic signal
        service_text,
        _qos_search_text(intent),
        f"weight {intent.get('weight', '')}",
    ]).strip()


def _intention_prompt_line(intent: dict) -> str:
    services = []
    for sid in intent.get("services", []):
        service = SERVICES_BY_ID.get(sid, {})
        service_name = _humanize(service.get("name", sid))
        services.append(f"{sid}:{service_name}")
    return (
        f"- {intent.get('id')}: {intent.get('description', '')} "
        f"| services: {', '.join(services) if services else 'none'}"
    )


def _all_intentions_prompt_block() -> str:
    preload_detection_profiles()
    return "\n".join(_intention_prompt_line(profile["intent"]) for profile in _INTENTION_PROFILES)


def preload_detection_profiles(force: bool = False) -> list[dict]:
    """Precompute generic searchable profiles and embeddings once at startup."""
    global _INTENTION_PROFILES, _PROFILE_BY_ID
    if _INTENTION_PROFILES and not force and len(_INTENTION_PROFILES) == len(intentions):
        return _INTENTION_PROFILES

    profiles = []
    for intent in intentions:
        search_text = build_intention_search_text(intent)
        profile = {
            "id": intent["id"],
            "intent": intent,
            "search_text": search_text,
            "search_norm": normalize_text(search_text),
            "tokens": set(tokenize(search_text)),
            "description_base_tokens": set(normalize_text(intent.get("description", "")).split()),
            "embedding": _local_embedding(search_text),
        }
        profiles.append(profile)

    _INTENTION_PROFILES = profiles
    _PROFILE_BY_ID = {profile["id"]: profile for profile in profiles}
    _DETECTION_CACHE.clear()
    print(f"Detection profiles precomputed: {len(_INTENTION_PROFILES)} intentions")
    return _INTENTION_PROFILES


def split_intent_chunks(text: str) -> list[str]:
    """Split a paragraph into ordered clauses before generic classification."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []

    parts = [p.strip(" ,.;:") for p in CLAUSE_CONNECTOR_PATTERN.split(raw) if p.strip(" ,.;:")]
    if len(parts) <= 1:
        return parts or [raw]

    cleaned: list[str] = []
    for chunk in parts:
        chunk = chunk.strip(" ,.;:")
        if not chunk:
            continue
        base_words = normalize_text(chunk).split()
        has_action = bool(set(base_words) & ACTION_WORDS)
        if cleaned and len(base_words) <= 2 and not has_action:
            cleaned[-1] = f"{cleaned[-1]} {chunk}".strip()
        else:
            cleaned.append(chunk)
    return cleaned or [raw]


def _fuzzy_score(query_norm: str, target_norm: str) -> float:
    if not query_norm or not target_norm:
        return 0.0
    if fuzz:
        return max(
            fuzz.token_set_ratio(query_norm, target_norm),
            fuzz.partial_ratio(query_norm, target_norm),
        ) / 100.0
    return SequenceMatcher(None, query_norm, target_norm).ratio()


def _keyword_overlap_score(query_tokens: set[str], target_tokens: set[str]) -> tuple[float, list[str]]:
    if not query_tokens or not target_tokens:
        return 0.0, []

    content_tokens = query_tokens - ACTION_WORDS
    base_tokens = content_tokens or query_tokens
    overlap = base_tokens & target_tokens
    if not overlap:
        return 0.0, []

    query_coverage = len(overlap) / max(len(base_tokens), 1)
    compact_overlap = len(overlap) / max(min(len(base_tokens), len(target_tokens)), 1)
    return min(1.0, query_coverage * 0.8 + compact_overlap * 0.2), sorted(overlap)


def _empty_score(intent: dict) -> dict:
    return {
        "id": intent.get("id"),
        "intent": intent,
        "score": 0.0,
        "confidence": 0.0,
        "detection_method": "semantic",
        "semantic": 0.0,
        "fuzzy": 0.0,
        "keyword": 0.0,
        "overlap": [],
    }


def _score_profile(
    query_norm: str,
    query_tokens: set[str],
    query_embedding: list[float],
    profile: dict,
) -> dict:
    intent = profile["intent"]
    semantic = _cosine(query_embedding, profile["embedding"])
    fuzzy_score = _fuzzy_score(query_norm, profile["search_norm"])
    keyword_score, overlap = _keyword_overlap_score(query_tokens, profile["tokens"])
    final_score = (
        SEMANTIC_WEIGHT * semantic
        + FUZZY_WEIGHT * fuzzy_score
        + KEYWORD_WEIGHT * keyword_score
    )

    query_base_tokens = set(query_norm.split())
    broad_terms = {"all", "everything", "full", "complete", "heavy", "workload", "pipeline", "services"}
    service_count = len(intent.get("services", []))
    description_base_overlap = query_base_tokens & profile.get("description_base_tokens", set())
    if service_count >= 4 and not (query_base_tokens & broad_terms) and len(description_base_overlap) < 2:
        final_score = max(0.0, final_score - 0.18)

    explicit_all_service_terms = {"all", "everything", "services", "heavy", "workload"}
    is_all_services_intent = (
        service_count >= max(5, int(len(SERVICES_BY_ID) * 0.8))
        or bool(profile.get("description_base_tokens", set()) & {"heavy", "workload"})
    )
    if is_all_services_intent and not (query_base_tokens & explicit_all_service_terms):
        final_score = max(0.0, final_score - 0.22)

    intent_tokens = profile["tokens"]
    query_has_ar = bool(query_tokens & AR_TERMS)
    query_has_voice = bool(query_tokens & VOICE_TERMS)
    intent_is_voice = (
        service_count <= 2
        and bool(intent_tokens & VOICE_TERMS)
        and not bool(profile.get("description_base_tokens", set()) & {"ar", "pipeline", "workflow"})
    )
    intent_is_ar_pipeline = (
        service_count >= 4
        and bool(intent_tokens & {"ar", "augmented", "reality", "pipeline", "workflow"})
    )
    if query_has_ar and not query_has_voice and intent_is_voice:
        final_score = max(0.0, final_score - 0.25)
        print(f"   Negative voice score: AR-focused clause without voice terms -> {intent['id']}")

    if query_has_ar and bool(query_tokens & {"workflow", "pipeline", "complete", "full"}) and intent_is_ar_pipeline:
        final_score = min(1.0, final_score + 0.16)

    detection_method = "fuzzy" if fuzzy_score >= semantic and fuzzy_score >= 0.70 else "semantic"

    return {
        "id": intent["id"],
        "intent": intent,
        "score": round(final_score, 3),
        "confidence": round(final_score, 3),
        "detection_method": detection_method,
        "semantic": round(semantic, 3),
        "fuzzy": round(fuzzy_score, 3),
        "keyword": round(keyword_score, 3),
        "overlap": overlap,
    }


def score_intention(text: str, intent: dict) -> dict:
    preload_detection_profiles()
    profile = _PROFILE_BY_ID.get(intent["id"])
    if not profile:
        return _empty_score(intent)

    return _score_profile(
        normalize_text(text),
        set(tokenize(text)),
        _local_embedding(text),
        profile,
    )


def rank_intentions(text: str, limit: int | None = None) -> list[dict]:
    preload_detection_profiles()
    if not text or not text.strip():
        return []

    query_norm = normalize_text(text)
    query_tokens = set(tokenize(text))
    query_embedding = _local_embedding(text)
    ranked = [
        _score_profile(query_norm, query_tokens, query_embedding, profile)
        for profile in _INTENTION_PROFILES
    ]
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:limit] if limit else ranked


def compute_keyword_scores(text_lower: str) -> dict:
    # Kept for compatibility with older call sites/tests.
    return {r["id"]: r["score"] for r in rank_intentions(text_lower)}


def prefilter_intentions(text_lower: str, top_n: int = 10) -> list:
    return [r["intent"] for r in rank_intentions(text_lower, limit=top_n)]


def _print_ranked(ranked: list[dict], title: str = "Matching candidates"):
    print(f"\n   {title}:")
    for r in ranked[:8]:
        detail = []
        if r["overlap"]:
            detail.append(f"words={','.join(r['overlap'][:6])}")
        suffix = f" ({'; '.join(detail)})" if detail else ""
        print(
            f"      {r['id']} score={r['score']} "
            f"method={r.get('detection_method', '?')} "
            f"sem={r['semantic']} fuzzy={r['fuzzy']} kw={r['keyword']}{suffix}"
        )


def _select_ranked(ranked: list[dict], max_intents: int | None = None) -> list:
    _print_ranked(ranked)
    selected = [r for r in ranked if r["score"] >= DETECTION_THRESHOLD]
    if max_intents is not None:
        selected = selected[:max_intents]

    if not selected:
        top = ranked[0] if ranked else None
        if top:
            print(
                f"   No reliable intention: top={top['id']} "
                f"score={top['score']} threshold={DETECTION_THRESHOLD}"
            )
        return []

    print(
        "   Matched intentions: "
        + ", ".join(f"{r['id']}(conf={r['confidence']})" for r in selected)
    )
    return [r["intent"] for r in selected]


def keyword_fallback(text_lower: str, max_intents: int | None = None) -> list:
    return _select_ranked(rank_intentions(text_lower), max_intents)


def _extract_json_object(raw: str) -> dict | None:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


def _fallback_semantic_candidates(text: str, limit: int = 3) -> list:
    ranked = rank_intentions(text, limit=limit)
    fallback = [r for r in ranked if r["score"] >= DETECTION_THRESHOLD]
    print(
        "   Semantic fallback candidates -> "
        + str([(r["id"], r["confidence"]) for r in fallback])
    )
    if not fallback:
        print("   Semantic fallback returned no result because all scores are below threshold")
    return [r["intent"] for r in fallback]


def _validate_ollama_matches(data: dict) -> list:
    raw_matches = data.get("matched_intentions", []) if isinstance(data, dict) else []
    if not isinstance(raw_matches, list):
        return []

    detected = []
    seen = set()
    for item in raw_matches:
        if isinstance(item, dict):
            iid = str(item.get("id", "")).strip()
            reason = str(item.get("reason", "")).strip()
        else:
            iid = str(item).strip()
            reason = ""

        if iid in seen:
            continue
        if iid not in INTENTIONS_BY_ID:
            print(f"   Ollama invalid ID ignored: {iid}")
            continue

        print(f"   Ollama valid match: {iid} reason={reason or 'not provided'}")
        detected.append(INTENTIONS_BY_ID[iid])
        seen.add(iid)

    return detected


def detect_with_ollama(text: str, text_lower: str = "") -> list:
    if os.getenv("IBN_SKIP_OLLAMA", "").lower() in {"1", "true", "yes"}:
        print("   Ollama skipped by IBN_SKIP_OLLAMA")
        return _fallback_semantic_candidates(text)

    prompt = f"""You are an intention classifier. Choose only intentions from the provided list. Do not invent new IDs.
Do not choose the first intention by default. Match the user meaning to the closest provided descriptions and services.
If no intention is supported by the user command, return an empty matched_intentions list.
Return only valid JSON. No markdown, no explanations outside JSON.

JSON format:
{{
  "matched_intentions": [
    {{
      "id": "existing_intention_id",
      "reason": "short reason from the user command"
    }}
  ]
}}

Available intentions:
{_all_intentions_prompt_block()}

User command:
{text}

JSON:"""
    try:
        raw = ollama_call(prompt, max_tokens=OLLAMA_MAX_TOKENS, temperature=0.0)
        print(f"   Ollama raw response: {raw.strip()}")
        data = _extract_json_object(raw)
        if data is None:
            print("   Ollama invalid JSON; using semantic fallback candidates")
            return _fallback_semantic_candidates(text)

        detected = _validate_ollama_matches(data)
        if detected:
            print(f"   Detection method: ollama, matched IDs={[i['id'] for i in detected]}")
            return detected

        print("   Ollama returned no valid dataset IDs; using semantic fallback candidates")
        return _fallback_semantic_candidates(text)
    except Exception as e:
        print(f"   Ollama error: {e}")
        return _fallback_semantic_candidates(text)


def _detect_single_block(text: str, max_intents: int | None = None) -> list:
    ranked = rank_intentions(text)
    local = _select_ranked(ranked, max_intents)
    if local:
        local_ids = [i["id"] for i in local]
        local_methods = [
            r.get("detection_method", "semantic")
            for r in ranked
            if r["id"] in set(local_ids)
        ]
        print(f"   Detection method: local, matched IDs={local_ids}, methods={local_methods}")
        return local

    if os.getenv("IBN_SKIP_OLLAMA", "").lower() in {"1", "true", "yes"}:
        print("   Detection method: semantic, no confident match; Ollama skipped")
        return []

    print("   Local confidence weak; calling Ollama fallback")
    return detect_with_ollama(text, normalize_text(text))


def detect_multiple_intentions(text: str) -> list:
    """Detect all matching intentions dynamically from the loaded dataset."""
    cached = _get_cached_detection(text)
    if cached is not None:
        return cached

    print(f"\nOriginal request: {text}")
    chunks = split_intent_chunks(text)
    print(f"Detected chunks ({len(chunks)}):")
    for idx, chunk in enumerate(chunks, 1):
        print(f"   chunk {idx}: {chunk}")

    best_by_id: dict[str, dict] = {}
    ollama_attempted = False
    for idx, chunk in enumerate(chunks, 1):
        print(f"\nChunk {idx} detection: {chunk}")
        ranked = rank_intentions(chunk)
        _print_ranked(ranked)
        selected = [r for r in ranked if r["score"] >= DETECTION_THRESHOLD]
        print(
            f"Chunk {idx} -> detected "
            f"{[(r['id'], r['confidence']) for r in selected] if selected else 'none'}"
        )

        if selected:
            print(
                f"Detection method: local, matched IDs="
                f"{[r['id'] for r in selected]}, confidence="
                f"{[r['confidence'] for r in selected]}, methods="
                f"{[r.get('detection_method', 'semantic') for r in selected]}"
            )
        elif os.getenv("IBN_SKIP_OLLAMA", "").lower() in {"1", "true", "yes"}:
            print("Detection method: semantic, no confident match; Ollama skipped")
        else:
            print("Detection method: ollama fallback triggered by weak local confidence")
            ollama_attempted = True
            for intent in detect_with_ollama(chunk, normalize_text(chunk)):
                result = score_intention(chunk, intent)
                result["score"] = max(result["score"], DETECTION_THRESHOLD)
                result["confidence"] = max(result["confidence"], DETECTION_THRESHOLD)
                result["detection_method"] = "ollama"
                selected.append(result)

        for result in selected:
            existing = best_by_id.get(result["id"])
            if existing is None or result["score"] > existing["score"]:
                best_by_id[result["id"]] = {**result, "chunk_index": idx}

    if (
        not best_by_id
        and not ollama_attempted
        and os.getenv("IBN_SKIP_OLLAMA", "").lower() not in {"1", "true", "yes"}
    ):
        print("No chunk produced a valid match; calling Ollama on the full command")
        for intent in detect_with_ollama(text, normalize_text(text)):
            result = score_intention(text, intent)
            result["score"] = max(result["score"], DETECTION_THRESHOLD)
            result["confidence"] = max(result["confidence"], DETECTION_THRESHOLD)
            result["detection_method"] = "ollama"
            best_by_id[result["id"]] = {**result, "chunk_index": 0}

    merged = sorted(
        best_by_id.values(),
        key=lambda r: (-r["confidence"], r["chunk_index"], r["id"]),
    )
    detected = [r["intent"] for r in merged]
    print(
        "Final merged intentions -> "
        + str([(r["id"], r["confidence"], r.get("detection_method", "semantic")) for r in merged])
    )
    _store_cached_detection(text, detected)
    return detected


def detect_intention(text: str):
    results = detect_multiple_intentions(text)
    return results[0] if results else None


# Warm the dataset-driven profiles once when the app imports this module.
preload_detection_profiles()
